"""时空坐标枚举加载与校验（帝王 / 政权 / 朝代 / 文明）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

SKILL_DIR = Path(__file__).resolve().parent
REF = SKILL_DIR / "reference"

EMPEROR_JSON = REF / "帝王.json"
ZONGQI_JSON = REF / "宗戚.json"
REGIME_JSON = REF / "政权.json"
DYNASTY_JSON = REF / "朝代.json"
CIVILIZATION_JSON = REF / "文明.json"

# Step 4 坐标字段（顺序：文明 → 朝代 → 政权 → 帝王）
COORD_FIELDS = (
    "一级文明坐标",
    "二级朝代坐标",
    "三级政权坐标",
    "四级帝王坐标",
)

# 非君王人物：LLM 只判定四级帝王；一～三级由帝王.json 反推
FOURTH_EMPIRE_COORD_FIELD = "四级帝王坐标"
SCRIPT_COORD_FIELDS = COORD_FIELDS[:3]

# Step 4 坐标 ID（与 COORD_FIELDS 一一对应，脚本从 reference/*.json 自动写入）
COORD_ID_FIELDS = (
    "文明ID",
    "朝代ID",
    "政权ID",
    "帝王ID",
)

LEGACY_COORD_MAP = {
    "一级文明归属": "一级文明坐标",
    "二级王朝归属": "二级朝代坐标",
    "三级帝王归属": "四级帝王坐标",
}

LEGACY_CATEGORY_MAP = {
    "君纪": "君王",
    "著作": "论著",
    "思想": "论著",
}

# 禁止作为四级帝王坐标写入的标准名（须用右侧标准名，见 reference/帝王命名规范.md）
FORBIDDEN_EMPEROR_NAMES: Dict[str, str] = {
    "汉高帝": "汉高祖",
}


def _norm_key(key: str) -> str:
    return key.lstrip("\ufeff").strip()


def _row_dict(raw: dict) -> dict:
    return {_norm_key(k): v for k, v in raw.items()}


def load_civilization_records(path: Optional[Path] = None) -> List[dict]:
    p = path or CIVILIZATION_JSON
    with open(p, encoding="utf-8-sig") as f:
        rows = json.load(f)
    out: List[dict] = []
    for raw in rows:
        r = _row_dict(raw)
        name = (r.get("文明名称") or "").strip()
        if not name:
            continue
        out.append({
            "name": name,
            "id": (r.get("文明ID") or "").strip(),
            "order": r.get("文明序号"),
        })
    return out


def build_civilization_index(records: Optional[List[dict]] = None) -> Dict[str, dict]:
    records = records if records is not None else load_civilization_records()
    index: Dict[str, dict] = {}
    for info in records:
        name = info["name"]
        if name not in index:
            index[name] = info
    return index


def valid_civilizations() -> frozenset:
    return frozenset(build_civilization_index().keys())


def civilization_id_map() -> Dict[str, str]:
    return {info["name"]: info["id"] for info in build_civilization_index().values()}


def resolve_civilization_id(civilization: str) -> str:
    civ = (civilization or "").strip()
    alias = {"北亚游牧": "北亚"}
    civ = alias.get(civ, civ)
    return civilization_id_map().get(civ, "")


def dynasty_name_pinyin(name: str) -> str:
    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError as exc:
        raise ImportError("生成朝代ID需要安装 pypinyin：pip install pypinyin") from exc
    text = re.sub(r"[()（）\s·\-—]", "", name)
    chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    if not chars:
        chars = list(text)
    py = "".join(lazy_pinyin("".join(chars), style=Style.NORMAL))
    return re.sub(r"[^a-zA-Z0-9]", "", py).upper()


def make_dynasty_id(civilization_id: str, dynasty_name: str) -> str:
    civ_id = (civilization_id or "").strip()
    dynasty = (dynasty_name or "").strip()
    return f"CD_{civ_id}_{dynasty_name_pinyin(dynasty)}"


def dynasty_id_slug(civilization_id: str, dynasty_id: str, dynasty_name: str) -> str:
    civ_id = (civilization_id or "").strip()
    did = (dynasty_id or "").strip()
    prefix = f"CD_{civ_id}_"
    if did.startswith(prefix):
        return did[len(prefix):]
    return dynasty_name_pinyin(dynasty_name)


def make_regime_id(
    civilization_id: str,
    dynasty_id: str,
    dynasty_name: str,
    regime_name: str,
) -> str:
    civ_id = (civilization_id or "").strip()
    slug = dynasty_id_slug(civ_id, dynasty_id, dynasty_name)
    regime_py = dynasty_name_pinyin(regime_name)
    return f"ZQ_{civ_id}_{slug}_{regime_py}"


def regime_id_slug(
    civilization_id: str,
    dynasty_id: str,
    regime_id: str,
    regime_name: str = "",
) -> str:
    civ_id = (civilization_id or "").strip()
    did = (dynasty_id or "").strip()
    rid = (regime_id or "").strip()
    dyn_slug = dynasty_id_slug(civ_id, did, "")
    prefix = f"ZQ_{civ_id}_{dyn_slug}_"
    if rid.startswith(prefix):
        return rid[len(prefix):]
    return dynasty_name_pinyin(regime_name)


def make_emperor_id(
    civilization_id: str,
    dynasty_id: str,
    regime_id: str,
    emperor_name: str,
) -> str:
    civ_id = (civilization_id or "").strip()
    dyn_slug = dynasty_id_slug(civ_id, dynasty_id, "")
    reg_slug = regime_id_slug(civ_id, dynasty_id, regime_id, "")
    name_py = dynasty_name_pinyin(emperor_name)
    return f"DW_{civ_id}_{dyn_slug}_{reg_slug}_{name_py}"


def emperor_row_name(row: dict) -> str:
    return (row.get("帝王名称") or row.get("帝王") or "").strip()


def emperor_row_id(row: dict) -> str:
    return (row.get("帝王ID") or row.get("帝王 ID") or "").strip()


def emperor_row_given_name(row: dict) -> str:
    return (row.get("帝王原名") or row.get("帝王名字") or "").strip()


VALID_CIVILIZATIONS = valid_civilizations()


def parse_year_value(value) -> Optional[int]:
    """解析 JSON 中的年份（支持 约-3000、-2698、至今 等）。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip()
    if not s or s in ("-", "—", "未知", "不详"):
        return None
    if "至今" in s:
        return None
    s = re.sub(r"^[约 circa]+", "", s, flags=re.I).strip()
    if s.lstrip("-").isdigit():
        return int(s)
    m = re.match(r"^(-?\d+)", s)
    return int(m.group(1)) if m else None


