"""成稿程序化后处理：引号按母本校正；参考著作按正文《》拼接。"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.prose_sanitize import normalize_corner_quotes
from lib.reference_normalize import normalize_reference_list, normalize_reference_title
from lib.source_citation import build_source_citation
from lib.source_text import build_source_original

_OPENCLAW_ROOT = Path(__file__).resolve().parents[2]
if str(_OPENCLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_OPENCLAW_ROOT))

from shared.reference_works import dedupe_reference_works  # noqa: E402

# 成对引号（开→闭）；不含书名号《》
_QUOTE_PAIRS = (
    ("「", "」"),
    ("『", "』"),
    ("“", "”"),
    ("‘", "’"),
    ('"', '"'),
    ("'", "'"),
)

_TITLE_RE = re.compile(r"《[^》]+》")


def _plain_for_match(text: str) -> str:
    """匹配用：去空白与常见标点变体，便于原文对照。"""
    t = str(text or "")
    t = re.sub(r"\s+", "", t)
    t = t.replace("：", ":").replace("；", ";").replace("，", ",").replace("。", ".")
    t = t.replace("（", "(").replace("）", ")").replace("！", "!").replace("？", "?")
    return t


def split_body_and_refs(detail: str) -> Tuple[str, str]:
    detail = str(detail or "")
    if "*参考著作*" in detail:
        body, ref = detail.split("*参考著作*", 1)
        return body.rstrip(), "*参考著作*" + ref
    if "参考著作" in detail:
        body, ref = detail.rsplit("参考著作", 1)
        return body.rstrip(), "参考著作" + ref
    return detail.rstrip(), ""


def fix_quotes_by_mother(body: str, mother_text: str) -> Tuple[str, int]:
    """引号校正：内容能在母本原文中找到 →「」；否则 →“”。

    扫描正文中成对引号（含直角/弯/ASCII），按母本子串匹配重写开闭符。
    不改动《书名》。返回 (新正文, 改写次数)。
    """
    mother_plain = _plain_for_match(mother_text)
    if not body:
        return body, 0

    opens = {p[0] for p in _QUOTE_PAIRS}
    # 按出现顺序找最短成对区间，避免贪婪跨段
    out: List[str] = []
    i = 0
    n = len(body)
    changes = 0
    while i < n:
        ch = body[i]
        if ch not in opens:
            out.append(ch)
            i += 1
            continue
        close_candidates = [c for o, c in _QUOTE_PAIRS if o == ch]
        # ASCII 开闭同形时，向后找下一个相同字符
        end = -1
        inner = ""
        for c in close_candidates:
            j = body.find(c, i + 1)
            if j < 0:
                continue
            # 取最近的合法闭合
            if end < 0 or j < end:
                end = j
                inner = body[i + 1 : j]
        if end < 0:
            out.append(ch)
            i += 1
            continue
        plain_inner = _plain_for_match(inner)
        use_corner = bool(plain_inner) and bool(mother_plain) and plain_inner in mother_plain
        new_open, new_close = ("「", "」") if use_corner else ("“", "”")
        old_open, old_close = body[i], body[end]
        if old_open != new_open or old_close != new_close:
            changes += 1
        out.append(new_open)
        out.append(inner)
        out.append(new_close)
        i = end + 1
    return "".join(out), changes


def _ref_key(title: str) -> str:
    """去重键：忽略《》与间隔号·。"""
    t = normalize_reference_title(title)
    return re.sub(r"[《》·\s]", "", t)


def _with_work_volume_dot(title: str, work_hint: str = "") -> str:
    """《史记屈原贾生列传》→《史记·屈原贾生列传》（已有·则原样）。"""
    t = normalize_reference_title(title)
    bare = t.strip("《》")
    if not bare or "·" in bare:
        return t
    work = re.sub(r"^\d+", "", work_hint or "") or ""
    for prefix in ("史记", "汉书", "后汉书", "三国志", work):
        if prefix and bare.startswith(prefix) and len(bare) > len(prefix):
            return normalize_reference_title(f"《{prefix}·{bare[len(prefix):]}》")
    return t


def mother_reference_title(recalled: Dict[str, Any]) -> str:
    """参考著作第 1 条：母本这一卷。"""
    work_hint = str(recalled.get("母本著作") or "")
    primary = str(recalled.get("主要史料出处") or "").strip()
    if primary:
        if not primary.startswith("《"):
            primary = f"《{primary.strip('《》')}》"
        return _with_work_volume_dot(primary, work_hint)
    cite = build_source_citation(recalled)
    if cite:
        return _with_work_volume_dot(cite, work_hint)
    work = str(recalled.get("母本著作") or "").strip()
    if work:
        bare = re.sub(r"^\d+", "", work) or work
        return normalize_reference_title(f"《{bare}》")
    return ""


def extract_book_titles_in_order(body: str) -> List[str]:
    """按正文出现顺序抽取《…》，去重保序（· 与否视为同一书）。"""
    seen: set[str] = set()
    out: List[str] = []
    for m in _TITLE_RE.finditer(body or ""):
        title = normalize_reference_title(m.group(0))
        key = _ref_key(title)
        if not title or key in seen:
            continue
        seen.add(key)
        out.append(title)
    return out


def build_reference_section_from_body(
    body: str,
    recalled: Dict[str, Any],
) -> str:
    """母本卷为首 + 正文《》去重顺序列出。"""
    mother = mother_reference_title(recalled)
    body_titles = extract_book_titles_in_order(body)
    refs: List[str] = []
    seen: set[str] = set()

    mother_key = _ref_key(mother) if mother else ""
    if mother_key:
        # 若正文已有等价书名（常带·），优先用正文写法作首条
        first = mother
        for t in body_titles:
            if _ref_key(t) == mother_key:
                first = t
                break
        refs.append(first)
        seen.add(mother_key)

    for t in body_titles:
        key = _ref_key(t)
        if key in seen:
            continue
        seen.add(key)
        refs.append(t)

    refs = normalize_reference_list(refs)
    # 裸母书名与同书卷篇并存时丢弃前者（如 《史记》 vs 《史记·封禅书》）
    final = dedupe_reference_works(refs)
    if not final:
        return ""
    lines = "\n".join(f"{i}. {r}" for i, r in enumerate(final, start=1))
    return f"参考著作：\n{lines}"


def finalize_translation_detail(
    detail: str,
    recalled: Dict[str, Any],
    *,
    plan: Dict[str, Any] | None = None,
    mother_text: str | None = None,
) -> Tuple[str, List[str]]:
    """成稿终处理：引号校正 + 程序拼接参考著作。

    plan 参数保留兼容，参考著作不再依赖 plan「参考著作」列表。
    mother_text：可直接传入已落盘的「史料原文」；缺省则从 recalled 组装。
    """
    _ = plan
    changes: List[str] = []
    body, _old_refs = split_body_and_refs(detail)
    mother = (mother_text or "").strip() or build_source_original(recalled)
    if not mother:
        mother = str(recalled.get("史料原文") or recalled.get("text") or "").strip()
    normalized = normalize_corner_quotes(body)
    if normalized != body:
        changes.append("白角引号『』→「」")
        body = normalized
    fixed_body, n_quotes = fix_quotes_by_mother(body, mother)
    if n_quotes:
        changes.append(f"引号校正 {n_quotes} 处")
        body = fixed_body
    elif fixed_body != body:
        body = fixed_body

    ref_block = build_reference_section_from_body(body, recalled)
    if ref_block:
        changes.append("程序拼接参考著作")
        new_detail = f"{body.rstrip()}\n\n{ref_block}"
    else:
        new_detail = body.rstrip()
    if not new_detail.endswith("\n"):
        new_detail += "\n"
    return new_detail, changes
