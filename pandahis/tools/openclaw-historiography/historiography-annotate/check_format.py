#!/usr/bin/env python3
"""
Step 2: 格式与覆盖自检（硬门）
输入: 骨架 JSON（Step 1 产出）
输出: exit 0=通过, 1=需修正

用法:
  python3 check_format.py <skeleton.json> [--src-dir DIR] [--phase skeleton|final]
  python3 check_format.py <skeleton.json> --no-quote-check
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from coordinate_index import COORD_FIELDS, COORD_ID_FIELDS, EMPEROR_JSON, LEGACY_COORD_MAP, migrate_entry_fields, normalize_entry_category, validate_entry_coordinates, validate_emperor_records
from detail_coords import DETAIL_FIELDS
from category_v3 import OFFICIAL_CATEGORIES, SPINDLE_CATEGORIES
from lib_config import (
    LEGACY_CATS,
    PERSON_CATS,
    SKILL_DIR,
    VALID_CATS,
    VALID_EXCLUDE_REASONS,
    VALID_PRIORITIES,
    build_dynasty_index,
    build_emperor_index,
    detect_sandwich_excludes,
    load_regime_index,
    owner_key,
    paths,
    validate_entry_years,
    validate_cosegment_years,
    validate_year_quality,
    validate_person_spindle_rationale_batch,
)
from junji_naming import collect_junji_violations
from identity_gate import validate_skeleton_identity
from emperor_resolve import build_emperor_info_index, is_cross_volume_emperor_coord, volume_junji_emperors
from knowledge_provenance import validate_knowledge_provenance
from protagonist_metadata import expected_protagonist_count

PERSON_ENTRY_CATS = PERSON_CATS
from paragraph_utils import (
    check_paragraph_count,
    classify_paragraph_header,
    count_source_paragraphs,
    resolve_source_file,
    split_paragraphs,
    split_mode_for_work,
    work_from_skeleton_path,
)

PIPELINE_DIR = Path(__file__).resolve().parent.parent / "historiography-pipeline"


def _enforce_lease(json_path: str) -> None:
    sys.path.insert(0, str(PIPELINE_DIR))
    from hist_gates import GateError, enforce_script, gate_fail  # noqa: WPS433

    try:
        enforce_script(json_path)
    except GateError as e:
        gate_fail(str(e))

errors: List[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print(f"  ❌ {msg}")


def warn(msg: str) -> None:
    print(f"  ⚠️ {msg}")


def _normalize_hanshu_volume_title(title: str) -> str:
    """
    汉书卷名比较用归一化：去掉卷次序数「第XX」，保留上下分册。
    扬雄传第五十七上 / 扬雄传上 → 扬雄传上
    陈胜项籍传第一 / 陈胜项籍传 → 陈胜项籍传
    """
    if not title:
        return ""
    return re.sub(
        r"第[一二三四五六七八九十百零廿卅]+(?=[上下]$|$)",
        "",
        title.strip(),
    )


def _volume_title_from_source(source_file: str) -> str:
    """02汉书_041_陈胜项籍传第一.txt → 陈胜项籍传第一（完整卷名段）"""
    m = re.match(r"^02汉书_\d{3}_(.+)\.txt$", source_file or "")
    return m.group(1) if m else ""


def _volume_title_from_skeleton_stem(stem: str) -> str:
    """02汉书_041_陈胜项籍传_skeleton → 陈胜项籍传"""
    base = stem.replace("_skeleton", "")
    m = re.match(r"^02汉书_\d{3}_(.+)$", base)
    return m.group(1) if m else ""


def check_volume_naming(data: dict, skeleton_path: Path) -> None:
    """skeleton 文件名、volume 字段、source_file 卷名三者须一致。"""
    work = work_from_skeleton_path(skeleton_path)
    if work != "02汉书":
        return
    volume = (data.get("volume") or "").strip()
    source_file = data.get("source_file") or ""
    src_title = _volume_title_from_source(source_file)
    sk_title = _volume_title_from_skeleton_stem(skeleton_path.stem)
    if not src_title:
        return
    print("\n  📛 卷名一致性")
    ok = True
    src_norm = _normalize_hanshu_volume_title(src_title)
    sk_norm = _normalize_hanshu_volume_title(sk_title)
    vol_norm = _normalize_hanshu_volume_title(volume)
    if sk_norm and src_norm and sk_norm != src_norm:
        ok = False
        err(
            f"skeleton 文件名卷名「{sk_title}」≠ source_file「{src_title}」"
            f"（归一化后：{sk_norm} ≠ {src_norm}）"
        )
    if vol_norm and src_norm and vol_norm != src_norm:
        ok = False
        err(
            f"volume「{volume}」≠ source_file 卷名「{src_title}」"
            f"（归一化后：{vol_norm} ≠ {src_norm}）"
        )
    if ok:
        shown = src_title if src_norm == src_title else f"{src_title}（≈{src_norm}）"
        print(f"  ✅ 卷名一致: {shown}")


# 汉书合传卷名 → 核心人物标识（单字=姓氏前缀匹配；双字=全名匹配）
_HEZHUAN_CORE_OVERRIDES: Dict[str, List[str]] = {
  # 四姓合传（每字一姓，勿按二字切块）
    "张陈王周": ["张", "陈", "王", "周"],
    "张冯汲郑": ["张", "冯", "汲", "郑"],
    "贾邹枚路": ["贾", "邹", "枚", "路"],
    "窦田灌韩": ["窦", "田", "灌", "韩"],
    "匡张孔马": ["匡", "张", "孔", "马"],
  # 二人合传
    "陈胜项籍": ["陈胜", "项籍"],
    "张耳陈馀": ["张耳", "陈馀"],
    "魏豹田儋韩王信": ["魏豹", "田儋", "韩王信"],
    "韩彭英卢吴": ["韩信", "彭越", "黥布", "卢绾", "吴芮"],
    "荆燕吴": ["刘贾", "刘泽", "刘濞"],
    "季布栾布田叔": ["季布", "栾布", "田叔"],
    "萧何曹参": ["萧何", "曹参"],
    "爰盎晁错": ["爰盎", "晁错"],
    "李广苏建": ["李广", "苏建"],
    "赵充国辛庆忌": ["赵充国", "辛庆忌"],
    "傅常郑甘陈段": ["傅介子", "常惠", "甘延寿", "陈汤", "郑吉", "段会宗"],
    "魏相丙吉": ["魏相", "丙吉"],
    "薛宣朱博": ["薛宣", "朱博"],
    "谷永杜邺": ["谷永", "杜邺"],
  # 五姓/多段合传（卷名相邻简称拼接，勿作史略名）
    "张周赵任申屠": ["张", "周", "赵", "任", "申屠"],
    "郦陆朱刘叔孙": ["郦", "陆", "朱", "刘", "叔孙"],
    "万石卫直周张": ["万石", "卫", "直", "周", "张"],
    "隽疏于薛平彭": ["隽不疑", "疏广", "疏受", "于定国", "薛广德", "平当", "彭宣"],
    "王贡两龚鲍": ["王吉", "贡禹", "龚胜", "龚舍", "鲍宣"],
    "眭两夏侯京翼李": ["眭弘", "夏侯始昌", "夏侯胜", "京房", "翼奉", "李寻"],
    "赵尹韩张两王": ["赵广汉", "尹翁归", "韩延寿", "张敞", "王尊", "王章"],
    "王商史丹傅喜": ["王商", "史丹", "傅喜"],
  # 非多人合传硬检（跳过）
    "司马相如": [],
    "景十三王": [],
    "宣元六王": [],
}

# 四姓合传：禁止用卷名二字块作史略名称
_FOUR_SURNAME_HEZHUAN = frozenset(
    k for k, v in _HEZHUAN_CORE_OVERRIDES.items() if len(v) == 4 and all(len(x) == 1 for x in v)
)


def _core_person_covered(segment: str, person_entries: Set[str]) -> bool:
    """segment 为全名或单姓；person_entries 为士臣/君王史略名称集合。"""
    aliases = _PERSON_ALIASES.get(segment, {segment})
    if aliases & person_entries:
        return True
    if len(segment) == 1:
        return any(e and e[0] == segment for e in person_entries)
    return any(
        e == segment or e.startswith(segment) or segment in e
        for e in person_entries
    )


def _split_hezhuan_core_names(
    core: str,
    person_entries: Optional[Set[str]] = None,
) -> List[str]:
    """合传卷名核心（传字前）拆为人物标识；优先 overrides，其次按已有条目消歧。"""
    if core in _HEZHUAN_CORE_OVERRIDES:
        return _HEZHUAN_CORE_OVERRIDES[core]
    n = len(core)
    if n == 4:
        options = [[core[:2], core[2:]], list(core)]
        if person_entries:
            for opt in options:
                if len(opt) >= 2 and all(
                    _core_person_covered(s, person_entries) for s in opt
                ):
                    return opt
        return [core[:2], core[2:]]
    if n == 6:
        return [core[:2], core[2:4], core[4:6]]
    if n == 7 and core.endswith("王信"):
        return [core[:2], core[2:4], core[4:]]
    return []


def _title_chunk_pseudo_names(segments: List[str]) -> Set[str]:
    """卷名按人物段相邻拼接形成的伪史略名（如张周、郦陆、卫直、申屠）。"""
    bogus: Set[str] = set()
    if all(len(s) == 1 for s in segments):
        i = 0
        n = len(segments)
        while i < n:
            seg = segments[i]
            if len(seg) >= 2 and (i == 0 or i == n - 1):
                bogus.add(seg)
                i += 1
            elif i + 1 < n:
                bogus.add(seg + segments[i + 1])
                i += 2
            else:
                bogus.add(seg)
                i += 1
        return bogus
    # 全名二人/多人合传：仅禁止相邻卷名简称拼接（如「陈胜项籍」），不禁单名条目
    for i in range(len(segments) - 1):
        bogus.add(segments[i] + segments[i + 1])
    return bogus


def _bogus_hezhuan_chunk_names(core: str) -> Set[str]:
    """合传卷名简称切块伪人名（禁止作士臣/君王史略名称）。"""
    if core in _HEZHUAN_CORE_OVERRIDES:
        segs = _HEZHUAN_CORE_OVERRIDES[core]
        if len(segs) >= 2:
            return _title_chunk_pseudo_names(segs)
    if core in _FOUR_SURNAME_HEZHUAN:
        return {core[:2], core[2:]}
    return set()


def _format_hezhuan_segment_hint(core: str, segment: str) -> str:
    """错误提示用可读说明，避免要求 LLM 造「张陈」类伪名。"""
    hints = {
        "张": "张良/张苍/张欧", "陈": "陈平", "王": "王陵", "周": "周勃/周昌/周仁",
        "郦": "郦食其", "陆": "陆贾", "朱": "朱建", "刘": "刘敬",
        "叔孙": "叔孙通", "赵": "赵尧", "任": "任敖", "申屠": "申屠嘉",
        "万石": "万石君石奋", "卫": "卫绾", "直": "直不疑",
    }
    if segment in hints:
        return f"「{segment}」→ 应有士臣如「{hints[segment]}」"
    if len(segment) == 1 and core in _FOUR_SURNAME_HEZHUAN:
        return _format_hezhuan_segment_hint("张陈王周", segment)
    return f"「{segment}」"


_PERSON_ALIASES: Dict[str, Set[str]] = {
    "项籍": {"项籍", "项羽"},
    "项羽": {"项籍", "项羽"},
    "黥布": {"黥布", "英布"},
    "英布": {"黥布", "英布"},
    "刘贾": {"刘贾", "荆王"},
    "荆王": {"刘贾", "荆王"},
    "刘泽": {"刘泽", "燕王"},
    "燕王": {"刘泽", "燕王"},
    "刘濞": {"刘濞", "吴王"},
    "吴王": {"刘濞", "吴王"},
    "万石": {"万石", "万石君", "万石君石奋", "石奋"},
    "石奋": {"石奋", "万石君", "万石君石奋", "万石"},
    "万石君石奋": {"石奋", "万石君", "万石君石奋", "万石"},
}


def _is_liezhuan_volume(data: dict) -> bool:
    return (data.get("volume_type") or "") in ("列传", "纪传叙事")


def check_hezhuan_core_persons(data: dict) -> None:
    """合传列传：卷名核心人物须有对应人物条目（按姓/全名匹配，非卷名字符串切块）。"""
    if not _is_liezhuan_volume(data):
        return
    source_file = data.get("source_file") or ""
    m = re.match(r"^02汉书_\d{3}_(.+?)传", source_file)
    if not m:
        return
    core = m.group(1)
    bogus = _bogus_hezhuan_chunk_names(core)
    bogus_found: List[str] = []
    for e in data.get("entries") or []:
        name = e.get("史略名称", "")
        if name in bogus and normalize_entry_category(e.get("史略分类", "")) in {
            "文臣",
            "武将",
            "宦官",
            "君王",
        }:
            bogus_found.append(name)
            err(
                f"伪合传简称条目「{name}」：卷「{core}传」中此为卷名相邻简称"
                f"（非独立历史人物），禁止作史略名称；"
                f"请删此条并为每位核心人物各建独立人物条目（用全名或通行称呼）"
            )

    person_entries = {
        e.get("史略名称", "")
        for e in data.get("entries") or []
        if normalize_entry_category(e.get("史略分类", "")) in PERSON_ENTRY_CATS
    }
    person_entries = person_entries - bogus

    names = _split_hezhuan_core_names(core, person_entries)
    if len(names) < 2:
        return
    print("\n  👥 合传核心人物")
    ok = True
    covered_labels: List[str] = []
    for segment in names:
        if _core_person_covered(segment, person_entries):
            if len(segment) == 1:
                matched = sorted(
                    e for e in person_entries if e and e[0] == segment
                )
                covered_labels.append(matched[0] if matched else f"{segment}*")
            else:
                covered_labels.append(segment)
            continue
        ok = False
        hint = _format_hezhuan_segment_hint(core, segment)
        err(
            f"合传「{core}传」核心人物 {hint} 缺少人物条目"
            f"（按姓氏/全名核查，勿造「{core[:2]}」类卷名切块伪名）"
        )
    if ok:
        print(f"  ✅ 合传核心人物已覆盖: {', '.join(covered_labels)}")


def check_liezhuan_entry_density(data: dict, skeleton_path: Path) -> None:
    """
    多人卷压扁硬检：依据 Step1a LLM 判定的主轴人数（protagonists），
    非脚本书名「纪/传」推断。单人本纪/单人列传整卷 1 entry 合法。
    """
    total = int(data.get("total_paragraphs") or 0)
    entries = data.get("entries") or []
    if total < 10 or len(entries) > 1:
        return

    n_prot, src = expected_protagonist_count(data, skeleton_path)
    if n_prot is None:
        warn(
            "未找到 Step1a LLM 主轴人数（protagonist_count / protagonists.json），"
            "跳过「整卷压扁」硬检；须先完成 Step1a"
        )
        return

    if n_prot < 2:
        subtype = (data.get("volume_subtype") or "单人卷").strip()
        print(
            f"\n  📋 主轴人数（LLM Step1a）: {n_prot}（{subtype}），"
            f"整卷 {len(entries)} 条 entry 合法"
        )
        return

    vol_name = (data.get("volume") or "").strip()
    subtype = (data.get("volume_subtype") or "多人卷").strip()
    err(
        f"{subtype}「{vol_name}」Step1a 判定 {n_prot} 位主轴（来源 {src}），"
        f"但 {total} 段仅 {len(entries)} 条 entry，疑似整卷压扁；"
        f"须按主轴人物拆分（含本纪多人、列传合传、世家合传）"
    )


def check_paragraph_index_freshness(data: dict, skeleton_path: Path) -> None:
    """段落索引 total 须与原文实际段数一致。"""
    work = work_from_skeleton_path(skeleton_path)
    vol_m = re.search(r"_(\d{3})_", skeleton_path.name)
    if not vol_m:
        return
    vol = vol_m.group(1)
    idx_path = paths()["paragraph_index"] / f"{work}_{vol}.json"
    if not idx_path.is_file():
        return
    source = resolve_source_file(data, skeleton_path)
    if not source:
        return
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    idx_total = int(idx.get("total") or 0)
    actual, _, _ = count_source_paragraphs(source, work)
    if idx_total != actual:
        err(
            f"段落索引 stale：索引 {idx_total} 段 ≠ 原文 {actual} 段"
            f"（请 hist.py bootstrap --work {work} 或重建 {idx_path.name}）"
        )


def check_json_structure(data: dict, phase: str) -> bool:
    required = ["volume", "source_file", "total_paragraphs", "segment_attribution", "entries"]
    for key in required:
        if key not in data:
            err(f"缺少顶层字段: {key}")
    if not isinstance(data.get("entries"), list):
        err("entries 不是数组")
    elif not data.get("entries"):
        vt = data.get("volume_type", "")
        if vt not in ("表", "志书数据", "艺文目录", "非人物叙事"):
            err("entries 为空，没有标注任何条目")
        else:
            print("  ℹ️  entries 为空（表/志书类卷，属正常）")
    if not isinstance(data.get("segment_attribution"), list):
        err("segment_attribution 不是数组")
    elif not data.get("segment_attribution"):
        err("segment_attribution 为空，必须先产出逐段归属表")
    if phase == "final":
        for key in ["优先级", "史略开始年", "史略结束年"]:
            pass  # checked per entry below
    return not errors


def check_entries(entries: list, total_paragraphs: int, phase: str) -> Set[Tuple[str, str]]:
    """返回 entry owner 集合 {(名称, 分类)}"""
    ids_seen: Set[str] = set()
    owners: Set[Tuple[str, str]] = set()

    for i, entry in enumerate(entries):
        prefix = f"[{i + 1}/{len(entries)}] "

        for key in ["史略ID", "史略名称", "史略简介", "原文字句", "史略分类", "主要史料出处"]:
            if key not in entry or not entry[key]:
                err(f"{prefix}缺少字段: {key}")

        eid = entry.get("史略ID", "")
        if eid and not re.match(r"^[A-Z0-9]+_\d{3}_\d{2}$", eid):
            err(f"{prefix}ID 格式不对 ({eid})，应为 PREFIX_NNN_NN")
        if eid in ids_seen:
            err(f"{prefix}ID 重复: {eid}")
        ids_seen.add(eid)

        cat = normalize_entry_category(entry.get("史略分类", ""))
        raw_cat = entry.get("史略分类", "")
        if raw_cat == "士臣":
            err(f"{prefix}史略分类「士臣」已废弃，须改为文臣/武将/宦官")
        if raw_cat == "宫眷":
            err(f"{prefix}史略分类「宫眷」已废弃，须改为宗戚")
        if raw_cat in LEGACY_CATS:
            err(f"{prefix}史略分类「{raw_cat}」非法，须为君王/宗戚/宦官/文臣/武将/蕃祚/庶众")
        if cat and cat not in VALID_CATS:
            err(f"{prefix}非法分类: '{raw_cat}'（合法值: {', '.join(sorted(VALID_CATS))}）")

        intro = entry.get("史略简介", "")
        if intro and len(intro) > 20:
            err(f"{prefix}简介 {len(intro)} 字，超过 20 字上限")

        name = entry.get("史略名称", "")

        if name and intro and name == intro and len(name) > 5:
            warn(f"{prefix}简介与名称相同，可能未写简介")

        paragraphs = entry.get("paragraphs", [])
        if not paragraphs:
            err(f"{prefix}paragraphs 为空")
        elif not isinstance(paragraphs, list):
            err(f"{prefix}paragraphs 不是数组")
        else:
            for pi, p in enumerate(paragraphs):
                pf, pt = p.get("paragraph_from"), p.get("paragraph_to")
                if not isinstance(pf, int) or not isinstance(pt, int):
                    err(f"{prefix}paragraphs[{pi}] from/to 不是整数")
                elif pf > pt:
                    err(f"{prefix}paragraphs[{pi}] from({pf}) > to({pt})")
                elif pf < 1 or pt > total_paragraphs:
                    err(f"{prefix}paragraphs[{pi}] 越界 ({pf}-{pt}，总段数 {total_paragraphs})")

        if phase == "final":
            migrate_entry_fields(entry)
            for old in LEGACY_COORD_MAP:
                if old in entry and entry.get(old) not in (None, ""):
                    err(f"{prefix}仍使用旧坐标字段「{old}」，请改为「{LEGACY_COORD_MAP[old]}」")
            for key in [
                "优先级",
                "优先级判定理由",
                "史略开始年",
                "史略结束年",
                "峰值年",
                "峰值原因",
                "峰值类型",
                "峰值置信度",
                *COORD_FIELDS,
                *COORD_ID_FIELDS,
                *DETAIL_FIELDS,
            ]:
                if key not in entry or entry[key] in (None, ""):
                    err(f"{prefix}Step 4 未完成，缺少: {key}")
            pri = entry.get("优先级", "")
            if pri and pri not in VALID_PRIORITIES:
                err(f"{prefix}非法优先级: {pri}")
            if "_needs_llm" in entry and entry.get("_needs_llm"):
                err(f"{prefix}仍含 _needs_llm，LLM 补全后应删除临时字段")
            for msg in validate_entry_years(entry):
                err(msg)
            from peak_year import validate_peak  # noqa: WPS433

            for msg in validate_peak(entry):
                err(msg)
            wj = (entry.get("五级细坐标") or "").strip()
            if wj:
                parts = wj.split("·")
                if len(parts) >= 4:
                    wj_cat = parts[2]
                    if wj_cat == "士臣":
                        err(f"{prefix}五级细坐标仍用废止分类「士臣」，须与史略分类一致")
                    elif wj_cat != cat:
                        err(
                            f"{prefix}五级细坐标「{wj}」中段分类「{wj_cat}」"
                            f"与史略分类「{cat}」不一致"
                        )

        if name and cat:
            owners.add(owner_key(name, cat))

    if phase == "final":
        ei = build_emperor_index()
        ri = load_regime_index()
        di = build_dynasty_index()
        for entry in entries:
            migrate_entry_fields(entry)
            for msg in validate_entry_coordinates(
                entry, emperor_index=ei, regime_index=ri, dynasty_index=di
            ):
                err(msg)
        for msg in validate_cosegment_years(entries):
            err(msg)
        for msg in validate_year_quality(entries):
            err(msg)
        for msg in validate_person_spindle_rationale_batch(entries):
            err(msg)

    return owners


def check_volume_title_paragraphs(
    attribution: list,
    skeleton_path: Path,
    data: dict,
) -> None:
    """卷首标题 / 纪年眉批须计段；标题段 exclude=卷首标题，纪年眉批 exclude=纯纪年。"""
    source = resolve_source_file(data, skeleton_path)
    if not source:
        return
    work = work_from_skeleton_path(skeleton_path)
    text = source.read_text(encoding="utf-8")
    mode = split_mode_for_work(work, text)
    paras = split_paragraphs(text, mode)
    attr_map = {
        row["paragraph"]: row
        for row in attribution
        if isinstance(row.get("paragraph"), int)
    }
    for i, para_text in enumerate(paras, 1):
        header = classify_paragraph_header(para_text)
        if not header:
            continue
        row = attr_map.get(i)
        label = para_text[:28] + ("…" if len(para_text) > 28 else "")
        if not row:
            err(f"段{i} 为{header}（{label}），归属表缺少该段")
            continue
        if row.get("owners"):
            err(
                f"段{i} 为{header}（{label}），"
                f"不得设 owners，须 exclude_reason={header}"
            )
        elif row.get("exclude_reason") != header:
            err(
                f"段{i} 为{header}（{label}），"
                f"须 exclude_reason={header}（当前: {row.get('exclude_reason')!r}）"
            )


def check_exclude_content_paragraphs(
    data: dict,
    skeleton_path: Path,
) -> None:
    """exclude 须与段落正文一致（双向：正文禁误标卷首/世系链）。"""
    from exclude_content_gate import validate_skeleton_excludes

    print("\n  📄 exclude 内容门")
    m = re.search(r"^(\d{2}[^_]+)_(\d{3})_", skeleton_path.name)
    work_id = m.group(1) if m else ""
    source = resolve_source_file(data, skeleton_path)
    para_text: Dict[int, str] = {}
    if source and source.is_file():
        text = source.read_text(encoding="utf-8")
        work = work_from_skeleton_path(skeleton_path)
        lines = split_paragraphs(text, split_mode_for_work(work, text))
        para_text = {i + 1: ln for i, ln in enumerate(lines)}
    if not para_text:
        print("  ⏭ 无法加载原文段落，跳过")
        return
    ok, msg = validate_skeleton_excludes(data, para_text, work_id=work_id)
    if ok:
        print(f"  ✅ {msg}")
    else:
        for line in msg.splitlines():
            if line.strip():
                err(line.strip())


def check_segment_attribution(
    attribution: list,
    total: int,
    entry_owners: Set[Tuple[str, str]],
) -> None:
    """校验逐段归属表：段数完整、排除合法、与 entries 双向一致。"""
    if len(attribution) != total:
        err(f"segment_attribution 行数 {len(attribution)} ≠ total_paragraphs {total}")

    seen_p: Set[int] = set()
    attr_map: Dict[int, dict] = {}

    for i, row in enumerate(attribution):
        prefix = f"[归属表 {i + 1}] "
        p = row.get("paragraph")
        if not isinstance(p, int):
            err(f"{prefix}paragraph 必须是整数")
            continue
        if p in seen_p:
            err(f"{prefix}段号重复: {p}")
        seen_p.add(p)
        attr_map[p] = row

        owners = row.get("owners", [])
        exclude_reason = row.get("exclude_reason")

        if not isinstance(owners, list):
            err(f"{prefix}owners 必须是数组")
            continue

        if not owners:
            if not exclude_reason:
                err(f"{prefix}段{p}: owners 为空但未声明 exclude_reason")
            elif exclude_reason not in VALID_EXCLUDE_REASONS:
                err(f"{prefix}段{p}: 非法 exclude_reason '{exclude_reason}'")
        else:
            if exclude_reason:
                err(f"{prefix}段{p}: 有 owners 时不应同时设 exclude_reason")
            for oi, o in enumerate(owners):
                oname = o.get("name", "").strip()
                ocat = o.get("category", "").strip()
                if not oname or not ocat:
                    err(f"{prefix}段{p} owners[{oi}] 缺少 name/category")
                elif ocat not in VALID_CATS:
                    err(f"{prefix}段{p} owners[{oi}] 非法分类: {ocat}")
                elif owner_key(oname, ocat) not in entry_owners:
                    err(f"{prefix}段{p} owners[{oi}] [{oname}] {ocat} 在 entries 中无对应条目")

    missing = sorted(set(range(1, total + 1)) - seen_p)
    if missing:
        err(f"segment_attribution 缺少段号: {missing}")


def cross_check_entries_attribution(entries: list, attribution: list) -> None:
    """entries.paragraphs 与 segment_attribution 双向精确校验。"""
    attr_map = {row["paragraph"]: row for row in attribution if isinstance(row.get("paragraph"), int)}

    for entry in entries:
        name = entry.get("史略名称", "")
        cat = entry.get("史略分类", "")
        key = owner_key(name, cat)

        # 收集条目 paragraphs 覆盖的段号
        para_segs = set()
        for pblock in entry.get("paragraphs", []):
            for seg in range(pblock["paragraph_from"], pblock["paragraph_to"] + 1):
                para_segs.add(seg)

        # 收集 segment_attribution 中该条目的段号
        attr_segs = set()
        for seg, row in attr_map.items():
            row_owners = {owner_key(o.get("name", ""), o.get("category", "")) for o in row.get("owners", [])}
            if key in row_owners:
                attr_segs.add(seg)

        if not attr_segs:
            continue  # entry 在 attribution 中没有出现，由 audit 处理

        # paragraphs 中有但 attribution 中没有 → paragraphs 过宽
        extra = para_segs - attr_segs
        if extra:
            err(f"[{entry.get('史略ID')}] 段{min(extra)} 在 paragraphs 中但归属表未标 [{name}] {cat}")

        # attribution 中有但 paragraphs 中没有 → 漏标
        missing = attr_segs - para_segs
        if missing:
            err(f"[{entry.get('史略ID')}] 归属段 {sorted(missing)} 未写入 paragraphs")


def check_quotes(
    entries: list,
    source_dir: str,
    data: dict,
    skeleton_path: Path,
) -> None:
    src = resolve_source_file(data, skeleton_path)
    if not src and source_dir:
        for entry in entries:
            for p in entry.get("paragraphs", []):
                vol = p.get("volume", "")
                if vol:
                    matches = glob.glob(os.path.join(source_dir, f"*{vol}*.txt"))
                    if matches:
                        src = Path(matches[0])
                        break
            if src:
                break

    if not src or not src.is_file():
        warn("无法定位源文件，跳过原文字句验证（建议提供 --src-dir 或修正 原文路径）")
        return

    full_text = src.read_text(encoding="utf-8")
    work = work_from_skeleton_path(skeleton_path)
    mode = split_mode_for_work(work, full_text)
    src_lines = split_paragraphs(full_text, mode)

    for entry in entries:
        quote = entry.get("原文字句", "")
        if not quote:
            continue
        if quote in full_text:
            continue
        short = quote[: min(15, len(quote))]
        if short in full_text:
            err(f"原文字句非逐字匹配 [{entry['史略ID']}]: 仅部分匹配，须逐字复制原文")
        else:
            err(f"原文字句验证失败 [{entry['史略ID']}]: 原文中找不到 \"{short}...\"")

    # 文臣/武将/宦官 字数门槛
    for i, entry in enumerate(entries):
        if entry.get("史略分类") not in OFFICIAL_CATEGORIES:
            continue
        paragraphs = entry.get("paragraphs", [])
        total_chars = 0
        for pr in paragraphs:
            start = pr.get("paragraph_from", 0)
            end = pr.get("paragraph_to", 0)
            for pidx in range(start - 1, min(end, len(src_lines))):
                if pidx < len(src_lines):
                    total_chars += len(src_lines[pidx])
        if total_chars < 20:
            err(f"[{i+1}/{len(entries)}] {entry['史略分类']} {entry['史略名称']} 原文共计 {total_chars} 字（门槛 ≥20），建议删除或并入君主")


def build_coverage_table(attribution: list) -> None:
    print("\n  📊 逐段归属表:")
    for row in sorted(attribution, key=lambda r: r.get("paragraph", 0)):
        p = row.get("paragraph")
        owners = row.get("owners", [])
        if owners:
            label = " + ".join(f"[{o['name']}] {o['category']}" for o in owners)
            tag = "🔗" if len(owners) > 1 else "  "
            print(f"    {tag} 段{p:02d} → {label}")
        else:
            reason = row.get("exclude_reason", "未标注")
            print(f"     ⛔ 段{p:02d} → 排除 ({reason})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 2: 格式与覆盖自检（硬门）")
    parser.add_argument("json_path", help="骨架 JSON 路径")
    parser.add_argument("--src-dir", default=None, help="原文目录，用于原文字句验证")
    parser.add_argument("--phase", choices=["skeleton", "final"], default="skeleton",
                        help="skeleton=Step2, final=Step4 补全后复检")
    parser.add_argument("--no-quote-check", action="store_true", help="跳过原文字句验证")
    args = parser.parse_args()

    if not os.path.exists(args.json_path):
        print(f"❌ 文件不存在: {args.json_path}")
        sys.exit(1)

    _enforce_lease(args.json_path)

    with open(args.json_path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n🔍 Step 2 自检 ({args.phase}): {data.get('volume', '未知卷')}")
    print(f"   条目数: {len(data.get('entries', []))}")

    print("\n  👑 参考表检查")
    if EMPEROR_JSON.is_file():
        with open(EMPEROR_JSON, encoding="utf-8") as ef:
            emperor_rows = json.load(ef)
        for issue in validate_emperor_records(emperor_rows):
            err(f"帝王.json: {issue}")
    else:
        err(f"缺少参考表: {EMPEROR_JSON}")

    skeleton_path = Path(args.json_path)

    print("\n  📐 结构检查")
    if not check_json_structure(data, args.phase):
        _exit_with_errors()

    check_paragraph_index_freshness(data, skeleton_path)
    check_volume_naming(data, skeleton_path)

    print("\n  📏 段落数校验（原文对照）")
    ok_para, para_msg, _, _ = check_paragraph_count(data, skeleton_path)
    if ok_para and not para_msg.startswith("⚠️"):
        print(f"  ✅ {para_msg}")
    elif ok_para:
        warn(para_msg.replace("⚠️ ", ""))
    else:
        err(para_msg)

    entries = data["entries"]
    total = data["total_paragraphs"]
    attribution = data["segment_attribution"]

    print(f"\n  📝 条目检查 ({len(entries)} 条)")
    check_liezhuan_entry_density(data, skeleton_path)
    entry_owners = check_entries(entries, total, args.phase)
    check_hezhuan_core_persons(data)

    print(f"\n  📊 归属表检查 (共 {total} 段)")
    check_segment_attribution(attribution, total, entry_owners)
    for sandwich_msg in detect_sandwich_excludes(data):
        warn(sandwich_msg)
    check_volume_title_paragraphs(attribution, skeleton_path, data)
    check_exclude_content_paragraphs(data, skeleton_path)
    check_junji_naming(data)
    check_volume_identity(data, skeleton_path)
    check_junji_year_uniqueness(entries, phase=args.phase)
    check_spindle_emperor_coords(entries, phase=args.phase)
    if args.phase == "skeleton":
        check_admission_process_hint(data)
    cross_check_entries_attribution(entries, attribution)
    build_coverage_table(attribution)

    if not args.no_quote_check:
        print("\n  🔎 原文字句验证")
        check_quotes(entries, args.src_dir or "", data, skeleton_path)

    if args.phase == "final":
        print("\n  🤖 知识性决策溯源（LLM 硬门）")
        work = work_from_skeleton_path(skeleton_path)
        prov_errors = validate_knowledge_provenance(data, work, phase=args.phase)
        if prov_errors:
            for msg in prov_errors:
                err(msg)
        else:
            print("  ✅ Step1/Step4 知识性字段已标记 LLM 溯源")

    if args.phase == "skeleton":
        _quality_warnings(attribution, entries, total, data, skeleton_path)

    _exit_with_errors()


def check_admission_process_hint(data: dict) -> None:
    """v2 人物标注：无额外准入过程提示。"""
    _ = data


def check_volume_identity(data: dict, skeleton_path: Path) -> None:
    """卷主轴人物 ↔ 帝王表标准名 ↔ 时代（补「名在表中即可过」漏洞）。"""
    print("\n  🎯 卷主轴身份")
    m = re.search(r"^(\d{2}[^_]+)_(\d{3})_", skeleton_path.name)
    if not m:
        print("  ⏭ 无法解析卷号，跳过")
        return
    ok, msg = validate_skeleton_identity(m.group(1), m.group(2), data)
    if ok:
        print(f"  ✅ {msg}")
    else:
        for line in msg.splitlines():
            if line.strip():
                err(line.strip())


def check_junji_naming(data: dict) -> None:
    """君王名称须在帝王.json「帝王」字段枚举内。"""
    print("\n  👑 君王命名")
    emperor_index = build_emperor_index()
    violations = collect_junji_violations(data, emperor_index=emperor_index)
    if violations:
        for v in violations:
            err(v)
    else:
        print("  ✅ 君王名称均在帝王.json 枚举内")


def _load_posthumous_names() -> Set[str]:
    """从 帝王追尊.json 加载所有追尊帝王名字。"""
    ref = SKILL_DIR / "reference" / "帝王追尊.json"
    names: Set[str] = set()
    try:
        with open(ref, "r", encoding="utf-8") as f:
            data = json.load(f)
        for group in data.get("groups", {}).values():
            for m in group.get("members", []):
                if m.get("帝王"):
                    names.add(m["帝王"])
    except Exception:
        pass
    return names


_POSTHUMOUS_NAMES: Optional[Set[str]] = None


def _is_posthumous(name: str) -> bool:
    global _POSTHUMOUS_NAMES
    if _POSTHUMOUS_NAMES is None:
        _POSTHUMOUS_NAMES = _load_posthumous_names()
    return name in _POSTHUMOUS_NAMES


def check_junji_year_uniqueness(entries: list, *, phase: str) -> None:
    """同卷、同政权多个君纪不得共用完全相同的起止年（追尊除外）。"""
    if phase != "final":
        return
    print("\n  📅 君王年份")
    seen: Dict[Tuple[int, int, str], str] = {}
    ok = True
    for entry in entries:
        if normalize_entry_category(entry.get("史略分类", "")) != "君王":
            continue
        start, end = entry.get("史略开始年"), entry.get("史略结束年")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        name = entry.get("史略名称", "?")
        regime = (entry.get("三级政权坐标") or "").strip()
        # 追尊君纪允许即位年=退位年=开国年，不视为重复
        if _is_posthumous(name) and start == end:
            continue
        key = (start, end, regime)
        if key in seen:
            ok = False
            err(
                f"君纪「{name}」与「{seen[key]}」起止年完全相同"
                f"（{start}～{end}，政权「{regime or '—'}」），"
                f"须按各自即位/退位年区分；史无记载时可单点落位（开始年=结束年）"
            )
        else:
            seen[key] = name
    if ok:
        print("  ✅ 君王年份无重复区间")


def check_spindle_emperor_coords(entries: list, *, phase: str) -> None:
    """
    非君王条目的四级帝王坐标应优先落在本卷君王主轴上。
    不在君纪列表但可于帝王.json 解析的坐标 → 跨卷人物，自动放行（勿人工确认）。
    追尊人士的士臣条目允许指向前朝帝王（坐标归前朝）。
    """
    junwang_emps = volume_junji_emperors({"entries": entries})
    if not junwang_emps:
        return
    print("\n  🎯 主轴君主")
    emperor_index = build_emperor_info_index()
    flagged = 0
    cross_volume = 0
    spindle_cats = SPINDLE_CATEGORIES
    for entry in entries:
        cat = normalize_entry_category(entry.get("史略分类", ""))
        if cat not in spindle_cats:
            continue
        emp = (entry.get("四级帝王坐标") or "").strip()
        if not emp or emp in junwang_emps:
            continue
        name = entry.get("史略名称", "?")
        # 追尊人士的士臣条目：四级帝王可指向前朝君主
        if cat in OFFICIAL_CATEGORIES and _is_posthumous(name):
            continue
        if is_cross_volume_emperor_coord(emp, junwang_emps, emperor_index):
            cross_volume += 1
            continue
        flagged += 1
        msg = (
            f"[{entry.get('史略ID')}] {cat}「{name}」"
            f"四级帝王坐标「{emp}」不在本卷君王列表 {sorted(junwang_emps)}，"
            f"且无法于帝王.json 解析，请改成本卷主轴君主或补录帝王表"
        )
        if phase == "final":
            err(msg)
        else:
            warn(msg)
    if cross_volume:
        print(f"  ℹ️ 跨卷四级帝王坐标 {cross_volume} 条（帝王表已收录，已自动放行）")
    if not flagged:
        if not cross_volume:
            print("  ✅ 非君纪坐标均落在本卷君王主轴内")


def _quality_warnings(
    attribution: list,
    entries: list,
    total: int,
    data: dict,
    skeleton_path: Path,
) -> None:
    """质量告警（不阻塞，仅 ⚠️ 提醒人工复核）"""
    print("\n  🟡 质量告警")

    src_lines: List[str] = []
    src = resolve_source_file(data, skeleton_path)
    if src and src.is_file():
        text = src.read_text(encoding="utf-8")
        work = work_from_skeleton_path(skeleton_path)
        src_lines = split_paragraphs(text, split_mode_for_work(work, text))

    # 1. 排除段 >150字且不是"太史公曰" → 列出
    long_excluded = []
    for sa in attribution:
        if sa.get("exclude_reason") and sa["exclude_reason"] != "太史公曰":
            p = sa["paragraph"]
            if 1 <= p <= len(src_lines) and len(src_lines[p-1]) > 150:
                long_excluded.append((p, sa["exclude_reason"], len(src_lines[p-1])))
    if long_excluded:
        print("  ⚠️  大段被排除，请逐条确认是否正确:")
        for p, reason, chars in sorted(long_excluded):
            print(f"      P{p}: {chars}字, 原因: {reason}")
    else:
        print("  ✅ 排除段无异常大段")

    # 2. 君纪 ≤2段 → 提醒检查是否有独立叙事
    thin_jun = []
    for e in entries:
        if e.get("史略分类") != "君王":
            continue
        pcount = sum(pr["paragraph_to"] - pr["paragraph_from"] + 1 for pr in e.get("paragraphs", []))
        if pcount <= 2:
            thin_jun.append((e["史略ID"], e["史略名称"], pcount))
    if thin_jun:
        print("  ⚠️  薄君王（≤2段），请确认是否有独立叙事:")
        for eid, name, n in sorted(thin_jun):
            print(f"      {eid}: {name} 仅{n}段")
    else:
        print("  ✅ 君王条目段数正常")

    # 3. 士臣 20-25字门槛边缘 → 提醒核实
    edge_shichen = []
    for e in entries:
        if e.get("史略分类") not in OFFICIAL_CATEGORIES or not src_lines:
            continue
        total_chars = 0
        for pr in e.get("paragraphs", []):
            for p in range(pr["paragraph_from"], pr["paragraph_to"] + 1):
                if 1 <= p <= len(src_lines):
                    total_chars += len(src_lines[p-1])
        if 20 <= total_chars <= 25:
            edge_shichen.append((e["史略ID"], e["史略名称"], total_chars))
    if edge_shichen:
        print("  ⚠️  文臣/武将/宦官字数在门槛边缘（20-25字），请核实质量:")
        for eid, name, chars in sorted(edge_shichen):
            print(f"      {eid}: {name} 共{chars}字")
    else:
        print("  ✅ 文臣/武将/宦官字数充足")


def _exit_with_errors() -> None:
    if errors:
        print(f"\n⛔ 发现 {len(errors)} 个错误，修正前不得进入下一步:")
        for msg in errors:
            print(f"  - {msg}")
        sys.exit(1)
    print("\n✅ 全部检查通过")


if __name__ == "__main__":
    main()