def load_emperor_records(path: Optional[Path] = None) -> List[dict]:
    p = path or EMPEROR_JSON
    with open(p, encoding="utf-8-sig") as f:
        rows = json.load(f)
    out: List[dict] = []
    for raw in rows:
        r = _row_dict(raw)
        emperor = emperor_row_name(r)
        if not emperor:
            continue
        out.append({
            "id": emperor_row_id(r),
            "emperor": emperor,
            "regime": (r.get("政权") or "").strip(),
            "dynasty": (r.get("朝代") or "").strip(),
            "civilization": (r.get("文明") or "").strip(),
            "civilization_id": (r.get("文明ID") or resolve_civilization_id(r.get("文明", ""))).strip(),
            "dynasty_id": (r.get("朝代ID") or "").strip(),
            "regime_id": (r.get("政权ID") or "").strip(),
            "given_name": emperor_row_given_name(r),
            "start_year": parse_year_value(r.get("即位时间")),
            "end_year": parse_year_value(r.get("退位时间")),
        })
    return out


def zongqi_row_name(row: dict) -> str:
    return (row.get("宗戚名称") or row.get("名称") or "").strip()


def zongqi_row_id(row: dict) -> str:
    return (row.get("宗戚ID") or "").strip()


def load_zongqi_records(path: Optional[Path] = None) -> List[dict]:
    p = path or ZONGQI_JSON
    if not p.is_file():
        return []
    with open(p, encoding="utf-8-sig") as f:
        rows = json.load(f)
    out: List[dict] = []
    for raw in rows:
        r = _row_dict(raw)
        name = zongqi_row_name(r)
        if not name:
            continue
        out.append({
            "id": zongqi_row_id(r),
            "name": name,
            "given_name": (r.get("宗戚原名") or "").strip(),
            "type": (r.get("宗戚类型") or "").strip(),
            "enfeoffing_emperor": (r.get("册封之君") or "").strip(),
            "enfeoffing_emperor_id": (r.get("册封之君ID") or "").strip(),
            "regime": (r.get("政权") or "").strip(),
            "dynasty": (r.get("朝代") or "").strip(),
            "civilization": (r.get("文明") or "").strip(),
            "civilization_id": (r.get("文明ID") or resolve_civilization_id(r.get("文明", ""))).strip(),
            "dynasty_id": (r.get("朝代ID") or "").strip(),
            "regime_id": (r.get("政权ID") or "").strip(),
            "start_year": parse_year_value(r.get("受封时间")),
            "end_year": parse_year_value(r.get("卒年")),
        })
    return out


