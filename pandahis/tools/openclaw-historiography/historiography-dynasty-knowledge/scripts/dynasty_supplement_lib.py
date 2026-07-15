"""朝代知识补全：LLM 调用、JSON 解析、ID 与坐标工具。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

OPENCLAW_ROOT = Path(__file__).resolve().parents[2]
ANNOTATE_REF = OPENCLAW_ROOT / "historiography-annotate" / "reference"

PERSON_CATEGORIES = ("君王", "宗戚", "宦官", "文臣", "武将", "蕃祚", "庶众")
PERSON_INDEX_CATEGORIES = frozenset(PERSON_CATEGORIES)

FORBIDDEN_PROSE_WORDS = (
    "综上所述",
    "由此可见",
    "众所周知",
    "历史长河",
    "命运齿轮",
    "毫无疑问",
    "此外",
    "与此同时",
    "值得注意的是",
    "堪称",
    "可谓",
    "不啻",
    "则是",
    "时代洪流",
    "拉开序幕",
    "翻开新篇章",
    "历史终将证明",
    "注定",
    "必然",
)

MIN_PARAGRAPHS_BY_PRIORITY = {
    "P0": 7,  # 开篇引入 + 6 正文段
    "P1": 5,
    "P2": 4,
    "P3": 3,
}

# 质检/撰写 retry 上限（防 agent 或脚本死循环）
MAX_COMPOSE_REVISE_ROUNDS = 1
MAX_PATCH_ROUNDS = 1
MAX_QA_DETAIL_ROUNDS = 2  # compose + 1 revise，整条 qa 链路上限

CATEGORY_SLUG_TO_CN = {
    "shilue": "事略",
    "dianzhi": "典制",
    "lunzhu": "论著",
    "jundwang": "君王",
    "junwang": "君王",
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
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
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
        return None


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


def load_emperors(histograph_root: Path, dynasty_id: str) -> list[dict[str, Any]]:
    path = histograph_root / "data" / "01历史坐标数据" / "帝王.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in rows if str(r.get("朝代ID", "")).strip() == dynasty_id]


def resolve_emperor(
    name: str,
    emperors: list[dict[str, Any]],
) -> dict[str, str] | None:
    """从帝王.json反查完整坐标链（文明→朝代→政权→帝王）。

    设计原则：LLM只需保证四级帝王坐标正确，其余坐标全部从帝王.json权威数据自动推导，
    不依赖LLM输出，杜绝漏标/错标。
    """
    name = (name or "").strip()
    if not name:
        return None
    for row in emperors:
        if name in (
            str(row.get("帝王名称", "")).strip(),
            str(row.get("帝王原名", "")).strip(),
        ):
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
    return None


def apply_coord_defaults(entry: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    out = dict(entry)
    out.setdefault("一级文明坐标", context.get("文明") or "华夏")
    out.setdefault("二级朝代坐标", context.get("朝代名称"))
    out.setdefault("三级政权坐标", context.get("朝代名称"))
    out.setdefault("文明ID", context.get("文明ID") or "HX")
    out.setdefault("朝代ID", context.get("朝代ID"))
    out.setdefault("政权ID", "ZQ_HX_WUDI_WUDI")
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
    "五级细坐标": {"type": str, "nullable": False, "default": ""},
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
    for field, spec in ENTRY_FIELD_SCHEMA.items():
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


# 二期朝代知识详情：默认全文不注音（高级读物，非识字教辅）
# 仅下列词条因含罕用字，允许保留注音；其余一律删除
_ALLOW_PINYIN_WORDS = frozenset(
    {
        "颛顼",
        "帝喾",
        "瞽叟",
        "瞽瞍",
        "娵訾",
        "妫汭",
        "獬廌",
        "獬豸",
        "饕餮",
        "梼杌",
        "穷奇",
        "浑沌",
        "魑魅",
        "少皞",
    }
)

def _normalize_allowed_pinyin(word: str, pinyin: str) -> str:
    """允许词条的注音规范化（如帝喾只保留喾音）。"""
    if word == "帝喾":
        parts = re.split(r"[\s,，]+", pinyin.strip())
        if parts and re.match(r"d[iìíǐ]", parts[0], re.I):
            rest = " ".join(parts[1:]).strip()
            return f"帝喾（{rest}）" if rest else "帝喾"
    return f"{word}（{pinyin.strip()}）"


_PINYIN_ANNOT_RE = re.compile(
    r"([\u4e00-\u9fff]{1,12})[（(]([^）)]+)[）)]"
)
_LATIN_OR_TONE_RE = re.compile(
    r"[A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]"
)
_PAREN_ANNOT_RE = re.compile(r"[（(]([^）)]+)[）)]")


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


def _looks_like_pinyin_annotation(inner: str, word: str) -> bool:
    """仅处理注音/今属地；跳过长篇括注说明。"""
    s = inner.strip()
    if not s:
        return False
    if _is_modern_location_only(s):
        return True
    if _LATIN_OR_TONE_RE.search(s):
        return True
    if word in _ALLOW_PINYIN_WORDS and len(s) <= 24:
        return True
    # 纯拼音音节（短）
    if len(s) <= 16 and re.fullmatch(
        r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z\s·]+", s
    ):
        return True
    return False


def _resolve_annotation(word: str, inner: str, original: str) -> str:
    if not word:
        return original
    if _is_modern_location_only(inner):
        return f"{word}（{inner.strip()}）"

    if _LATIN_OR_TONE_RE.search(inner):
        loc_m = re.search(r"今[^）)]+", inner)
        if loc_m:
            return f"{word}（{loc_m.group(0)}）"
        if word in _ALLOW_PINYIN_WORDS:
            py = re.sub(r"[^a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z\s]", "", inner)
            py = py.strip()
            if py:
                return _normalize_allowed_pinyin(word, py)
        return word

    if word in _ALLOW_PINYIN_WORDS:
        return _normalize_allowed_pinyin(word, inner)
    return word


def clean_over_pinyin(text: str) -> tuple[str, list[str]]:
    """删除一切非白名单注音；保留纯「今属地」标注。"""
    changes: list[str] = []
    parts: list[str] = []
    last = 0
    for m in _PAREN_ANNOT_RE.finditer(text):
        parts.append(text[last : m.start()])
        inner = m.group(1)
        word, word_start = _annotation_word(text, m.start())
        original = text[word_start : m.end()]
        if not _looks_like_pinyin_annotation(inner, word):
            parts.append(original)
            last = m.end()
            continue
        resolved = _resolve_annotation(word, inner, original)
        if resolved != original:
            changes.append(f"{original} → {resolved}")
        parts.append(resolved)
        last = m.end()
    parts.append(text[last:])
    return "".join(parts), changes


def detect_over_pinyin(body: str) -> list[str]:
    """检出一切非白名单注音（gate 用）；「今属地」不报错。"""
    issues: list[str] = []
    for m in _PAREN_ANNOT_RE.finditer(body):
        inner = m.group(1)
        word, word_start = _annotation_word(body, m.start())
        original = body[word_start : m.end()]
        if not _looks_like_pinyin_annotation(inner, word):
            continue
        if _is_modern_location_only(inner):
            continue
        if word in _ALLOW_PINYIN_WORDS:
            continue
        if _resolve_annotation(word, inner, original) == original:
            issues.append(f"禁止注音：{original}")
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


def load_emperor_gaps(
    histograph_root: Path,
    dynasty_id: str,
    alias_index: dict[str, str],
) -> list[dict[str, str]]:
    """帝王.json 中一期未覆盖者（别名归一后，含宗戚已覆盖的太后等）。"""
    phase1, alias_map = load_phase1_person_index(histograph_root, dynasty_id)
    phase1_canonical = {str(p["标准名"]) for p in phase1}
    phase1_names = {str(p["史略名称"]) for p in phase1}

    gaps: list[dict[str, str]] = []
    for row in load_emperors(histograph_root, dynasty_id):
        name = str(row.get("帝王名称", "")).strip()
        if not name:
            continue
        canon = alias_index.get(name) or normalize_person_name(name, alias_map)
        if canon in phase1_canonical or name in phase1_names or canon in phase1_names:
            continue
        gaps.append({"帝王名称": name, "补全理由": "帝王表条目、一期无对应人物条"})
    return gaps
