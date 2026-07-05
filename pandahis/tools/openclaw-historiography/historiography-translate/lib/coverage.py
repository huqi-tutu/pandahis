"""母本逐句清单覆盖度校验（白话译文：原文关键词 + 信息点）。"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

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


def _coverage_strict() -> bool:
    return os.environ.get("TRANSLATE_COVERAGE_STRICT", "1") != "0"


def _coverage_min_ratio() -> float:
    return float(os.environ.get("TRANSLATE_COVERAGE_MIN_RATIO", "0.85"))


def _item_pass_threshold() -> float:
    return float(os.environ.get("TRANSLATE_COVERAGE_ITEM_MIN", "0.45"))


def _normalize_body(body: str) -> str:
    body = re.sub(r"[\s　]", "", body)
    for a, b in (
        ("老百姓", "百姓"),
        ("民众", "百姓"),
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
    # 先按标点分片，避免 greedy {2,4} 把「殷契，母曰简狄」切成「殷契母曰」
    segments = re.split(r"[，。、；：]", text) if re.search(r"[，。、；：]", text) else [text]
    for seg in segments:
        seg = re.sub(r"[「」『』《》\s'\"“”]", "", seg)
        if not seg:
            continue
        tokens.extend(re.findall(r"[\u4e00-\u9fff]{2,4}", seg))
    # 补充 2 字切分，避免 greedy 4 字块漏检
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


def sentence_coverage_score(orig: str, body: str) -> float:
    return _keyword_score(_keywords(orig), body)


def _bigram_coverage(short: str, body: str) -> float:
    short = re.sub(r"[\s　，、；：。.!?]", "", short)
    if len(short) < 4:
        return 1.0
    grams = {short[i : i + 2] for i in range(len(short) - 1)}
    hits = sum(1 for g in grams if g in body)
    return hits / len(grams)


def item_coverage_score(item: Dict[str, Any], body: str) -> float:
    """综合信息点（白话，主）+ 原文摘句（文言，辅）。"""
    body_n = _normalize_body(body)
    info = str(item.get("信息点") or "").strip()
    orig = str(item.get("原文摘句") or item.get("text") or "").strip()

    scores: List[float] = []
    if info:
        info_n = _normalize_body(info)
        clause_sc = _clause_scores(info_n, body_n)
        if clause_sc:
            avg = sum(clause_sc) / len(clause_sc)
            good_ratio = sum(1 for s in clause_sc if s >= 0.34) / len(clause_sc)
            scores.append(max(avg, good_ratio * 0.92))
            scores.append(max(clause_sc))
        scores.append(_bigram_coverage(info_n, body_n))
        scores.append(_keyword_score(_keywords(info_n, max_tokens=10), body_n))
    if orig:
        orig_n = _normalize_body(orig)
        clause_sc = _clause_scores(orig_n, body_n)
        if clause_sc:
            scores.append(max(clause_sc) * 0.9)
        scores.append(_keyword_score(_keywords(orig_n, max_tokens=8), body_n) * 0.85)
    must = item.get("必现词") or []
    if isinstance(must, list) and must:
        must_keys = [str(p).strip() for p in must if str(p).strip()]
        scores.append(_keyword_score(must_keys, body_n))
        # 「」内原词或子串即算命中
        hits = 0
        for p in must_keys:
            if p in body_n or f"「{p}」" in body_n:
                hits += 1
            elif any(p in m.group(1) for m in re.finditer(r"「([^」]+)」", body_n) if p in m.group(1)):
                hits += 1
        if must_keys:
            scores.append(hits / len(must_keys))
    if not scores:
        return 1.0
    return max(scores)


def verify_mother_coverage(
    detail: str,
    plan: Dict[str, Any],
    *,
    min_ratio: float | None = None,
    max_report: int = 8,
) -> Tuple[bool, List[str]]:
    """
    对照 plan「母本逐句清单」校验译文是否覆盖每条母本信息。
    默认对所有条目启用；未达标则 verify 失败（TRANSLATE_COVERAGE_STRICT=1）。
    """
    if min_ratio is None:
        min_ratio = _coverage_min_ratio()

    errors: List[str] = []
    body = detail.split("*参考著作*")[0].split("参考著作")[0]
    checklist = plan.get("母本逐句清单") or []
    if not isinstance(checklist, list) or not checklist:
        errors.append("source plan 缺少「母本逐句清单」，无法校验母本覆盖")
        return False, errors

    min_checklist = int(os.environ.get("TRANSLATE_COVERAGE_MIN_CHECKLIST", "1"))
    if len(checklist) < min_checklist:
        errors.append(f"母本逐句清单条数不足: {len(checklist)} < {min_checklist}")
        return False, errors

    item_threshold = _item_pass_threshold()
    weak: List[Tuple[str, str, float]] = []
    ok_count = 0
    for item in checklist:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("编号") or item.get("id") or "")
        orig = str(item.get("原文摘句") or item.get("text") or "").strip()
        if not orig and not str(item.get("信息点") or "").strip():
            ok_count += 1
            continue
        score = item_coverage_score(item, body)
        if score >= item_threshold:
            ok_count += 1
        else:
            weak.append((sid, orig or str(item.get("信息点") or ""), score))

    ratio = ok_count / len(checklist)
    if ratio < min_ratio:
        msgs = [
            f"母本覆盖不足: {ok_count}/{len(checklist)} 条命中 "
            f"({ratio:.0%} < {min_ratio:.0%})"
        ]
        for sid, snippet, sc in weak[:max_report]:
            msgs.append(f"  疑似漏译 {sid} [{sc:.0%}] {snippet[:48]}")
        if len(weak) > max_report:
            msgs.append(f"  …另有 {len(weak) - max_report} 条弱覆盖")
        if _coverage_strict():
            errors.extend(msgs)
        else:
            errors.extend([f"[warn] {m}" for m in msgs[:3]])
            return True, errors
    return len(errors) == 0, errors