def build_zongqi_index(records: Optional[List[dict]] = None) -> Dict[str, dict]:
    records = records if records is not None else load_zongqi_records()
    index: Dict[str, dict] = {}
    for info in records:
        name = info["name"]
        if name not in index:
            index[name] = info
        given = info.get("given_name") or ""
        if given and given not in index:
            index[given] = info
    return index


def load_regime_records(path: Optional[Path] = None) -> List[dict]:
    p = path or REGIME_JSON
    with open(p, encoding="utf-8-sig") as f:
        rows = json.load(f)
    out: List[dict] = []
    for raw in rows:
        r = _row_dict(raw)
        regime = (r.get("政权") or "").strip()
        if not regime:
            continue
        out.append({
            "regime": regime,
            "regime_id": (r.get("政权ID") or "").strip(),
            "dynasty": (r.get("朝代") or "").strip(),
            "dynasty_id": (r.get("朝代ID") or "").strip(),
            "civilization": (r.get("文明") or "").strip(),
            "civilization_id": (r.get("文明ID") or resolve_civilization_id(r.get("文明", ""))).strip(),
            "start_year": parse_year_value(r.get("开始时间")),
            "end_year": parse_year_value(r.get("结束时间")),
            "id": (r.get("政权ID") or r.get("ID") or "").strip(),
        })
    return out


def load_dynasty_records(path: Optional[Path] = None) -> List[dict]:
    p = path or DYNASTY_JSON
    with open(p, encoding="utf-8-sig") as f:
        rows = json.load(f)
    out: List[dict] = []
    for raw in rows:
        r = _row_dict(raw)
        dynasty = (r.get("朝代") or "").strip()
        if not dynasty:
            continue
        out.append({
            "dynasty": dynasty,
            "dynasty_id": (r.get("朝代ID") or make_dynasty_id(r.get("文明ID", ""), dynasty)).strip(),
            "civilization": (r.get("文明") or "").strip(),
            "civilization_id": (r.get("文明ID") or resolve_civilization_id(r.get("文明", ""))).strip(),
            "start_year": parse_year_value(r.get("开始时间")),
            "end_year": parse_year_value(r.get("结束时间")),
        })
    return out


def build_emperor_index(records: Optional[List[dict]] = None) -> Dict[str, dict]:
    records = records if records is not None else load_emperor_records()
    index: Dict[str, dict] = {}
    for info in records:
        name = info["emperor"]
        if name not in index:
            index[name] = info
    return index


