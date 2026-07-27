#!/usr/bin/env python3
"""《史记》世家卷 blocks 配置：033/039 人工精修，其余由旧版索引 + 段落消歧生成。"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from emperor_resolve import build_emperor_info_index  # noqa: E402
from paths_config import get_histograph_root  # noqa: E402

BlockSpec = Tuple[str, str, int, int]
ExcludeSpec = Tuple[int, int, str]

DATA = get_histograph_root() / "data"
OLD_INDEX = DATA / "03索引标注条目" / "旧版备份" / "史略索引_01至02.json"
IDX_DIR = DATA / "03索引标注条目" / "段落索引"

# 人工精修（试点）
MANUAL: Dict[str, dict] = {
    "033": {
        "blocks": [
            ("周公旦", "诸侯", 1, 13),
            ("鲁公伯禽", "诸侯", 14, 16),
            ("鲁武公", "诸侯", 19, 20),
            ("鲁惠公", "诸侯", 23, 24),
            ("鲁隐公", "诸侯", 25, 27),
            ("鲁桓公", "诸侯", 28, 31),
            ("鲁庄公", "诸侯", 32, 35),
            ("鲁湣公", "诸侯", 36, 37),
            ("鲁釐公", "诸侯", 38, 42),
            ("鲁文公", "诸侯", 43, 47),
            ("鲁宣公", "诸侯", 48, 49),
            ("鲁成公", "诸侯", 50, 54),
            ("鲁襄公", "诸侯", 55, 63),
            ("鲁昭公", "诸侯", 64, 73),
            ("鲁定公", "诸侯", 74, 76),
            ("鲁哀公", "诸侯", 77, 85),
            ("鲁顷公", "诸侯", 91, 91),
        ],
        "excludes": [
            (17, 18, "其他"),
            (21, 22, "其他"),
            (86, 90, "其他"),
            (92, 92, "其他"),
            (93, 93, "太史公曰"),
        ],
    },
    "039": {
        "blocks": [
            ("晋武公", "诸侯", 1, 23),
            ("晋献公", "诸侯", 24, 44),
            ("晋惠公", "诸侯", 45, 61),
            ("晋文公", "诸侯", 62, 102),
            ("晋襄公", "诸侯", 103, 109),
            ("晋灵公", "诸侯", 110, 120),
            ("晋景公", "诸侯", 121, 144),
            ("晋厉公", "诸侯", 145, 151),
            ("晋悼公", "诸侯", 152, 156),
            ("晋平公", "诸侯", 157, 162),
            ("晋顷公", "诸侯", 163, 167),
            ("晋定公", "诸侯", 168, 172),
            ("晋出公", "诸侯", 173, 176),
        ],
        "excludes": [(177, 182, "其他"), (183, 183, "太史公曰")],
    },
    "031": {
        "blocks": [
            ("吴太伯", "诸侯", 1, 21),
            ("吴王阖闾", "诸侯", 22, 39),
            ("吴王夫差", "诸侯", 40, 51),
        ],
        "excludes": [(52, 52, "太史公曰")],
    },
    "047": {
        "blocks": [("孔子", "文臣", 1, 106)],
        "excludes": [(107, 108, "太史公曰")],
        "entry_meta": {
            "孔子": {
                "patron": "鲁定公",
                "start": -551,
                "end": -479,
                "axis": "孔子为鲁国人，周游列国主轴锚鲁定公。",
                "reason": "孔子世家主轴（文臣），共106段",
            }
        },
    },
    "048": {
        "blocks": [("陈涉", "庶众", 2, 21)],
        "excludes": [(1, 1, "卷首标题"), (22, 28, "其他")],
        "entry_meta": {
            "陈涉": {
                "patron": "秦二世",
                "start": -209,
                "end": -196,
                "axis": "陈涉起义反秦，主轴锚秦二世。",
                "reason": "陈涉世家主轴（庶众），共20段",
            }
        },
    },
    "049": {
        "blocks": [
            ("薄太后", "宗戚", 4, 8),
            ("窦太后", "宗戚", 9, 15),
            ("王太后", "宗戚", 16, 28),
            ("卫子夫", "宗戚", 29, 44),
        ],
        "excludes": [(1, 3, "其他"), (45, 56, "其他")],
        "entry_meta": {
            "薄太后": {"patron": "汉文帝", "start": -203, "end": -155, "reason": "薄太后叙事，共5段"},
            "窦太后": {"patron": "汉景帝", "start": -205, "end": -135, "reason": "窦太后叙事，共7段"},
            "王太后": {"patron": "汉武帝", "start": -188, "end": -104, "reason": "王太后及栗姬、王儿姁，共13段"},
            "卫子夫": {"patron": "汉武帝", "start": -139, "end": -91, "reason": "卫子夫及外戚专宠，共16段"},
        },
    },
    "050": {
        "blocks": [("楚元王", "宗戚", 1, 11)],
        "excludes": [(12, 12, "太史公曰")],
        "entry_meta": {
            "楚元王": {"patron": "汉高祖", "reason": "楚元王刘交世家，锚汉高祖，共11段"},
        },
    },
    "051": {
        "blocks": [
            ("荆王", "宗戚", 1, 7),
            ("燕王", "宗戚", 8, 12),
        ],
        "excludes": [(13, 13, "太史公曰")],
        "entry_meta": {
            "荆王": {"patron": "汉高祖", "reason": "荆王刘贾，锚汉高祖，共7段"},
            "燕王": {"patron": "汉高祖", "reason": "燕王刘泽，锚汉高祖，共5段"},
        },
    },
    "052": {
        "blocks": [("齐悼惠王", "宗戚", 1, 56)],
        "excludes": [(57, 57, "太史公曰")],
        "entry_meta": {
            "齐悼惠王": {"patron": "汉高祖", "reason": "齐悼惠王刘肥世家，锚汉高祖，共56段"},
        },
    },
    "053": {"blocks": [("萧何", "文臣", 1, 20)], "excludes": []},
    "054": {"blocks": [("曹参", "文臣", 1, 25)], "excludes": [(26, 26, "太史公曰")]},
    "055": {"blocks": [("张良", "文臣", 1, 41)], "excludes": [(42, 42, "太史公曰"), (43, 43, "其他")]},
    "056": {"blocks": [("陈平", "文臣", 1, 37)], "excludes": [(38, 38, "太史公曰"), (39, 39, "其他")]},
    "057": {"blocks": [("周勃", "文臣", 1, 31)], "excludes": [(32, 32, "太史公曰"), (33, 33, "其他")]},
    "058": {
        "blocks": [("梁孝王", "宗戚", 1, 37)],
        "excludes": [],
        "entry_meta": {"梁孝王": {"patron": "汉文帝", "reason": "梁孝王刘武世家，锚汉文帝，共37段"}},
    },
    "059": {
        "blocks": [
            ("栗姬", "宗戚", 1, 9),
            ("程姬", "宗戚", 10, 18),
            ("贾夫人", "宗戚", 19, 26),
            ("唐姬", "宗戚", 27, 30),
            ("儿姁", "宗戚", 31, 45),
        ],
        "excludes": [(46, 47, "太史公曰")],
        "entry_meta": {
            "栗姬": {"patron": "汉景帝", "start": -176, "end": -150, "reason": "栗姬宗支，共9段"},
            "程姬": {"patron": "汉景帝", "start": -155, "end": -108, "reason": "程姬宗支，共9段"},
            "贾夫人": {"patron": "汉景帝", "start": -155, "end": -92, "reason": "贾夫人宗支，共8段"},
            "唐姬": {"patron": "汉景帝", "start": -155, "end": -128, "reason": "唐姬宗支，共4段"},
            "儿姁": {"patron": "汉景帝", "start": -148, "end": -104, "reason": "儿姁宗支，共15段"},
        },
    },
    "060": {
        "blocks": [
            ("齐王刘闳", "宗戚", 12, 13),
            ("齐王刘闳", "宗戚", 21, 21),
            ("齐王刘闳", "宗戚", 23, 23),
            ("燕王刘旦", "宗戚", 14, 15),
            ("燕王刘旦", "宗戚", 29, 34),
            ("广陵王刘胥", "宗戚", 16, 17),
            ("广陵王刘胥", "宗戚", 25, 28),
        ],
        "excludes": [
            (1, 11, "其他"),
            (18, 18, "太史公曰"),
            (19, 20, "其他"),
            (22, 22, "其他"),
            (24, 24, "其他"),
        ],
        "entry_meta": {
            "齐王刘闳": {"patron": "汉武帝", "start": -117, "end": -110, "reason": "齐王策+褚补，共5段"},
            "燕王刘旦": {"patron": "汉武帝", "start": -117, "end": -80, "reason": "燕王策+褚补，共8段"},
            "广陵王刘胥": {"patron": "汉武帝", "start": -117, "end": -54, "reason": "广陵王策+褚补，共6段"},
        },
    },
}

# 旧版不收录或需过滤的名称
SKIP_NAMES = {
    "楚先祖",
    "赵氏先祖",
    "韩氏先祖",
    "晋唐叔虞",
}


def _load_legacy_raw(vol: str) -> List[Tuple[str, int, int]]:
    doc = json.loads(OLD_INDEX.read_text(encoding="utf-8"))
    emperors = set(build_emperor_info_index().keys())
    acc: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for e in doc.get("entries") or []:
        if e.get("史略分类") not in ("诸侯", "君纪"):
            continue
        name = (e.get("史略名称") or "").strip()
        if not name or name in SKIP_NAMES or name not in emperors:
            continue
        for p in e.get("paragraphs") or []:
            if p.get("work") == "01史记" and str(p.get("vol")).zfill(3) == vol:
                acc[name].append((int(p["paragraph_from"]), int(p["paragraph_to"])))
                break
    raw: List[Tuple[str, int, int]] = []
    for name, ranges in acc.items():
        ranges.sort()
        merged: List[Tuple[int, int]] = []
        for pf, pt in ranges:
            if merged and pf <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], pt))
            else:
                merged.append((pf, pt))
        for pf, pt in merged:
            raw.append((name, pf, pt))
    raw.sort(key=lambda x: (x[1], x[2] - x[1]))
    return raw


def _score_owner(name: str, p: int, pf: int, pt: int, text: str) -> int:
    score = 0
    if p == pf:
        score += 20
    if re.search(rf"是为{re.escape(name)}", text):
        score += 200
    short = name[-2:] if len(name) >= 2 else name
    if short and re.search(rf"是为{re.escape(short)}", text):
        score += 80
    if name in text[:80]:
        score += 15
    score -= (pt - pf)
    return score


def _resolve_paragraph_owners(
    raw: List[Tuple[str, int, int]], total: int, para: Dict[int, str]
) -> Dict[int, str]:
    owners: Dict[int, str] = {}
    for p in range(1, total + 1):
        cands = [(n, pf, pt) for n, pf, pt in raw if pf <= p <= pt]
        if not cands:
            continue
        text = para.get(p, "")
        best = max(cands, key=lambda c: _score_owner(c[0], p, c[1], c[2], text))
        owners[p] = best[0]
    return owners


def _owners_to_blocks(owners: Dict[int, str]) -> List[BlockSpec]:
    if not owners:
        return []
    blocks: List[BlockSpec] = []
    ps = sorted(owners)
    start = ps[0]
    cur = owners[start]
    prev = start
    for p in ps[1:]:
        if owners[p] != cur:
            blocks.append((cur, "诸侯", start, prev))
            start = p
            cur = owners[p]
        prev = p
    blocks.append((cur, "诸侯", start, prev))
    return blocks


def _find_taishi(total: int, para: Dict[int, str]) -> int | None:
    for p in range(total, 0, -1):
        if para.get(p, "").strip().startswith("太史公曰"):
            return p
    return None


def _build_excludes(total: int, owners: Dict[int, str], para: Dict[int, str]) -> List[ExcludeSpec]:
    excludes: List[ExcludeSpec] = []
    taishi = _find_taishi(total, para)
    p = 1
    while p <= total:
        if taishi and p == taishi:
            excludes.append((p, p, "太史公曰"))
            p += 1
            continue
        if p not in owners:
            text = para.get(p, "").strip()
            if text == "【原文】":
                excludes.append((p, p, "卷首标题"))
                p += 1
                continue
            start = p
            while p <= total and p not in owners and (not taishi or p != taishi):
                p += 1
            excludes.append((start, p - 1, "其他"))
            continue
        p += 1
    return _merge_adjacent_excludes(excludes)


def _merge_adjacent_excludes(excludes: List[ExcludeSpec]) -> List[ExcludeSpec]:
    if not excludes:
        return []
    out: List[ExcludeSpec] = []
    pf, pt, reason = excludes[0]
    for nf, nt, nr in excludes[1:]:
        if nr == reason and nf == pt + 1:
            pt = nt
        else:
            out.append((pf, pt, reason))
            pf, pt, reason = nf, nt, nr
    out.append((pf, pt, reason))
    return out


def build_vol_config(vol: str) -> dict:
    vol = vol.zfill(3)
    if vol in MANUAL:
        cfg = dict(MANUAL[vol])
        cfg.setdefault("entry_meta", "auto")
        return cfg

    idx_path = IDX_DIR / f"01史记_{vol}.json"
    if not idx_path.exists():
        raise FileNotFoundError(idx_path)
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    total = int(idx["total"])
    para = {int(r["id"]): (r.get("text") or "") for r in idx.get("paragraphs") or []}

    raw = _load_legacy_raw(vol)
    if not raw:
        raise ValueError(f"卷{vol} 旧版无诸侯块")
    owners = _resolve_paragraph_owners(raw, total, para)
    blocks = _owners_to_blocks(owners)
    excludes = _build_excludes(total, owners, para)
    return {"blocks": blocks, "excludes": excludes, "entry_meta": "auto"}


def all_jiashi_vols() -> List[str]:
    return [f"{i:03d}" for i in range(31, 61)]


def build_all_repairs() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for vol in all_jiashi_vols():
        out[vol] = build_vol_config(vol)
    return out


if __name__ == "__main__":
    for vol in all_jiashi_vols():
        cfg = build_vol_config(vol)
        n = len(cfg["blocks"])
        print(f"卷{vol}: {n} blocks, {len(cfg['excludes'])} excludes")
