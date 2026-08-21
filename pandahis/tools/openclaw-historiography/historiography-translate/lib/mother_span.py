"""母本段落覆盖：拦润色时连续整段情节蒸发。

只做程序比对，不替代语义覆盖账本。允许改写、压缩描写；
连续 ≥2 个带锚点的母本段对不上，或单段过长且专名锚点全失，视为整段漏。
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
import os
import re
from typing import Dict, Iterable, List, Sequence, Tuple

_REF_SEPS = ("\n\n参考著作\n", "\n参考著作\n", "\n\n参考著作", "\n参考著作：")

COMMON = {
    "汉王",
    "高祖",
    "沛公",
    "项羽",
    "刘邦",
    "项王",
    "怀王",
    "皇帝",
    "天子",
    "吕后",
    "太公",
    "韩信",
    "张耳",
    "张良",
    "萧何",
    "曹参",
    "樊哙",
    "英布",
    "黥布",
    "彭越",
    "章邯",
    "取天下",
    "得天下",
    "分天下",
    "有天下",
    "平天下",
    "定天下",
    "诸侯",
    "天下",
    "于是",
    "因此",
    "这个",
    "那个",
    "没有",
    "可以",
    "已经",
    "后来",
    "时候",
    "地方",
    "东门",
    "西门",
    "家人",
    "自杀",
    "举兵",
    "城郭",
    "子女",
    "齐兵",
    "粮食",
    "受命",
    "将军",
    "汉军",
    "楚军",
    "秦军",
    "汉兵",
    "楚兵",
    "关中",
    "巴蜀",
}

FUNC = set(
    "的了在是其之乎者也矣焉於于曰而则以与及乃则此故夫若或又都把被从到对就还没已不"
    "一二三四五六七八九十百千万这那所可却但如因故彼何岂未无有为能会要很更最就还将便即皆亦复"
)

_MIN_HOLE = 2
_LONG_ISOLATED = 120
_MAX_MDF = 4
_MAX_SRC = 12


@dataclass(frozen=True)
class MotherSpan:
    index: int
    text: str
    primaries: Tuple[str, ...]
    names: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SpanHole:
    start: int
    end: int
    spans: Tuple[MotherSpan, ...]


def span_gate_enabled() -> bool:
    return (os.environ.get("TRANSLATE_MOTHER_SPAN_GATE") or "1").strip() not in {
        "0",
        "false",
        "no",
        "off",
    }


def strip_reference_section(text: str) -> str:
    body = str(text or "")
    for sep in _REF_SEPS:
        if sep in body:
            return body.split(sep, 1)[0].rstrip()
    return body.rstrip()


def split_reference_section(text: str) -> Tuple[str, str]:
    body = str(text or "")
    for sep in _REF_SEPS:
        if sep in body:
            head, tail = body.split(sep, 1)
            return head.rstrip(), sep + tail
    return body.rstrip(), ""


def split_mother_spans(mother: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", strip_reference_section(mother)) if p.strip()]


def _hanzi_only(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fff]", "", text)


def _is_hanzi(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff"


def _blocked(gram: str) -> bool:
    if not gram or gram in COMMON:
        return True
    if gram[0] in FUNC:
        return True
    for common in COMMON:
        if gram.startswith(common):
            return True
        # 「取天」是「取天下」残片，不能当专名
        if len(gram) >= 2 and common.startswith(gram):
            return True
    return False


def _gram_df(spans: Sequence[str]) -> Dict[str, int]:
    df: Dict[str, int] = defaultdict(int)
    for sp in spans:
        s = _hanzi_only(sp)
        seen = set()
        for n in range(2, 5):
            for i in range(0, max(0, len(s) - n + 1)):
                seen.add(s[i : i + n])
        for g in seen:
            df[g] += 1
    return df


def _greedy_names(text: str, *, mdf: Dict[str, int], source: str) -> List[str]:
    names: List[str] = []
    i = 0
    src = source or ""
    while i < len(text):
        ch = text[i]
        if not _is_hanzi(ch):
            i += 1
            continue
        taken = None
        for n in (4, 3, 2):
            g = text[i : i + n]
            if len(g) < n or not all(_is_hanzi(c) for c in g):
                continue
            if _blocked(g):
                continue
            if src:
                cnt = src.count(g)
                if cnt == 0 or cnt > _MAX_SRC:
                    continue
            if mdf.get(g, 0) > _MAX_MDF:
                continue
            if n == 2 and mdf.get(g, 0) > 1:
                continue
            taken = g
            break
        if taken:
            names.append(taken)
            i += len(taken)
        else:
            i += 1
    return names


def _uniq(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in items:
        if x in seen or x in COMMON:
            continue
        seen.add(x)
        out.append(x)
    return out


def analyze_mother_spans(mother: str, source_original: str = "") -> List[MotherSpan]:
    raw = split_mother_spans(mother)
    mdf = _gram_df(raw)
    source = str(source_original or "")

    def primaries_of(sp: str) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        names = tuple(_uniq(_greedy_names(sp, mdf=mdf, source=source)))
        strong = [n for n in names if len(n) >= 3]
        pool = list(strong or names)
        pool.sort(
            key=lambda a: (
                mdf.get(a, 99),
                -len(a),
                source.count(a) if source else 0,
                a,
            )
        )
        return tuple(pool[:2]), names

    out: List[MotherSpan] = []
    for i, sp in enumerate(raw, start=1):
        primaries, names = primaries_of(sp)
        out.append(MotherSpan(index=i, text=sp, primaries=primaries, names=names))
    return out


def _span_hit(span: MotherSpan, detail: str, mdf: Dict[str, int]) -> bool:
    if not span.primaries:
        return True
    for p in span.primaries:
        if p in detail:
            return True
        if len(p) >= 4:
            for i in range(0, len(p) - 2):
                sub = p[i : i + 3]
                if _blocked(sub):
                    continue
                if mdf.get(sub, 99) > 1:
                    continue
                if sub in detail:
                    return True
        if len(p) == 3:
            for sub in (p[:2], p[1:]):
                if _blocked(sub) or mdf.get(sub, 99) > 1:
                    continue
                if sub in detail:
                    return True
    for n in span.names:
        if len(n) == 2 and mdf.get(n, 99) == 1 and n in detail:
            return True
    return False


def _missed_spans(
    spans: Sequence[MotherSpan], detail: str, mdf: Dict[str, int]
) -> List[MotherSpan]:
    body = strip_reference_section(detail)
    missed: List[MotherSpan] = []
    for sp in spans:
        if sp.primaries and not _span_hit(sp, body, mdf):
            missed.append(sp)
    return missed


def missing_mother_span_holes(
    mother: str,
    detail: str,
    source_original: str = "",
) -> List[SpanHole]:
    """连续对不上的母本段。孤立短段忽略（允许压缩改写）。"""
    if not span_gate_enabled():
        return []
    spans = analyze_mother_spans(mother, source_original)
    if not spans:
        return []
    mdf = _gram_df([s.text for s in spans])
    missed = _missed_spans(spans, detail, mdf)
    if not missed:
        return []
    by_idx = {s.index: s for s in missed}
    ids = [s.index for s in missed]
    runs: List[Tuple[int, int]] = []
    start = end = ids[0]
    for x in ids[1:]:
        if x == end + 1:
            end = x
        else:
            runs.append((start, end))
            start = end = x
    runs.append((start, end))

    holes: List[SpanHole] = []
    hole_ids: set[int] = set()
    for a, b in runs:
        width = b - a + 1
        if width >= _MIN_HOLE:
            chunk = tuple(by_idx[i] for i in range(a, b + 1) if i in by_idx)
            if chunk:
                holes.append(SpanHole(start=a, end=b, spans=chunk))
                hole_ids.update(range(a, b + 1))
    for sp in missed:
        if sp.index in hole_ids:
            continue
        if len(_hanzi_only(sp.text)) < _LONG_ISOLATED:
            continue
        if not any(len(p) >= 3 for p in sp.primaries):
            continue
        holes.append(SpanHole(start=sp.index, end=sp.index, spans=(sp,)))
    holes.sort(key=lambda h: h.start)
    return holes


def format_span_checklist(mother: str, source_original: str = "", *, max_spans: int = 180) -> str:
    spans = analyze_mother_spans(mother, source_original)
    lines = ["母本段落锚点（可改写压缩措辞，禁止整段删情节）："]
    for sp in spans[:max_spans]:
        if not sp.primaries:
            continue
        anchors = "／".join(sp.primaries)
        lines.append(f"#{sp.index} {anchors}")
    if len(spans) > max_spans:
        lines.append(f"…共 {len(spans)} 段")
    return "\n".join(lines)


def format_span_hole_errors(holes: Sequence[SpanHole]) -> List[str]:
    errs: List[str] = []
    for hole in holes:
        anchors: List[str] = []
        for sp in hole.spans:
            anchors.extend(list(sp.primaries[:1]))
        shown = "、".join(anchors[:6]) or "（无锚点）"
        preview = hole.spans[0].text.replace("\n", " ")[:40]
        if hole.start == hole.end:
            loc = f"第{hole.start}段"
        else:
            loc = f"第{hole.start}–{hole.end}段"
        errs.append(
            f"整段漏：母本{loc}在成稿中对不上（锚点：{shown}）。"
            f"润色可删字压缩描写，禁止整段删情节。段首：{preview}"
        )
    return errs


@dataclass(frozen=True)
class BackfillSlot:
    """漏段补洞夹缝：程序只定位，不往成稿里塞母本原文。"""

    hole: SpanHole
    after_para_index: int  # 成稿段 0-based；插在该段之后（-1=文首）
    before_para_index: int  # 成稿段 0-based；插在该段之前（len=文末）
    before_excerpt: str
    after_excerpt: str
    mother_block: str
    anchors: Tuple[str, ...]


def _location_tokens(span: MotherSpan, mdf: Dict[str, int]) -> List[str]:
    """定位夹缝只用母本内稀有词（mdf==1），含 names，避免跨段复现专名指错位置。"""
    toks: List[str] = []
    for p in list(span.primaries) + list(span.names):
        if len(p) < 2 or mdf.get(p, 99) != 1:
            continue
        if p in toks or p in COMMON:
            continue
        toks.append(p)
    if toks:
        return toks
    return [p for p in span.primaries if p]


def _para_hits_for_locate(span: MotherSpan, para: str, mdf: Dict[str, int]) -> bool:
    return any(t in para for t in _location_tokens(span, mdf))


def _first_hit_index(
    span: MotherSpan, dparas: Sequence[str], mdf: Dict[str, int]
) -> int | None:
    for i, para in enumerate(dparas):
        if _para_hits_for_locate(span, para, mdf):
            return i
    return None


def _last_hit_before(
    span: MotherSpan,
    dparas: Sequence[str],
    mdf: Dict[str, int],
    *,
    before: int | None,
) -> int | None:
    """上一覆盖段在成稿中的落点：取 next 之前的最后一次，避免同名锚点偏到后文。"""
    limit = before if before is not None else len(dparas)
    found: int | None = None
    for i in range(0, max(0, limit)):
        if _para_hits_for_locate(span, dparas[i], mdf):
            found = i
    return found


def _clip_excerpt(text: str, *, limit: int = 160) -> str:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    if len(s) <= limit:
        return s
    return s[: limit // 2] + "…" + s[-(limit // 2) :]


def locate_span_backfill_slots(
    detail: str,
    mother: str,
    source_original: str = "",
) -> List[BackfillSlot]:
    """为每个漏洞找成稿夹缝（上一覆盖段之后、下一覆盖段之前）。"""
    holes = missing_mother_span_holes(mother, detail, source_original)
    if not holes:
        return []
    spans = analyze_mother_spans(mother, source_original)
    mdf = _gram_df([s.text for s in spans])
    body, _refs = split_reference_section(detail)
    dparas = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not dparas:
        return [
            BackfillSlot(
                hole=h,
                after_para_index=-1,
                before_para_index=0,
                before_excerpt="（文首）",
                after_excerpt="（文末）",
                mother_block="\n\n".join(s.text for s in h.spans),
                anchors=tuple(
                    a for s in h.spans for a in s.primaries[:1] if a
                ),
            )
            for h in holes
        ]

    slots: List[BackfillSlot] = []
    for hole in holes:
        next_i: int | None = None
        for nxt in range(hole.end + 1, len(spans) + 1):
            sp = spans[nxt - 1]
            # 下一段本身已覆盖才可作为夹缝下界
            if not _span_hit(sp, body, mdf):
                continue
            next_i = _first_hit_index(sp, dparas, mdf)
            if next_i is not None:
                break

        prev_i: int | None = None
        for prev in range(hole.start - 1, 0, -1):
            sp = spans[prev - 1]
            if not _span_hit(sp, body, mdf):
                continue
            prev_i = _last_hit_before(sp, dparas, mdf, before=next_i)
            if prev_i is not None:
                break

        # 下界优先：紧贴下一覆盖段之前（润色常把大战扩成多段，prev 会偏早）
        before_idx = next_i if next_i is not None else len(dparas)
        if next_i is not None:
            after_idx = next_i - 1
        else:
            after_idx = prev_i if prev_i is not None else -1

        if before_idx < len(dparas) and after_idx >= before_idx:
            after_idx = before_idx - 1

        before_ex = (
            _clip_excerpt(dparas[after_idx]) if after_idx >= 0 else "（文首）"
        )
        after_ex = (
            _clip_excerpt(dparas[before_idx])
            if before_idx < len(dparas)
            else "（文末）"
        )
        anchors = tuple(a for s in hole.spans for a in s.primaries[:1] if a)
        slots.append(
            BackfillSlot(
                hole=hole,
                after_para_index=after_idx,
                before_para_index=before_idx,
                before_excerpt=before_ex,
                after_excerpt=after_ex,
                mother_block="\n\n".join(s.text for s in hole.spans),
                anchors=anchors,
            )
        )
    return slots


def format_span_hole_retry_note(
    holes: Sequence[SpanHole],
    *,
    slots: Sequence[BackfillSlot] | None = None,
) -> str:
    """补洞提示：给夹缝 + 母本情节，禁止程序塞原文、禁止保留概括顶替句。"""
    use_slots = list(slots) if slots is not None else []
    if not use_slots and not holes:
        return ""
    parts = [
        "上轮润色删掉了连续母本情节。不要整篇重写。",
        "只在标明的成稿夹缝里补回情节，改成前后一致的说书口吻。",
        "可以压缩措辞、可以补 L3/L4；禁止再删这些情节；禁止改动夹缝外的前后文。",
        "若夹缝后文或附近已有一句概括顶替（如「韩信已经平定了魏地、赵地…」），",
        "须删掉或改写该概括，改成完整情节，禁止详写+概括双写。",
        "",
    ]
    if use_slots:
        for i, slot in enumerate(use_slots, 1):
            hole = slot.hole
            loc = (
                f"第{hole.start}段"
                if hole.start == hole.end
                else f"第{hole.start}–{hole.end}段"
            )
            anchors = "、".join(slot.anchors[:8]) or "（见母本）"
            parts.append(f"### 补洞 {i}｜母本{loc}｜锚点：{anchors}")
            parts.append(f"插在成稿「前段」之后、「后段」之前：")
            parts.append(f"【前段】{slot.before_excerpt}")
            parts.append(f"【后段】{slot.after_excerpt}")
            parts.append("【须补回的母本情节（改口吻，勿整段誊抄）】")
            parts.append(slot.mother_block)
            parts.append("")
    else:
        for hole in holes:
            parts.append(f"—— 母本第{hole.start}–{hole.end}段 ——")
            for sp in hole.spans:
                parts.append(f"#{sp.index} {sp.text}")
                parts.append("")
    return "\n".join(parts).rstrip()


def splice_missing_mother_spans(
    detail: str,
    mother: str,
    source_original: str = "",
) -> Tuple[str, List[SpanHole]]:
    """兼容旧测试：程序插回仅作调试；生产路径用 locate_span_backfill_slots。

    插点用「下一覆盖段之前 / 上一覆盖段在 next 之前的最后一次」，避免同名锚点落到后文。
    """
    slots = locate_span_backfill_slots(detail, mother, source_original)
    if not slots:
        return detail, []
    body, refs = split_reference_section(detail)
    dparas = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not dparas:
        filled = "\n\n".join(s.mother_block for s in slots)
        return (filled + (("\n\n" + refs.lstrip("\n")) if refs else "")), [
            s.hole for s in slots
        ]

    ops: List[Tuple[int, str]] = []
    for slot in slots:
        ops.append((slot.after_para_index, slot.mother_block))
    ops.sort(key=lambda x: x[0], reverse=True)
    new = list(dparas)
    for after, block in ops:
        idx = after + 1
        if idx <= 0:
            new.insert(0, block)
        elif idx >= len(new):
            new.append(block)
        else:
            new.insert(idx, block)
    rebuilt = "\n\n".join(new)
    if refs:
        rebuilt = rebuilt.rstrip() + "\n\n" + refs.lstrip("\n")
    return rebuilt, [s.hole for s in slots]