def validate_emperor_records(
    rows: List[dict],
    *,
    regimes: Optional[List[dict]] = None,
    dynasties: Optional[List[dict]] = None,
) -> List[str]:
    """校验帝王.json：ID/名称唯一、必填字段、政权ID/朝代ID 外键存在。"""
    from collections import Counter

    issues: List[str] = []
    if not rows:
        issues.append("帝王.json 为空")
        return issues

    ids = [(i, (r.get("帝王ID") or "").strip()) for i, r in enumerate(rows)]
    empty_ids = [i for i, eid in ids if not eid]
    if empty_ids:
        issues.append(f"缺少帝王ID: 行 {empty_ids[:5]}")

    id_vals = [eid for _, eid in ids if eid]
    id_dup = [k for k, v in Counter(id_vals).items() if v > 1]
    if id_dup:
        issues.append(f"帝王ID 重复 {len(id_dup)} 组: {id_dup[:8]}")

    names = [(r.get("帝王名称") or r.get("帝王") or "").strip() for r in rows]
    empty_names = [i for i, n in enumerate(names) if not n]
    if empty_names:
        issues.append(f"缺少帝王名称: 行 {empty_names[:5]}")

    name_dup = [k for k, v in Counter(names).items() if v > 1 and k]
    if name_dup:
        issues.append(f"帝王名称重复 {len(name_dup)} 组: {name_dup[:8]}")

    required = ("政权", "朝代", "文明", "文明ID", "朝代ID", "政权ID")
    for i, row in enumerate(rows):
        label = row.get("帝王名称") or f"行{i}"
        for f in required:
            if not (row.get(f) or "").strip():
                issues.append(f"[{label}] 缺少 {f}")

    if regimes is None:
        with open(REGIME_JSON, encoding="utf-8-sig") as f:
            regimes = json.load(f)
    if dynasties is None:
        with open(DYNASTY_JSON, encoding="utf-8-sig") as f:
            dynasties = json.load(f)

    regime_ids = {
        (r.get("政权ID") or r.get("ID") or "").strip()
        for r in regimes
        if isinstance(r, dict)
    }
    regime_ids.discard("")
    dynasty_ids = {
        (d.get("朝代ID") or d.get("ID") or "").strip()
        for d in dynasties
        if isinstance(d, dict)
    }
    dynasty_ids.discard("")

    missing_regime: dict[str, list[str]] = {}
    missing_dynasty: dict[str, list[str]] = {}
    for row in rows:
        label = row.get("帝王名称") or "?"
        rid = (row.get("政权ID") or "").strip()
        did = (row.get("朝代ID") or "").strip()
        if rid and rid not in regime_ids:
            missing_regime.setdefault(rid, []).append(label)
        if did and did not in dynasty_ids:
            missing_dynasty.setdefault(did, []).append(label)

    for rid, labels in sorted(missing_regime.items()):
        issues.append(
            f"政权ID {rid} 在政权.json 中不存在（如 {labels[0]} 等 {len(labels)} 条）"
        )
    for did, labels in sorted(missing_dynasty.items()):
        issues.append(
            f"朝代ID {did} 在朝代.json 中不存在（如 {labels[0]} 等 {len(labels)} 条）"
        )

    return issues


def build_regime_index(records: Optional[List[dict]] = None) -> Dict[str, dict]:
    """按政权名索引（同名多朝代时仅保留首条，精确匹配请用 build_regime_pair_index）。"""
    records = records if records is not None else load_regime_records()
    index: Dict[str, dict] = {}
    for info in records:
        regime = info["regime"]
        if regime not in index:
            index[regime] = info
    return index


