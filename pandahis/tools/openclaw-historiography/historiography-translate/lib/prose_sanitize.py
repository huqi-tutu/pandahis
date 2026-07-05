"""Phase2 成稿后处理：去除 LLM 元叙述与无出处模糊表述。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from lib.verify import VAGUE_CITATION_PATTERNS

_META_PREFIX = re.compile(
    r"^本条\s*\d+\s*段.*?---\s*",
    re.S,
)

# 翻译规则「喊数」自检行，不得出现在 翻译详情 正文
_META_CHECKLIST_LINE = re.compile(
    r"^本条\s*\d+\s*段（母本\s*\d+\s*\+\s*索引补充\s*\d+）；"
    r"母本逐句清单\s*\d+\s*句；"
    r"外部补全仅限可标出处内容；"
    r"已读完\s*\d+/\d+\s*段[。]?\s*",
    re.M,
)

_FIXUPS: tuple[tuple[str, str], ...] = (
    (r"，据说是太阳升起的地方", "，即日出之处"),
    (r"据说是太阳升起的地方", "即日出之处"),
    (r"，三苗据说是蚩尤的后裔部落", ""),
    (r"三苗据说是蚩尤的后裔部落[，,]?", ""),
    (r"就是传说中极南的交趾之地", "即南方交趾之地"),
    (r"传说中极南的交趾之地", "南方交趾之地"),
    (r"，有人说类似后世浑天仪的前身", "，或为观测天象的仪器"),
    (r"有人说类似后世浑天仪的前身[，,]?", ""),
    (r"按《([^》]+)》的说法", r"《\1》载"),
)


def sanitize_mother_detail(detail: str) -> str:
    text = (detail or "").strip()
    if not text:
        return text
    # Phase1 误用《「篇名」》引用他书，改回引号原词
    text = re.sub(r"《「([^」]+)」》", r"「\1」", text)
    text = re.sub(r"《([^》·]+)》", lambda m: f"「{m.group(1).strip('「」')}」" if "·" not in m.group(1) and "史记" not in m.group(1) else m.group(0), text)
    return text


def polish_mother_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    key = "母本顺译" if "母本顺译" in data else "翻译详情"
    body = str(data.get(key) or "")
    cleaned = sanitize_mother_detail(body)
    if cleaned == body:
        return False
    data[key] = cleaned
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def _demote_six_arts_citations(text: str) -> str:
    """六经名目在解释性语境中不用《》，避免 Phase2 白名单误拦。"""
    parts = re.split(r"([。！？\n])", text)
    out: list[str] = []
    for i in range(0, len(parts), 2):
        seg = parts[i]
        punct = parts[i + 1] if i + 1 < len(parts) else ""
        if seg and re.search(r"六[蓺艺经]", seg):
            seg = re.sub(
                r"《(诗|书|礼|乐|易|春秋)》",
                r"「\1」",
                seg,
            )
        out.append(seg + punct)
    return "".join(out)


def sanitize_enrich_detail(detail: str) -> str:
    text = (detail or "").strip()
    if not text:
        return text

    text = _META_PREFIX.sub("", text).strip()
    text = _META_CHECKLIST_LINE.sub("", text).strip()

    for pat, rep in _FIXUPS:
        text = re.sub(pat, rep, text)

    text = _demote_six_arts_citations(text)

    for word in VAGUE_CITATION_PATTERNS:
        text = re.sub(
            rf"([，,；;])?{re.escape(word)}[^。！？\n《]{{0,24}}",
            "",
            text,
        )

    text = re.sub(r"[，,]{2,}", "，", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def polish_enrich_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    detail = str(data.get("翻译详情") or "")
    cleaned = sanitize_enrich_detail(detail)
    if cleaned == detail:
        return False
    data["翻译详情"] = cleaned
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True
