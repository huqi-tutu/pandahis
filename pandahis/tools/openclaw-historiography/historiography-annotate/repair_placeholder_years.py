#!/usr/bin/env python3
"""修复卷级占位年代：清除宽泛区间，按分类重新推断条目级年份。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))

from coordinate_index import (  # noqa: E402
    build_dynasty_index_from_json,
    build_regime_index,
    migrate_entry_fields,
    normalize_entry_category,
)
from emperor_resolve import (  # noqa: E402
    build_emperor_info_index,
    resolve_emperor_label,
    work_id_from_skeleton,
)
from fill_fields import merge_all_entries  # noqa: E402
from lib_config import SINGLE_YEAR_CATEGORIES  # noqa: E402
from shilue_year_resolve import (  # noqa: E402
    cn_reign_year_to_int,
    emperor_accession_year,
    extract_bc_years,
    extract_reign_years_from_text,
    infer_shilue_years,
    reign_accession_for_text,
    reign_year_to_absolute,
)

_RE_BC = re.compile(r"前(\d{1,4})")
_RE_DEATH_REIGN = re.compile(
    r"之死也，以(?:秦昭王|昭王|秦王|王)?([一二三四五六七八九十两\d]+)年"
)
MAX_PERSON_SPAN = 35
MAX_PERSON_BIO_SPAN = 65
MAX_EVENT_SPAN = 25
PLACEHOLDER_MIN_SPAN = 50
PLACEHOLDER_MIN_SHARE = 3
SHARED_RANGE_MIN_SPAN = 8
SHARED_RANGE_MIN_SHARE = 3
MIN_PERSON_SPAN_LONG_BIO = 12

# 脚本可确定性写入的年份推断（不经 LLM「仅知一年」判定）
_CONFIDENT_REPAIR_PREFIXES = frozenset({
    "person_career_to_death",
    "person_text_span",
    "event_death",
    "junji_emperor_table",
})


def _year_range_counter(entries: list) -> Counter:
    return Counter(
        (e.get("史略开始年"), e.get("史略结束年"))
        for e in entries
        if isinstance(e.get("史略开始年"), int) and isinstance(e.get("史略结束年"), int)
    )


def detect_volume_placeholder(entries: list) -> Optional[Tuple[int, int]]:
    """返回该卷最常见的宽泛占位区间 (start, end)。"""
    if len(entries) < PLACEHOLDER_MIN_SHARE:
        return None
    ranges = _year_range_counter(entries)
    if not ranges:
        return None
    (start, end), cnt = ranges.most_common(1)[0]
    if cnt < PLACEHOLDER_MIN_SHARE or start == end:
        return None
    if end - start < PLACEHOLDER_MIN_SPAN:
        return None
    return start, end


def detect_shared_range_placeholder(entries: list) -> Optional[Tuple[int, int]]:
    """≥3 条共享同一多年区间（跨度≥8），视为卷级批量填充。"""
    if len(entries) < SHARED_RANGE_MIN_SHARE:
        return None
    for (start, end), cnt in _year_range_counter(entries).most_common():
        if cnt < SHARED_RANGE_MIN_SHARE or start == end:
            continue
        if end - start >= SHARED_RANGE_MIN_SPAN:
            return start, end
    return None


def volume_placeholder(entries: list) -> Optional[Tuple[int, int]]:
    return detect_volume_placeholder(entries) or detect_shared_range_placeholder(entries)


def _paragraph_span(entry: dict) -> int:
    prs = entry.get("paragraphs") or []
    if not prs:
        return 0
    lo = min(int(p["paragraph_from"]) for p in prs)
    hi = max(int(p["paragraph_to"]) for p in prs)
    return hi - lo + 1


def _shilue_copies_person_bio(entry: dict, entries: list) -> bool:
    if normalize_entry_category(entry.get("史略分类", "")) != "事略":
        return False
    es, ee = entry.get("史略开始年"), entry.get("史略结束年")
    if not isinstance(es, int) or not isinstance(ee, int) or es == ee:
        return False
    name = entry.get("史略名称", "")
    for peer in entries:
        if peer is entry:
            continue
        pc = normalize_entry_category(peer.get("史略分类", ""))
        if pc not in ("士臣", "民录"):
            continue
        peer_name = peer.get("史略名称", "")
        if peer_name and peer_name not in name:
            continue
        ps, pe = peer.get("史略开始年"), peer.get("史略结束年")
        if ps == es and pe == ee:
            return True
    return False


def _shilue_uniform_single_year(entry: dict, entries: list) -> bool:
    """同卷≥2条事略被标为同一年单点（常见批量 -202）。"""
    if normalize_entry_category(entry.get("史略分类", "")) != "事略":
        return False
    es, ee = entry.get("史略开始年"), entry.get("史略结束年")
    if not isinstance(es, int) or es != ee:
        return False
    same = sum(
        1
        for e in entries
        if normalize_entry_category(e.get("史略分类", "")) == "事略"
        and e.get("史略开始年") == es
        and e.get("史略结束年") == ee
    )
    return same >= 2


def extract_death_year(text: str, accession: Optional[int]) -> Optional[int]:
    """从「……之死也，以昭王N年」等句式提取绝对年。"""
    if accession is None or not text:
        return None
    m = _RE_DEATH_REIGN.search(text)
    if not m:
        return None
    ry = cn_reign_year_to_int(m.group(1))
    if ry is None:
        return None
    return reign_year_to_absolute(ry, accession)


def entry_source_text(entry: dict, *, work_id: str, vol: str) -> str:
    """召回 paragraphs 全区间原文，避免仅用截断的「原文字句」。"""
    intro = entry.get("史略简介", "") or ""
    quote = entry.get("原文字句", "") or ""
    try:
        from recall_paragraphs import (  # noqa: WPS433
            join_recalled,
            load_paragraph_index,
            recall_entry_ranges,
        )

        idx = load_paragraph_index(work_id, vol)
        chunks = recall_entry_ranges(entry, work=work_id, vol=vol, index=idx)
        body = join_recalled(chunks)
        if body.strip():
            return f"{intro} {body}"
    except Exception:
        pass
    return f"{intro} {quote}"


def infer_person_years(
    entry: dict,
    emperor_index: Dict[str, dict],
    *,
    work_id: str = "",
    vol: str = "",
) -> Optional[Tuple[int, int, str]]:
    """士臣/民录：全段落纪年 → 首见年至卒年；禁止仅用开篇几年冒充生卒。"""
    text = entry_source_text(entry, work_id=work_id, vol=vol)
    accession, _, emp_name = reign_accession_for_text(entry, emperor_index, text)

    reign_years: List[int] = []
    abs_years: List[int] = []
    if accession is not None:
        reign_years = extract_reign_years_from_text(text)
        for ry in reign_years:
            abs_years.append(reign_year_to_absolute(ry, accession))
    abs_years.extend(extract_bc_years(text))

    death = extract_death_year(text, accession)
    if death is not None:
        if reign_years:
            # 「后五年」等会误抽出 5 年，起点取 ≥10 的最小纪年（如昭王十三年）
            credible_reign = [ry for ry in reign_years if ry >= 10] or reign_years
            start = reign_year_to_absolute(min(credible_reign), accession)
            if death >= start:
                return start, death, f"person_career_to_death:{emp_name or '?'}"
        if abs_years:
            start = min(y for y in abs_years if y <= death)
            if death >= start:
                return start, death, f"person_career_to_death:{emp_name or '?'}"
        return death, death, f"person_death_only:{emp_name or '?'}"

    if abs_years:
        abs_years = sorted(set(abs_years))
        if len(abs_years) >= 2:
            start, end = abs_years[0], abs_years[-1]
            span = end - start
            limit = MAX_PERSON_BIO_SPAN if len(entry.get("paragraphs") or []) else MAX_PERSON_SPAN
            if span <= limit:
                return start, end, "person_text_span"
            return start, start, "person_text_span_too_wide_use_start"
        y = abs_years[0]
        return y, y, "person_text_single"

    if accession is not None:
        return accession, accession, f"person_emperor_anchor:{emp_name or '?'}"
    return None


def infer_single_year_entry(
    entry: dict,
    emperor_index: Dict[str, dict],
) -> Optional[Tuple[int, int, str]]:
    text = f"{entry.get('史略简介', '')} {entry.get('原文字句', '')}"
    accession, _, emp_name = emperor_accession_year(entry, emperor_index)

    abs_years: List[int] = []
    if accession is not None:
        for ry in extract_reign_years_from_text(text):
            abs_years.append(reign_year_to_absolute(ry, accession))
    abs_years.extend(extract_bc_years(text))
    if abs_years:
        y = sorted(abs_years)[0]
        return y, y, "single_text"
    if accession is not None:
        return accession, accession, f"single_emperor_anchor:{emp_name or '?'}"
    return None


def infer_junji_years(
    entry: dict,
    emperor_index: Dict[str, dict],
    work_id: str,
) -> Optional[Tuple[int, int, str]]:
    name = (entry.get("史略名称") or "").strip()
    resolved, _ = resolve_emperor_label(name, work_id=work_id, emperor_index=emperor_index)
    info = resolved or emperor_index.get(name)
    if not info:
        coord = (entry.get("四级帝王坐标") or "").strip()
        info = emperor_index.get(coord)
    if not info:
        return None
    rs, re = info.get("start_year"), info.get("end_year")
    if rs is None or re is None:
        return None
    return rs, re, "junji_emperor_table"


def is_bad_year(
    entry: dict,
    placeholder: Optional[Tuple[int, int]],
    *,
    work_id: str = "",
    vol: str = "",
    emperor_index: Optional[Dict[str, dict]] = None,
    all_entries: Optional[list] = None,
    data: Optional[dict] = None,
) -> bool:
    start, end = entry.get("史略开始年"), entry.get("史略结束年")
    if not isinstance(start, int) or not isinstance(end, int):
        return True
    cat = normalize_entry_category(entry.get("史略分类", ""))
    entries = all_entries or []
    eidx = emperor_index or build_emperor_info_index()
    if placeholder and (start, end) == placeholder:
        return True
    span = end - start
    if cat in SINGLE_YEAR_CATEGORIES and start != end:
        return True
    if cat == "事略" and span > MAX_EVENT_SPAN:
        return True
    if cat in ("士臣", "民录") and span > MAX_PERSON_BIO_SPAN:
        return True
    if cat == "君纪" and span >= PLACEHOLDER_MIN_SPAN:
        return True
    if entries and _shilue_copies_person_bio(entry, entries):
        return True
    if entries and _shilue_uniform_single_year(entry, entries):
        return True
    if cat in ("士臣", "民录") and start == end:
        auto = entry.get("_auto_filled") or {}
        if not auto.get("_年LLM已确认单点"):
            return True
    if cat in ("士臣", "民录") and work_id and vol:
        pr_span = _paragraph_span(entry)
        if pr_span >= 4 and span < MIN_PERSON_SPAN_LONG_BIO:
            auto = entry.get("_auto_filled") or {}
            if not auto.get("_年LLM已确认单点"):
                return True
        if pr_span >= 5 and span < 20:
            auto = entry.get("_auto_filled") or {}
            if not auto.get("_年LLM已确认单点"):
                return True
        accession, _, _ = emperor_accession_year(entry, eidx)
        death = extract_death_year(entry_source_text(entry, work_id=work_id, vol=vol), accession)
        if death is not None and end != death:
            return True
        if death is not None and end == death and accession is not None:
            reign_years = extract_reign_years_from_text(
                entry_source_text(entry, work_id=work_id, vol=vol)
            )
            if reign_years:
                credible = [ry for ry in reign_years if ry >= 10] or reign_years
                expected = reign_year_to_absolute(min(credible), accession)
                if start != expected and expected <= end:
                    return True
    if cat == "事略" and work_id and vol:
        accession, _, _ = emperor_accession_year(entry, eidx)
        death = extract_death_year(entry_source_text(entry, work_id=work_id, vol=vol), accession)
        if death is not None and start != death:
            return True
    return False


def is_confident_year_repair(note: str) -> bool:
    """是否为脚本可确定性写入的年份（非 Step4「仅知一年」LLM 兜底）。"""
    return (note or "").split(":")[0] in _CONFIDENT_REPAIR_PREFIXES


def flag_shilue_years_for_llm(entry: dict, *, reason: str = "") -> None:
    """事略：脚本无法从原文确定性推断事件年时，交 LLM 考订。"""
    entry.pop("史略开始年", None)
    entry.pop("史略结束年", None)
    auto = dict(entry.get("_auto_filled") or {})
    hint = "事略事件年须由 LLM 据原文纪年/学界共识逐条考订，禁止批量锚定同一年。"
    if reason:
        hint += f" 脚本曾尝试：{reason}。"
    auto["_年待LLM"] = hint
    entry["_auto_filled"] = auto
    needs = list(entry.get("_needs_llm") or [])
    for field in ("史略开始年", "史略结束年"):
        if field not in needs:
            needs.append(field)
    entry["_needs_llm"] = needs


def flag_years_for_llm(entry: dict, *, reason: str = "") -> None:
    """
    士臣/民录：脚本无法从原文确定性推断生卒区间时，交 Step4 LLM 判定。
    「仅知一年 → 两年相同」须 LLM 据史料与学界共识确认，脚本不得代行。
    """
    entry.pop("史略开始年", None)
    entry.pop("史略结束年", None)
    auto = dict(entry.get("_auto_filled") or {})
    hint = (
        "生卒/活跃区间须由 LLM 据原文与学界共识判定；"
        "「仅知一年→两年相同」或帝王表兜底仅在 LLM 确认史学界无另一端年份后使用。"
    )
    if reason:
        hint += f" 脚本曾尝试：{reason}（不足确定性，未写入）。"
    auto["_年待LLM"] = hint
    entry["_auto_filled"] = auto
    needs = list(entry.get("_needs_llm") or [])
    for field in ("史略开始年", "史略结束年"):
        if field not in needs:
            needs.append(field)
    entry["_needs_llm"] = needs


def apply_years(entry: dict, start: int, end: int, note: str) -> None:
    entry["史略开始年"] = start
    entry["史略结束年"] = end
    auto = dict(entry.get("_auto_filled") or {})
    auto.pop("_年待LLM", None)
    entry["_auto_filled"] = auto or None
    if not entry["_auto_filled"]:
        entry.pop("_auto_filled", None)
    needs = [f for f in (entry.get("_needs_llm") or []) if f not in ("史略开始年", "史略结束年")]
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)
    entry["_year_repair"] = note


def repair_entry(
    entry: dict,
    data: dict,
    emperor_index: Dict[str, dict],
    work_id: str,
    vol: str,
    placeholder: Optional[Tuple[int, int]],
) -> bool:
    entries = data.get("entries", [])
    if not is_bad_year(
        entry,
        placeholder,
        work_id=work_id,
        vol=vol,
        emperor_index=emperor_index,
        all_entries=entries,
        data=data,
    ):
        return False

    cat = normalize_entry_category(entry.get("史略分类", ""))
    entry.pop("史略开始年", None)
    entry.pop("史略结束年", None)

    result = None
    if cat == "君纪":
        result = infer_junji_years(entry, emperor_index, work_id)
    elif cat == "事略":
        text = entry_source_text(entry, work_id=work_id, vol=vol)
        accession, _, emp_name = emperor_accession_year(entry, emperor_index)
        death = extract_death_year(text, accession)
        if death is not None:
            result = (death, death, f"event_death:{emp_name or '?'}")
        else:
            full_text = entry_source_text(entry, work_id=work_id, vol=vol)
            inferred = infer_shilue_years(
                entry,
                data=data,
                emperor_index=emperor_index,
                text=full_text,
            )
            if inferred:
                start, end, level, msg = inferred
                if level == "junji_accession_single_point":
                    flag_shilue_years_for_llm(entry, reason=msg)
                    return True
                result = (start, end, f"{level}:{msg}")
    elif cat in ("士臣", "民录"):
        py = infer_person_years(entry, emperor_index, work_id=work_id, vol=vol)
        if py:
            result = py
    elif cat in SINGLE_YEAR_CATEGORIES:
        sy = infer_single_year_entry(entry, emperor_index)
        if sy:
            result = sy

    if not result:
        if cat in ("士臣", "民录"):
            flag_years_for_llm(entry, reason="无法从原文推断")
            return True
        if cat == "事略":
            flag_shilue_years_for_llm(entry, reason="无法从原文推断")
            return True
        accession, _, emp = emperor_accession_year(entry, emperor_index)
        if accession is not None:
            result = (accession, accession, f"fallback_anchor:{emp or '?'}")

    if not result:
        return False

    start, end, note = result
    if cat in ("士臣", "民录") and not is_confident_year_repair(note):
        flag_years_for_llm(entry, reason=note)
        return True
    if cat in SINGLE_YEAR_CATEGORIES:
        end = start
    if cat == "事略" and end - start > MAX_EVENT_SPAN:
        end = start
    apply_years(entry, start, end, note)
    return True


def repair_skeleton(path: Path, *, dry_run: bool = False) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    work_id = work_id_from_skeleton(data, str(path))
    vol = path.name.split("_")[1]
    emperor_index = build_emperor_info_index()
    placeholder = volume_placeholder(entries)

    changed = 0
    for entry in entries:
        migrate_entry_fields(entry)
        if repair_entry(entry, data, emperor_index, work_id, vol, placeholder):
            changed += 1

    if changed and not dry_run:
        dynasty_index = build_dynasty_index_from_json()
        regime_index = build_regime_index()
        merge_all_entries(
            entries,
            data=data,
            json_path=str(path),
            emperor_index=emperor_index,
            dynasty_index=dynasty_index,
            regime_index=regime_index,
            work_id=work_id,
        )
        for entry in entries:
            migrate_entry_fields(entry)
            ph2 = volume_placeholder(entries)
            if is_bad_year(
                entry,
                ph2,
                work_id=work_id,
                vol=vol,
                emperor_index=emperor_index,
                all_entries=entries,
                data=data,
            ):
                repair_entry(entry, data, emperor_index, work_id, vol, ph2)
        for entry in entries:
            entry.pop("_year_repair", None)
        data["entries"] = entries
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    still_ph = volume_placeholder(entries)
    return {
        "path": str(path),
        "volume": data.get("volume", ""),
        "changed": changed,
        "still_placeholder": still_ph,
        "entries": len(entries),
    }


def iter_targets(annotations_dir: Path, work: str, vols: Optional[List[str]]) -> List[Path]:
    if vols:
        out = []
        for v in vols:
            hits = sorted(annotations_dir.glob(f"{work}_{v.zfill(3)}_*_skeleton.json"))
            if hits:
                out.append(hits[0])
        return out
    return sorted(annotations_dir.glob(f"{work}_*_skeleton.json"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="01史记")
    ap.add_argument("--vol", action="append", help="仅修指定卷，如 071")
    ap.add_argument("--only-placeholder", action="store_true", help="仅修命中卷级占位模式的卷")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check-format", action="store_true")
    args = ap.parse_args()

    from lib_config import paths

    ann = paths()["annotations"]
    targets = iter_targets(ann, args.work, args.vol)

    results = []
    for path in targets:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if args.only_placeholder and not volume_placeholder(data.get("entries", [])):
            continue
        results.append(repair_skeleton(path, dry_run=args.dry_run))

    ok = sum(1 for r in results if not r["still_placeholder"])
    changed = sum(r["changed"] for r in results)
    print(f"处理 {len(results)} 卷，修改条目 {changed}，清除占位 {ok}/{len(results)}")
    for r in results:
        flag = "✅" if not r["still_placeholder"] else "⚠️"
        ph = r["still_placeholder"]
        phs = f"{ph[0]}~{ph[1]}" if ph else "—"
        print(f"  {flag} {Path(r['path']).name}: 改{r['changed']}条 残留占位={phs}")

    if args.check_format and not args.dry_run:
        src = paths()["sources"] / "01史记_拆分后"
        cf = SKILL_DIR / "check_format.py"
        fails = []
        for r in results:
            code = subprocess.run(
                [sys.executable, str(cf), r["path"], "--phase", "final", "--src-dir", str(src)],
                capture_output=True,
                text=True,
            ).returncode
            if code != 0:
                fails.append(Path(r["path"]).name)
        if fails:
            print(f"check_format 失败 {len(fails)} 卷: {', '.join(fails[:10])}")
            return 1
        print("check_format final 全部通过")

    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
