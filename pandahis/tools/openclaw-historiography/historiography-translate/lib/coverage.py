"""母本逐句清单覆盖度校验（白话：信息点 + 宽松 bigram，非文言字面控词）。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.coverage_info import (
    CoverageUnit,
    body_without_intro_zone,
    build_coverage_units,
    info_point_is_classical,
)
from lib.coverage_info import CoverageUnit  # noqa: F401 — re-export for tests

# 常见虚词/高频词，不参与命中
_STOP = frozenset(
    "之乎者也矣焉於于以而则乃若其吾汝尔彼此何谁孰哉兮耶欤耳盖夫且尚又及与为在是有非无已"
    "所以于是然后因为如果但是不过已经还是就是不是这样当时后来现在什么怎么为什么"
    "一个这个那个他们我们的自己可以不能没有什么怎么为什么孔子鲁国齐国楚国卫国宋国"
    "大夫君子小人天子诸侯君主Says".split()
)

# 母本句中过泛、不应单独作为覆盖依据
_GENERIC = frozenset(
    "黄帝轩辕神农尧舜禹启汤文武诸侯百姓万民天下天子帝王".split()
)

# 长文（如禹本纪禹贡）清单条数达到此值时启用略低的通过率
_LONG_CHECKLIST_SIZE = 80


def _coverage_strict() -> bool:
    return os.environ.get("TRANSLATE_COVERAGE_STRICT", "1") != "0"


def _coverage_min_ratio(checklist_size: int) -> float:
    base = float(os.environ.get("TRANSLATE_COVERAGE_MIN_RATIO", "0.70"))
    if checklist_size >= _LONG_CHECKLIST_SIZE:
        long_ratio = float(os.environ.get("TRANSLATE_COVERAGE_MIN_RATIO_LONG", "0.65"))
        return min(base, long_ratio)
    return base


def _item_pass_threshold() -> float:
    return float(os.environ.get("TRANSLATE_COVERAGE_ITEM_MIN", "0.32"))


def _normalize_body(body: str) -> str:
    body = re.sub(r"[\s　]", "", body)
    for a, b in (
        ("老百姓", "百姓"),
        ("民众", "百姓"),
        ("稻种", "稻"),
        ("低湿", "卑湿"),
        ("低湿地", "卑湿"),
        ("欺负", "暴虐"),
        ("残害", "暴虐"),
        ("不来朝贡", "不享"),
        ("不朝贡", "不享"),
        ("不按时朝贡", "不享"),
        ("平定了就走", "平者去之"),
        ("打服了就走", "平者去之"),
        ("思维敏捷", "徇齐"),
        ("小大人", "徇齐"),
        ("透着灵气", "神灵"),
        ("开口说话", "能言"),
        ("敦厚", "敦敏"),
        ("厚道", "敦敏"),
        ("见识过人", "聪明"),
        ("聪慧", "聪明"),
        ("五行", "五气"),
        ("五谷", "五种"),
        ("丈量四方", "度四方"),
        ("驯化", "蓺"),
        ("种植", "蓺"),
        ("被封到", "降居"),
        ("封到", "降居"),
        ("镇不住场面", "世衰"),
        ("势力已经衰落", "世衰"),
        ("训练军队", "习用干戈"),
        ("拿起武器", "习用干戈"),
        ("跑来归顺", "来宾从"),
        ("转头投靠", "归轩辕"),
        ("扩张自己的地盘", "侵陵诸侯"),
        ("修养德行", "修德"),
        ("整顿军队", "振兵"),
        ("理顺", "治"),
        ("种好", "蓺"),
        ("安抚各地百姓", "抚万民"),
        ("万民", "百姓"),
        ("造反", "作乱"),
        ("不听号令", "不用帝命"),
        ("不服从", "不用帝命"),
        ("官职名称都用云", "官名皆以云"),
        ("叫『云师』", "为云师"),
        ("云来命名", "以云命"),
        ("擒获", "禽"),
        ("处死", "杀"),
        ("推举", "尊"),
        ("取代", "代"),
        ("开山凿路", "披山通道"),
        ("安稳地长住", "宁居"),
        ("走到大海边", "至于海"),
        ("分给百姓", "予众"),
        ("分给", "予"),
    ):
        body = body.replace(a, b)
    return body


def _clause_scores(text: str, body: str) -> List[float]:
    clauses = [c.strip() for c in re.split(r"[，。；]", text) if len(c.strip()) >= 3]
    scores: List[float] = []
    for clause in clauses:
        keys = _keywords(clause, max_tokens=6)
        if keys:
            scores.append(_keyword_score(keys, body))
        else:
            scores.append(_bigram_coverage(clause, body))
    return scores


def _keywords(text: str, *, max_tokens: int = 8) -> List[str]:
    s = re.sub(r"[。，、；：「」『』《》\s'\"“”]", "", text)
    tokens: List[str] = []
    segments = re.split(r"[，。、；：]", text) if re.search(r"[，。、；：]", text) else [text]
    for seg in segments:
        seg = re.sub(r"[「」『』《》\s'\"“”]", "", seg)
        if not seg:
            continue
        tokens.extend(re.findall(r"[\u4e00-\u9fff]{2,4}", seg))
    for seg in segments:
        seg = re.sub(r"[「」『』《》\s'\"“”]", "", seg)
        for i in range(len(seg) - 1):
            bi = seg[i : i + 2]
            if re.fullmatch(r"[\u4e00-\u9fff]{2}", bi):
                tokens.append(bi)
    tokens.extend(re.findall(r"\d+", s))
    out: List[str] = []
    seen: set[str] = set()
    for t in tokens:
        if t in _STOP or t in _GENERIC:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    if not out and len(s) >= 2:
        for i in range(0, min(len(s) - 1, 8), 2):
            tri = s[i : i + 2]
            if tri not in seen:
                out.append(tri)
                seen.add(tri)
    return out[:max_tokens]


def _keyword_score(keys: List[str], body: str) -> float:
    if not keys:
        return 1.0
    hits = sum(1 for k in keys if k in body)
    return hits / len(keys)


def _bigram_coverage(short: str, body: str) -> float:
    short = re.sub(r"[\s　，、；：。.!?]", "", short)
    if len(short) < 4:
        return 1.0
    grams = {short[i : i + 2] for i in range(len(short) - 1)}
    if not grams:
        return 1.0
    hits = sum(1 for g in grams if g in body)
    return hits / len(grams)


def _must_phrase_score(must_keys: List[str], body: str) -> float:
    if not must_keys:
        return 1.0
    hits = 0
    for p in must_keys:
        if p in body or f"「{p}」" in body:
            hits += 1
            continue
        if any(p in m.group(1) for m in re.finditer(r"「([^」]+)」", body) if p in m.group(1)):
            hits += 1
    return hits / len(must_keys)


def _score_baihua_info(info: str, body_n: str) -> List[float]:
    scores: List[float] = []
    clause_sc = _clause_scores(info, body_n)
    if clause_sc:
        avg = sum(clause_sc) / len(clause_sc)
        good_ratio = sum(1 for s in clause_sc if s >= 0.28) / len(clause_sc)
        scores.append(max(avg, good_ratio * 0.9))
        scores.append(max(clause_sc))
    scores.append(_bigram_coverage(info, body_n))
    scores.append(_keyword_score(_keywords(info, max_tokens=10), body_n))
    return scores


def _score_paraphrase_orig(orig: str, body_n: str) -> List[float]:
    """文言摘句：仅用 bigram / 子句宽松匹配，不做原文字面控词。"""
    scores: List[float] = [_bigram_coverage(orig, body_n)]
    clause_sc = _clause_scores(orig, body_n)
    if clause_sc:
        scores.append(max(clause_sc))
        scores.append(sum(1 for s in clause_sc if s >= 0.22) / len(clause_sc))
    return scores


def item_coverage_score(item: Dict[str, Any], body: str) -> float:
    """单条得分：白话信息点为主；文言摘句走 paraphrase 模式；必现词仅作加分。"""
    body_n = _normalize_body(body)
    info = str(item.get("信息点") or "").strip()
    orig = str(item.get("原文摘句") or item.get("text") or "").strip()
    must = item.get("必现词") or []
    must_keys = [str(p).strip() for p in must if str(p).strip()] if isinstance(must, list) else []

    scores: List[float] = []
    if info and not info_point_is_classical(info, orig):
        scores.extend(_score_baihua_info(info, body_n))
    elif orig:
        scores.extend(_score_paraphrase_orig(orig, body_n))

    if must_keys:
        scores.append(_must_phrase_score(must_keys, body_n) * 0.55)

    if not scores:
        return 1.0
    return max(scores)


def _unit_coverage_score(unit: CoverageUnit, body: str) -> float:
    if unit.kind == "group":
        return max(item_coverage_score(row, body) for row in unit.items)
    return item_coverage_score(unit.primary, body)


def verify_mother_coverage(
    detail: str,
    plan: Dict[str, Any],
    *,
    min_ratio: float | None = None,
    max_report: int = 8,
    entry_id: str = "",
    entry_name: str = "",
    work_dir: Path | None = None,
) -> Tuple[bool, List[str]]:
    """
    对照 plan「母本逐句清单」校验译文信息覆盖（概率制，非逐词硬控）。

    - 默认全局通过率 70%（长文 ≥80 条为 65%）
    - 单条及格线 32%（组内 parallel_cluster 取组内最高分）
    - 前置引入区不参与计分
    """
    errors: List[str] = []
    body = body_without_intro_zone(detail)
    checklist = plan.get("母本逐句清单") or []
    if not isinstance(checklist, list) or not checklist:
        errors.append("source plan 缺少「母本逐句清单」，无法校验母本覆盖")
        return False, errors

    min_checklist = int(os.environ.get("TRANSLATE_COVERAGE_MIN_CHECKLIST", "1"))
    if len(checklist) < min_checklist:
        errors.append(f"母本逐句清单条数不足: {len(checklist)} < {min_checklist}")
        return False, errors

    if min_ratio is None:
        min_ratio = _coverage_min_ratio(len(checklist))

    units = build_coverage_units(checklist)
    if not units:
        return True, []

    item_threshold = _item_pass_threshold()
    weak_units: List[Tuple[CoverageUnit, float]] = []
    ok_count = 0
    for unit in units:
        score = _unit_coverage_score(unit, body)
        if score >= item_threshold:
            ok_count += 1
        else:
            weak_units.append((unit, score))

    ratio = ok_count / len(units)
    if ratio < min_ratio:
        from shared.coverage_semantic import should_trigger_l2

        weak_snippets: List[Tuple[str, str, float]] = []
        for unit, sc in weak_units:
            row = unit.primary
            snippet = str(row.get("原文摘句") or row.get("信息点") or "").strip()
            weak_snippets.append((unit.label, snippet, sc))

        rescued = False
        l2_notes: List[str] = []
        if (
            entry_id
            and should_trigger_l2(
                checklist_size=len(checklist),
                ratio=ratio,
                min_ratio=min_ratio,
            )
        ):
            try:
                from lib.coverage_l2 import apply_l2_rescue, run_l2_coverage_review

                l2_report = run_l2_coverage_review(
                    entry_id=entry_id,
                    entry_name=entry_name or str(plan.get("史略名称") or ""),
                    detail=detail,
                    weak_units=weak_units,
                    l1_ratio=ratio,
                    l1_min_ratio=min_ratio,
                    work_dir=work_dir,
                )
                ok_count, rescued, l2_notes = apply_l2_rescue(
                    ok_count=ok_count,
                    units_total=len(units),
                    min_ratio=min_ratio,
                    weak_units=weak_units,
                    report=l2_report,
                )
                ratio = ok_count / len(units)
                if rescued:
                    weak_snippets = [
                        (unit.label, str(unit.primary.get("原文摘句") or "")[:48], sc)
                        for unit, sc in weak_units
                        if unit.label not in l2_report.conveyed_ids
                    ]
            except Exception as exc:
                l2_notes.append(f"L2 语义复核失败（仍按 L1 判定）: {exc}")

        if ratio >= min_ratio and rescued:
            info = (
                f"母本覆盖（L1+L2）: {ok_count}/{len(units)} 单元命中 ({ratio:.0%} ≥ {min_ratio:.0%})"
            )
            if l2_notes:
                info += "；" + l2_notes[0]
            return True, [f"[info] {info}"]

        msgs = [
            f"母本覆盖不足: {ok_count}/{len(units)} 单元命中 "
            f"({ratio:.0%} < {min_ratio:.0%}；单条及格线 {item_threshold:.0%})"
        ]
        for sid, snippet, sc in weak_snippets[:max_report]:
            msgs.append(f"  疑似漏译 {sid} [{sc:.0%}] {snippet[:48]}")
        if len(weak_snippets) > max_report:
            msgs.append(f"  …另有 {len(weak_snippets) - max_report} 单元弱覆盖")
        for note in l2_notes:
            msgs.append(f"  {note}")
        if _coverage_strict():
            errors.extend(msgs)
        else:
            errors.extend([f"[warn] {m}" for m in msgs[:3]])
            return True, errors
    return len(errors) == 0, errors


# 兼容旧调用
def sentence_coverage_score(orig: str, body: str) -> float:
    return item_coverage_score({"原文摘句": orig, "信息点": ""}, body)
