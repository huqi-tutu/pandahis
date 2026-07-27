"""朝代知识补全：LLM 调用、JSON 解析、ID 与坐标工具。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

OPENCLAW_ROOT = Path(__file__).resolve().parents[2]
HISTOGRAPH_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = HISTOGRAPH_ROOT / "scripts"
ANNOTATE_REF = OPENCLAW_ROOT / "historiography-annotate" / "reference"

if str(OPENCLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENCLAW_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from emperor_year_align import (  # noqa: E402
    align_junji_entry_years,
    build_emperor_indexes,
    validate_junji_years,
)

from shared.ai_flavor_words import (  # noqa: E402
    AI_FLAVOR_WORD_FAIL_AT,
    AI_FLAVOR_WORDS,
    FORBIDDEN_PROSE_WORDS,
    ai_flavor_verify_issues,
    ai_flavor_word_counts,
)
PERSON_CATEGORIES = ("君王", "诸侯", "宗戚", "宦官", "文臣", "武将", "蕃祚", "庶众")
PERSON_INDEX_CATEGORIES = frozenset(PERSON_CATEGORIES)
SOVEREIGN_CATEGORIES = frozenset({"君王", "诸侯"})

# 兼容旧常量名（撰写侧与 verify 共用 shared/ai_flavor_words.py）
AI_FLAVOR_WORD_MAX_TOTAL = AI_FLAVOR_WORD_FAIL_AT - 1
AI_FLAVOR_WORD_MAX_PER_WORD = AI_FLAVOR_WORD_FAIL_AT - 1


# 元叙述 / 编辑腔（交付物 §0.3；出现在读者正文即 error）
FORBIDDEN_META_PHRASES = (
    "正文不载",
    "正文不宜",
    "读者能把握",
    "本条须",
    "史实边界",
    "对读者而言",
    "并不采此写法",
    "应留空",
    "不宜补写",
    "须落定的硬史实",
    "若谈史实边界",
    "不得把神话",
    "当作本文硬事实",
    "写作的基本前提",
    "后世亦不得",
    "其余细节应留空",
)

MIN_PARAGRAPHS_BY_PRIORITY = {
    "P0": 7,  # 开篇引入 + 6 正文段
    "P1": 5,
    "P2": 4,
    "P3": 3,
}

# 质检/撰写 retry 上限（防 agent 或脚本死循环）
MAX_COMPOSE_REVISE_ROUNDS = 1
MAX_COMPOSE_PARSE_ATTEMPTS = 3  # compose LLM 输出 JSON 解析失败时重试
MAX_PATCH_ROUNDS = 3  # Kimi 精准改稿 + review↔fix 循环上限（轮）
MAX_REVIEW_FIX_ROUNDS = 3  # Kimi 事实核查最多 3 轮；第 3 轮仍有问题则 forced_pass
MAX_QA_DETAIL_ROUNDS = 2  # compose + 1 revise，整条 qa 链路上限

CATEGORY_SLUG_TO_CN = {
    "shilue": "事略",
    "dianzhi": "典制",
    "lunzhu": "论著",
    "jundwang": "君王",
    "junwang": "君王",
    "zhuhou": "诸侯",
    "zongqi": "宗戚",
    "huanguan": "宦官",
    "wenchen": "文臣",
    "wujiang": "武将",
    "fanzhuo": "蕃祚",
    "fanzuo": "蕃祚",
    "shuzhong": "庶众",
}


def normalize_category(category: str) -> str:
    """索引 category_key / 英文 slug → 中文史略分类（gate/compose 统一）。"""
    raw = str(category or "").strip()
    if not raw:
        return raw
    key = raw.lower()
    if key in CATEGORY_SLUG_TO_CN:
        return CATEGORY_SLUG_TO_CN[key]
    return raw


def qa_state_path(logs_dir: Path, entry_id: str) -> Path:
    return logs_dir / "qa_state" / f"{entry_id}.json"


def load_qa_state(logs_dir: Path, entry_id: str) -> dict[str, Any]:
    path = qa_state_path(logs_dir, entry_id)
    if not path.is_file():
        return {
            "史略ID": entry_id,
            "compose_attempts": 0,
            "patch_attempts": 0,
            "status": "pending",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_qa_state(logs_dir: Path, state: dict[str, Any]) -> Path:
    path = qa_state_path(logs_dir, str(state.get("史略ID", "?")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_env() -> None:
    env_file = OPENCLAW_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def llm_model_label() -> str:
    load_env()
    try:
        from llm.config import provider_label  # noqa: WPS433

        return provider_label()
    except Exception:
        return "DeepSeek (未加载)"


def call_llm(
    prompt: str,
    *,
    session_prefix: str,
    timeout_sec: int = 600,
    temperature: float | None = 0.2,
) -> str:
    load_env()
    from llm.provider import run_agent_turn  # noqa: WPS433

    sid = session_prefix + hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
    res = run_agent_turn(
        prompt,
        session_id=sid,
        timeout_sec=timeout_sec,
        temperature=temperature,
    )
    return str(res.get("result") or "").strip()


def extract_json_array(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("["), text.rfind("]")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("{"), text.rfind("}")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    # 容错：从首个 { 起 raw_decode（应对尾部多余文字）
    dec = json.JSONDecoder()
    start = text.find("{")
    if start != -1:
        try:
            data, _ = dec.raw_decode(text[start:])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def parse_compose_detail_response(text: str) -> dict[str, Any] | None:
    """从 compose-detail LLM 回复解析 {史略ID, 翻译详情}。"""
    data = extract_json_object(text)
    if not data:
        return None
    body = str(data.get("翻译详情") or "").strip()
    if not body:
        return None
    return data


def max_glbl_num(histograph_root: Path) -> int:
    index_path = histograph_root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    supplement_glob = list(
        (histograph_root / "data" / "06朝代知识补全" / "索引条目").glob("*.json")
    )
    nums: list[int] = []
    for path in [index_path, *supplement_glob]:
        if not path.is_file():
            continue
        root = json.loads(path.read_text(encoding="utf-8"))
        entries = root.get("entries") if isinstance(root, dict) else root
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            m = re.match(r"GLBL_(\d+)", str(e.get("史略ID", "")))
            if m:
                nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def allocate_glbl_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"GLBL_{counter[0]:05d}"


# 帝王表强制补全：仅本朝共主（周天子、先周首领），不含诸侯开国之君
_MANDATORY_MONARCH_NAME = re.compile(r"^周.+王$")
_PRE_DYNASTY_MONARCHS = frozenset({"姬昌", "古公亶父", "季历", "后稷"})


def is_mandatory_dynasty_monarch(emperor_row: dict[str, Any]) -> bool:
    """帝王.json 行是否须强制补全为「君王」详情（非诸侯开国之君）。"""
    name = str(emperor_row.get("帝王名称", "")).strip()
    if not name:
        return False
    if name in _PRE_DYNASTY_MONARCHS:
        return True
    return bool(_MANDATORY_MONARCH_NAME.match(name))


def load_emperors(histograph_root: Path, dynasty_id: str) -> list[dict[str, Any]]:
    path = histograph_root / "data" / "01历史坐标数据" / "帝王.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in rows if str(r.get("朝代ID", "")).strip() == dynasty_id]


def load_emperor_alias_config() -> dict[str, Any]:
    path = ANNOTATE_REF / "帝王别名.json"
    if not path.is_file():
        return {"global": {}, "strip_prefixes": []}
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_emperor_lookup_name(
    name: str,
    alias_map: dict[str, str] | None = None,
) -> str:
    """标注名/异名 → 帝王.json 标准「帝王名称」。"""
    raw = (name or "").strip()
    if not raw:
        return raw
    alias_map = alias_map if alias_map is not None else load_person_alias_maps()
    cfg = load_emperor_alias_config()
    merged = dict(alias_map)
    for alias, canonical in (cfg.get("global") or {}).items():
        a, c = str(alias).strip(), str(canonical).strip()
        if a and c:
            merged[a] = c
    normalized = normalize_person_name(raw, merged)
    if normalized in merged.values() or normalized:
        return normalized
    for prefix in cfg.get("strip_prefixes") or []:
        p = str(prefix).strip()
        if p and raw.startswith(p) and len(raw) > len(p):
            stripped = raw[len(p) :].strip()
            if stripped:
                return normalize_emperor_lookup_name(stripped, merged)
    return raw


def _emperor_row_to_coords(row: dict[str, Any]) -> dict[str, str]:
    return {
        "一级文明坐标": str(row.get("文明", "")).strip(),
        "文明ID": str(row.get("文明ID", "")).strip(),
        "二级朝代坐标": str(row.get("朝代", "")).strip(),
        "朝代ID": str(row.get("朝代ID", "")).strip(),
        "三级政权坐标": str(row.get("政权", "")).strip(),
        "政权ID": str(row.get("政权ID", "")).strip(),
        "四级帝王坐标": str(row.get("帝王名称", "")).strip(),
        "帝王ID": str(row.get("帝王ID", "")).strip(),
    }


def find_emperor_row_exact(
    name: str,
    emperors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """仅按帝王.json「帝王名称」或「帝王原名」精确匹配，不走别名表。"""
    key = (name or "").strip()
    if not key:
        return None
    for row in emperors:
        if key in (
            str(row.get("帝王名称", "")).strip(),
            str(row.get("帝王原名", "")).strip(),
        ):
            return row
    return None


def resolve_emperor(
    name: str,
    emperors: list[dict[str, Any]],
    *,
    alias_map: dict[str, str] | None = None,
) -> dict[str, str] | None:
    """从本朝帝王.json 精确反查坐标链（文明→朝代→政权→帝王）。

    候选/挂靠名必须是帝王表中的「帝王名称」或「帝王原名」，一字不差。
    不使用别名表归一——避免 LLM 自由写法与维护成本。
    """
    _ = alias_map  # 保留参数兼容旧调用，已忽略
    row = find_emperor_row_exact(name, emperors)
    if not row:
        return None
    return _emperor_row_to_coords(row)


def format_emperor_catalog(emperors: list[dict[str, Any]]) -> str:
    """供 fill prompt 展示：本朝可选挂靠帝王（标准名）。"""
    lines: list[str] = []
    for row in emperors:
        name = str(row.get("帝王名称", "")).strip()
        if not name:
            continue
        orig = str(row.get("帝王原名", "")).strip()
        enth = str(row.get("即位时间", "")).strip()
        abd = str(row.get("退位时间", "")).strip()
        extra = f"，原名 {orig}" if orig and orig != name else ""
        lines.append(f"- {name}{extra}（在位 {enth}～{abd}）")
    return "\n".join(lines)


LLM_COORD_FIELDS = (
    "四级帝王坐标",
    "帝王ID",
    "一级文明坐标",
    "二级朝代坐标",
    "三级政权坐标",
    "文明ID",
    "朝代ID",
    "政权ID",
)


def strip_llm_coordinate_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """移除 LLM 可能填写的坐标链字段，改由脚本从帝王表写入。"""
    out = dict(entry)
    for key in LLM_COORD_FIELDS:
        out.pop(key, None)
    return out


def determine_attach_emperor_name(
    category: str,
    candidate: dict[str, Any],
    entry_name: str,
) -> str:
    """确定挂靠帝王名：君王=条目名；其余=候选建议挂靠帝王（须为帝王表标准名）。"""
    cat = str(category or "").strip()
    if cat in SOVEREIGN_CATEGORIES:
        return str(entry_name or "").strip()
    return str(candidate.get("建议挂靠帝王") or "").strip()


def validate_attach_emperor_name(
    attach_name: str,
    emperors: list[dict[str, Any]],
    *,
    entry_id: str = "",
) -> None:
    if not attach_name:
        raise ValueError(
            f"{entry_id} 缺少挂靠帝王：候选须填写「建议挂靠帝王」（本朝帝王表标准名）"
        )
    if find_emperor_row_exact(attach_name, emperors) is None:
        catalog = ", ".join(
            str(r.get("帝王名称", "")).strip()
            for r in emperors
            if str(r.get("帝王名称", "")).strip()
        )
        raise ValueError(
            f"{entry_id} 挂靠帝王「{attach_name}」不在本朝帝王表；"
            f"可选：{catalog}"
        )


def align_entry_emperor_coords(
    entry: dict[str, Any],
    emperors: list[dict[str, Any]],
    *,
    attach_emperor: str | None = None,
    alias_map: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """据挂靠帝王名（帝王表精确匹配）写回完整坐标链。"""
    _ = alias_map
    out = dict(entry)
    changes: list[str] = []
    cat = str(out.get("史略分类", "")).strip()
    eid = str(out.get("史略ID", "")).strip()
    attach = (attach_emperor or "").strip()
    if not attach:
        if cat in SOVEREIGN_CATEGORIES:
            attach = str(out.get("史略名称") or "").strip()
        else:
            attach = str(out.get("四级帝王坐标") or "").strip()
    emp = resolve_emperor(attach, emperors) if attach else None
    if not emp:
        return out, changes
    for key, value in emp.items():
        old = out.get(key)
        if old != value:
            changes.append(f"{eid} {key}: {old!r} → {value!r}")
            out[key] = value
    return out, changes


def _coerce_year_value(raw: Any) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == "-":
        return None
    if s.startswith("约"):
        s = s[1:]
    try:
        return int(s)
    except ValueError:
        return None


def _emperor_info_for_entry(
    entry: dict[str, Any],
    emperors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    eid = str(entry.get("帝王ID") or "").strip()
    coord = str(entry.get("四级帝王坐标") or "").strip()
    for row in emperors:
        if eid and str(row.get("帝王ID", "")).strip() == eid:
            return {
                "emperor": str(row.get("帝王名称", "")).strip(),
                "start_year": _coerce_year_value(row.get("即位时间")),
                "end_year": _coerce_year_value(row.get("退位时间")),
            }
        if coord and str(row.get("帝王名称", "")).strip() == coord:
            return {
                "emperor": coord,
                "start_year": _coerce_year_value(row.get("即位时间")),
                "end_year": _coerce_year_value(row.get("退位时间")),
            }
    return None


def apply_person_years_for_entry(
    entry: dict[str, Any],
    emperors: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """人物类缺年：复用史料标注 person_year_fallback 兜底链。"""
    _ensure_annotate_on_path()
    from person_year_fallback import (  # noqa: WPS433
        apply_person_year_fallback,
        entry_has_complete_years,
        write_fallback_years_to_entry,
    )

    out = dict(entry)
    changes: list[str] = []
    eid = str(out.get("史略ID", "")).strip()
    cat = str(out.get("史略分类", "")).strip()
    af = dict(out.get("_auto_filled") or {})
    emperor_info = _emperor_info_for_entry(out, emperors)
    if (
        entry_has_complete_years(out)
        and af.get("_年兜底级别") == "朝代起始年"
        and emperor_info
        and emperor_info.get("start_year") is not None
    ):
        out.pop("史略开始年", None)
        out.pop("史略结束年", None)
        af.pop("_年兜底级别", None)
        af.pop("_年兜底依据", None)
        out["_auto_filled"] = af
        changes.append(f"{eid} 清除朝代起始年兜底，改取挂靠帝王在位")
    if cat in SOVEREIGN_CATEGORIES:
        aligned = align_junji_entry_with_emperor_list(out, emperors, force=True)
        if aligned.get("史略开始年") != out.get("史略开始年") or aligned.get(
            "史略结束年"
        ) != out.get("史略结束年"):
            changes.append(
                f"{eid} 君王年对齐帝王表: {out.get('史略开始年')}~{out.get('史略结束年')}"
                f" → {aligned.get('史略开始年')}~{aligned.get('史略结束年')}"
            )
        return aligned, changes
    if entry_has_complete_years(out):
        return out, changes
    emperor_info = _emperor_info_for_entry(out, emperors)
    start, end, level, note = apply_person_year_fallback(
        out, emperor_info=emperor_info
    )
    if start is None or end is None:
        return out, changes
    write_fallback_years_to_entry(out, start, end, level, note)
    changes.append(f"{eid} 年份兜底({level}): {start}~{end} — {note}")
    return out, changes


def repair_supplement_entries(
    entries: list[dict[str, Any]],
    emperors: list[dict[str, Any]],
    *,
    alias_map: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """修复朝代补全条目：帝王坐标链、删五级细坐标、人物年份兜底。"""
    alias_map = alias_map if alias_map is not None else load_person_alias_maps()
    out_entries: list[dict[str, Any]] = []
    all_changes: list[str] = []
    for entry in entries:
        row = dict(entry)
        if is_dynasty_supplement_entry(row):
            row.pop("五级细坐标", None)
            row.pop("六级段落锚点", None)
        row, coord_changes = align_entry_emperor_coords(row, emperors)
        all_changes.extend(coord_changes)
        row, year_changes = apply_person_years_for_entry(row, emperors)
        all_changes.extend(year_changes)
        out_entries.append(row)
    return out_entries, all_changes


def align_junji_entry_with_emperor_list(
    entry: dict[str, Any],
    emperors: list[dict[str, Any]],
    *,
    force: bool = True,
) -> dict[str, Any]:
    """君王条目：即位/退位年强制对齐帝王.json（覆盖 LLM 输出）。"""
    if str(entry.get("史略分类", "")).strip() not in SOVEREIGN_CATEGORIES:
        return entry
    dynasty_id = str(entry.get("朝代ID", "")).strip() or None
    by_name, by_id = build_emperor_indexes(emperors, dynasty_id=dynasty_id)
    aligned, _ = align_junji_entry_years(
        entry,
        by_name=by_name,
        by_id=by_id,
        force=force,
    )
    return aligned


def align_junji_entries_with_emperor_list(
    entries: list[dict[str, Any]],
    emperors: list[dict[str, Any]],
    *,
    force: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    dynasty_id = ""
    for entry in entries:
        if str(entry.get("史略分类", "")).strip() in SOVEREIGN_CATEGORIES:
            dynasty_id = str(entry.get("朝代ID", "")).strip()
            break
    by_name, by_id = build_emperor_indexes(
        emperors, dynasty_id=dynasty_id or None
    )
    out: list[dict[str, Any]] = []
    changes: list[str] = []
    for entry in entries:
        aligned, row_changes = align_junji_entry_years(
            entry,
            by_name=by_name,
            by_id=by_id,
            force=force,
        )
        out.append(aligned)
        changes.extend(row_changes)
    return out, changes


def validate_junji_years_for_dynasty(
    entries: list[dict[str, Any]],
    dynasty_id: str,
) -> list[str]:
    return validate_junji_years(entries, dynasty_id=dynasty_id or None)


REGIME_ID_BY_DYNASTY: dict[str, str] = {
    "CD_HX_WUDI": "ZQ_HX_WUDI_WUDI",
    "CD_HX_XIA": "ZQ_HX_XIA_XIA",
}


def default_regime_id(context: dict[str, Any]) -> str:
    rid = str(context.get("政权ID") or "").strip()
    if rid:
        return rid
    did = str(context.get("朝代ID") or "").strip()
    return REGIME_ID_BY_DYNASTY.get(did, "")


def is_dynasty_supplement_entry(entry: dict[str, Any]) -> bool:
    return (
        str(entry.get("母本著作") or "").strip() == "朝代补全"
        or str(entry.get("史略来源") or "").strip() == "模型补全"
    )


def apply_coord_defaults(entry: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    out = dict(entry)
    out.setdefault("一级文明坐标", context.get("文明") or "华夏")
    out.setdefault("二级朝代坐标", context.get("朝代名称"))
    out.setdefault("三级政权坐标", context.get("朝代名称"))
    out.setdefault("文明ID", context.get("文明ID") or "HX")
    out.setdefault("朝代ID", context.get("朝代ID"))
    out.setdefault("政权ID", default_regime_id(context))
    out.setdefault("母本著作", "朝代补全")
    out.setdefault("来源著作", ["朝代补全"])
    out.setdefault("史略来源", "模型补全")
    out.setdefault("来源条目数", 1)
    out.setdefault("段落域数", 0)
    out.setdefault("原文字句", None)
    out.setdefault("paragraphs", [])
    return out


# ── 字段 Schema 校验（gate 集成） ──────────────────────────────────

# 条目字段：类型、是否允许为空、null 替换默认值
ENTRY_FIELD_SCHEMA: dict[str, dict[str, Any]] = {
    "一级文明坐标": {"type": str, "nullable": False, "default": ""},
    "二级朝代坐标": {"type": str, "nullable": False, "default": ""},
    "三级政权坐标": {"type": str, "nullable": False, "default": ""},
    "五级细坐标": {"type": str, "nullable": True, "default": ""},
    "六级段落锚点": {"type": str, "nullable": False, "default": ""},
    "母本史略ID": {"type": str, "nullable": False, "default": ""},
    "考订依据": {"type": dict, "nullable": False, "default_factory": dict},
    "史略开始年": {"type": int, "nullable": True},
    "史略结束年": {"type": int, "nullable": True},
    "峰值年": {"type": int, "nullable": True},
    "主要史料出处": {"type": list, "nullable": False, "default_factory": list},
    "史略ID": {"type": str, "nullable": False},
    "史略名称": {"type": str, "nullable": False},
    "史略分类": {"type": str, "nullable": False},
    "史略简介": {"type": str, "nullable": False, "default": ""},
    "史略来源": {"type": str, "nullable": False, "default": "模型补全"},
    "母本著作": {"type": str, "nullable": False, "default": "朝代补全"},
    "来源著作": {"type": list, "nullable": False, "default_factory": list},
    "优先级": {"type": str, "nullable": False, "default": "P1"},
    "边界备注": {"type": str, "nullable": True, "default": ""},
    "文明ID": {"type": str, "nullable": False},
    "朝代ID": {"type": str, "nullable": False},
    "政权ID": {"type": str, "nullable": False},
    "帝王ID": {"type": str, "nullable": True, "default": ""},
    "四级帝王坐标": {"type": str, "nullable": True, "default": ""},
    "peak_type": {"type": str, "nullable": True},
    "来源条目数": {"type": int, "nullable": False, "default": 1},
    "段落域数": {"type": int, "nullable": False, "default": 0},
    "原文字句": {"type": type(None), "nullable": True, "default": None},
    "paragraphs": {"type": list, "nullable": False, "default_factory": list},
    "前身制度": {"type": str, "nullable": True, "default": ""},
    "后续演变": {"type": str, "nullable": True, "default": ""},
    "备注": {"type": str, "nullable": True, "default": ""},
    "史料丰度": {"type": str, "nullable": True, "default": ""},
}

# 详情字段
DETAIL_FIELD_SCHEMA: dict[str, dict[str, Any]] = {
    "史略ID": {"type": str, "nullable": False},
    "翻译详情": {"type": str, "nullable": False},
}

# null 别名（统一归一为 ""）
NULL_ALIASES: frozenset[str] = frozenset({None, "", "——", "null", "NULL"})


def _is_null_like(value: Any) -> bool:
    """是否应被视为 null/空值（包括 None、空字符串、——、null 字符串）。"""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() in ("", "——", "null", "NULL"):
        return True
    return False


def validate_entry_schema(
    entry: dict[str, Any],
    entry_id: str = "?",
) -> list[str]:
    """校验单条索引条目的字段完整性和类型正确性。

    返回 issue 列表（空 = 通过）。
    """
    issues: list[str] = []
    supplement = is_dynasty_supplement_entry(entry)
    for field, spec in ENTRY_FIELD_SCHEMA.items():
        if field == "五级细坐标" and supplement:
            entry.pop("五级细坐标", None)
            continue
        if field == "六级段落锚点" and supplement:
            continue
        # 检查字段是否存在
        if field not in entry:
            if not spec["nullable"] and "default" in spec:
                entry[field] = spec["default"]
            elif not spec["nullable"] and "default_factory" in spec:
                entry[field] = spec["default_factory"]()
            elif not spec["nullable"]:
                issues.append(f"[{entry_id}] 必填字段缺失: {field}")
            continue

        value = entry[field]

        # null-like 值统一归一为默认值
        if _is_null_like(value):
            if spec["nullable"]:
                continue
            if "default" in spec:
                entry[field] = spec["default"]
            elif "default_factory" in spec:
                entry[field] = spec["default_factory"]()
            else:
                entry[field] = ""
            continue

        # 类型检查
        expected_type = spec["type"]
        if expected_type is type(None):
            if value is not None:
                issues.append(
                    f"[{entry_id}] {field} 应为 null，实际类型 {type(value).__name__}"
                )
        elif not isinstance(value, expected_type):
            issues.append(
                f"[{entry_id}] {field} 类型错误: "
                f"期望 {expected_type.__name__}, 实际 {type(value).__name__} "
                f"(值: {str(value)[:60]})"
            )
    return issues


def validate_detail_schema(
    detail: dict[str, Any],
    detail_id: str = "?",
) -> list[str]:
    """校验单条详情的字段完整性。"""
    issues: list[str] = []
    for field, spec in DETAIL_FIELD_SCHEMA.items():
        if field not in detail or _is_null_like(detail.get(field)):
            issues.append(f"[{detail_id}] 详情字段缺失: {field}")
    return issues


# ── 字数下限（双轴：优先级 × 史料丰度 S0–S3） ────────────────────────

# S3 档与旧版 MIN_DETAIL_CHARS 对齐，作为上限 cap
MIN_DETAIL_CHARS = {
    ("事略", "P0"): 1000,
    ("事略", "P1"): 700,
    ("事略", "P2"): 400,
    ("事略", "P3"): 200,
    ("典制", "P0"): 700,
    ("典制", "P1"): 500,
    ("典制", "P2"): 300,
    ("典制", "P3"): 150,
    ("论著", "P0"): 700,
    ("论著", "P1"): 500,
    ("论著", "P2"): 300,
    ("论著", "P3"): 150,
    ("君王", "P0"): 1000,
    ("君王", "P1"): 700,
    ("君王", "P2"): 400,
    ("君王", "P3"): 200,
    ("诸侯", "P0"): 1000,
    ("诸侯", "P1"): 700,
    ("诸侯", "P2"): 400,
    ("诸侯", "P3"): 200,
    ("宗戚", "P0"): 700,
    ("宗戚", "P1"): 500,
    ("宗戚", "P2"): 300,
    ("宗戚", "P3"): 150,
    ("宦官", "P0"): 700,
    ("宦官", "P1"): 500,
    ("宦官", "P2"): 300,
    ("宦官", "P3"): 150,
    ("文臣", "P0"): 700,
    ("文臣", "P1"): 500,
    ("文臣", "P2"): 300,
    ("文臣", "P3"): 150,
    ("武将", "P0"): 700,
    ("武将", "P1"): 500,
    ("武将", "P2"): 300,
    ("武将", "P3"): 150,
    ("庶众", "P0"): 500,
    ("庶众", "P1"): 400,
    ("庶众", "P2"): 250,
    ("庶众", "P3"): 150,
    ("蕃祚", "P0"): 700,
    ("蕃祚", "P1"): 500,
    ("蕃祚", "P2"): 300,
    ("蕃祚", "P3"): 150,
}

SOURCE_DENSITY_LEVELS = frozenset({"S0", "S1", "S2", "S3"})

_EVENT_DENSITY_FLOORS: dict[str, dict[str, dict[str, int]]] = {
    "事略": {
        "P0": {"S0": 450, "S1": 650, "S2": 950, "S3": 1000},
        "P1": {"S0": 350, "S1": 550, "S2": 700, "S3": 700},
        "P2": {"S0": 250, "S1": 350, "S2": 400, "S3": 400},
        "P3": {"S0": 150, "S1": 200, "S2": 200, "S3": 200},
    },
    "典制": {
        "P0": {"S0": 350, "S1": 500, "S2": 700, "S3": 700},
        "P1": {"S0": 280, "S1": 400, "S2": 500, "S3": 500},
        "P2": {"S0": 200, "S1": 280, "S2": 300, "S3": 300},
        "P3": {"S0": 120, "S1": 150, "S2": 150, "S3": 150},
    },
    "论著": {
        "P0": {"S0": 350, "S1": 500, "S2": 700, "S3": 700},
        "P1": {"S0": 280, "S1": 400, "S2": 500, "S3": 500},
        "P2": {"S0": 200, "S1": 280, "S2": 300, "S3": 300},
        "P3": {"S0": 120, "S1": 150, "S2": 150, "S3": 150},
    },
}

_PERSON_DENSITY_FLOORS: dict[str, dict[str, int]] = {
    "P0": {"S0": 450, "S1": 650, "S2": 950, "S3": 1000},
    "P1": {"S0": 350, "S1": 500, "S2": 700, "S3": 700},
    "P2": {"S0": 250, "S1": 350, "S2": 400, "S3": 400},
    "P3": {"S0": 150, "S1": 200, "S2": 250, "S3": 250},
}

_SHUZHONG_DENSITY_FLOORS: dict[str, dict[str, int]] = {
    "P0": {"S0": 300, "S1": 400, "S2": 500, "S3": 500},
    "P1": {"S0": 250, "S1": 350, "S2": 400, "S3": 400},
    "P2": {"S0": 180, "S1": 250, "S2": 250, "S3": 250},
    "P3": {"S0": 120, "S1": 150, "S2": 150, "S3": 150},
}


def resolve_source_density(
    entry: dict[str, Any],
    anchor: dict[str, Any] | None = None,
) -> str:
    """推断史料丰度 S0（极薄）– S3（有母本/史料充沛）。"""
    raw = str(entry.get("史料丰度") or "").strip().upper()
    if raw in SOURCE_DENSITY_LEVELS:
        return raw

    if anchor:
        hard_n = len(anchor.get("hard_facts") or [])
        if hard_n <= 2:
            return "S0"
        if hard_n <= 6:
            return "S1"
        if hard_n <= 12:
            return "S2"
        return "S3"

    if entry.get("母本史略ID") or entry.get("原文字句"):
        return "S2"

    if str(entry.get("朝代ID", "")) == "CD_HX_WUDI":
        pri = str(entry.get("优先级", "P1"))
        if pri in ("P2", "P3"):
            return "S0"
        return "S1"

    return "S2"


def _density_base_floor(category: str, priority: str, density: str) -> int:
    pri = priority if priority in ("P0", "P1", "P2", "P3") else "P1"
    den = density if density in SOURCE_DENSITY_LEVELS else "S2"

    if category in _EVENT_DENSITY_FLOORS:
        return _EVENT_DENSITY_FLOORS[category][pri][den]
    if category == "庶众":
        return _SHUZHONG_DENSITY_FLOORS[pri][den]
    if category in PERSON_CATEGORIES:
        return _PERSON_DENSITY_FLOORS[pri][den]
    return MIN_DETAIL_CHARS.get((category, pri), 400)


def anchor_floor_bonus(anchor: dict[str, Any] | None) -> int:
    if not anchor:
        return 0
    bonus = 0
    bonus += 30 * len(anchor.get("hard_facts") or [])
    bonus += 20 * len(anchor.get("legend_facts") or [])
    for item in anchor.get("core_enumerations") or []:
        if isinstance(item, dict):
            bonus += 40 * len(item.get("items") or [])
        elif isinstance(item, list):
            bonus += 40 * len(item)
    return bonus


def detail_effective_floor(
    category: str,
    priority: str,
    entry: dict[str, Any] | None = None,
    anchor: dict[str, Any] | None = None,
) -> int:
    """effective_floor = 丰度基线 + 锚点加成，cap 至 S3 旧版上限。"""
    entry = entry or {}
    density = resolve_source_density(entry, anchor)
    base = _density_base_floor(category, priority, density)
    bonus = anchor_floor_bonus(anchor)
    cap = MIN_DETAIL_CHARS.get((category, priority), base + bonus)
    return min(base + bonus, cap)


def detail_min_chars(
    category: str,
    priority: str,
    entry: dict[str, Any] | None = None,
    anchor: dict[str, Any] | None = None,
) -> int:
    """gate / compose 统一入口；优先双轴 effective_floor。"""
    if entry is not None or anchor is not None:
        return detail_effective_floor(category, priority, entry, anchor)
    return MIN_DETAIL_CHARS.get((category, priority), 400)


def load_anchor(anchors_dir: Path, entry_id: str) -> dict[str, Any] | None:
    path = anchors_dir / f"{entry_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_anchor(anchors_dir: Path, entry_id: str, anchor: dict[str, Any]) -> Path:
    anchors_dir.mkdir(parents=True, exist_ok=True)
    path = anchors_dir / f"{entry_id}.json"
    path.write_text(json.dumps(anchor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def review_artifact_path(logs_dir: Path, entry_id: str) -> Path:
    return logs_dir / "reviews" / f"{entry_id}_review.json"


def verify_artifact_path(logs_dir: Path, entry_id: str) -> Path:
    return logs_dir / "verify" / f"{entry_id}_verify.json"


def load_review_artifact(logs_dir: Path, entry_id: str) -> dict[str, Any] | None:
    path = review_artifact_path(logs_dir, entry_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_review_artifact(logs_dir: Path, entry_id: str, review: dict[str, Any]) -> Path:
    path = review_artifact_path(logs_dir, entry_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def save_verify_artifact(logs_dir: Path, entry_id: str, report: dict[str, Any]) -> Path:
    path = verify_artifact_path(logs_dir, entry_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def split_detail_paragraphs(body: str) -> list[str]:
    """与小程序 box-detail splitDetailParagraphs 一致：按 \\n\\n 切段。"""
    text = strip_detail_body(body).strip()
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return parts if parts else [text]


PERSON_CAT_SLUG = {
    "君王": "JUNWANG",
    "诸侯": "ZHUHOU",
    "宗戚": "ZONGQI",
    "宦官": "HUANGUAN",
    "文臣": "WENCHEN",
    "武将": "WUJIANG",
    "蕃祚": "FANZUO",
    "庶众": "SHUZHONG",
}

def detail_compose_temperature(category: str) -> float:
    """详情撰写温度：事略/人物偏叙事 0.3，典制/论著偏准确 0.2。"""
    if category in ("事略", *PERSON_CATEGORIES):
        return 0.3
    return 0.2


def strip_detail_body(text: str) -> str:
    body = text
    for marker in ("*参考著作", "参考著作"):
        if marker in body:
            body = body.split(marker, 1)[0]
    return body.strip()


# 对客正文：全文禁止拼音括注（读者通过字典查读音）；纯「今…」地名标注保留


_PAREN_ANNOT_RE = re.compile(r"[（(]([^）)]+)[）)]")
_LATIN_OR_TONE_RE = re.compile(
    r"[A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]"
)


def _chinese_run_before(text: str, idx: int, *, max_len: int = 8) -> str:
    chars: list[str] = []
    j = idx - 1
    while j >= 0 and len(chars) < max_len:
        c = text[j]
        if "\u4e00" <= c <= "\u9fff":
            chars.insert(0, c)
            j -= 1
        else:
            break
    return "".join(chars)


def _annotation_word(text: str, paren_start: int) -> tuple[str, int]:
    """从括号前截取被注音/标注的词头（避免「发生在阪泉（」整段误匹配）。"""
    run = _chinese_run_before(text, paren_start)
    if not run:
        return "", paren_start
    if len(run) <= 4:
        return run, paren_start - len(run)
    # 长串取末尾 2～4 字为词（阪泉、颛顼、姬水等）
    for n in (2, 3, 4):
        if len(run) >= n:
            return run[-n:], paren_start - n
    return run, paren_start - len(run)


def _is_modern_location_only(inner: str) -> bool:
    s = inner.strip()
    if s.startswith("今"):
        return _LATIN_OR_TONE_RE.search(s) is None
    return False


def _is_exempt_annotation(inner: str) -> bool:
    """非注音括注：母本编号、西元纪年等。"""
    s = inner.strip()
    if re.fullmatch(r"M\d{1,4}", s):
        return True
    if re.fullmatch(r"BC\d{1,4}", s, re.I):
        return True
    return False


def _looks_like_pinyin_annotation(inner: str, word: str) -> bool:
    """仅处理注音/今属地；跳过长篇括注说明。"""
    s = inner.strip()
    if not s:
        return False
    if _is_exempt_annotation(s):
        return False
    if _is_modern_location_only(s):
        return True
    if _LATIN_OR_TONE_RE.search(s):
        return True
    # 纯拼音音节（短）
    if len(s) <= 16 and re.fullmatch(
        r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z\s·]+", s
    ):
        return True
    return False


def _resolve_annotation(word: str, inner: str, original: str) -> str:
    if not word:
        if _is_modern_location_only(inner):
            return f"（{inner.strip()}）"
        if _LATIN_OR_TONE_RE.search(inner):
            loc_m = re.search(r"今[^）)]+", inner)
            if loc_m:
                return f"（{loc_m.group(0)}）"
            return ""
        if len(inner.strip()) <= 16 and re.fullmatch(
            r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z\s·]+", inner.strip()
        ):
            return ""
        return original

    if _is_modern_location_only(inner):
        return f"{word}（{inner.strip()}）"

    if _LATIN_OR_TONE_RE.search(inner):
        loc_m = re.search(r"今[^）)]+", inner)
        if loc_m:
            return f"{word}（{loc_m.group(0)}）"
        return word

    if len(inner.strip()) <= 16 and re.fullmatch(
        r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z\s·]+", inner.strip()
    ):
        return word
    return word


def fix_doubled_word_heads(text: str) -> tuple[str, list[str]]:
    """修复 clean_over_pinyin 历史 bug 造成的连续重复词头（如 妫汭妫汭 → 妫汭）。"""
    changes: list[str] = []
    doubled = re.compile(r"([\u4e00-\u9fff]{2,4})\1")

    def repl(m: re.Match[str]) -> str:
        changes.append(f"{m.group(0)} → {m.group(1)}")
        return m.group(1)

    return doubled.sub(repl, text), changes


def clean_over_pinyin(text: str) -> tuple[str, list[str]]:
    """删除一切拼音括注；保留纯「今属地」标注。"""
    changes: list[str] = []
    parts: list[str] = []
    last = 0
    for m in _PAREN_ANNOT_RE.finditer(text):
        inner = m.group(1)
        word, word_start = _annotation_word(text, m.start())
        original = text[word_start : m.end()]
        if not _looks_like_pinyin_annotation(inner, word):
            parts.append(text[last : m.end()])
            last = m.end()
            continue
        seg_start = word_start if word else m.start()
        parts.append(text[last : seg_start])
        resolved = _resolve_annotation(word, inner, original)
        if resolved != original:
            changes.append(f"{original} → {resolved}")
        parts.append(resolved)
        last = m.end()
    parts.append(text[last:])
    cleaned = "".join(parts)
    cleaned, dedupe_changes = fix_doubled_word_heads(cleaned)
    changes.extend(dedupe_changes)
    return cleaned, changes


def detect_over_pinyin(body: str) -> list[str]:
    """检出一切拼音括注（gate 用）；纯「今属地」不报错。"""
    issues: list[str] = []
    for m in _PAREN_ANNOT_RE.finditer(body):
        inner = m.group(1)
        word, word_start = _annotation_word(body, m.start())
        original = body[word_start : m.end()]
        if not _looks_like_pinyin_annotation(inner, word):
            continue
        if _is_modern_location_only(inner):
            continue
        if not word:
            issues.append(f"多余括注：{original}")
            continue
        if _resolve_annotation(word, inner, original) != original:
            issues.append(f"多余括注：{original}")
        elif _LATIN_OR_TONE_RE.search(inner):
            issues.append(f"多余括注：{original}")
    return issues


def load_person_alias_maps() -> dict[str, str]:
    """标注名/异名 → 标准名（帝王别名 + 宗戚别名）。"""
    out: dict[str, str] = {}
    for rel in ("帝王别名.json", "宗戚别名.json"):
        path = ANNOTATE_REF / rel
        if not path.is_file():
            continue
        cfg = json.loads(path.read_text(encoding="utf-8"))
        for alias, canonical in (cfg.get("global") or {}).items():
            a, c = str(alias).strip(), str(canonical).strip()
            if a and c:
                out[a] = c
    return out


def normalize_person_name(name: str, alias_map: dict[str, str]) -> str:
    n = (name or "").strip()
    if not n:
        return n
    seen: set[str] = set()
    cur = n
    while cur not in seen:
        seen.add(cur)
        nxt = alias_map.get(cur)
        if not nxt or nxt == cur:
            break
        cur = nxt
    return cur


def load_phase1_person_index(
    histograph_root: Path,
    dynasty_id: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """一期已标注人物（本朝）+ 别名→标准名索引。"""
    alias_map = load_person_alias_maps()
    index_path = histograph_root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    if not index_path.is_file():
        return [], alias_map

    root = json.loads(index_path.read_text(encoding="utf-8"))
    entries = root.get("entries") if isinstance(root, dict) else root
    persons: list[dict[str, Any]] = []
    canonical_to_aliases: dict[str, set[str]] = {}

    emperor_path = histograph_root / "data" / "01历史坐标数据" / "帝王.json"
    orig_to_std: dict[str, str] = {}
    if emperor_path.is_file():
        for row in json.loads(emperor_path.read_text(encoding="utf-8")):
            std = str(row.get("帝王名称", "")).strip()
            orig = str(row.get("帝王原名", "")).strip()
            if std and orig:
                orig_to_std[orig] = std

    if not isinstance(entries, list):
        return [], alias_map

    for e in entries:
        if not isinstance(e, dict):
            continue
        if str(e.get("朝代ID", "")).strip() != dynasty_id:
            continue
        cat = str(e.get("史略分类", "")).strip()
        if cat not in PERSON_INDEX_CATEGORIES:
            continue
        name = str(e.get("史略名称", "")).strip()
        if not name:
            continue
        canonical = normalize_person_name(name, alias_map)
        persons.append(
            {
                "史略ID": e.get("史略ID"),
                "史略名称": name,
                "标准名": canonical,
                "史略分类": cat,
            }
        )
        canonical_to_aliases.setdefault(canonical, set()).add(name)
        for alias, std in alias_map.items():
            if std == canonical or std == name:
                canonical_to_aliases[canonical].add(alias)
        if name in orig_to_std:
            canonical_to_aliases[canonical].add(orig_to_std[name])
        for orig, std in orig_to_std.items():
            if std == canonical:
                canonical_to_aliases[canonical].add(orig)

    alias_index: dict[str, str] = {}
    for canonical, aliases in canonical_to_aliases.items():
        for a in aliases:
            if a:
                alias_index[a] = canonical
        alias_index[canonical] = canonical

    phase1_canonical_set = {str(p["标准名"]) for p in persons}
    for alias, std in alias_map.items():
        if std in phase1_canonical_set or std in {str(p["史略名称"]) for p in persons}:
            alias_index[alias] = std

    return persons, alias_index


def _ensure_annotate_on_path() -> None:
    ann = OPENCLAW_ROOT / "historiography-annotate"
    if str(ann) not in sys.path:
        sys.path.insert(0, str(ann))


def is_phase1_juwang_adequately_covered(entry: dict[str, Any]) -> bool:
    """一期君王是否视为已覆盖（朝代补全条目，或史料提取且厚度达标）。"""
    if str(entry.get("母本著作") or "").strip() == "朝代补全":
        return True
    if str(entry.get("史略来源") or "").strip() == "朝代补全":
        return True
    _ensure_annotate_on_path()
    from source_thickness import classify_glbl_thickness  # noqa: WPS433

    result = classify_glbl_thickness(entry)
    return str(result.get("verdict") or "") in ("pass", "pass_swap_recommended")


def load_dynasty_supplement_person_index(
    histograph_root: Path,
    dynasty_id: str,
) -> list[dict[str, Any]]:
    """06朝代知识补全已有的人物索引（本朝）。"""
    index_dir = histograph_root / "data" / "06朝代知识补全" / "索引条目"
    if not index_dir.is_dir():
        return []
    persons: list[dict[str, Any]] = []
    for fp in sorted(index_dir.glob("*.json")):
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for e in doc.get("entries") or []:
            if not isinstance(e, dict):
                continue
            if str(e.get("朝代ID", "")).strip() != dynasty_id:
                continue
            cat = str(e.get("史略分类", "")).strip()
            if cat not in PERSON_INDEX_CATEGORIES:
                continue
            name = str(e.get("史略名称", "")).strip()
            if name:
                persons.append(e)
    return persons


def _emperor_name_keys(
    name: str,
    alias_index: dict[str, str],
    alias_map: dict[str, str],
) -> set[str]:
    canon = alias_index.get(name) or normalize_person_name(name, alias_map)
    keys = {name, canon}
    keys.discard("")
    return keys


def collect_covered_emperor_names(
    histograph_root: Path,
    dynasty_id: str,
    alias_index: dict[str, str],
    *,
    extra_entries: list[dict[str, Any]] | None = None,
) -> set[str]:
    """已覆盖帝王名（一期合格君王 + 06补全君王 + 本批 entries）。"""
    alias_map = load_person_alias_maps()
    covered: set[str] = set()

    index_path = histograph_root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    if index_path.is_file():
        root = json.loads(index_path.read_text(encoding="utf-8"))
        for e in root.get("entries") or []:
            if not isinstance(e, dict):
                continue
            if str(e.get("朝代ID", "")).strip() != dynasty_id:
                continue
            if str(e.get("史略分类", "")).strip() not in SOVEREIGN_CATEGORIES:
                continue
            if not is_phase1_juwang_adequately_covered(e):
                continue
            name = str(e.get("史略名称", "")).strip()
            covered.update(_emperor_name_keys(name, alias_index, alias_map))

    for e in load_dynasty_supplement_person_index(histograph_root, dynasty_id):
        if str(e.get("史略分类", "")).strip() not in SOVEREIGN_CATEGORIES:
            continue
        name = str(e.get("史略名称", "")).strip()
        covered.update(_emperor_name_keys(name, alias_index, alias_map))

    for e in extra_entries or []:
        if str(e.get("史略分类", "")).strip() not in SOVEREIGN_CATEGORIES:
            continue
        name = str(e.get("史略名称", "")).strip()
        covered.update(_emperor_name_keys(name, alias_index, alias_map))

    return covered


def load_emperor_gaps(
    histograph_root: Path,
    dynasty_id: str,
    alias_index: dict[str, str],
    *,
    extra_entries: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """帝王.json 中尚未覆盖者（薄一期 GLBL、06 补全、本批 entries 均计入已覆盖）。"""
    alias_map = load_person_alias_maps()
    covered = collect_covered_emperor_names(
        histograph_root, dynasty_id, alias_index, extra_entries=extra_entries
    )

    gaps: list[dict[str, str]] = []
    for row in load_emperors(histograph_root, dynasty_id):
        if not is_mandatory_dynasty_monarch(row):
            continue
        name = str(row.get("帝王名称", "")).strip()
        if not name:
            continue
        if _emperor_name_keys(name, alias_index, alias_map) & covered:
            continue
        gaps.append(
            {
                "帝王名称": name,
                "帝王ID": str(row.get("帝王ID", "")).strip(),
                "补全理由": "帝王表正牌君王、当前无合格条目，须朝代知识补全",
            }
        )
    return gaps


def emperor_gap_to_candidate(gap: dict[str, str]) -> dict[str, Any]:
    name = str(gap.get("帝王名称", "")).strip()
    return {
        "名称": name,
        "史略分类": "君王",
        "补全来源": "帝王表强制",
        "补全理由": str(gap.get("补全理由") or "帝王表强制补全"),
        "建议挂靠帝王": name,
        "主要史料出处": "",
        "边界备注": f"帝王ID={gap.get('帝王ID', '')}",
        "审核状态": "mandatory",
        "强制补全": True,
        "去重自检": "帝王表缺口，脚本强制注入",
    }


def validate_mandatory_emperor_coverage(
    histograph_root: Path,
    dynasty_id: str,
    alias_index: dict[str, str],
    *,
    extra_entries: list[dict[str, Any]] | None = None,
) -> list[str]:
    gaps = load_emperor_gaps(
        histograph_root, dynasty_id, alias_index, extra_entries=extra_entries
    )
    return [f"缺少强制君王：{g['帝王名称']}（{g['补全理由']}）" for g in gaps]


def inject_mandatory_juwang_candidates(
    candidates: list[dict[str, Any]],
    *,
    emperor_gaps: list[dict[str, str]],
    thin_deferred: list[dict[str, Any]],
    alias_index: dict[str, str],
    phase1_canonicals: set[str],
) -> list[dict[str, Any]]:
    """脚本强制注入帝王表缺口与薄标注君王（不依赖 LLM）。"""
    alias_map = load_person_alias_maps()
    out = list(candidates)
    existing_names = {str(r.get("名称", "")).strip() for r in out}

    def _add(seed: dict[str, Any], *, mandatory: bool = False) -> None:
        name = str(seed.get("名称", "")).strip()
        if not name:
            return
        if name in existing_names:
            return
        if not mandatory:
            canon = alias_index.get(name) or normalize_person_name(name, alias_map)
            if canon in phase1_canonicals:
                return
        out.insert(0, seed)
        existing_names.add(name)

    for gap in emperor_gaps:
        _add(emperor_gap_to_candidate(gap), mandatory=True)

    for row in thin_deferred:
        if str(row.get("史略分类", "")).strip() not in SOVEREIGN_CATEGORIES:
            continue
        seed = thin_deferred_to_candidate(row)
        seed["强制补全"] = True
        seed["审核状态"] = "mandatory"
        seed["补全来源"] = "薄标注待补"
        _add(seed, mandatory=True)

    return out


def thin_deferred_registry_path(histograph_root: Path) -> Path:
    return histograph_root / "data" / "05工作流中间产物" / "薄标注待补全" / "registry.json"


def load_thin_deferred_for_dynasty(
    histograph_root: Path,
    dynasty_id: str,
    *,
    dynasty_name: str = "",
) -> list[dict[str, Any]]:
    """merge 厚度门拒收的薄标注条目（本朝），供 candidates-renwu 优先候选。"""
    fp = thin_deferred_registry_path(histograph_root)
    if not fp.is_file():
        return []
    doc = json.loads(fp.read_text(encoding="utf-8"))
    rows = doc.get("entries") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_dyn = str(row.get("朝代ID", "")).strip()
        row_coord = str(row.get("二级朝代坐标", "")).strip()
        if row_dyn != dynasty_id and not (dynasty_name and row_coord == dynasty_name):
            continue
        cat = str(row.get("史略分类", "")).strip()
        if cat not in PERSON_INDEX_CATEGORIES:
            continue
        out.append(row)
    return out


def thin_deferred_to_candidate(row: dict[str, Any]) -> dict[str, Any]:
    """薄标注注册表 → 人物候选行。"""
    name = str(row.get("史略名称", "")).strip()
    chars = int(row.get("source_char_count") or 0)
    refs = row.get("merge_sources") or []
    ref_note = "; ".join(
        f"{r.get('work', '')}{r.get('vol', '')}({r.get('source_char_count', '?')}字)"
        for r in refs[:3]
    )
    return {
        "名称": name,
        "史略分类": row.get("史略分类"),
        "补全来源": "薄标注待补",
        "补全理由": f"一期标注合计仅{chars}字（<100），未升GLBL；史料薄不宜顺译",
        "主要史料出处": row.get("主要史料出处") or ref_note,
        "边界备注": f"著作级ID={row.get('史略ID', '')}；{ref_note}",
        "审核状态": "pending",
        "去重自检": "来自薄标注注册表，一期无 GLBL",
    }
