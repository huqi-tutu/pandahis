#!/usr/bin/env python3
"""史略 Peak Year（峰值年）标注：规则 → LLM → 兜底 三层，幂等可审核。

字段（中文键，与索引 JSON 一致）：
  峰值年 / 峰值原因 / 峰值类型 / 峰值置信度
元数据（写入 _auto_filled）：
  _峰值LLM依据 / _峰值人工锁定 / _峰值兜底级别 / _峰值指纹 / _峰值待审

设计约束（见 reference/峰值年规则.md）：
  - 同一实体（内容指纹不变）重跑结果一致：LLM temperature=0 + 指纹缓存跳过。
  - 硬约束 开始年 <= 峰值年 <= 结束年，越界 clamp 并降置信度、标待审。
  - 人工锁定（_峰值人工锁定=true）永不被脚本覆盖。

用法：
  python3 peak_year.py <index_or_skeleton.json>            # 仅规则+兜底
  python3 peak_year.py <index.json> --llm                  # 叠加 LLM 判定层
  python3 peak_year.py <index.json> --verify               # 只校验，exit 1=有问题
  python3 peak_year.py <index.json> --dry-run              # 只算不写，打印统计
  python3 peak_year.py <index.json> --llm --review-out review.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent
PKG_ROOT = SKILL_DIR.parent
for _p in (str(SKILL_DIR), str(PKG_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib_config import coerce_year  # noqa: E402
from category_v3 import normalize_entry_category  # noqa: E402

# ── 字段常量 ────────────────────────────────────────────────
PEAK_YEAR = "峰值年"
PEAK_REASON = "峰值原因"
PEAK_TYPE = "峰值类型"
PEAK_CONF = "峰值置信度"

META_LLM_BASIS = "_峰值LLM依据"
META_LOCK = "_峰值人工锁定"
META_LEVEL = "_峰值兜底级别"
META_FP = "_峰值指纹"
META_REVIEW = "_峰值待审"

# ── 枚举与默认映射 ──────────────────────────────────────────
VALID_PEAK_TYPES = frozenset({
    "political_peak",
    "military_peak",
    "career_peak",
    "institutional_maturity",
    "thought_spread",
    "territorial_peak",
    "event_climax",
    "founding",
})

DEFAULT_PEAK_TYPE_BY_CATEGORY: Dict[str, str] = {
    "君王": "political_peak",
    "宗戚": "political_peak",
    "宦官": "political_peak",
    "文臣": "career_peak",
    "武将": "military_peak",
    "蕃祚": "territorial_peak",
    "庶众": "event_climax",
    # 兼容旧分类
    "事略": "event_climax",
    "典制": "institutional_maturity",
    "论著": "thought_spread",
    "民录": "event_climax",
    "著作": "thought_spread",
    "思想": "thought_spread",
    "士臣": "career_peak",
}

REVIEW_CONF_THRESHOLD = 0.4
FALLBACK_CONF = 0.3
HIGH_RISK_BATCH_SIZE = 5
MOTHER_QUOTE_MAX = 300

LEVEL_RULE = "rule"
LEVEL_LLM = "llm"
LEVEL_FALLBACK = "fallback_midpoint"


def default_peak_type(category: str) -> str:
    return DEFAULT_PEAK_TYPE_BY_CATEGORY.get(
        normalize_entry_category(category), "founding"
    )


# ── 幂等与锁定 ──────────────────────────────────────────────
def entry_fingerprint(entry: dict) -> str:
    """内容指纹：仅依赖实体自身语义字段，与 DB 排序 / 页面无关。"""
    basis = "|".join(
        str(entry.get(k, ""))
        for k in (
            "史略ID",
            "史略名称",
            "史略分类",
            "史略开始年",
            "史略结束年",
            "史略简介",
            "原文字句",
        )
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def _auto(entry: dict) -> dict:
    auto = entry.get("_auto_filled")
    if not isinstance(auto, dict):
        auto = {}
        entry["_auto_filled"] = auto
    return auto


def is_locked(entry: dict) -> bool:
    return bool((entry.get("_auto_filled") or {}).get(META_LOCK))


def has_valid_peak(entry: dict) -> bool:
    return coerce_year(entry.get(PEAK_YEAR)) is not None


def is_fresh(entry: dict) -> bool:
    """已有峰值年且指纹未变 → 可跳过（幂等）。"""
    auto = entry.get("_auto_filled") or {}
    return has_valid_peak(entry) and auto.get(META_FP) == entry_fingerprint(entry)


# ── 写入与校验 ──────────────────────────────────────────────
def _clamp(year: int, start: int, end: int) -> Tuple[int, bool]:
    if year < start:
        return start, True
    if year > end:
        return end, True
    return year, False


def write_peak(
    entry: dict,
    year: int,
    reason: str,
    ptype: str,
    conf: float,
    level: str,
) -> None:
    """写入峰值字段（含 clamp、类型归一、待审标记）。不覆盖人工锁定。"""
    if is_locked(entry):
        return
    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))

    clamped = False
    if start is not None and end is not None:
        if start > end:
            start, end = end, start
        year, clamped = _clamp(int(year), start, end)

    if ptype not in VALID_PEAK_TYPES:
        ptype = default_peak_type(entry.get("史略分类", ""))
    conf = max(0.0, min(1.0, float(conf)))
    if clamped:
        conf = min(conf, 0.4)

    entry[PEAK_YEAR] = int(year)
    entry[PEAK_REASON] = (reason or "").strip() or "（待补原因）"
    entry[PEAK_TYPE] = ptype
    entry[PEAK_CONF] = round(conf, 2)

    auto = _auto(entry)
    auto[META_LEVEL] = level
    auto[META_FP] = entry_fingerprint(entry)
    if level == LEVEL_LLM:
        auto[META_LLM_BASIS] = entry[PEAK_REASON]
    need_review = clamped or conf < REVIEW_CONF_THRESHOLD
    if need_review:
        notes = []
        if clamped:
            notes.append("峰值年越界已收敛到区间")
        if conf < REVIEW_CONF_THRESHOLD:
            notes.append(f"置信度低({conf:.2f})")
        auto[META_REVIEW] = "；".join(notes)
    else:
        auto.pop(META_REVIEW, None)


def validate_peak(entry: dict) -> List[str]:
    """返回错误文案列表，空=通过。"""
    eid = entry.get("史略ID", "?")
    name = entry.get("史略名称", "?")
    prefix = f"[{eid}] {name}"
    issues: List[str] = []

    py = coerce_year(entry.get(PEAK_YEAR))
    if py is None:
        issues.append(f"{prefix} 缺少有效峰值年")
        return issues
    if not isinstance(entry.get(PEAK_YEAR), int):
        issues.append(f"{prefix} 峰值年须为 JSON 整数")

    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))
    if start is not None and end is not None:
        lo, hi = min(start, end), max(start, end)
        if not (lo <= py <= hi):
            issues.append(f"{prefix} 峰值年({py}) 越界 [{lo},{hi}]")

    ptype = entry.get(PEAK_TYPE)
    if ptype not in VALID_PEAK_TYPES:
        issues.append(f"{prefix} 非法峰值类型: {ptype}")

    conf = entry.get(PEAK_CONF)
    if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
        issues.append(f"{prefix} 峰值置信度须为 [0,1]: {conf}")

    if not (entry.get(PEAK_REASON) or "").strip():
        issues.append(f"{prefix} 缺少峰值原因")
    return issues


# ── Layer 1：确定性规则 ─────────────────────────────────────
def apply_rule_layer(entry: dict) -> bool:
    """能确定性判定的场景。返回是否已落定。"""
    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))
    if start is None or end is None:
        return False
    # 单点年份：峰值年唯一，置信度满
    if start == end:
        write_peak(
            entry,
            start,
            "单点年份，峰值即该年",
            default_peak_type(entry.get("史略分类", "")),
            1.0,
            LEVEL_RULE,
        )
        return True
    return False


# ── Layer 3：兜底中点 ───────────────────────────────────────
def apply_fallback_layer(entry: dict) -> bool:
    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))
    if start is None or end is None:
        return False
    mid = int(round((start + end) / 2))
    write_peak(
        entry,
        mid,
        "无法精确判定，取区间中点（需人工审核）",
        default_peak_type(entry.get("史略分类", "")),
        FALLBACK_CONF,
        LEVEL_FALLBACK,
    )
    return True


# ── Layer 2：LLM 判定（主体锁定 + 富字段输入）────────────────
PEAK_RULES_BRIEF = (
    "峰值年=该实体历史/政治/军事/思想/社会影响达到最高峰的年份，"
    "不是出生年/建立年/死亡年（除非该年本身即最高点）。"
    "君王:统一/开创盛世/权力巅峰>登基>崩; 宗戚/宦官:实际掌权年; "
    "文臣:主持改革/核心职位; 武将:决定性战役/最大军功; "
    "事略:关键爆发/转折年; 典制:成熟推广年>建立年; 论著:成书/思想成熟年; "
    "庶众:社会影响最大年; 蕃祚:疆域最大/国势鼎盛年。"
    "峰值类型枚举: political_peak/military_peak/career_peak/"
    "institutional_maturity/thought_spread/territorial_peak/event_climax/founding。"
)

SUBJECT_LOCK_PROMPT = """【主体锁定 — 必须遵守】
- 峰值年只属于字段「判定对象」（=史略名称），不是卷名传主、不是四级帝王坐标、不是母本原文字句里顺带提到的人。
- 合传/世家：卷名可含他人（如《魏相丙吉传》），每条只判该条「判定对象」本人；勿把合传另一人/events 套到本条。
- 四级帝王坐标仅表示「本条主要活跃于哪位帝王在位期间」，不要把帝王即位年当作非君王人物的峰值年。
- 峰值原因必须点明「判定对象」的哪项成就/事件；原因主语若是他人 → 置信度≤0.3。
- 证据范围以「母本段落」「母本原文字句」「坐标主轴」为准，勿用卷内其他段落推断。"""


def _kaoding(entry: dict) -> dict:
    raw = entry.get("考订依据")
    return raw if isinstance(raw, dict) else {}


def _volume_title_from_source(source: str) -> str:
    """从《史记·卷86·魏相丙吉传》提取卷名核心「魏相丙吉」。"""
    text = (source or "").strip()
    if "·" in text:
        text = text.rsplit("·", 1)[-1]
    return text.replace("》", "").replace("传", "").replace("纪", "").strip()


def is_joint_biography(entry: dict) -> bool:
    """合传/卷名含多人：易把卷内他人当峰值主体。"""
    src = entry.get("主要史料出处") or ""
    if "合传" in src:
        return True
    inner = _volume_title_from_source(src)
    name = (entry.get("史略名称") or "").strip()
    if not inner or not name:
        return False
    if any(sep in inner for sep in ("与", "及", "并")):
        return True
    if len(inner) > len(name) and name in inner:
        return True
    return False


def is_high_risk_entry(entry: dict) -> bool:
    """合传、多源合并、蕃祚等：缩小 LLM 批次、加强待审。"""
    if is_joint_biography(entry):
        return True
    if len(entry.get("source_entries") or []) > 1:
        return True
    if normalize_entry_category(entry.get("史略分类", "")) == "蕃祚":
        return True
    # 世家卷多君（卷题非本条名称）
    src = entry.get("主要史料出处") or ""
    if "世家" in src and entry.get("史略分类") == "君王":
        vol = _volume_title_from_source(src)
        name = (entry.get("史略名称") or "").strip()
        if vol and name and vol not in name and name not in vol:
            return True
    return False


def mother_paragraph_ref(entry: dict) -> str:
    anchor = (entry.get("六级段落锚点") or "").strip()
    if anchor:
        return anchor.strip("[]")
    paragraphs = entry.get("paragraphs") or []
    mother = next((p for p in paragraphs if p.get("role") == "母本"), None)
    if not mother and paragraphs:
        mother = paragraphs[0]
    if not isinstance(mother, dict):
        return ""
    pf, pt = mother.get("paragraph_from"), mother.get("paragraph_to")
    if pf is None:
        return ""
    if pt is None or pt == pf:
        return f"P{pf}"
    return f"P{pf}-P{pt}"


def mother_work_label(entry: dict) -> str:
    paragraphs = entry.get("paragraphs") or []
    mother = next((p for p in paragraphs if p.get("role") == "母本"), None)
    if isinstance(mother, dict):
        parts = [mother.get("work"), mother.get("volume")]
        label = "·".join(str(p) for p in parts if p)
        if label:
            return label
    return _volume_title_from_source(entry.get("主要史料出处") or "")


def _name_in_text(name: str, text: str) -> bool:
    name = (name or "").strip()
    text = (text or "").strip()
    if not name or not text:
        return False
    if name in text:
        return True
    if len(name) >= 2 and name[-2:] in text and len(name) <= 4:
        return True
    return False


def _emperor_coord_matches(entry: dict) -> bool:
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat != "君王":
        return True
    name = (entry.get("史略名称") or "").strip()
    coord = (entry.get("四级帝王坐标") or "").strip()
    if not name or not coord:
        return True
    return name in coord or coord in name or (len(name) >= 2 and name[-2:] in coord)


def build_llm_input(entry: dict) -> dict:
    """组装给 LLM 的条目载荷（不含卷内优先级等易误导字段）。"""
    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))
    name = (entry.get("史略名称") or "").strip()
    kaoding = _kaoding(entry)
    lo, hi = (min(start, end), max(start, end)) if start is not None and end is not None else (None, None)

    payload: dict = {
        "史略ID": entry.get("史略ID"),
        "判定对象": name,
        "史略分类": normalize_entry_category(entry.get("史略分类", "")),
        "史略简介": entry.get("史略简介"),
        "史略开始年": start,
        "史略结束年": end,
        "峰值年合法区间": f"[{lo},{hi}]" if lo is not None and hi is not None else None,
        "坐标主轴": kaoding.get("坐标主轴") or "",
        "年考订": kaoding.get("年") or "",
        "主要史料出处": entry.get("主要史料出处"),
        "母本段落": mother_paragraph_ref(entry),
        "母本著作": mother_work_label(entry),
        "五级细坐标": entry.get("五级细坐标"),
        "二级朝代坐标": entry.get("二级朝代坐标"),
        "三级政权坐标": entry.get("三级政权坐标"),
        "四级帝王坐标": entry.get("四级帝王坐标"),
        "母本原文字句": (entry.get("原文字句") or "")[:MOTHER_QUOTE_MAX],
    }
    if is_high_risk_entry(entry):
        payload["注意"] = (
            "合传/多源/蕃祚/世家多君等易混淆场景：只判「判定对象」本人，勿与卷内他人混淆"
        )
    return {k: v for k, v in payload.items() if v not in (None, "")}


def apply_post_llm_checks(entry: dict) -> List[str]:
    """LLM 写入后的守门：原因主语、君王坐标一致性。"""
    notes: List[str] = []
    name = (entry.get("史略名称") or "").strip()
    reason = (entry.get(PEAK_REASON) or "").strip()

    if name and reason and not _name_in_text(name, reason):
        notes.append(f"峰值原因未点名判定对象({name})")
        conf = entry.get(PEAK_CONF)
        if isinstance(conf, (int, float)):
            entry[PEAK_CONF] = round(min(float(conf), 0.35), 2)

    if not _emperor_coord_matches(entry):
        notes.append("君王四级帝王坐标与史略名称不一致")
        conf = entry.get(PEAK_CONF)
        if isinstance(conf, (int, float)):
            entry[PEAK_CONF] = round(min(float(conf), 0.35), 2)

    if notes:
        auto = _auto(entry)
        prev = (auto.get(META_REVIEW) or "").strip()
        merged = "；".join(x for x in [prev, "；".join(notes)] if x)
        auto[META_REVIEW] = merged
    return notes


def _llm_batches(items: List[dict], default_batch: int) -> List[List[dict]]:
    """高风险条目用小批次，普通条目用默认批次。"""
    high = [e for e in items if is_high_risk_entry(e)]
    normal = [e for e in items if not is_high_risk_entry(e)]
    chunks: List[List[dict]] = []
    risk_size = min(HIGH_RISK_BATCH_SIZE, default_batch)
    for group, size in ((high, risk_size), (normal, default_batch)):
        for i in range(0, len(group), size):
            chunks.append(group[i : i + size])
    return chunks


def build_llm_prompt(category: str, batch: List[dict]) -> str:
    lines = [
        f"你是历史考订助手。为下列「{category}」类史略逐条判定峰值年。",
        SUBJECT_LOCK_PROMPT,
        "",
        PEAK_RULES_BRIEF,
        "",
        "硬约束：峰值年必须是整数（公元前为负），且落在「峰值年合法区间」内。",
        "置信度 ∈ [0,1]；无法精确判定时取区间中段并把置信度降到 <=0.4。",
        "",
        "只输出一个 JSON 数组，每个元素形如："
        '{"史略ID":"...","峰值年":整数,"峰值原因":"简述（须点名判定对象）",'
        '"峰值类型":"枚举值","峰值置信度":0.xx}',
        "不要输出数组以外的任何文字。",
        "",
        "待判定条目：",
    ]
    for e in batch:
        lines.append(json.dumps(build_llm_input(e), ensure_ascii=False))
    return "\n".join(lines)


def _extract_json_array(text: str) -> List[dict]:
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


def _log(msg: str) -> None:
    print(msg, flush=True)


def run_llm_batch(
    category: str,
    batch: List[dict],
    *,
    batch_index: int,
    timeout_sec: int = 180,
) -> Dict[str, dict]:
    """单批 LLM 调用，返回 {史略ID: 结果dict}。"""
    from llm.provider import run_agent_turn  # 延迟导入

    risk_n = sum(1 for e in batch if is_high_risk_entry(e))
    prompt = build_llm_prompt(category, batch)
    sid = "peak-" + hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
    tag = f"含{risk_n}条高风险" if risk_n else "常规"
    _log(f"  🤖 LLM 峰值判定 [{category}] 第 {batch_index} 批 ({len(batch)} 条, {tag})")
    out: Dict[str, dict] = {}
    try:
        res = run_agent_turn(
            prompt, session_id=sid, timeout_sec=timeout_sec, temperature=0
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"     ⚠️ LLM 调用失败，本批改兜底: {exc}")
        return out
    for row in _extract_json_array(str(res.get("result", ""))):
        rid = str(row.get("史略ID", "")).strip()
        if rid:
            out[rid] = row
    return out


def _apply_llm_row(entry: dict, row: Optional[dict], stats: Dict[str, int]) -> None:
    year = coerce_year(row.get("峰值年")) if row else None
    if row and year is not None:
        write_peak(
            entry,
            year,
            str(row.get("峰值原因", "")),
            str(row.get("峰值类型", "")),
            float(row.get("峰值置信度", 0.6) or 0.6),
            LEVEL_LLM,
        )
        if apply_post_llm_checks(entry):
            stats["llm_flagged"] += 1
        stats["llm"] += 1
    else:
        apply_fallback_layer(entry)
        stats["fallback"] += 1


def run_llm_layer(
    pending: List[dict],
    *,
    batch_size: int = 20,
    timeout_sec: int = 180,
    on_batch_done: Optional[Callable[[], None]] = None,
) -> Dict[str, dict]:
    """对 pending 条目按分类分批调用 LLM，返回 {史略ID: 结果dict}。"""
    by_cat: Dict[str, List[dict]] = {}
    for e in pending:
        by_cat.setdefault(normalize_entry_category(e.get("史略分类", "")), []).append(e)

    out: Dict[str, dict] = {}
    batch_no = 0
    for cat, items in by_cat.items():
        for batch in _llm_batches(items, batch_size):
            batch_no += 1
            batch_results = run_llm_batch(
                cat, batch, batch_index=batch_no, timeout_sec=timeout_sec
            )
            out.update(batch_results)
            if on_batch_done:
                on_batch_done()
    return out


# ── 编排 ────────────────────────────────────────────────────
def filter_entries_by_dynasty(
    entries: List[dict], dynasty_id: Optional[str]
) -> List[dict]:
    if not dynasty_id:
        return entries
    return [e for e in entries if (e.get("朝代ID") or "") == dynasty_id]


def annotate(
    entries: List[dict],
    *,
    use_llm: bool = False,
    force: bool = False,
    batch_size: int = 20,
    llm_timeout_sec: int = 180,
    on_batch_done: Optional[Callable[[], None]] = None,
) -> Dict[str, int]:
    stats = {
        "total": len(entries),
        "locked": 0,
        "fresh": 0,
        "rule": 0,
        "llm": 0,
        "llm_flagged": 0,
        "fallback": 0,
        "no_year": 0,
    }
    pending_llm: List[dict] = []

    for e in entries:
        if is_locked(e):
            stats["locked"] += 1
            continue
        if not force and is_fresh(e):
            stats["fresh"] += 1
            continue
        if coerce_year(e.get("史略开始年")) is None or coerce_year(e.get("史略结束年")) is None:
            stats["no_year"] += 1
            continue
        if apply_rule_layer(e):
            stats["rule"] += 1
            continue
        if use_llm:
            pending_llm.append(e)
        else:
            apply_fallback_layer(e)
            stats["fallback"] += 1

    if on_batch_done and (stats["rule"] > 0 or stats["fallback"] > 0):
        on_batch_done()

    if use_llm and pending_llm:
        by_cat: Dict[str, List[dict]] = {}
        for e in pending_llm:
            by_cat.setdefault(normalize_entry_category(e.get("史略分类", "")), []).append(e)

        batch_no = 0
        for cat, items in by_cat.items():
            for batch in _llm_batches(items, batch_size):
                batch_no += 1
                batch_results = run_llm_batch(
                    cat, batch, batch_index=batch_no, timeout_sec=llm_timeout_sec
                )
                for e in batch:
                    rid = str(e.get("史略ID", "")).strip()
                    _apply_llm_row(e, batch_results.get(rid), stats)
                if on_batch_done:
                    on_batch_done()

    return stats


def entry_has_complete_years(entry: dict) -> bool:
    return (
        coerce_year(entry.get("史略开始年")) is not None
        and coerce_year(entry.get("史略结束年")) is not None
    )


def annotate_skeleton(
    skeleton_path: Path,
    *,
    use_llm: bool = True,
    force: bool = False,
    batch_size: int = 20,
    review_dir: Optional[Path] = None,
    dynasty_id: Optional[str] = None,
) -> Tuple[Dict[str, int], List[str]]:
    """编排器入口：加载 skeleton → 标注峰值年 → 写回；返回 (stats, logs)。"""
    data, entries = _load(skeleton_path)
    logs: List[str] = []
    if not entries:
        return {"total": 0, "skipped_empty": 1}, ["无 entries，跳过峰值年"]

    work = filter_entries_by_dynasty(entries, dynasty_id) if dynasty_id else entries
    if dynasty_id:
        logs.append(f"朝代过滤 {dynasty_id}: {len(work)}/{len(entries)} 条")

    def _checkpoint() -> None:
        data["entries"] = entries
        skeleton_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    stats = annotate(
        work,
        use_llm=use_llm,
        force=force,
        batch_size=batch_size,
        on_batch_done=_checkpoint if use_llm else None,
    )
    data["entries"] = entries
    skeleton_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logs.append("峰值年标注 " + " ".join(f"{k}={v}" for k, v in stats.items()))

    review_n = len(collect_review(entries))
    if review_n:
        logs.append(f"待人工审核 {review_n} 条（低置信/越界 clamp，不阻断 Step4）")
    if review_dir is not None:
        review_dir.mkdir(parents=True, exist_ok=True)
        review_file = review_dir / f"{skeleton_path.stem}_peak_review.md"
        review_file.write_text(render_review_md(entries), encoding="utf-8")
        logs.append(f"待审清单 → {review_file}")

    return stats, logs


def verify_entries_peak(entries: List[dict]) -> Tuple[bool, List[str]]:
    """硬校验：有完整年份的条目须有合法峰值字段。低置信不 fail。"""
    issues: List[str] = []
    for entry in entries:
        if not entry_has_complete_years(entry):
            continue
        issues.extend(validate_peak(entry))
    return len(issues) == 0, issues


def collect_review(entries: List[dict]) -> List[dict]:
    out = []
    for e in entries:
        auto = e.get("_auto_filled") or {}
        conf = e.get(PEAK_CONF)
        low = isinstance(conf, (int, float)) and conf < REVIEW_CONF_THRESHOLD
        if auto.get(META_REVIEW) or low:
            out.append(e)
    return out


def render_review_md(entries: List[dict]) -> str:
    rows = collect_review(entries)
    lines = [f"# 峰值年待审清单（{len(rows)} 条）", ""]
    for e in rows:
        auto = e.get("_auto_filled") or {}
        lines.append(
            f"- [{e.get('史略ID')}] {e.get('史略名称')}（{e.get('史略分类')}）"
            f" 峰值年={e.get(PEAK_YEAR)} 置信度={e.get(PEAK_CONF)}"
            f" 区间[{e.get('史略开始年')},{e.get('史略结束年')}]"
            f" 原因：{e.get(PEAK_REASON)}"
            + (f"  ⚠️ {auto.get(META_REVIEW)}" if auto.get(META_REVIEW) else "")
        )
    return "\n".join(lines) + "\n"


# ── CLI ─────────────────────────────────────────────────────
def _load(path: Path) -> Tuple[dict, List[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise SystemExit("JSON 顶层须含 entries 数组")
    return data, entries


def main() -> int:
    ap = argparse.ArgumentParser(description="史略峰值年标注")
    ap.add_argument("json_path", type=Path)
    ap.add_argument("--llm", action="store_true", help="启用 LLM 判定层（DeepSeek）")
    ap.add_argument("--force", action="store_true", help="忽略幂等缓存，重标全部")
    ap.add_argument("--verify", action="store_true", help="只校验，exit 1=有问题")
    ap.add_argument("--dry-run", action="store_true", help="只算不写，打印统计")
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument(
        "--dynasty-id",
        default=None,
        help="仅处理指定朝代ID（如 CD_HX_XIHAN），用于 GLBL 分批补全",
    )
    ap.add_argument("--review-out", type=Path, default=None, help="待审清单输出 md")
    args = ap.parse_args()

    if not args.json_path.is_file():
        print(f"❌ 文件不存在: {args.json_path}")
        return 1

    data, all_entries = _load(args.json_path)

    if args.verify:
        issues: List[str] = []
        for e in all_entries:
            issues.extend(validate_peak(e))
        if issues:
            print(f"❌ 峰值年校验失败（{len(issues)} 项）:")
            for line in issues[:40]:
                print(f"  - {line}")
            return 1
        print(f"✅ 峰值年校验通过（{len(all_entries)} 条）")
        return 0

    work = all_entries
    if args.dynasty_id:
        work = filter_entries_by_dynasty(all_entries, args.dynasty_id)
        _log(f"  朝代过滤 {args.dynasty_id}: {len(work)}/{len(all_entries)} 条")

    def _checkpoint() -> None:
        data["entries"] = all_entries
        args.json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    stats = annotate(
        work,
        use_llm=args.llm,
        force=args.force,
        batch_size=args.batch_size,
        on_batch_done=_checkpoint if args.llm else None,
    )
    _log(
        "📊 峰值年标注: "
        + " ".join(f"{k}={v}" for k, v in stats.items())
    )

    review = collect_review(all_entries if args.dynasty_id else work)
    if review:
        print(f"  🔎 待人工审核 {len(review)} 条")
    if args.review_out:
        scope = filter_entries_by_dynasty(all_entries, args.dynasty_id) if args.dynasty_id else all_entries
        args.review_out.write_text(render_review_md(scope), encoding="utf-8")
        print(f"  📝 待审清单 → {args.review_out}")

    if args.dry_run:
        print("（dry-run：未写回文件）")
        return 0

    data["entries"] = all_entries
    args.json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"✅ 已写回: {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
