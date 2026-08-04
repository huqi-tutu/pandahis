#!/usr/bin/env python3
"""v2 Step1b 硬门：blocks.json 覆盖、exclude 白名单、边界证据、夹心 exclude。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

_ROOT = Path(__file__).resolve().parents[2]
_ANNOTATE = _ROOT / "historiography-annotate"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ANNOTATE) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE))

from expand_blocks import expand_blocks  # noqa: E402
from paths_config import histograph_paths  # noqa: E402

V2_EXCLUDE_REASONS = frozenset({
    "卷首标题",
    "太史公曰",
    "论赞",
    "赞曰",
    "共段总述",
    "世系链",  # 与主轴无直接关系的族谱/享国纪年
})

LEGACY_EXCLUDE_MARKERS = (
    "过渡叙事",
    "无故事弧",
    "纯纪年",
    "志书数据",
    "艺文目录",
    "篇内小标题",
    "其他",
)

LUNZAN_REASONS = frozenset({"太史公曰", "论赞", "赞曰"})

_CHRONICLE_RESUME = re.compile(
    r"^(?:"
    r"明年|后年|其年|是岁|是时|"
    r"春[，,]|夏[，,]|秋[，,]|冬[，,]|"
    r"于是[，,]"
    r")"
)

_GENEALOGY_TABLE = re.compile(r"^.+享国\d+年")

_SURVEY_COMMENTARY = re.compile(
    r"^(?:至|及|自).+(?:兴|衰|亡|乱|治|霸|并|微|散)"
)

_ESSAY_OPENERS = re.compile(
    r"^(?:今|夫|故|借使|乡使|是时|当此|若|然则|故曰|善哉|即|是以|于是)"
)

_RHETORICAL_QIN = re.compile(
    r"^秦王(?:怀|行|不|废|自|既|并|离|有)"
)


def _paragraph_index_path(work: str, vol: str) -> Path:
    vol = vol.zfill(3)
    paths = histograph_paths()
    names = (f"{work}_{vol}.json", f"{work}_{vol.zfill(3)}.json")
    for base in (paths["paragraph_index"], paths.get("annotations_v1", paths["data"] / "03索引标注条目") / "段落索引"):
        for name in names:
            candidate = base / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"段落索引不存在: {work} vol {vol}")


def _load_index(work: str, vol: str) -> dict:
    return json.loads(_paragraph_index_path(work, vol).read_text(encoding="utf-8"))


def _para_text_map(index: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for item in index.get("paragraphs") or []:
        if not isinstance(item, dict):
            continue
        pid = int(item.get("paragraph") or item.get("id") or 0)
        text = (item.get("text") or "").strip()
        if pid > 0:
            out[pid] = text
    return out


def _blocks_path(work: str, vol: str) -> Path:
    vol = vol.zfill(3)
    return histograph_paths()["annotate_work"] / f"{work}_{vol}_blocks.json"


def _protagonists_path(work: str, vol: str) -> Path:
    vol = vol.zfill(3)
    return histograph_paths()["annotate_work"] / f"{work}_{vol}_protagonists.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_taishigong_header(text: str) -> bool:
    return text.strip().startswith("太史公曰")


def _is_chronicle_resume(text: str) -> bool:
    t = text.strip()
    if not t or _is_taishigong_header(t):
        return False
    if _GENEALOGY_TABLE.match(t):
        return False
    if _SURVEY_COMMENTARY.match(t):
        return False
    if _ESSAY_OPENERS.match(t):
        return False
    if _RHETORICAL_QIN.match(t):
        return False
    if "其语在" in t or "详见" in t:
        return False
    if _CHRONICLE_RESUME.match(t):
        return True
    # 编年体起笔：主角 + 时序/行动（排除史论引述）
    if re.match(r"^(?:秦王|秦始皇帝|始皇|二世皇帝|二世)", t):
        if re.search(r"(?:元年|二年|三年|四年|五年|六年|七年|八年|九年|十年)", t[:36]):
            return True
        if re.search(r"(?:攻|击|取|巡|崩|薨|立为|代立|即位|杀|灭|徙)", t[:28]):
            return True
    return False


def _collect_lunzan_runs(exclude_map: Dict[int, str], total: int) -> List[Tuple[int, int]]:
    runs: List[Tuple[int, int]] = []
    p = 1
    while p <= total:
        if exclude_map.get(p) not in LUNZAN_REASONS:
            p += 1
            continue
        start = p
        while p <= total and exclude_map.get(p) in LUNZAN_REASONS:
            p += 1
        runs.append((start, p - 1))
    return runs


def _validate_lunzan_overreach(
    total: int,
    exclude_map: Dict[int, str],
    owner_map: Dict[int, str],
    para_text: Dict[int, str],
) -> Tuple[List[str], List[str]]:
    """论赞/太史公曰 不得盲延：夹叙单段 vs 卷末论赞块。"""
    errors: List[str] = []
    warnings: List[str] = []

    for start, end in _collect_lunzan_runs(exclude_map, total):
        prev_owner = owner_map.get(start - 1)
        next_owner = owner_map.get(end + 1)
        run_len = end - start + 1

        # 同一传主 block 被多段论赞 exclude 打断 → 仅允许单段太史公曰夹叙
        if prev_owner and next_owner and prev_owner == next_owner and run_len > 1:
            errors.append(
                f"LUNZAN_OVERREACH: P{start}-P{end} 论赞块过长；"
                f"P{start - 1}/P{end + 1} 均为 {prev_owner} 叙事，"
                f"夹叙论赞通常仅含单段太史公曰"
            )

        # 论赞块内若出现编年叙事续写 → 误标 exclude
        for p in range(start, end + 1):
            text = para_text.get(p, "")
            if p == start and _is_taishigong_header(text):
                continue
            if _is_chronicle_resume(text):
                errors.append(
                    f"LUNZAN_OVERREACH: P{p} 标 {exclude_map[p]!r} 但段首似传主编年叙事续写"
                )

        # block → 论赞 exclude → 下一段仍论赞且似叙事回归
        for p in range(start, end):
            prev_o = owner_map.get(p - 1)
            nxt = p + 1
            if (
                prev_o
                and exclude_map.get(nxt) in LUNZAN_REASONS
                and _is_chronicle_resume(para_text.get(nxt, ""))
            ):
                errors.append(
                    f"LUNZAN_OVERREACH: P{nxt} 仍标 {exclude_map[nxt]!r} "
                    f"但似 {prev_o} 叙事回归（P{p - 1} 为 block）"
                )

        # 多段论赞块后不可回归同一传主 block
        if prev_owner and next_owner and prev_owner == next_owner and run_len > 1:
            errors.append(
                f"LUNZAN_RESUME_BLOCK: P{start}-P{end} 论赞后 P{end + 1} "
                f"回归 {next_owner} 叙事，论赞区间应止于夹叙段"
            )

        # 卷末论赞：多段 run 前一段应为 block 收束或太史公曰/世系链
        if run_len > 1 and exclude_map.get(start) == "论赞":
            prev_reason = exclude_map.get(start - 1)
            if prev_reason not in ("太史公曰", "世系链") and not prev_owner:
                warnings.append(
                    f"LUNZAN_BOUNDARY: P{start}-P{end} 论赞续段前无 block 收束或太史公曰，"
                    f"请确认非见论赞就盲延"
                )

    return errors, warnings


def _parse_ranges(items: List[dict]) -> List[Tuple[int, int, dict]]:
    out: List[Tuple[int, int, dict]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        pf = int(item.get("paragraph_from") or 0)
        pt = int(item.get("paragraph_to") or pf)
        out.append((pf, pt, item))
    return out


def validate_blocks(
    draft: dict,
    *,
    index: dict,
    protagonists: dict | None,
) -> Tuple[List[str], List[str]]:
    """返回 (errors, warnings)。"""
    errors: List[str] = []
    warnings: List[str] = []

    total = int(index.get("total") or draft.get("total_paragraphs") or 0)
    if total <= 0:
        errors.append("COVERAGE: 段数无效")
        return errors, warnings

    draft_total = int(draft.get("total_paragraphs") or 0)
    if draft_total != total:
        errors.append(f"COVERAGE: total_paragraphs={draft_total} ≠ 索引 {total}")

    # Protagonist set
    proto_names: Set[str] = set()
    if protagonists:
        for p in protagonists.get("protagonists") or []:
            if isinstance(p, dict):
                name = (p.get("name") or "").strip()
                if name:
                    proto_names.add(name)

    excludes = _parse_ranges(draft.get("excludes") or [])
    blocks = _parse_ranges(draft.get("blocks") or [])
    para_text = _para_text_map(index)

    exclude_map: Dict[int, str] = {}
    for pf, pt, item in excludes:
        reason = (item.get("exclude_reason") or "").strip()
        if reason not in V2_EXCLUDE_REASONS:
            if any(m in reason for m in LEGACY_EXCLUDE_MARKERS):
                errors.append(f"EXCLUDE_LEGACY: P{pf}-P{pt} 使用 v1 exclude {reason!r}")
            else:
                errors.append(f"EXCLUDE_V2: P{pf}-P{pt} 非法 exclude_reason {reason!r}")
        for p in range(pf, pt + 1):
            if p in exclude_map:
                errors.append(f"OVERLAP: P{p} 重复 exclude")
            exclude_map[p] = reason

    owner_map: Dict[int, str] = {}
    for pf, pt, item in blocks:
        name = (item.get("name") or "").strip()
        if not name:
            errors.append(f"PROTAGONIST: P{pf}-P{pt} block 缺 name")
        elif proto_names and name not in proto_names:
            errors.append(f"PROTAGONIST: block [{name}] 不在 Step1a 名单")
        for p in range(pf, pt + 1):
            if p in exclude_map:
                errors.append(f"OVERLAP: P{p} 同时在 exclude 与 block [{name}]")
                continue
            if p in owner_map:
                errors.append(f"OVERLAP: P{p} 重复 block [{owner_map[p]}] 与 [{name}]")
            owner_map[p] = name

        ev = item.get("boundary_evidence") or {}
        if not isinstance(ev, dict):
            errors.append(f"BOUNDARY_PHRASE: [{name}] 缺 boundary_evidence")
            continue
        open_p = int(ev.get("open_paragraph") or pf)
        phrase = (ev.get("open_phrase") or "").strip()
        if len(phrase) < 6:
            errors.append(f"BOUNDARY_PHRASE: [{name}] open_phrase 须 ≥6 字")
        else:
            text = para_text.get(open_p, "")
            if phrase not in text:
                errors.append(
                    f"BOUNDARY_PHRASE: [{name}] open_phrase 非 P{open_p} 原文子串: {phrase!r}"
                )

    for p in range(1, total + 1):
        if p not in exclude_map and p not in owner_map:
            errors.append(f"COVERAGE: P{p} 未覆盖")

    # expand_blocks dry run
    dry = dict(draft)
    dry["total_paragraphs"] = total
    _, expand_errs = expand_blocks(dry)
    for msg in expand_errs[:10]:
        errors.append(f"EXPAND: {msg}")

    # Sandwich exclude
    attribution, _ = expand_blocks(dry)
    seg_by_p = {int(s["paragraph"]): s for s in attribution}
    for p in range(2, total):
        prev_seg = seg_by_p.get(p - 1) or {}
        next_seg = seg_by_p.get(p + 1) or {}
        cur = seg_by_p.get(p) or {}
        if not cur.get("exclude_reason"):
            continue
        prev_owners = [o.get("name") for o in prev_seg.get("owners") or []]
        next_owners = [o.get("name") for o in next_seg.get("owners") or []]
        if (
            len(prev_owners) == 1
            and prev_owners == next_owners
            and prev_owners[0]
            and cur.get("exclude_reason") not in (
                "共段总述",
                "世系链",
                "太史公曰",
                "论赞",
                "赞曰",
                "卷首标题",
            )
        ):
            errors.append(
                f"SANDWICH: P{p} exclude 但 P{p-1}/P{p+1} 均归 {prev_owners[0]}"
            )

    # multi_owner_segments：仅允许「两主轴世系交接」双挂；禁止三人以上或非主轴
    multi_items = draft.get("multi_owner_segments") or []
    for item in multi_items:
        if not isinstance(item, dict):
            continue
        pid = int(item.get("paragraph") or 0)
        owners = item.get("owners") or []
        if pid <= 0:
            errors.append("MULTI_OWNER: 缺 paragraph")
            continue
        names = []
        for o in owners:
            if not isinstance(o, dict):
                continue
            n = (o.get("name") or "").strip()
            if not n:
                continue
            names.append(n)
            if proto_names and n not in proto_names:
                errors.append(f"MULTI_OWNER: P{pid} [{n}] 不在 Step1a")
        if len(names) < 2:
            warnings.append(f"MULTI_OWNER: P{pid} owners<2，可合并为单 owner block")
        elif len(names) > 2:
            errors.append(
                f"MULTI_OWNER_FORBIDDEN: P{pid} 有 {len(names)} 个 owner；"
                "仅允许两主轴「卒/立」交接双挂；并列无主角须 exclude=共段总述"
            )

    if not blocks:
        errors.append("COVERAGE: blocks 为空")

    lunzan_errs, lunzan_warns = _validate_lunzan_overreach(
        total, exclude_map, owner_map, para_text
    )
    errors.extend(lunzan_errs)
    warnings.extend(lunzan_warns)

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="v2 blocks 硬门")
    ap.add_argument("--work", required=True)
    ap.add_argument("--vol", required=True)
    ap.add_argument("--blocks", type=Path, help="blocks.json 路径（默认 annotate_work）")
    args = ap.parse_args()

    work = args.work.strip()
    vol = args.vol.zfill(3)
    bp = args.blocks or _blocks_path(work, vol)
    if not bp.exists():
        print(f"❌ blocks 不存在: {bp}", file=sys.stderr)
        return 1

    try:
        index = _load_index(work, vol)
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    draft = _load_json(bp)
    protagonists = None
    pp = _protagonists_path(work, vol)
    if pp.exists():
        protagonists = _load_json(pp)

    errors, warnings = validate_blocks(draft, index=index, protagonists=protagonists)

    for w in warnings:
        print(f"⚠️  {w}")
    if errors:
        print(f"❌ v2_blocks_gate 失败 ({len(errors)} 项):", file=sys.stderr)
        for e in errors:
            print(f"  · {e}", file=sys.stderr)
        return 1

    n_blocks = len(draft.get("blocks") or [])
    n_ex = len(draft.get("excludes") or [])
    print(f"✅ v2_blocks_gate 通过 · {n_blocks} 块 · {n_ex} exclude · {index['total']} 段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
