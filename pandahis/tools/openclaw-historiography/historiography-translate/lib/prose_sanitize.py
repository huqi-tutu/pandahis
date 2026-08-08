"""Phase2 成稿后处理：去除 LLM 元叙述与无出处模糊表述。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

import sys
from pathlib import Path

_OPENCLAW_ROOT = Path(__file__).resolve().parents[2]
if str(_OPENCLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_OPENCLAW_ROOT))

from shared.vague_citation import VAGUE_CITATION_TRIGGERS  # noqa: E402

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
    (r"^```json\s*", ""),
    (r"^```\s*", ""),
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

    # Strip markdown code block markers from LLM output
    text = re.sub(r'^```(?:json)?\\s*', '', text)
    text = re.sub(r'```\\s*$', '', text)

    for pat, rep in _FIXUPS:
        text = re.sub(pat, rep, text)

    text = _demote_six_arts_citations(text)

    parts = re.split(r"([。！？\n])", text)
    cleaned_parts: list[str] = []
    for i in range(0, len(parts), 2):
        seg = parts[i]
        punct = parts[i + 1] if i + 1 < len(parts) else ""
        if seg and "《" not in seg:
            for word in VAGUE_CITATION_TRIGGERS:
                seg = re.sub(
                    rf"([，,；;])?{re.escape(word)}[^。！？\n《]{{0,24}}",
                    "",
                    seg,
                )
        cleaned_parts.append(seg + punct)
    text = "".join(cleaned_parts)

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



def _merge_short_paragraphs(text: str) -> str:
    """将连续的单句/双句段落合并为正常段落。"""
    paras = text.split("\n\n")
    if len(paras) <= 1:
        return text
    merged = []
    buffer = ""
    for p in paras:
        sentences = [s for s in re.split(r"[。！？\n]", p) if s.strip()]
        if len(sentences) <= 2 and buffer:
            # 若缓冲段以句号/问号/感叹号结尾，直接用空字符串拼接
            join_char = "" if buffer.rstrip()[-1:] in "。！？" else "，"
            buffer += join_char + p.lstrip()
        else:
            if buffer:
                merged.append(buffer)
            buffer = p
    if buffer:
        merged.append(buffer)
    return "\n\n".join(merged)


def _remove_bold_markers(text: str) -> str:
    """去掉正文中的 Markdown 加粗；小程序仅对「」『』内原文自动加粗。"""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text


def _strip_first_second_markers(text: str) -> str:
    """去掉叙事正文中「首先」「其次」「第一」等分节词。"""
    text = re.sub(r"^(首先|其次|再次)[，,]", "", text, flags=re.M)
    text = re.sub(r"[。；](首先|其次|再次)[，,]", r"。", text)
    text = re.sub(r"[，,](第一|第二|第三)[，,]", "，", text)
    return text


def fix_reference_section_format(detail: str) -> str:
    """正文末段与「参考著作」之间强制空一行（匹配 verify 规则）。"""
    if "参考著作" not in detail:
        return detail
    if re.search(r"\n\n参考著作\s*[:：]", detail):
        return detail
    m = re.search(r"\*?参考著作\s*[:：]\*?", detail)
    if not m:
        return detail
    before = detail[: m.start()].rstrip()
    after = detail[m.start() :]
    after = re.sub(r"^\*?参考著作\s*[:：]\*?", "参考著作：", after.lstrip())
    return f"{before}\n\n{after}"


def sanitize_enrich_detail_full(detail: str) -> str:
    """增强版后处理：段落合并 + 去加粗 + 去分节词 + 参考著作段格式。"""
    text = sanitize_enrich_detail(detail)
    text = _merge_short_paragraphs(text)
    text = _remove_bold_markers(text)
    text = _strip_first_second_markers(text)
    text = fix_reference_section_format(text)
    return text


def polish_enrich_file_full(path) -> bool:
    """增强版润色，在标准 polished 基础上追加段落/格式修复。"""
    if not path.is_file():
        return False
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    detail = str(data.get("翻译详情") or "")
    cleaned = sanitize_enrich_detail_full(detail)
    if cleaned == detail:
        return False
    data["翻译详情"] = cleaned
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True