def build_regime_pair_index(records: Optional[List[dict]] = None) -> Dict[Tuple[str, str], dict]:
    """(二级朝代, 三级政权) → 政权.json 行（SSOT 精确匹配）。"""
    records = records if records is not None else load_regime_records()
    index: Dict[Tuple[str, str], dict] = {}
    for info in records:
        dynasty = (info.get("dynasty") or "").strip()
        regime = (info.get("regime") or "").strip()
        if not dynasty or not regime:
            continue
        key = (dynasty, regime)
        if key not in index:
            index[key] = info
    return index


def lookup_regime_row(
    dynasty: str,
    regime: str,
    *,
    regime_index: Optional[Dict[str, dict]] = None,
    pair_index: Optional[Dict[Tuple[str, str], dict]] = None,
) -> Optional[dict]:
    """在政权.json 中查找 (朝代, 政权) 对应行。"""
    from dynasty_resolve import canonical_dynasty

    dyn = canonical_dynasty((dynasty or "").strip())
    reg = (regime or "").strip()
    if not reg:
        return None
    pi = pair_index if pair_index is not None else build_regime_pair_index()
    if dyn:
        hit = pi.get((dyn, reg))
        if hit:
            return hit
    ri = regime_index if regime_index is not None else build_regime_index()
    info = ri.get(reg)
    if not info:
        return None
    reg_dyn = (info.get("dynasty") or "").strip()
    if not dyn or not reg_dyn or reg_dyn == dyn:
        return info
    return None


def build_dynasty_index_from_json(records: Optional[List[dict]] = None) -> Dict[str, dict]:
    records = records if records is not None else load_dynasty_records()
    index: Dict[str, dict] = {}
    for info in records:
        dynasty = info["dynasty"]
        if dynasty not in index:
            index[dynasty] = info
    return index


