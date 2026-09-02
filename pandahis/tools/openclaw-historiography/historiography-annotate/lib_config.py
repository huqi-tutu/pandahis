"""共享配置：路径、枚举、帝王索引加载。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from paths_config import DEFAULT_HISTOGRAPH_ROOT, get_histograph_root, histograph_paths  # noqa: E402

from category_v3 import (
    LEGACY_CATEGORY_MAP as _V3_LEGACY_MAP,
    SPINDLE_CATEGORIES,
    VALID_CATS,
    normalize_entry_category,
)
from coordinate_index import (
    COORD_FIELDS,
    EMPEROR_JSON,
    LEGACY_COORD_MAP,
    VALID_CIVILIZATIONS,
    build_dynasty_index_from_json,
    build_emperor_index,
    build_regime_index,
    coords_from_emperor,
    load_emperor_records,
    migrate_entry_fields,
    parse_year_value,
    validate_entry_coordinates,
)

LEGACY_CATEGORY_MAP = _V3_LEGACY_MAP

# 与 category_v3 同步
PERSON_CATS = VALID_CATS
# 读盘兼容：旧 skeleton 可能仍含七类
LEGACY_CATS = frozenset({"君纪", "事略", "典制", "民录", "论著", "著作", "思想"})
VALID_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
VALID_EXCLUDE_REASONS = frozenset({
    "太史公曰",
    "论赞",  # 《汉书》赞曰/《后汉书》论曰及续论段
    "赞曰",
    "评曰",  # 《三国志》陈寿卷末论赞
    "共段总述",  # v2：多位主轴并列总述、无单一叙事主角，无法归一人
    "世系链",
    "过渡叙事",
    "纯纪年",
    "志书数据",
    "艺文目录",
    "卷首标题",
    "篇内小标题",
    "无故事弧",
    "其他",
})

DYNASTY_JSON = SKILL_DIR / "reference" / "朝代.json"
REGIME_JSON = SKILL_DIR / "reference" / "政权.json"
CIVILIZATION_JSON = SKILL_DIR / "reference" / "文明.json"


def paths() -> Dict[str, Path]:
    return histograph_paths()


def load_emperor_index(json_path: Optional[Path] = None) -> Dict[str, dict]:
    """从 reference/帝王.json 构建帝王名索引。"""
    if json_path and json_path != EMPEROR_JSON:
        return build_emperor_index(load_emperor_records(json_path))
    return build_emperor_index()


def build_dynasty_index(emperor_index: Optional[Dict[str, dict]] = None) -> Dict[str, dict]:
    """朝代时间索引（优先朝代.json）。"""
    return build_dynasty_index_from_json()


def load_regime_index() -> Dict[str, dict]:
    return build_regime_index()


def owner_key(name: str, category: str) -> Tuple[str, str]:
    return (name.strip(), category.strip())


# 块内「夹心 exclude」敏感原因：前后同 owner 时高概率误伤
SANDWICH_SENSITIVE_EXCLUDES = frozenset({
    "世系链",
    "过渡叙事",
    "无故事弧",
    "其他",
})


def detect_sandwich_excludes(data: dict) -> List[str]:
    """
    检测块内中间段落误排除：P(n-1) 与 P(n+1) 同 owner，P(n) 却被 exclude。
    返回警告文案（供 check_format / audit_precheck 使用）。
    """
    rows = sorted(
        data.get("segment_attribution") or [],
        key=lambda r: int(r.get("paragraph") or 0),
    )
    if len(rows) < 3:
        return []
    issues: List[str] = []
    for i in range(1, len(rows) - 1):
        prev, mid, nxt = rows[i - 1], rows[i], rows[i + 1]
        reason = (mid.get("exclude_reason") or "").strip()
        if not reason or reason not in SANDWICH_SENSITIVE_EXCLUDES:
            continue
        prev_owners = prev.get("owners") or []
        nxt_owners = nxt.get("owners") or []
        if not prev_owners or not nxt_owners:
            continue
        if len(prev_owners) != 1 or len(nxt_owners) != 1:
            continue
        pk = owner_key(prev_owners[0].get("name", ""), prev_owners[0].get("category", ""))
        nk = owner_key(nxt_owners[0].get("name", ""), nxt_owners[0].get("category", ""))
        if pk != nk:
            continue
        p = mid.get("paragraph")
        name = prev_owners[0].get("name", "")
        issues.append(
            f"段{p} 标为「{reason}」，但 P{int(p) - 1} 与 P{int(p) + 1} 均归 [{name}]，"
            f"疑为块内中间段落误排除，请复核是否应并入该人物叙事"
        )
    return issues


# 卷类型 → 反密度阈值除数（None = 不设阈）
VOLUME_TYPE_THRESHOLDS: Dict[str, Optional[int]] = {
    "纪传叙事": 8,
    "志书叙事": 15,
    "志书数据": 30,
    "目录艺文": 30,
    "表": None,
}

VALID_VOLUME_TYPES = frozenset(VOLUME_TYPE_THRESHOLDS.keys())

# Step 4 年份：人物类均为区间年（无单点类）
SINGLE_YEAR_CATEGORIES: frozenset[str] = frozenset()


def coerce_year(value) -> Optional[int]:
    """将史略开始年/结束年规范为整数；无效返回 None。"""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s.lstrip("-").isdigit():
            return int(s)
    return None


def year_range_label(category: str) -> str:
    """各分类在坐标轴上应使用的时间语义（供 Step 4 / 硬检提示）。"""
    from person_year_fallback import person_year_semantics

    return person_year_semantics(category)


def validate_entry_years(entry: dict) -> List[str]:
    """
    校验 Step 4 时间坐标字段。返回错误文案列表，空=通过。
    每条史略必须有史略开始年+史略结束年，否则无法上时间轴。
    """
    issues: List[str] = []
    cat = normalize_entry_category(entry.get("史略分类", ""))
    eid = entry.get("史略ID", "?")
    name = entry.get("史略名称", "?")
    prefix = f"[{eid}] {name}"

    raw_start = entry.get("史略开始年")
    raw_end = entry.get("史略结束年")
    start = coerce_year(raw_start)
    end = coerce_year(raw_end)

    if start is None:
        issues.append(f"{prefix} 缺少有效史略开始年（整数，公元前为负）")
    if end is None:
        issues.append(f"{prefix} 缺少有效史略结束年（整数，公元前为负）")
    if start is None or end is None:
        return issues

    if not isinstance(raw_start, int):
        issues.append(f"{prefix} 史略开始年须为 JSON 整数，勿用字符串")
    if not isinstance(raw_end, int):
        issues.append(f"{prefix} 史略结束年须为 JSON 整数，勿用字符串")

    if start > end:
        issues.append(f"{prefix} 史略开始年({start}) 大于结束年({end})")

    if cat in SINGLE_YEAR_CATEGORIES and start != end:
        issues.append(
            f"{prefix} {cat} 须在时间轴上单点落位：史略开始年=史略结束年，"
            f"现为 {start}～{end}（{year_range_label(cat)}）"
        )

    return issues


def validate_year_quality(entries: list) -> List[str]:
    """年代质量硬检：批量占位、人物跨度过短、帝王在位年冒充生卒。"""
    issues: List[str] = []
    if not entries:
        return issues

    from hanshu_step4_hardening import (  # noqa: WPS433
        detect_person_year_placeholder,
        entry_year_needs_llm_basis,
        person_year_needs_llm,
    )

    range_counts: Dict[Tuple[int, int], int] = {}
    for entry in entries:
        es, ee = entry.get("史略开始年"), entry.get("史略结束年")
        if isinstance(es, int) and isinstance(ee, int):
            key = (es, ee)
            range_counts[key] = range_counts.get(key, 0) + 1

    shared_placeholder: Optional[Tuple[int, int]] = None
    for (es, ee), cnt in sorted(range_counts.items(), key=lambda x: -x[1]):
        if cnt >= 3 and es != ee and ee - es >= 8:
            shared_placeholder = (es, ee)
            break

    person_index: Dict[str, dict] = {}
    for entry in entries:
        cat = normalize_entry_category(entry.get("史略分类", ""))
        if cat in SPINDLE_CATEGORIES and cat != "君王":
            person_index[entry.get("史略名称", "")] = entry

    for entry in entries:
        eid = entry.get("史略ID", "?")
        name = entry.get("史略名称", "?")
        prefix = f"[{eid}] {name}"
        cat = normalize_entry_category(entry.get("史略分类", ""))
        es, ee = entry.get("史略开始年"), entry.get("史略结束年")
        if not isinstance(es, int) or not isinstance(ee, int):
            continue

        if shared_placeholder and (es, ee) == shared_placeholder:
            issues.append(
                f"{prefix} 年份与同卷 {shared_placeholder[0]}～{shared_placeholder[1]} "
                f"批量占位一致（{range_counts[shared_placeholder]} 条），须逐条考订"
            )

        if person_year_needs_llm(entry) or (
            cat == "君王" and entry_year_needs_llm_basis(entry)
        ):
            label = "人物生卒" if cat != "君王" else "君王在位年"
            issues.append(
                f"{prefix} {label}缺 _年LLM依据，禁止脚本占位；"
                f"须据史料考订并写入 _auto_filled._年LLM依据"
            )
        else:
            ph = detect_person_year_placeholder(entry)
            if ph:
                issues.append(f"{prefix} {ph}；须 LLM 考订生卒并写 _年LLM依据")

        if cat in SPINDLE_CATEGORIES and cat != "君王":
            prs = entry.get("paragraphs") or []
            if prs:
                lo = min(int(p["paragraph_from"]) for p in prs)
                hi = max(int(p["paragraph_to"]) for p in prs)
                span = ee - es
                auto = entry.get("_auto_filled") or {}
                label = "人物"
                # ④ 去世年单点锚定（开始=结束）不强制与段落数匹配
                if es == ee:
                    continue
                single_year_anchor = auto.get("_短跨度合理") or auto.get("_死亡年锚定")
                if (auto.get("_年LLM依据") or "").strip():
                    continue
                if hi - lo + 1 >= 4 and span < 12 and not single_year_anchor:
                    issues.append(
                        f"{prefix} {label}生卒跨度仅 {span} 年"
                        f"（{es}～{ee}），与 {hi - lo + 1} 段传记篇幅不符"
                    )

    return issues


def validate_cosegment_years(entries: list, *, slack: int = 3) -> List[str]:
    """v2 人物标注：无事略条目，跳过共段事略年校验。"""
    _ = entries, slack
    return []


def _coord_triplet(entry: dict) -> Tuple[str, str, str]:
    return (
        (entry.get("二级朝代坐标") or "").strip(),
        (entry.get("三级政权坐标") or "").strip(),
        (entry.get("四级帝王坐标") or "").strip(),
    )


def collect_cosegment_peer_entries(entry: dict, entries: list) -> List[dict]:
    """共段条目在本卷 entries 中的对应对象（不含自身）。"""
    auto = entry.get("_auto_filled") or {}
    index: Dict[Tuple[str, str], dict] = {}
    for e in entries:
        migrate_entry_fields(e)
        index[(e.get("史略名称", ""), normalize_entry_category(e.get("史略分类", "")))] = e
    peers: List[dict] = []
    for peer in auto.get("_共段条目") or []:
        key = (peer.get("name", ""), normalize_entry_category(peer.get("category", "")))
        host = index.get(key)
        if host and host is not entry:
            peers.append(host)
    return peers


PERSON_SPINDLE_RATIONALE_MIN_LEN = 8

# Step4 merge-auto / restore 时须保留的大模型考订字段（禁止脚本覆盖）
LLM_AUTO_FILLED_PRESERVE_KEYS = frozenset({
    "_坐标主轴说明",
    "_年LLM依据",
})
CROSS_REGIME_MIN_SPAN = 30
CROSS_REGIME_MIN_EVENTS = 2


def detect_cross_regime_person(entry: dict, entries: list) -> Optional[str]:
    """文臣/武将/宦官/庶众/宗戚/蕃祚跨时期：共段坐标与人物主轴不一致。"""
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat not in SPINDLE_CATEGORIES or cat == "君王":
        return None
    p_dyn, p_reg, p_emp = _coord_triplet(entry)
    if not p_emp:
        return None

    mismatches: List[str] = []
    for peer in collect_cosegment_peer_entries(entry, entries):
        pc = normalize_entry_category(peer.get("史略分类", ""))
        if pc not in PERSON_CATS or pc == "君王":
            continue
        c_dyn, c_reg, c_emp = _coord_triplet(peer)
        if not c_emp:
            continue
        parts: List[str] = []
        if c_dyn and p_dyn and c_dyn != p_dyn:
            parts.append(f"朝代{c_dyn}")
        if c_reg and p_reg and c_reg != p_reg:
            parts.append(f"政权{c_reg}")
        if c_emp != p_emp:
            parts.append(f"帝王{c_emp}")
        if parts:
            label = peer.get("史略名称", "?")
            mismatches.append(f"「{label}」({'/'.join(parts)})")

    if mismatches:
        return "共段坐标与主轴分歧：" + "；".join(mismatches)

    ss, se = entry.get("史略开始年"), entry.get("史略结束年")
    if isinstance(ss, int) and isinstance(se, int) and se - ss >= CROSS_REGIME_MIN_SPAN:
        return (
            f"活跃跨度 {se - ss} 年，"
            f"须说明为何四级帝王取「{p_emp}」"
            f"（主政/仕宦/最高官职/功业所在；难分则取更早帝王）"
        )
    return None


def person_spindle_rationale(entry: dict) -> str:
    auto = entry.get("_auto_filled") or {}
    return (auto.get("_坐标主轴说明") or "").strip()


def validate_person_spindle_rationale(entry: dict, entries: list) -> List[str]:
    """final 阶段：跨时期人物须含 _auto_filled._坐标主轴说明（finalize 前）。"""
    if "_auto_filled" not in entry:
        return []
    reason = detect_cross_regime_person(entry, entries)
    if not reason:
        return []
    eid = entry.get("史略ID", "?")
    name = entry.get("史略名称", "?")
    if len(person_spindle_rationale(entry)) >= PERSON_SPINDLE_RATIONALE_MIN_LEN:
        return []
    return [
        f"[{eid}] {name} 跨时期人物：{reason}；"
        f"须在 _auto_filled 填写 _坐标主轴说明（为何四级帝王取本卷主轴）"
    ]


def validate_person_spindle_rationale_batch(entries: list) -> List[str]:
    issues: List[str] = []
    for entry in entries:
        issues.extend(validate_person_spindle_rationale(entry, entries))
    return issues


def spindle_rationale_prompt(reason: str) -> str:
    from coord_attrib_rules import SPINDLE_RATIONALE_PROMPT_SUFFIX

    return (
        f"跨时期人物：{reason}。"
        f"四级帝王=主政/仕宦/最高官职/功业所在之君（功绩难分则取更早）；"
        f"二/三级随主轴帝王反推。"
        f"{SPINDLE_RATIONALE_PROMPT_SUFFIX}"
    )


def detect_volume_type(
    volume: str,
    source_file: str = "",
    override: Optional[str] = None,
) -> Tuple[str, str]:
    """返回 (卷类型, 判定来源 rule|manual)。"""
    if override and override in VALID_VOLUME_TYPES:
        return override, "manual"

    text = f"{volume} {source_file}"

    if "艺文" in text or "经籍" in text:
        return "目录艺文", "rule"
    if any(k in text for k in ("天文", "律历", "五行", "符瑞", "河渠")):
        return "志书数据", "rule"
    if "表" in volume and "本纪" not in volume and "世家" not in volume:
        return "表", "rule"
    if any(k in text for k in ("食货", "刑法", "礼乐", "地理", "礼仪", "封禅", "郊祀")):
        return "志书叙事", "rule"
    if volume.endswith("志") or "志" in volume:
        return "志书叙事", "rule"
    # 本纪 / 世家 / 列传 / 默认纪传
    return "纪传叙事", "rule"


def entry_owner_set(entries: list) -> set:
    return {owner_key(e.get("史略名称", ""), e.get("史略分类", "")) for e in entries}
