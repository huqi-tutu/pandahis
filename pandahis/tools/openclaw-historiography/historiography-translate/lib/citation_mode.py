"""母本摘句引用粒度：叙事句 / 并列句群 / 世系 / 品评 + 经典引用候选。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 旧版提示（落盘后会被替换）
_LEGACY_HINTS = (
    "叙事句：专名与数字融入白话叙述；「」用于完整摘句、对话或并列句群。",
    "并列句群：先整段或整簇引用原文，再作一段白话解释。",
    "世系句：整句引用后串讲谱系。",
    "品评句：对称句群整段引用后作一段品评。",
)


def detect_citation_mode(orig: str) -> str:
    """返回 narrative | parallel_cluster | genealogy | appraisal。"""
    s = orig.strip()
    if not s:
        return "narrative"

    # 世系：X父曰Y，Y父曰Z
    if len(re.findall(r"父曰|母曰|生曰|孙曰", s)) >= 2:
        return "genealogy"

    # 并列排比：多个「，」分隔的 2-6 字短语
    clauses = [c.strip() for c in re.split(r"[，,]", s) if c.strip()]
    short_clauses = [c for c in clauses if 2 <= len(c) <= 8]
    if len(short_clauses) >= 3 and len(short_clauses) >= len(clauses) * 0.6:
        return "parallel_cluster"

    # 品评 dense：静渊以有谋；聪以知远
    if re.search(r"[\u4e00-\u9fff]{1,4}以[\u4e00-\u9fff]{1,6}", s) and len(clauses) >= 2:
        return "appraisal"

    return "narrative"


def citation_mode_hint(mode: str) -> str:
    """写法提示：默认白话；「」仅金句等；用后融入接叙。"""
    hints = {
        "narrative": (
            "叙事句：专名与数字融入白话。"
            "白话对话用弯引号“”；直角「」仅当本句含须保留的史料原文金句。"
            "用「」后优先接叙融合；反对同义 `「原文」——白话` 作业体。"
        ),
        "parallel_cluster": (
            "并列/排比：默认整段白话叙述。"
            "仅当气势不可替代时，用直角「」引**史料原文**后白话接叙（可点明增量，勿同义再译主腔）。"
            "禁止先贴原文再整段对照翻译。"
        ),
        "genealogy": (
            "世系句：默认白话串讲谱系；一般不引原文。"
            "仅罕见固定称谓需保留原文时用直角「」。"
        ),
        "appraisal": (
            "品评句：优先直角「」引**原文品评**，随后白话说明其判断力；"
            "禁止「」内已是白话；破折号仅可偶发点破增量，勿同义回声。"
        ),
    }
    return hints.get(mode, hints["narrative"])


def classic_quote_soft_quota(m_count: int) -> int:
    """长篇约 10–15、短篇更少；可用 TRANSLATE_CLASSIC_QUOTE_QUOTA 覆盖。"""
    env = os.environ.get("TRANSLATE_CLASSIC_QUOTE_QUOTA", "").strip()
    if env.isdigit():
        return max(0, int(env))
    n = max(0, int(m_count))
    if n <= 0:
        return 0
    if n < 40:
        return max(2, min(8, n // 4 or 2))
    # 467 → ~13
    return max(8, min(15, n // 35))


def score_classic_quote_candidate(orig: str, mode: str) -> int:
    """分数越高越宜作经典原文镶嵌；0 = 不宜。"""
    s = str(orig or "").strip()
    if len(s) < 10:
        return 0
    score = 0
    if mode == "appraisal":
        score += 5
    elif mode == "parallel_cluster":
        score += 4
    elif mode == "narrative":
        score += 1

    if "兮" in s or "歌" in s:
        score += 5
    if re.search(r"[曰云言][：「\"].{6,}", s) or ("曰" in s and len(s) >= 16):
        score += 3
    # 品质/判断密集
    if re.search(
        r"仁|德|智|勇|天命|拨乱|威加|大丈夫|约法|三章|终不|莫能|咸|皆",
        s,
    ):
        score += 2
    if 16 <= len(s) <= 72:
        score += 1
    if len(s) > 100:
        score -= 2  # 过长整段不宜整簇硬引
    return max(0, score)


def mark_classic_quote_candidates(checklist: List[Dict[str, Any]]) -> int:
    """为清单标注「经典引用候选」；按软配额保留最高分若干条。返回标 true 条数。"""
    scored: List[Tuple[int, int, Dict[str, Any]]] = []
    for i, item in enumerate(checklist):
        if not isinstance(item, dict):
            continue
        orig = str(item.get("原文摘句") or "").strip()
        mode = str(item.get("引用粒度") or detect_citation_mode(orig))
        sc = score_classic_quote_candidate(orig, mode)
        item["经典引用候选"] = False
        if sc > 0:
            scored.append((sc, i, item))

    scored.sort(key=lambda x: (-x[0], x[1]))
    quota = classic_quote_soft_quota(len(checklist))
    marked = 0
    for sc, _i, item in scored[:quota]:
        if sc < 3:  # 门槛：至少有一定「金句感」
            continue
        item["经典引用候选"] = True
        marked += 1
        tip = (
            "【经典引用候选】本句宜用直角「」镶嵌史料原文，再白话融入接叙；"
            "忌同义 `——` 再译主腔（偶发增量破折号可用）；非候选句勿为凑数而引。"
        )
        prev = str(item.get("母本提示") or "").strip()
        if tip not in prev:
            item["母本提示"] = f"{prev}；{tip}" if prev else tip
    return marked


def _strip_legacy_hints(prev: str) -> str:
    out = prev
    for legacy in _LEGACY_HINTS:
        out = out.replace(legacy, "")
    out = re.sub(r"；{2,}", "；", out).strip("；").strip()
    return out


def enrich_checklist_citation_modes(checklist: List[Dict[str, Any]]) -> None:
    for item in checklist:
        if not isinstance(item, dict):
            continue
        orig = str(item.get("原文摘句") or "").strip()
        if not orig:
            continue
        mode = detect_citation_mode(orig)
        item["引用粒度"] = mode
        hint = citation_mode_hint(mode)
        prev = _strip_legacy_hints(str(item.get("母本提示") or "").strip())
        # 去掉旧提示后写入新提示（避免重复堆叠）
        if hint not in prev:
            item["母本提示"] = f"{prev}；{hint}" if prev else hint
        else:
            item["母本提示"] = prev or hint
    mark_classic_quote_candidates(checklist)


def count_short_quote_density(text: str, *, threshold_len: int = 4) -> int:
    """统计过短「」引用次数（≤threshold_len 字）。"""
    return sum(
        1
        for m in re.finditer(r"「([^」]+)」", text)
        if len(m.group(1).strip()) <= threshold_len
    )


def count_classic_corner_quotes(text: str, *, min_len: int = 6) -> int:
    """统计足够长的直角「」摘句（视作经典原文引用）。"""
    return sum(
        1
        for m in re.finditer(r"「([^」]+)」", str(text or ""))
        if len(m.group(1).strip()) >= min_len
    )


def classic_quote_candidate_count(plan: Dict[str, Any] | None) -> int:
    if not plan:
        return 0
    cl = plan.get("母本逐句清单") or []
    if not isinstance(cl, list):
        return 0
    return sum(
        1
        for x in cl
        if isinstance(x, dict) and x.get("经典引用候选") is True
    )


_CURLY_QUOTE_RE = re.compile(r"“([^”]{2,240})”")
_CORNER_QUOTE_RE = re.compile(r"「([^」]{2,240})」")
# 白话痕迹：有这些则不把弯引判成「未译原文」；有这些且低原文重合则直角应改弯引
_BAIHUA_MARKERS_RE = re.compile(
    r"(的|了|吗|呢|吧|着|过|这|那|什么|怎么|不是|没有|已经|可以|应该|大家|我们|你们|"
    r"咱们|就是|还是|不过|然后|于是|接着|谁知|哪知|好嘛|搁今天|听说|如今|现在)"
)
# 文言痕迹：弯引内若有且无白话痕迹，亦视为原文对白
_WENYAN_MARKERS_RE = re.compile(
    r"(矣|焉|哉|耶|乎|耳|尔|勿|毋|岂|庶几|足下|不宜|何畏|僄悍|翘足|阬|皆阬|"
    r"无遗类|大人长者|无道秦|反国之王|拨乱世反之正|"
    r"鸿渐|元封|建元|元光|元狩|泰一|封禅|罪己)"
)


def _plain_han(s: str) -> str:
    return re.sub(r"[^\u4e00-\u9fff0-9]", "", s or "")


def mother_plain_blob(
    plan: Dict[str, Any] | None,
    source_original: str = "",
) -> str:
    """对照物：成稿「史料原文」全文优先，plan 摘句作补充（去标点）。"""
    parts: List[str] = []
    if source_original:
        parts.append(str(source_original))
    if plan:
        for it in plan.get("母本逐句清单") or []:
            if isinstance(it, dict) and it.get("原文摘句"):
                parts.append(str(it["原文摘句"]))
    return _plain_han("".join(parts))


def classic_candidate_plain_blob(plan: Dict[str, Any] | None) -> str:
    """经典引用候选的原文摘句（保护其直角「」不被改成弯引）。"""
    if not plan:
        return ""
    parts: List[str] = []
    for it in plan.get("母本逐句清单") or []:
        if not isinstance(it, dict) or it.get("经典引用候选") is not True:
            continue
        if it.get("原文摘句"):
            parts.append(str(it["原文摘句"]))
    return _plain_han("".join(parts))


def _longest_source_overlap(span_plain: str, mother_blob: str) -> int:
    """span 与母本最长连续重合字数。"""
    if not span_plain or not mother_blob:
        return 0
    if span_plain in mother_blob:
        return len(span_plain)
    n = len(span_plain)
    for length in range(min(n, 80), 3, -1):
        for i in range(0, n - length + 1):
            if span_plain[i : i + length] in mother_blob:
                return length
    return 0


def is_untranslated_source_span(
    inner: str,
    mother_blob: str = "",
    *,
    min_len: int = 4,
    min_ratio: float = 0.7,
) -> bool:
    """弯引内容是否实为未译史料原文（应改用「」）。"""
    s = (inner or "").strip()
    sp = _plain_han(s)
    if len(sp) < min_len:
        return False
    # 已明显白话且无文言 → 不是「未译原文」
    if _BAIHUA_MARKERS_RE.search(s) and not _WENYAN_MARKERS_RE.search(s):
        # 但整段就是母本子串（如年号夹在白话句）仍算原文标签误用
        if mother_blob and sp in mother_blob and len(sp) <= 12:
            return True
        return False
    if mother_blob:
        # 完整命中母本（含短年号/篇名）
        if sp in mother_blob:
            return True
        overlap = _longest_source_overlap(sp, mother_blob)
        if overlap / max(1, len(sp)) >= min_ratio:
            return True
    # 无母本或重合不足时：文言痕迹且几乎无白话助词
    if _WENYAN_MARKERS_RE.search(s) and not _BAIHUA_MARKERS_RE.search(s):
        return True
    return False


def is_vernacular_corner_span(
    inner: str,
    mother_blob: str = "",
    classic_blob: str = "",
    *,
    min_len: int = 4,
) -> bool:
    """直角「」内是否实为白话译文（应改用“”）。

    保守：须有白话痕迹，且与母本/经典候选重合不高。
    """
    s = (inner or "").strip()
    sp = _plain_han(s)
    if len(sp) < min_len:
        return False
    if not _BAIHUA_MARKERS_RE.search(s):
        return False
    # 保护：像未译原文 / 经典候选
    if is_untranslated_source_span(s, mother_blob, min_len=min_len):
        return False
    if classic_blob:
        ov = _longest_source_overlap(sp, classic_blob)
        if ov / max(1, len(sp)) >= 0.55:
            return False
    if mother_blob:
        ov = _longest_source_overlap(sp, mother_blob)
        if ov / max(1, len(sp)) >= 0.55:
            return False
    return True


def iter_curly_source_spans(
    text: str,
    plan: Dict[str, Any] | None = None,
    *,
    source_original: str = "",
    min_len: int = 4,
    min_ratio: float = 0.7,
) -> List[str]:
    """返回正文中应用「」却误用“”的原文片段（inner）。"""
    blob = mother_plain_blob(plan, source_original)
    out: List[str] = []
    for m in _CURLY_QUOTE_RE.finditer(text or ""):
        inner = m.group(1)
        if is_untranslated_source_span(
            inner, blob, min_len=min_len, min_ratio=min_ratio
        ):
            out.append(inner)
    return out


def iter_corner_vernacular_spans(
    text: str,
    plan: Dict[str, Any] | None = None,
    *,
    source_original: str = "",
    min_len: int = 4,
) -> List[str]:
    """返回正文中应用“”却误用「」的白话片段（inner）。"""
    blob = mother_plain_blob(plan, source_original)
    classic = classic_candidate_plain_blob(plan)
    out: List[str] = []
    for m in _CORNER_QUOTE_RE.finditer(text or ""):
        inner = m.group(1)
        if is_vernacular_corner_span(inner, blob, classic, min_len=min_len):
            out.append(inner)
    return out


def detect_curly_source_quotes(
    detail: str,
    plan: Dict[str, Any] | None = None,
    *,
    source_original: str = "",
    label: str = "正文",
) -> List[str]:
    """硬拦：弯引“”装未译史料原文。"""
    spans = iter_curly_source_spans(detail, plan, source_original=source_original)
    if not spans:
        return []
    samples = "；".join(f"“{s[:36]}”" for s in spans[:3])
    more = f"等共 {len(spans)} 处" if len(spans) > 3 else f"共 {len(spans)} 处"
    return [
        f"{label}：弯引“”装未译史料原文（{more}），须改直角「」：{samples}"
    ]


def fix_curly_source_to_corner(
    detail: str,
    plan: Dict[str, Any] | None = None,
    source_original: str = "",
) -> tuple[str, int]:
    """把误用弯引的未译原文改为直角「」；返回 (新正文, 替换次数)。"""
    blob = mother_plain_blob(plan, source_original)
    n = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal n
        inner = m.group(1)
        if is_untranslated_source_span(inner, blob):
            n += 1
            return f"「{inner}」"
        return m.group(0)

    return _CURLY_QUOTE_RE.sub(_repl, detail or ""), n


def fix_corner_vernacular_to_curly(
    detail: str,
    plan: Dict[str, Any] | None = None,
    source_original: str = "",
) -> tuple[str, int]:
    """把误用直角的白话改为弯引“”；返回 (新正文, 替换次数)。"""
    blob = mother_plain_blob(plan, source_original)
    classic = classic_candidate_plain_blob(plan)
    n = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal n
        inner = m.group(1)
        if is_vernacular_corner_span(inner, blob, classic):
            n += 1
            return f"“{inner}”"
        return m.group(0)

    return _CORNER_QUOTE_RE.sub(_repl, detail or ""), n


def apply_quote_style_fixes(
    detail: str,
    plan: Dict[str, Any] | None = None,
    source_original: str = "",
) -> tuple[str, List[str]]:
    """A 弯引原文→「」+ B 直角白话→“”。返回 (新正文, 变更说明列表)。"""
    text = detail or ""
    changes: List[str] = []
    text, n_a = fix_curly_source_to_corner(text, plan, source_original)
    if n_a:
        changes.append(f"弯引原文→「」×{n_a}")
    text, n_b = fix_corner_vernacular_to_curly(text, plan, source_original)
    if n_b:
        changes.append(f"直角白话→“”×{n_b}")
    return text, changes


def apply_quote_style_fixes_to_file(
    path: Path,
    plan: Dict[str, Any] | None = None,
    *,
    detail_key: str = "翻译详情",
) -> List[str]:
    """对 enrich/成稿 JSON 文件做引号风格修正；返回变更说明。"""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    key = detail_key if detail_key in data else (
        "母本顺译" if "母本顺译" in data else "翻译详情"
    )
    body = str(data.get(key) or "")
    source_original = str(data.get("史料原文") or "")
    fixed, changes = apply_quote_style_fixes(
        body, plan, source_original=source_original
    )
    if not changes:
        return []
    data[key] = fixed
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changes