def build_enum_sets(
    emperor_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    ei = emperor_index or build_emperor_index()
    ri = regime_index or build_regime_index()
    di = dynasty_index or build_dynasty_index_from_json()
    emperors = set(ei.keys())
    regimes = set(ri.keys())
    dynasties = set(di.keys())
    civilizations = set(valid_civilizations())
    for info in ei.values():
        if info.get("civilization"):
            civilizations.add(info["civilization"])
    for info in ri.values():
        if info.get("civilization"):
            civilizations.add(info["civilization"])
    for info in di.values():
        if info.get("civilization"):
            civilizations.add(info["civilization"])
    return civilizations, dynasties, regimes, emperors


def coords_from_emperor(info: dict, regime_index: Optional[Dict[str, dict]] = None) -> dict:
    """由帝王记录反推四级坐标（政权/朝代名规范为 reference 标准名）。"""
    from dynasty_resolve import canonical_dynasty
    from regime_resolve import canonical_regime

    dynasty = canonical_dynasty((info.get("dynasty") or "").strip())
    regime = canonical_regime(info.get("regime", ""), dynasty, regime_index)
    return {
        "四级帝王坐标": info.get("emperor", ""),
        "三级政权坐标": regime,
        "二级朝代坐标": dynasty,
        "一级文明坐标": info.get("civilization", ""),
    }


def ids_from_emperor(info: dict) -> dict:
    """由帝王记录反推四级坐标 ID。"""
    civ_id = (info.get("civilization_id") or "").strip()
    if not civ_id:
        civ_id = resolve_civilization_id(info.get("civilization", ""))
    return {
        "文明ID": civ_id,
        "朝代ID": (info.get("dynasty_id") or "").strip(),
        "政权ID": (info.get("regime_id") or "").strip(),
        "帝王ID": (info.get("id") or "").strip(),
    }


def coords_and_ids_from_emperor(
    info: dict,
    regime_index: Optional[Dict[str, dict]] = None,
) -> dict:
    return {
        **coords_from_emperor(info, regime_index),
        **ids_from_emperor(info),
    }


def ids_from_entry_coords(
    entry: dict,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> dict:
    """由条目四级坐标名反查 reference ID；优先以帝王表为 SSOT。"""
    ei = emperor_index or build_emperor_index()
    ri = regime_index or build_regime_index()
    di = dynasty_index or build_dynasty_index_from_json()

    emp_name = (entry.get("四级帝王坐标") or "").strip()
    if emp_name and emp_name in ei:
        return ids_from_emperor(ei[emp_name])

    civ = (entry.get("一级文明坐标") or "").strip()
    dyn = (entry.get("二级朝代坐标") or "").strip()
    reg = (entry.get("三级政权坐标") or "").strip()
    civ_id = resolve_civilization_id(civ) if civ else ""
    dinfo = di.get(dyn) or {}
    dynasty_id = (dinfo.get("dynasty_id") or "").strip()
    if not dynasty_id and civ_id and dyn:
        dynasty_id = make_dynasty_id(civ_id, dyn)
    rinfo = lookup_regime_row(dyn, reg, regime_index=ri) or ri.get(reg) or {}
    regime_id = (rinfo.get("regime_id") or "").strip()
    if not regime_id and civ_id and dynasty_id and reg:
        regime_id = make_regime_id(civ_id, dynasty_id, dyn, reg)
    emperor_id = ""
    if emp_name and civ_id and dynasty_id and regime_id:
        emperor_id = make_emperor_id(civ_id, dynasty_id, regime_id, emp_name)
    return {
        "文明ID": civ_id,
        "朝代ID": dynasty_id,
        "政权ID": regime_id,
        "帝王ID": emperor_id,
    }


def entry_coords_mismatch_emperor(
    entry: dict,
    emp_info: dict,
    *,
    regime_index: Optional[Dict[str, dict]] = None,
) -> List[str]:
    """返回与帝王表不一致的坐标字段名。"""
    expected = coords_from_emperor(emp_info, regime_index)
    mismatched: List[str] = []
    for f in COORD_FIELDS:
        cur = (entry.get(f) or "").strip()
        if cur != expected[f]:
            mismatched.append(f)
    return mismatched


def sync_entry_coords_from_emperor(
    entry: dict,
    emperor_index: Optional[Dict[str, dict]] = None,
    *,
    regime_index: Optional[Dict[str, dict]] = None,
) -> Optional[str]:
    """
    四级帝王已在帝王表时，以帝王表为 SSOT 同步整条坐标链。
    返回变更说明；无变更则 None。
    """
    ei = emperor_index or build_emperor_index()
    ri = regime_index or build_regime_index()
    emp_name = (entry.get("四级帝王坐标") or "").strip()
    if not emp_name or emp_name not in ei:
        return None
    expected = coords_from_emperor(ei[emp_name], ri)
    expected_ids = ids_from_emperor(ei[emp_name])
    mismatched = entry_coords_mismatch_emperor(entry, ei[emp_name], regime_index=ri)
    id_mismatched = [
        f for f in COORD_ID_FIELDS
        if (expected_ids.get(f) or "").strip()
        and (entry.get(f) or "").strip() != expected_ids[f]
    ]
    if not mismatched and not id_mismatched:
        return None
    old = {f: (entry.get(f) or "").strip() for f in mismatched}
    for f in COORD_FIELDS:
        entry[f] = expected[f]
    for f in COORD_ID_FIELDS:
        if expected_ids.get(f):
            entry[f] = expected_ids[f]
    auto = entry.get("_auto_filled")
    if isinstance(auto, dict):
        for f in COORD_FIELDS:
            auto[f] = expected[f]
        for f in COORD_ID_FIELDS:
            if expected_ids.get(f):
                auto[f] = expected_ids[f]
    parts = [f"{f}「{old.get(f, '')}」→「{expected[f]}」" for f in mismatched]
    if id_mismatched:
        parts.append(f"坐标ID: {', '.join(id_mismatched)}")
    eid = entry.get("史略ID", "?")
    return f"[{eid}] 帝王表对齐: {', '.join(parts)}"


def sync_entry_coord_ids(
    entry: dict,
    emperor_index: Optional[Dict[str, dict]] = None,
    *,
    regime_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> Optional[str]:
    """根据四级坐标名补全/校正 文明ID/朝代ID/政权ID/帝王ID。"""
    expected = ids_from_entry_coords(
        entry,
        emperor_index=emperor_index,
        regime_index=regime_index,
        dynasty_index=dynasty_index,
    )
    changed: List[str] = []
    for f in COORD_ID_FIELDS:
        val = (expected.get(f) or "").strip()
        if not val:
            continue
        if entry.get(f) != val:
            entry[f] = val
            changed.append(f)
    auto = entry.get("_auto_filled")
    if isinstance(auto, dict):
        for f in COORD_ID_FIELDS:
            if expected.get(f):
                auto[f] = expected[f]
    if not changed:
        return None
    eid = entry.get("史略ID", "?")
    return f"[{eid}] 坐标ID补全: {', '.join(changed)}"


def normalize_entry_category(cat: str) -> str:
    return LEGACY_CATEGORY_MAP.get(cat.strip(), cat.strip())


def migrate_entry_fields(entry: dict) -> None:
    """就地迁移旧分类名 / 旧坐标字段名（读盘兼容）。"""
    cat = entry.get("史略分类", "")
    if cat in LEGACY_CATEGORY_MAP:
        entry["史略分类"] = LEGACY_CATEGORY_MAP[cat]
    for old, new in LEGACY_COORD_MAP.items():
        if old in entry and new not in entry:
            entry[new] = entry.pop(old)


def validate_entry_coordinates(
    entry: dict,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> List[str]:
    issues: List[str] = []
    eid = entry.get("史略ID", "?")
    name = entry.get("史略名称", "?")
    cat = normalize_entry_category(entry.get("史略分类", ""))
    prefix = f"[{eid}] {name}"

    for old in LEGACY_COORD_MAP:
        if old in entry and entry.get(old) not in (None, ""):
            issues.append(f"{prefix} 仍使用旧字段「{old}」，请改为「{LEGACY_COORD_MAP[old]}」")

    ei = emperor_index or build_emperor_index()
    ri = regime_index or build_regime_index()
    di = dynasty_index or build_dynasty_index_from_json()
    civs, dyn_set, reg_set, emp_set = build_enum_sets(ei, ri, di)
    _ = civs  # 文明校验用 VALID_CIVILIZATIONS

    coords = {f: (entry.get(f) or "").strip() for f in COORD_FIELDS}
    for f in COORD_FIELDS:
        if not coords[f]:
            issues.append(f"{prefix} 缺少 {f}")

    if issues:
        return issues

    if coords["一级文明坐标"] not in valid_civilizations():
        issues.append(
            f"{prefix} 一级文明坐标「{coords['一级文明坐标']}」不在文明.json"
        )
    from dynasty_resolve import canonical_dynasty
    from regime_resolve import canonical_regime

    canon_dyn = canonical_dynasty(coords["二级朝代坐标"])
    if canon_dyn != coords["二级朝代坐标"]:
        coords = {**coords, "二级朝代坐标": canon_dyn}
    if coords["二级朝代坐标"] not in dyn_set:
        issues.append(f"{prefix} 二级朝代坐标「{coords['二级朝代坐标']}」不在朝代.json")

    pi = build_regime_pair_index()
    canon_reg = canonical_regime(coords["三级政权坐标"], coords["二级朝代坐标"], ri)
    if canon_reg != coords["三级政权坐标"]:
        coords = {**coords, "三级政权坐标": canon_reg}
    reg_row = lookup_regime_row(
        coords["二级朝代坐标"],
        coords["三级政权坐标"],
        regime_index=ri,
        pair_index=pi,
    )
    if not reg_row:
        issues.append(
            f"{prefix} 三级政权「{coords['三级政权坐标']}」与二级朝代"
            f"「{coords['二级朝代坐标']}」在政权.json 无对应行"
        )
    elif coords["三级政权坐标"] not in reg_set:
        _ = reg_set  # 保留枚举集供其它校验扩展
    if coords["四级帝王坐标"] not in emp_set:
        issues.append(f"{prefix} 四级帝王坐标「{coords['四级帝王坐标']}」不在帝王.json")

    forbidden = FORBIDDEN_EMPEROR_NAMES.get(coords["四级帝王坐标"])
    if forbidden:
        issues.append(
            f"{prefix} 四级帝王坐标禁止使用「{coords['四级帝王坐标']}」，"
            f"标准名为「{forbidden}」（见 reference/帝王命名规范.md）"
        )

    emp_info = ei.get(coords["四级帝王坐标"])
    if emp_info:
        expected = coords_from_emperor(emp_info, regime_index=ri)
        for f in COORD_FIELDS:
            if coords[f] != expected[f]:
                issues.append(
                    f"{prefix} {f}「{coords[f]}」与帝王表不一致"
                    f"（应为「{expected[f]}」）"
                )
        emp_reg_row = lookup_regime_row(
            emp_info.get("dynasty", ""),
            emp_info.get("regime", ""),
            regime_index=ri,
            pair_index=pi,
        )
        if not emp_reg_row:
            issues.append(
                f"{prefix} 帝王表「{coords['四级帝王坐标']}」的"
                f"朝代「{emp_info.get('dynasty', '')}」/政权「{emp_info.get('regime', '')}」"
                f"在政权.json 无对应行"
            )
        else:
            emp_rid = (emp_info.get("regime_id") or "").strip()
            row_rid = (emp_reg_row.get("regime_id") or "").strip()
            if emp_rid and row_rid and emp_rid != row_rid:
                issues.append(
                    f"{prefix} 帝王表「{coords['四级帝王坐标']}」政权ID"
                    f"「{emp_rid}」与政权.json「{row_rid}」不一致"
                )
        expected_ids = ids_from_emperor(emp_info)
        if reg_row:
            for id_field, row_key in (
                ("政权ID", "regime_id"),
                ("朝代ID", "dynasty_id"),
                ("文明ID", "civilization_id"),
            ):
                row_val = (reg_row.get(row_key) or "").strip()
                if row_val and expected_ids.get(id_field) != row_val:
                    expected_ids = {**expected_ids, id_field: row_val}
        for f in COORD_ID_FIELDS:
            val = (entry.get(f) or "").strip()
            exp = (expected_ids.get(f) or "").strip()
            if exp and val != exp:
                issues.append(f"{prefix} {f}「{val}」与帝王/政权表不一致（应为「{exp}」）")
            elif exp and not val:
                issues.append(f"{prefix} 缺少 {f}（应为「{exp}」）")

    if cat == "君王":
        from emperor_resolve import split_regnal_given_name

        if name != coords["四级帝王坐标"]:
            issues.append(
                f"{prefix} 君王史略名称须与四级帝王坐标、帝王.json「帝王」字段完全一致"
                f"（现为名称「{name}」坐标「{coords['四级帝王坐标']}」）"
            )
        if name not in emp_set:
            issues.append(f"{prefix} 君王史略名称「{name}」不在帝王.json")
        split = split_regnal_given_name(name)
        if split:
            title, given = split
            if title in emp_set:
                issues.append(
                    f"{prefix} 君王史略名称「{name}」含私名「{given}」，"
                    f"应改为帝王表标准名「{title}」（名入帝王.json「帝王原名」）"
                )
    elif cat in ("士臣", "庶众", "宗戚"):
        if coords["四级帝王坐标"] == name:
            issues.append(
                f"{prefix} 四级帝王坐标不得与史略名称相同"
                f"（须为事件/人物所属在位君主，见帝王.json）"
            )

    return issues
