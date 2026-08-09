#!/usr/bin/env python3
"""
帝王名解析与 skeleton 对齐：
1. 别名 / 帝王名字 / 庙号 / 去前缀 → 帝王.json 标准「帝王」名
2. 君王同步改史略名称 + segment_attribution owners + 四级坐标
3. 缺表时从 reference/帝王待补录.json 合并（字段须完整）
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from coordinate_index import (
    COORD_FIELDS,
    EMPEROR_JSON,
    build_dynasty_index_from_json,
    build_regime_index,
    coords_from_emperor,
    emperor_row_given_name,
    emperor_row_id,
    emperor_row_name,
    load_emperor_records,
    make_emperor_id,
    make_regime_id,
    migrate_entry_fields,
    normalize_entry_category,
    parse_year_value,
    resolve_civilization_id,
)
from category_v3 import OFFICIAL_CATEGORIES, SPINDLE_CATEGORIES

SKILL_DIR = Path(__file__).resolve().parent
ALIAS_JSON = SKILL_DIR / "reference" / "帝王别名.json"


def _allocate_emperor_id(base_id: str, used: Set[str]) -> str:
    """拼音撞车时按 1、2… 后缀分配唯一帝王ID。"""
    bid = (base_id or "").strip()
    if not bid:
        return bid
    if bid not in used:
        return bid
    n = 1
    while f"{bid}{n}" in used:
        n += 1
    return f"{bid}{n}"
SUPPLEMENT_JSON = SKILL_DIR / "reference" / "帝王待补录.json"

EMPEROR_ROW_FIELDS = (
    "帝王ID",
    "帝王名称",
    "政权",
    "政权ID",
    "朝代",
    "朝代ID",
    "文明",
    "文明ID",
    "帝王原名",
    "庙号",
    "年号",
    "即位时间",
    "退位时间",
    "在位时长",
    "重要性评级",
    "标签",
)

# 帝王.json 行内四级坐标链（对应标注四级坐标）
EMPEROR_COORD_ROW_KEYS = ("文明", "朝代", "政权", "帝王名称")


def _emperor_coord_chain_complete(row: dict) -> bool:
    """文明 / 朝代 / 政权 / 帝王 均须非空且非 '-'。"""
    for f in EMPEROR_COORD_ROW_KEYS:
        v = (row.get(f) or "").strip()
        if not v or v == "-":
            return False
    return True


def ensure_emperor_coord_chain(
    row: dict,
    hints: Optional[dict] = None,
    *,
    dynasty_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
) -> bool:
    """补全帝王行四级坐标链；返回是否有改动。"""
    from coordinate_index import build_dynasty_index_from_json, build_regime_index

    hints = hints or {}
    ri = regime_index or build_regime_index()
    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    changed = False

    dynasty = (row.get("朝代") or hints.get("朝代") or "").strip()
    regime = (row.get("政权") or hints.get("政权") or "").strip()
    civ = (row.get("文明") or hints.get("文明") or "").strip()

    if not dynasty and regime:
        dynasty = (ri.get(regime) or {}).get("dynasty", "").strip()
    if not regime and dynasty:
        regime = dynasty
    if dynasty and regime and regime != dynasty:
        regime_dyn = (ri.get(regime) or {}).get("dynasty", "").strip()
        if regime_dyn and regime_dyn != dynasty:
            regime = dynasty
    if not civ and dynasty:
        civ = infer_civilization_for_dynasty(dynasty, di)
    if not civ:
        civ = "华夏"

    for key, val in (("朝代", dynasty), ("政权", regime), ("文明", civ)):
        cur = (row.get(key) or "").strip()
        if val and val != "-" and cur in ("", "-"):
            row[key] = val
            changed = True

    dinfo = di.get(dynasty) or {}
    rinfo = ri.get(regime) or {}
    civ_id = (row.get("文明ID") or dinfo.get("civilization_id") or resolve_civilization_id(civ)).strip()
    dynasty_id = (row.get("朝代ID") or dinfo.get("dynasty_id") or "").strip()
    regime_id = (row.get("政权ID") or rinfo.get("regime_id") or "").strip()
    if not regime_id and civ_id and dynasty_id and regime:
        regime_id = make_regime_id(civ_id, dynasty_id, dynasty, regime)

    for key, val in (
        ("文明ID", civ_id),
        ("朝代ID", dynasty_id),
        ("政权ID", regime_id),
    ):
        if val and row.get(key) != val:
            row[key] = val
            changed = True

    emperor = emperor_row_name(row)
    if emperor and civ_id and dynasty_id and regime_id:
        eid = make_emperor_id(civ_id, dynasty_id, regime_id, emperor)
        current = (row.get("帝王ID") or "").strip()
        if not current:
            row["帝王ID"] = eid
            changed = True
        # 已有帝王ID 不覆盖（周景王/周敬王等同音拼音会撞 ID，靠后缀 1/2 区分）
    return changed


def normalize_emperor_row_schema(row: dict) -> bool:
    """将 开始年/结束年 等遗留字段规范为帝王表标准列，并补齐缺省列。"""
    changed = False
    if row.get("帝王") and not row.get("帝王名称"):
        row["帝王名称"] = row.pop("帝王")
        changed = True
    if row.get("帝王 ID") and not row.get("帝王ID"):
        row["帝王ID"] = row.pop("帝王 ID")
        changed = True
    if row.get("帝王名字") and not row.get("帝王原名"):
        row["帝王原名"] = row.pop("帝王名字")
        changed = True
    row.pop("帝王", None)
    row.pop("帝王 ID", None)
    row.pop("帝王名字", None)

    emperor = emperor_row_name(row)
    dynasty = (row.get("朝代") or "").strip()
    regime = (row.get("政权") or "").strip()
    civ_id = (row.get("文明ID") or resolve_civilization_id(row.get("文明", ""))).strip()
    dynasty_id = (row.get("朝代ID") or "").strip()
    regime_id = (row.get("政权ID") or "").strip()

    if "开始年" in row and not (row.get("即位时间") or "").strip():
        row["即位时间"] = _fmt_emperor_year(row.pop("开始年"))
        changed = True
    if "结束年" in row and not (row.get("退位时间") or "").strip():
        row["退位时间"] = _fmt_emperor_year(row.pop("结束年"))
        changed = True

    start = parse_year_value(row.get("即位时间"))
    end = parse_year_value(row.get("退位时间"))
    if start is not None and end is not None and not (row.get("在位时长") or "").strip():
        try:
            row["在位时长"] = str(abs(int(end) - int(start)))
            changed = True
        except (TypeError, ValueError):
            pass

    defaults = {
        "帝王ID": make_emperor_id(civ_id, dynasty_id, regime_id, emperor) if emperor else "",
        "帝王原名": "",
        "庙号": "",
        "年号": "-",
        "即位时间": "-",
        "退位时间": "-",
        "在位时长": "-",
        "重要性评级": "3",
        "标签": "",
    }
    for key, val in defaults.items():
        if key not in row or row[key] is None:
            row[key] = val
            changed = True
    if "备注" in row:
        note = (row.pop("备注") or "").strip()
        if note and not (row.get("标签") or "").strip():
            row["标签"] = note
            changed = True
    for legacy in ("录入时间", "开始年", "结束年"):
        if legacy in row:
            row.pop(legacy, None)
            changed = True
    return changed


def repair_emperor_json_coord_chains(
    rows: List[dict],
    *,
    dynasty_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
) -> Tuple[int, List[str]]:
    """扫描帝王.json，修补缺四级坐标链的行。"""
    from coordinate_index import build_dynasty_index_from_json, build_regime_index

    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    ri = regime_index or build_regime_index()
    patched = 0
    logs: List[str] = []
    for row in rows:
        emperor = emperor_row_name(row)
        if not emperor:
            continue
        if _emperor_coord_chain_complete(row):
            continue
        if ensure_emperor_coord_chain(row, dynasty_index=di, regime_index=ri):
            patched += 1
            logs.append(
                f"修补「{emperor}」坐标链 → "
                f"{row.get('文明')}/{row.get('朝代')}/{row.get('政权')}"
            )
    return patched, logs


def _norm_key(key: str) -> str:
    return key.lstrip("\ufeff").strip()


def load_alias_config(path: Optional[Path] = None) -> dict:
    p = path or ALIAS_JSON
    if not p.exists():
        return {"global": {}, "strip_prefixes": [], "by_work": {}}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_full_emperor_rows(path: Optional[Path] = None) -> List[dict]:
    p = path or EMPEROR_JSON
    with open(p, encoding="utf-8-sig") as f:
        rows = json.load(f)
    return [{_norm_key(k): v for k, v in raw.items()} for raw in rows]


def work_id_from_volume(volume: str) -> str:
    """如 01史记_002_夏本纪第二 → 01史记"""
    m = re.match(r"^(\d{2}[^_]+)", volume or "")
    return m.group(1) if m else ""


def work_id_from_skeleton(data: dict, json_path: str = "") -> str:
    """从 skeleton 路径 / source_file / volume 解析著作 ID（如 01史记）。"""
    for src in (json_path, data.get("source_file", ""), data.get("volume", "")):
        wid = work_id_from_volume(str(src or ""))
        if wid:
            return wid
    return ""


def _coord_matches_hints(info: dict, dynasty_hint: str, regime_hint: str) -> bool:
    if regime_hint and (info.get("regime") or "").strip() == regime_hint:
        return True
    if dynasty_hint:
        d = (info.get("dynasty") or "").strip()
        if d == dynasty_hint:
            return True
        if dynasty_hint in ("西汉", "东汉") and d in ("西汉", "东汉", "楚汉"):
            return True
    return not dynasty_hint and not regime_hint


def pick_emperor_from_text(
    text: str,
    emperor_index: Dict[str, dict],
    *,
    work_id: str = "",
    dynasty_hint: str = "",
    regime_hint: str = "",
    alias_map: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[dict], str]:
    """
    从原文/简介中推断关联帝王（外戚卷等无君王卷用）。
    优先：著作消歧 alias > 朝代/政权过滤 > 出现频次 > 名称长度。
    """
    text = (text or "").strip()
    if not text:
        return None, ""

    cfg = load_alias_config()
    amap = alias_map if alias_map is not None else build_alias_to_canonical()
    by_work = (cfg.get("by_work") or {}).get(work_id) or {}

    seen: Set[str] = set()
    candidates: List[Tuple[str, dict, int, int]] = []

    def add_hit(label: str, count: int) -> None:
        info, method =     resolve_emperor_label(
            label,
            work_id=work_id,
            alias_map={**amap, **by_work},
            emperor_index=emperor_index,
        )
        if not info:
            return
        emp = info["emperor"]
        if emp in seen:
            return
        seen.add(emp)
        candidates.append((emp, info, count, len(label)))

    for emp_name in sorted(emperor_index, key=len, reverse=True):
        if len(emp_name) < 2 or emp_name not in text:
            continue
        if emp_name == "黄帝" and "老子" in text:
            continue
        add_hit(emp_name, text.count(emp_name))

    alias_sources = {**amap, **by_work}
    for alias in sorted(alias_sources, key=len, reverse=True):
        if len(alias) < 2 or alias not in text:
            continue
        # 短别名（如庙号「武帝」）易歧义，仅著作白名单或≥3字
        if len(alias) < 3 and alias not in by_work:
            continue
        add_hit(alias, text.count(alias))

    if dynasty_hint or regime_hint:
        filtered = [
            c for c in candidates if _coord_matches_hints(c[1], dynasty_hint, regime_hint)
        ]
        if filtered:
            candidates = filtered
        elif candidates:
            # 有命中但与朝代/政权不符 → 不用歧义结果，改走政权默认
            candidates = []

    if not candidates:
        return None, ""

    if len(candidates) == 1:
        return candidates[0][1], "text_single_hit"

    preferred = ("汉高祖", "汉文帝", "汉景帝", "汉武帝", "汉宣帝")
    for name in preferred:
        for emp, info, count, alen in candidates:
            if emp == name:
                return info, "text_preferred_han"
    candidates.sort(key=lambda x: (-x[2], -x[3]))
    return candidates[0][1], "text_best_hit"


def default_emperor_for_hints(
    emperor_index: Dict[str, dict],
    *,
    dynasty_hint: str = "",
    regime_hint: str = "",
) -> Optional[dict]:
    """序论/无纪年段落：按政权/朝代取默认主轴（如西汉 → 汉高祖）。"""
    if regime_hint == "汉" or dynasty_hint in ("西汉", "东汉", "楚汉"):
        for name in ("汉高祖", "汉文帝", "汉武帝"):
            if name in emperor_index:
                return emperor_index[name]
    pool = [
        info
        for info in emperor_index.values()
        if _coord_matches_hints(info, dynasty_hint, regime_hint)
    ]
    if not pool:
        return None
    pool.sort(key=lambda x: x.get("start_year") if x.get("start_year") is not None else 99999)
    return pool[0]


def build_alias_to_canonical(
    full_rows: Optional[List[dict]] = None,
    alias_config: Optional[dict] = None,
) -> Dict[str, str]:
    """所有可解析别名 → 标准帝王名。"""
    full_rows = full_rows if full_rows is not None else load_full_emperor_rows()
    cfg = alias_config if alias_config is not None else load_alias_config()
    mapping: Dict[str, str] = {}

    def add(alias: str, canonical: str) -> None:
        a, c = alias.strip(), canonical.strip()
        if a and c:
            mapping[a] = c

    for row in full_rows:
        emperor = emperor_row_name(row)
        if not emperor:
            continue
        add(emperor, emperor)
        for field in ("帝王原名", "庙号"):
            if field == "帝王原名":
                val = emperor_row_given_name(row)
            else:
                val = (row.get(field) or "").strip()
            if val and val not in ("-", "—"):
                add(val, emperor)

    for alias, canonical in (cfg.get("global") or {}).items():
        add(alias, canonical)

    prefixes = cfg.get("strip_prefixes") or []
    emperors = {emperor_row_name(row) for row in full_rows}
    for emp in list(emperors):
        if not emp:
            continue
        for pfx in prefixes:
            if emp.startswith(pfx) and len(emp) > len(pfx):
                stripped = emp[len(pfx):]
                if stripped in emperors:
                    add(emp, stripped)

    return mapping


def build_emperor_info_index(
    full_rows: Optional[List[dict]] = None,
) -> Dict[str, dict]:
    """标准帝王名 → 坐标/年份信息（与 load_emperor_records 一致）。"""
    full_rows = full_rows if full_rows is not None else load_full_emperor_rows()
    index: Dict[str, dict] = {}
    for row in full_rows:
        emperor = emperor_row_name(row)
        if not emperor or emperor in index:
            continue
        index[emperor] = {
            "id": emperor_row_id(row),
            "emperor": emperor,
            "regime": (row.get("政权") or "").strip(),
            "dynasty": (row.get("朝代") or "").strip(),
            "civilization": (row.get("文明") or "").strip(),
            "civilization_id": (row.get("文明ID") or "").strip(),
            "dynasty_id": (row.get("朝代ID") or "").strip(),
            "regime_id": (row.get("政权ID") or "").strip(),
            "start_year": parse_year_value(row.get("即位时间")),
            "end_year": parse_year_value(row.get("退位时间")),
        }
    return index


# 封号+刘姓+名 → (标准帝王名, 帝王名字)；如 楚元王刘交 → (楚元王, 刘交)
_RE_TITLE_LIU_GIVEN = re.compile(r"^(.+[王帝后])(刘[\u4e00-\u9fff]{1,2})$")


def split_regnal_given_name(label: str) -> Optional[Tuple[str, str]]:
    """
    将「封号+姓+名」拆为标准帝王名与帝王名字。
    帝王.json「帝王」字段只用封号（楚元王），名入「帝王名字」（刘交）。
    """
    name = (label or "").strip()
    m = _RE_TITLE_LIU_GIVEN.match(name)
    if not m:
        return None
    title, given = m.group(1).strip(), m.group(2).strip()
    if len(title) < 2 or len(given) < 2:
        return None
    return title, given


def resolve_emperor_label(
    label: str,
    *,
    work_id: str = "",
    dynasty_hint: str = "",
    regime_hint: str = "",
    alias_map: Optional[Dict[str, str]] = None,
    emperor_index: Optional[Dict[str, dict]] = None,
    alias_config: Optional[dict] = None,
) -> Tuple[Optional[dict], str]:
    """
    将标注用帝王名解析为帝王表记录。
    返回 (info, method)；method 为空表示未解析。
    """
    name = (label or "").strip()
    if not name:
        return None, ""

    cfg = alias_config if alias_config is not None else load_alias_config()
    amap = alias_map if alias_map is not None else build_alias_to_canonical(alias_config=cfg)
    eidx = emperor_index if emperor_index is not None else build_emperor_info_index()

    # 0. 著作内消歧
    by_work = (cfg.get("by_work") or {}).get(work_id) or {}
    if name in by_work:
        canonical = by_work[name]
        if canonical in eidx:
            return eidx[canonical], f"by_work:{work_id}"

    # 1. 直接命中帝王表
    if name in eidx:
        return eidx[name], "exact"

    # 2. 别名表
    if name in amap:
        canonical = amap[name]
        if canonical in eidx:
            return eidx[canonical], "alias"

    # 3. 去前缀后再查
    for pfx in cfg.get("strip_prefixes") or []:
        if name.startswith(pfx) and len(name) > len(pfx):
            stripped = name[len(pfx):]
            if stripped in eidx:
                return eidx[stripped], f"strip_prefix:{pfx}"
            if stripped in amap and amap[stripped] in eidx:
                return eidx[amap[stripped]], f"strip_prefix_alias:{pfx}"

    # 4. 帝王名字精确匹配（不用子串，避免皋陶→皋）
    full_rows = load_full_emperor_rows()
    name_hits = []
    for row in full_rows:
        given = emperor_row_given_name(row)
        emperor = emperor_row_name(row)
        if given and given == name and emperor in eidx:
            name_hits.append(eidx[emperor])
    if len(name_hits) == 1:
        return name_hits[0], "given_name"

    # 5. 封号+刘姓+名 → 查封号标准名（楚元王刘交 → 楚元王）
    split = split_regnal_given_name(name)
    if split:
        title, given = split
        if title in eidx:
            return eidx[title], f"title_strip_given:{given}"
        if title in amap and amap[title] in eidx:
            return eidx[amap[title]], f"title_strip_given:{given}"

    # 6. 简称唯一后缀：阖闾 → 吴王阖闾（≥2 字且仅一条帝王名以此结尾）
    if len(name) >= 2:
        suffix_hits = [
            eidx[emp] for emp in eidx if emp.endswith(name) and emp != name
        ]
        if len(suffix_hits) == 1:
            return suffix_hits[0], "suffix_unique"

    return None, ""


def _rename_owner(
    owners: list,
    old_name: str,
    new_name: str,
    category: str,
) -> bool:
    changed = False
    for o in owners:
        if o.get("category") == category and o.get("name", "").strip() == old_name:
            o["name"] = new_name
            changed = True
    return changed


def align_skeleton_emperors(
    data: dict,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    alias_map: Optional[Dict[str, str]] = None,
    only_junji: bool = False,
) -> Tuple[dict, List[str]]:
    """
    就地解析并对齐帝王名。
    君王：史略名称 → 帝王表标准名，并刷新四级坐标。
    """
    changes: List[str] = []
    work_id = work_id_from_volume(data.get("volume", ""))
    amap = alias_map if alias_map is not None else build_alias_to_canonical()
    eidx = emperor_index if emperor_index is not None else build_emperor_info_index()
    rename_map: Dict[Tuple[str, str], str] = {}

    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        cat = normalize_entry_category(entry.get("史略分类", ""))
        old_name = (entry.get("史略名称") or "").strip()
        coord = (entry.get("四级帝王坐标") or "").strip()

        # 非君王：仅标准化四级坐标上的别名（夏禹→禹），不改主轴君主
        if cat != "君王" and coord:
            cinfo, cmethod = resolve_emperor_label(
                coord, work_id=work_id, alias_map=amap, emperor_index=eidx
            )
            if cinfo and cinfo["emperor"] != coord:
                for k, v in coords_from_emperor(cinfo).items():
                    entry[k] = v
                changes.append(
                    f"[{entry.get('史略ID')}] 四级帝王坐标 {coord} → {cinfo['emperor']} ({cmethod})"
                )

        if only_junji and cat != "君王":
            continue

        if cat != "君王":
            continue

        if not old_name:
            continue

        info, method = resolve_emperor_label(
            old_name,
            work_id=work_id,
            alias_map=amap,
            emperor_index=eidx,
            dynasty_hint=(entry.get("二级朝代坐标") or "").strip(),
            regime_hint=(entry.get("三级政权坐标") or "").strip(),
        )

        if not info:
            continue

        new_name = info["emperor"]
        if new_name != old_name:
            entry["史略名称"] = new_name
            rename_map[(old_name, "君王")] = new_name
            changes.append(
                f"君王 [{entry.get('史略ID')}] {old_name} → {new_name} ({method})"
            )

        for k, v in coords_from_emperor(info).items():
            entry[k] = v

    for row in data.get("segment_attribution", []):
        for owner in row.get("owners", []):
            ocat = owner.get("category", "")
            oname = owner.get("name", "").strip()
            key = (oname, ocat)
            if key in rename_map:
                owner["name"] = rename_map[key]
                changes.append(
                    f"段{row.get('paragraph')} 归属 {oname} → {rename_map[key]}"
                )
                continue
            if ocat == "君王":
                info, method = resolve_emperor_label(
                    oname, work_id=work_id, alias_map=amap, emperor_index=eidx
                )
                if info and info["emperor"] != oname:
                    owner["name"] = info["emperor"]
                    changes.append(
                        f"段{row.get('paragraph')} 君王归属 {oname} → {info['emperor']} ({method})"
                    )

    # 去重日志
    seen: Set[str] = set()
    deduped: List[str] = []
    for c in changes:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return data, deduped


def volume_has_junji(data: dict) -> bool:
    """本卷是否存在君王条目。"""
    return bool(volume_junji_emperors(data))


def co_segment_peers(entry: dict, data: dict) -> List[dict]:
    """与本 entry 共段的其它 owners（名称+分类）。"""
    name = (entry.get("史略名称") or "").strip()
    peers: List[dict] = []
    seen: Set[Tuple[str, str]] = set()
    for row in data.get("segment_attribution", []):
        owners = row.get("owners") or []
        names = {o.get("name") for o in owners}
        if name not in names:
            continue
        for o in owners:
            oname = (o.get("name") or "").strip()
            ocat = normalize_entry_category(o.get("category", ""))
            if not oname or oname == name:
                continue
            key = (oname, ocat)
            if key in seen:
                continue
            seen.add(key)
            peers.append({"name": oname, "category": ocat})
    return peers


def volume_junji_emperors(data: dict) -> Set[str]:
    """本卷君王/诸侯四级帝王坐标集合（主轴君主）。"""
    out: Set[str] = set()
    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        if normalize_entry_category(entry.get("史略分类", "")) not in ("君王", "诸侯"):
            continue
        emp = (entry.get("四级帝王坐标") or entry.get("史略名称") or "").strip()
        if emp:
            out.add(emp)
    return out


def is_cross_volume_emperor_coord(
    emp: str,
    junji_emperors: Set[str],
    emperor_index: Optional[Dict[str, dict]] = None,
) -> bool:
    """
    四级帝王不在本卷君王列表，但可于帝王.json 解析 → 跨卷参照坐标，自动放行。
    例：宋微子世家中比干/箕子事略挂殷纣，不应强行改成本卷宋君王主轴。
    """
    emp = (emp or "").strip()
    if not emp or emp in junji_emperors:
        return False
    eidx = emperor_index if emperor_index is not None else build_emperor_info_index()
    return emp in eidx


def collect_unresolved_junji(
    data: dict,
    emperor_index: Optional[Dict[str, dict]] = None,
) -> List[str]:
    eidx = emperor_index if emperor_index is not None else build_emperor_info_index()
    issues: List[str] = []
    for entry in data.get("entries", []):
        if normalize_entry_category(entry.get("史略分类", "")) not in ("君王", "诸侯"):
            continue
        name = (entry.get("史略名称") or "").strip()
        if name not in eidx:
            issues.append(
                f"[{entry.get('史略ID')}] 君王「{name}」无法解析到帝王.json"
            )
    return issues


def _row_has_complete_fields(row: dict) -> bool:
    for f in EMPEROR_ROW_FIELDS:
        if f not in row or row.get(f) is None:
            return False
    if not emperor_row_name(row):
        return False
    return _emperor_coord_chain_complete(row)


def merge_supplements_into_emperor_json(
    *,
    emperor_path: Optional[Path] = None,
    supplement_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, List[str]]:
    """将帝王待补录.json 中缺失项写入帝王.json。"""
    ep = emperor_path or EMPEROR_JSON
    sp = supplement_path or SUPPLEMENT_JSON
    if not sp.exists():
        return 0, ["帝王待补录.json 不存在"]

    rows = load_full_emperor_rows(ep)
    existing = {emperor_row_name(r) for r in rows}
    supplements = load_full_emperor_rows(sp)
    from coordinate_index import build_dynasty_index_from_json

    di = build_dynasty_index_from_json()

    added = 0
    logs: List[str] = []
    for raw in supplements:
        row = dict(raw)
        normalize_emperor_row_schema(row)
        ensure_emperor_coord_chain(row, dynasty_index=di)
        emperor = emperor_row_name(row)
        if not emperor:
            continue
        if not _row_has_complete_fields(row):
            logs.append(f"跳过「{emperor}」：字段不完整")
            continue
        if emperor in existing:
            logs.append(f"已存在「{emperor}」，跳过")
            continue
        rows.append(row)
        existing.add(emperor)
        added += 1
        logs.append(f"补录「{emperor}」")

    if added and not dry_run:
        with open(ep, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return added, logs


def _fmt_emperor_year(value) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def infer_civilization_for_dynasty(
    dynasty: str,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> str:
    from coordinate_index import build_dynasty_index_from_json

    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    info = di.get((dynasty or "").strip(), {})
    return (info.get("civilization") or "").strip() or "华夏"


def _entry_coord_hints(entry: dict) -> dict:
    auto = entry.get("_auto_filled") or {}
    return {
        "政权": (entry.get("三级政权坐标") or auto.get("三级政权坐标") or "").strip(),
        "朝代": (entry.get("二级朝代坐标") or auto.get("二级朝代坐标") or "").strip(),
        "文明": (entry.get("一级文明坐标") or auto.get("一级文明坐标") or "").strip(),
        "史略开始年": entry.get("史略开始年", auto.get("帝王开始年")),
        "史略结束年": entry.get("史略结束年", auto.get("帝王结束年")),
    }


def draft_emperor_row_from_entry(
    entry: dict,
    emperor_name: str,
    *,
    given_name_hint: str = "",
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> dict:
    """从 skeleton 条目草稿帝王表行（标注缺表时自动补录用）。"""
    hints = _entry_coord_hints(entry)
    dynasty = hints["朝代"]
    regime = hints["政权"]
    civ = hints["文明"]
    # 跨卷误填：条目的政权来自本卷主轴、朝代来自事件时代时不一致 → 政权回落为朝代
    if dynasty and regime and regime != dynasty:
        ri = build_regime_index()
        regime_dynasty = (ri.get(regime) or {}).get("dynasty", "").strip()
        if regime_dynasty and dynasty != regime_dynasty:
            regime = dynasty
    if not civ and dynasty:
        civ = infer_civilization_for_dynasty(dynasty, dynasty_index)
    if not civ:
        civ = "华夏"

    start = hints["史略开始年"]
    end = hints["史略结束年"]
    duration = "-"
    if start is not None and end is not None:
        try:
            duration = str(abs(int(end) - int(start)))
        except (TypeError, ValueError):
            duration = "-"

    cat = normalize_entry_category(entry.get("史略分类", ""))
    given = (given_name_hint or "").strip()
    if not given:
        raw = (entry.get("史略名称") or "").strip()
        split = split_regnal_given_name(raw)
        if split and split[0] == emperor_name:
            given = split[1]
    if not given and cat == "君王":
        text = (entry.get("原文字句") or "").strip()
        m = re.search(
            rf"{re.escape(emperor_name)}(刘[\u4e00-\u9fff]{{1,2}})",
            text,
        )
        if m:
            given = m.group(1)

    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    ri = build_regime_index()
    dinfo = di.get(dynasty) or {}
    rinfo = ri.get(regime) or {}
    civ_id = (dinfo.get("civilization_id") or resolve_civilization_id(civ)).strip()
    dynasty_id = (dinfo.get("dynasty_id") or "").strip()
    regime_id = (rinfo.get("regime_id") or "").strip()
    if not regime_id and civ_id and dynasty_id and regime:
        regime_id = make_regime_id(civ_id, dynasty_id, dynasty, regime)

    return {
        "帝王ID": make_emperor_id(civ_id, dynasty_id, regime_id, emperor_name),
        "帝王名称": emperor_name,
        "政权": regime or "-",
        "政权ID": regime_id,
        "朝代": dynasty or "-",
        "朝代ID": dynasty_id,
        "文明": civ,
        "文明ID": civ_id,
        "帝王原名": given,
        "庙号": "",
        "年号": "-",
        "即位时间": _fmt_emperor_year(start),
        "退位时间": _fmt_emperor_year(end),
        "在位时长": duration,
        "重要性评级": "3",
        "标签": "auto_from_skeleton",
    }


def patch_emperor_row_incomplete(
    row: dict,
    hints: Optional[dict] = None,
    *,
    dynasty_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
) -> bool:
    """修补帝王表已有行：四级坐标链须完整（文明/朝代/政权/帝王）。"""
    return ensure_emperor_coord_chain(
        row,
        hints,
        dynasty_index=dynasty_index,
        regime_index=regime_index,
    )


def collect_emperor_labels_from_skeleton(data: dict) -> Dict[str, dict]:
    """
    本卷引用的帝王名 → 最佳来源条目。
    来源：君王史略名称、各条目四级帝王坐标（含无君王卷 LLM 填写）、_主轴参考。
    """
    import re

    from coordinate_index import COORD_FIELDS

    labels: Dict[str, dict] = {}
    spindle_ref = re.compile(r"主轴帝王「([^」]+)」")

    def _coord_score(entry: dict) -> int:
        return sum(1 for f in COORD_FIELDS if (entry.get(f) or "").strip())

    def _consider(name: str, entry: dict) -> None:
        name = (name or "").strip()
        if not name or len(name) < 2:
            return
        if name not in labels or _coord_score(entry) > _coord_score(labels[name]):
            labels[name] = entry

    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        cat = normalize_entry_category(entry.get("史略分类", ""))
        if cat == "君王":
            _consider((entry.get("史略名称") or "").strip(), entry)
        coord = (entry.get("四级帝王坐标") or "").strip()
        if coord:
            _consider(coord, entry)
        auto = entry.get("_auto_filled") or {}
        ref = (auto.get("_主轴参考") or "").strip()
        m = spindle_ref.search(ref)
        if m:
            _consider(m.group(1), entry)

    junji_stub = {"史略分类": "君王"}
    seg_attr = data.get("segment_attribution") or []
    if isinstance(seg_attr, dict):
        # 非标准 skeleton（段落→人名字符串）跳过，避免 AttributeError
        pass
    else:
        for row in seg_attr:
            if not isinstance(row, dict):
                continue
            for owner in row.get("owners", []):
                if not isinstance(owner, dict):
                    continue
                if owner.get("category") != "君王":
                    continue
                n = (owner.get("name") or "").strip()
                if n:
                    _consider(n, junji_stub)

    return labels


def _majority_junji_coord_hints(data: dict) -> dict:
    """本卷君王条目中最常见的政权/朝代（Step2 补帝王表缺坐标时用）。"""
    from collections import Counter

    regimes: Counter = Counter()
    dynasties: Counter = Counter()
    civs: Counter = Counter()
    for entry in data.get("entries", []):
        if normalize_entry_category(entry.get("史略分类", "")) not in ("君王", "诸侯"):
            continue
        r = (entry.get("三级政权坐标") or "").strip()
        d = (entry.get("二级朝代坐标") or "").strip()
        c = (entry.get("一级文明坐标") or "").strip()
        if r:
            regimes[r] += 1
        if d:
            dynasties[d] += 1
        if c:
            civs[c] += 1
    return {
        "政权": regimes.most_common(1)[0][0] if regimes else "",
        "朝代": dynasties.most_common(1)[0][0] if dynasties else "",
        "文明": civs.most_common(1)[0][0] if civs else "华夏",
    }


def _entry_for_emperor_draft(entry: dict, data: dict) -> dict:
    """为补帝王表草稿补全缺坐标（沿用本卷多数君王坐标）。"""
    out = dict(entry)
    hints = _entry_coord_hints(out)
    vol = _majority_junji_coord_hints(data)
    field_map = (
        ("三级政权坐标", "政权"),
        ("二级朝代坐标", "朝代"),
        ("一级文明坐标", "文明"),
    )
    for field, key in field_map:
        if not (out.get(field) or "").strip() and vol.get(key):
            out[field] = vol[key]
    return out


def _entry_paragraph_ids(entry: dict) -> List[int]:
    ids: List[int] = []
    for p in entry.get("paragraphs") or []:
        fr = int(p.get("paragraph_from") or 0)
        to = int(p.get("paragraph_to") or fr)
        if fr > 0:
            ids.extend(range(fr, to + 1))
    return ids


def junji_from_entry_segments(
    entry: dict,
    data: dict,
    junji: Set[str],
) -> Optional[str]:
    """从段落归属找与本 entry 共段的君王主轴。"""
    name = (entry.get("史略名称") or "").strip()
    counts: Dict[str, int] = {}
    for row in data.get("segment_attribution", []):
        owners = row.get("owners") or []
        names = {o.get("name") for o in owners}
        if name not in names:
            continue
        for o in owners:
            if o.get("category") == "君王" and o.get("name") in junji:
                n = o["name"]
                counts[n] = counts.get(n, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def _nearest_junji_for_entry(
    entry: dict,
    data: dict,
    junji: Set[str],
) -> Optional[str]:
    """共段无君王时，向前后邻段找最近君王。"""
    pids = _entry_paragraph_ids(entry)
    if not pids:
        return None
    segs = {int(s["paragraph"]): s for s in data.get("segment_attribution", [])}
    lo, hi = min(pids), max(pids)
    total = int(data.get("total_paragraphs") or hi)
    for pid in range(lo, 0, -1):
        row = segs.get(pid) or {}
        for o in row.get("owners") or []:
            if o.get("category") == "君王" and o.get("name") in junji:
                return o["name"]
    for pid in range(hi, total + 1):
        row = segs.get(pid) or {}
        for o in row.get("owners") or []:
            if o.get("category") == "君王" and o.get("name") in junji:
                return o["name"]
    return None


def _pick_volume_primary_junji(junji: Set[str]) -> Optional[str]:
    if not junji:
        return None
    return sorted(junji)[0]


def _sanitized_coord_hints(entry: dict, work_id: str = "") -> Tuple[str, str]:
    """忽略 LLM 误填的非语境朝代（如外戚卷标三国）。"""
    dynasty = (entry.get("二级朝代坐标") or "").strip()
    regime = (entry.get("三级政权坐标") or "").strip()
    combined = f"{entry.get('史略简介', '')} {entry.get('原文字句', '')}"
    han_markers = ("汉", "吕后", "太后", "皇后", "太子", "外戚", "高祖", "文帝", "景帝", "武帝")
    if work_id == "01史记" and dynasty in (
        "三国", "南北朝", "北魏", "东晋", "五帝",
    ):
        if regime in ("汉", "西汉", "东汉") or any(m in combined for m in han_markers):
            return "西汉", regime if regime in ("汉", "西汉", "东汉") else "汉"
    return dynasty, regime


def _emperor_context_mismatch(
    entry: dict,
    current: dict,
    emperor_index: Dict[str, dict],
    *,
    work_id: str = "",
    alias_map: Optional[Dict[str, str]] = None,
) -> bool:
    """已解析坐标与原文/著作语境明显不符 → 需重推。"""
    intro = entry.get("史略简介", "") or ""
    text = entry.get("原文字句", "") or ""
    combined = f"{intro} {text}"
    dynasty_hint, regime_hint = _sanitized_coord_hints(entry, work_id)
    inferred, _ = pick_emperor_from_text(
        combined,
        emperor_index,
        work_id=work_id,
        dynasty_hint=dynasty_hint,
        regime_hint=regime_hint,
        alias_map=alias_map,
    )
    if not inferred:
        return False
    if inferred["emperor"] == current.get("emperor"):
        return False
    cur_dyn = (current.get("dynasty") or "").strip()
    new_dyn = (inferred.get("dynasty") or "").strip()
    if cur_dyn in ("三国", "南北朝", "北魏", "东晋", "西晋") and new_dyn in (
        "西汉", "东汉", "楚汉",
    ):
        return True
    if work_id == "01史记" and cur_dyn not in (
        "西汉", "东汉", "楚汉", "西周", "东周", "春秋", "战国", "秦", "商", "夏",
    ):
        if new_dyn in ("西汉", "东汉", "楚汉"):
            return True
    return False


def shichen_from_entry_segments(entry: dict, data: dict) -> Optional[str]:
    """从段落归属找与本 entry 共段的士臣（外戚卷等无君王时用）。"""
    name = (entry.get("史略名称") or "").strip()
    counts: Dict[str, int] = {}
    for row in data.get("segment_attribution", []):
        owners = row.get("owners") or []
        names = {o.get("name") for o in owners}
        if name not in names:
            continue
        for o in owners:
            if o.get("category") in OFFICIAL_CATEGORIES and o.get("name") != name:
                n = o["name"]
                counts[n] = counts.get(n, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def _entry_lookup(data: dict) -> Dict[Tuple[str, str], dict]:
    out: Dict[Tuple[str, str], dict] = {}
    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        key = (
            (entry.get("史略名称") or "").strip(),
            normalize_entry_category(entry.get("史略分类", "")),
        )
        if key[0]:
            out[key] = entry
    return out


def _is_valid_emperor_coord(
    coord: str,
    name: str,
    *,
    work_id: str = "",
    emperor_index: Dict[str, dict],
    alias_map: Dict[str, str],
) -> bool:
    if not coord or coord == name:
        return False
    info, _ = resolve_emperor_label(
        coord,
        work_id=work_id,
        alias_map=alias_map,
        emperor_index=emperor_index,
    )
    return info is not None


def infer_spindle_emperor(
    entry: dict,
    data: dict,
    emperor_index: Dict[str, dict],
    *,
    work_id: str = "",
    alias_map: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[dict], str]:
    """
    为非君王条目推断四级帝王主轴。
    君王共段 → 原文帝王名 → 共段士臣上下文 → 政权/朝代默认。
    """
    amap = alias_map if alias_map is not None else build_alias_to_canonical()
    junji = volume_junji_emperors(data)
    dynasty_hint, regime_hint = _sanitized_coord_hints(entry, work_id)
    intro = entry.get("史略简介", "") or ""
    text = entry.get("原文字句", "") or ""
    combined = f"{intro} {text}"

    if junji:
        primary = (
            junji_from_entry_segments(entry, data, junji)
            or _nearest_junji_for_entry(entry, data, junji)
            or _pick_volume_primary_junji(junji)
        )
        if primary and primary in emperor_index:
            return emperor_index[primary], "junji_segment"

    shichen = shichen_from_entry_segments(entry, data)
    if shichen:
        lookup = _entry_lookup(data)
        for oc in OFFICIAL_CATEGORIES:
            peer = lookup.get((shichen, oc))
            if peer:
                break
        else:
            peer = lookup.get((shichen, "士臣"))  # 读盘兼容
        if peer and peer is not entry:
            peer_text = f"{peer.get('史略简介', '')} {peer.get('原文字句', '')}"
            info, method = pick_emperor_from_text(
                peer_text,
                emperor_index,
                work_id=work_id,
                dynasty_hint=dynasty_hint or (peer.get("二级朝代坐标") or "").strip(),
                regime_hint=regime_hint or (peer.get("三级政权坐标") or "").strip(),
                alias_map=amap,
            )
            if info:
                return info, f"shichen_context:{shichen}:{method}"

    info, method = pick_emperor_from_text(
        combined,
        emperor_index,
        work_id=work_id,
        dynasty_hint=dynasty_hint,
        regime_hint=regime_hint,
        alias_map=amap,
    )
    if info:
        return info, method

    fallback = default_emperor_for_hints(
        emperor_index,
        dynasty_hint=dynasty_hint,
        regime_hint=regime_hint,
    )
    if fallback:
        return fallback, "regime_default"
    return None, ""


def align_event_emperor_coords(data: dict, *, json_path: str = "") -> List[str]:
    """
    四类人物：四级帝王坐标须为真实帝王。
    坐标=史略名 / 不在帝王表 → 共段君王或原文/共段士臣/政权默认反推。
    """
    changes: List[str] = []
    work_id = work_id_from_skeleton(data, json_path)
    amap = build_alias_to_canonical()
    eidx = build_emperor_info_index()
    spindle_cats = SPINDLE_CATEGORIES

    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        cat = normalize_entry_category(entry.get("史略分类", ""))
        if cat not in spindle_cats:
            continue
        name = (entry.get("史略名称") or "").strip()
        coord = (entry.get("四级帝王坐标") or "").strip()

        current_info = None
        if _is_valid_emperor_coord(
            coord, name, work_id=work_id, emperor_index=eidx, alias_map=amap
        ):
            current_info, method = resolve_emperor_label(
                coord, work_id=work_id, alias_map={**amap, **(load_alias_config().get("by_work") or {}).get(work_id, {})}, emperor_index=eidx
            )

        needs_realign = (
            not current_info
            or coord == name
            or _emperor_context_mismatch(
                entry, current_info, eidx, work_id=work_id, alias_map=amap
            )
        )

        if not needs_realign and current_info:
            alt, _ = infer_spindle_emperor(
                entry, data, eidx, work_id=work_id, alias_map=amap
            )
            if alt and alt["emperor"] != current_info["emperor"]:
                needs_realign = True

        if not needs_realign and current_info:
            expected = coords_from_emperor(current_info)
            coord_mismatch = any(
                (entry.get(f) or "").strip() != expected[f] for f in COORD_FIELDS
            )
            if current_info["emperor"] != coord or coord_mismatch:
                for k, v in expected.items():
                    entry[k] = v
                if current_info["emperor"] != coord:
                    changes.append(
                        f"[{entry.get('史略ID')}] 坐标别名 {coord} → {current_info['emperor']}"
                    )
                elif coord_mismatch:
                    changes.append(
                        f"[{entry.get('史略ID')}] 坐标链对齐帝王表"
                        f"（{expected['三级政权坐标']}）"
                    )
            continue

        info, method = infer_spindle_emperor(
            entry, data, eidx, work_id=work_id, alias_map=amap
        )
        if not info:
            continue
        primary = info["emperor"]
        for k, v in coords_from_emperor(info).items():
            entry[k] = v
        if coord != primary:
            changes.append(
                f"[{entry.get('史略ID')}] {cat}「{name}」"
                f"四级帝王 {coord or '—'} → {primary} ({method})"
            )

    return changes


def auto_supplement_emperors_from_skeleton(
    data: dict,
    *,
    emperor_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, int, List[str]]:
    """
    标注中出现的帝王若不在帝王.json → 从 skeleton 草稿补录；
    已存在但缺字段（如文明）→ 按朝代/skeleton 修补。
    会先合并帝王待补录.json。
    """
    from coordinate_index import build_dynasty_index_from_json

    merge_supplements_into_emperor_json(emperor_path=emperor_path, dry_run=dry_run)

    ep = emperor_path or EMPEROR_JSON
    rows = load_full_emperor_rows(ep)
    by_name: Dict[str, dict] = {}
    for row in rows:
        name = emperor_row_name(row)
        if name and name not in by_name:
            by_name[name] = row

    di = build_dynasty_index_from_json()
    eidx = build_emperor_info_index(rows)
    amap = build_alias_to_canonical()
    labels = collect_emperor_labels_from_skeleton(data)
    added = 0
    patched = 0
    logs: List[str] = []

    for emperor_name, entry in sorted(labels.items()):
        original_label = emperor_name
        given_hint = ""
        resolved, rmethod = resolve_emperor_label(
            emperor_name,
            alias_map=amap,
            emperor_index=eidx,
        )
        if resolved:
            canonical = resolved["emperor"]
            if canonical != emperor_name:
                logs.append(
                    f"「{emperor_name}」→「{canonical}」（{rmethod}），帝王表已有，跳过补录"
                )
                continue
            emperor_name = canonical
        else:
            split = split_regnal_given_name(emperor_name)
            if split:
                emperor_name, given_hint = split
                logs.append(f"「{original_label}」→ 标准名「{emperor_name}」（名入帝王原名）")

        draft = draft_emperor_row_from_entry(
            _entry_for_emperor_draft(entry, data),
            emperor_name,
            given_name_hint=given_hint,
            dynasty_index=di,
        )
        if emperor_name not in by_name:
            ensure_emperor_coord_chain(draft, dynasty_index=di)
            if not _row_has_complete_fields(draft):
                logs.append(
                    f"跳过「{emperor_name}」：四级坐标链不完整"
                    f"（{draft.get('文明')}/{draft.get('朝代')}/{draft.get('政权')}）"
                )
                continue
            used_ids = {emperor_row_id(r) for r in rows if emperor_row_id(r)}
            draft["帝王ID"] = _allocate_emperor_id(draft.get("帝王ID", ""), used_ids)
            rows.append(draft)
            by_name[emperor_name] = draft
            added += 1
            logs.append(f"自动补录「{emperor_name}」")
            continue

        row = by_name[emperor_name]
        if patch_emperor_row_incomplete(row, draft, dynasty_index=di):
            patched += 1
            logs.append(f"修补「{emperor_name}」四级坐标链")

    chain_n, chain_logs = repair_emperor_json_coord_chains(rows, dynasty_index=di)
    if chain_n:
        patched += chain_n
        logs.extend(chain_logs[:12])
        if len(chain_logs) > 12:
            logs.append(f"… 另有 {len(chain_logs) - 12} 条坐标链修补")

    schema_n = 0
    for row in rows:
        emperor = emperor_row_name(row)
        if not emperor:
            continue
        needs = (
            "开始年" in row
            or "结束年" in row
            or "录入时间" in row
            or "备注" in row
            or not emperor_row_id(row)
            or not (row.get("即位时间") or "").strip()
        )
        if needs and normalize_emperor_row_schema(row):
            schema_n += 1
            logs.append(f"规范「{emperor}」行结构")
    if schema_n:
        patched += schema_n

    if added or patched:
        from repair_emperor_dedup import apply_p0_suffixes

        p0_logs = apply_p0_suffixes(rows)
        if p0_logs:
            logs.extend(p0_logs[:12])
            if len(p0_logs) > 12:
                logs.append(f"… 另有 {len(p0_logs) - 12} 条 ID 去重")

    if (added or patched) and not dry_run:
        with open(ep, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return added, patched, logs


def merge_regime_supplements() -> Tuple[int, List[str]]:
    """补录西楚政权（项羽坐标链需要）。"""
    regime_path = SKILL_DIR / "reference" / "政权.json"
    with open(regime_path, encoding="utf-8-sig") as f:
        rows = json.load(f)
    names = {(r.get("政权") or r.get("\ufeff政权") or "").strip() for r in rows}
    if "西楚" in names:
        return 0, ["西楚政权已存在"]

    rows.append({
        "政权": "西楚",
        "政权ID": "ZQ_HX_QINMOHANCHU_XICHU",
        "朝代": "楚汉",
        "朝代ID": "CD_HX_QINMOHANCHU",
        "dynasty_zy": "楚汉",
        "文明": "华夏",
        "文明ID": "HX",
        "开始时间": "-206",
        "结束时间": "-202",
    })
    with open(regime_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return 1, ["补录政权「西楚」"]


def merge_dynasty_supplements() -> Tuple[int, List[str]]:
    dynasty_path = SKILL_DIR / "reference" / "朝代.json"
    with open(dynasty_path, encoding="utf-8-sig") as f:
        rows = json.load(f)
    names = {(r.get("朝代") or r.get("\ufeff朝代") or "").strip() for r in rows}
    if "楚汉" in names:
        return 0, ["楚汉朝代已存在"]

    rows.append({
        "朝代": "楚汉",
        "文明": "华夏",
        "开始时间": "-206",
        "结束时间": "-202",
    })
    with open(dynasty_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return 1, ["补录朝代「楚汉」"]
