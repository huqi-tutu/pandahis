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


# 标点硬错：冒号后逗号、句末引号外逗号、引号后逗号再破折号、段首破折号
_COLON_COMMA = re.compile(r"[：:]，")
# 引语内已有句末点号时，后引号外不得再加逗号（GB/T 15834）
_TERMINAL_QUOTE_OUTER_COMMA = re.compile(r"([。！？][」”])，")
_QUOTE_COMMA_EMDASH = re.compile(r"([」”])，\s*——")
_PARA_START_EMDASH = re.compile(r"(?m)^[ \t]*——")


def heal_prose_punctuation(text: str) -> str:
    """愈合标点硬错（写作规则「禁止事项 · 标点硬错」）。

    1. `：，` / `:，` → `：`
    2. `。”，` / `？」，` / `！」，` 等 → 去掉后引号外逗号
    3. `」`/`”` 与 `——` 之间的多余逗号 → 直连
    4. 段首 `——` → 删除破折号，保留后文
    """
    if not text:
        return text
    out = _COLON_COMMA.sub("：", text)
    out = _TERMINAL_QUOTE_OUTER_COMMA.sub(r"\1", out)
    out = _QUOTE_COMMA_EMDASH.sub(r"\1——", out)
    out = _PARA_START_EMDASH.sub("", out)
    return out


def detect_prose_punctuation_defects(text: str) -> list[str]:
    """返回仍存在的标点硬错说明（愈合后应为空）。"""
    body = text or ""
    found: list[str] = []
    if _COLON_COMMA.search(body):
        found.append("冒号后紧跟逗号（：，）")
    if _TERMINAL_QUOTE_OUTER_COMMA.search(body):
        found.append("句末引号外多逗号（。”，/？」，）")
    if _QUOTE_COMMA_EMDASH.search(body):
        found.append("引号后多逗号再破折号（」，——）")
    if _PARA_START_EMDASH.search(body):
        found.append("段首破折号（——）")
    return found


def _unwrap_nested_output_json(text: str) -> str:
    """剥掉误嵌的 {"史略ID":..., "翻译详情"|"母本顺译": "..."}（整段或夹在正文中）。

    兼容含未转义控制字符/尾部 ``` 的伪 JSON：用字段定位 + 字符串扫描兜底。
    """
    s = (text or "").strip()
    if not s or "史略ID" not in s:
        return s
    # 去掉模型偶发追加的 markdown 围栏
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()

    def _inner_from_obj(obj: Any) -> str | None:
        if not isinstance(obj, dict):
            return None
        inner = obj.get("翻译详情") or obj.get("母本顺译")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
        return None

    def _scan_inner_string(blob: str) -> str | None:
        m = re.search(r'"(?:翻译详情|母本顺译)"\s*:\s*"', blob)
        if not m:
            return None
        chars: list[str] = []
        i = m.end()
        while i < len(blob):
            c = blob[i]
            if c == "\\" and i + 1 < len(blob):
                nxt = blob[i + 1]
                esc = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
                chars.append(esc.get(nxt, nxt))
                i += 2
                continue
            if c == '"':
                break
            chars.append(c)
            i += 1
        inner = "".join(chars).strip()
        return inner or None

    # 整段就是 JSON
    if s.startswith("{"):
        try:
            inner = _inner_from_obj(json.loads(s))
            if inner:
                return inner
        except json.JSONDecodeError:
            start, end = s.find("{"), s.rfind("}")
            if start >= 0 and end > start:
                try:
                    inner = _inner_from_obj(json.loads(s[start : end + 1]))
                    if inner:
                        return inner
                except json.JSONDecodeError:
                    scanned = _scan_inner_string(s)
                    if scanned:
                        return scanned

    # 正文中夹嵌：用内层正文替换该 JSON 块（保留前后叙事）
    for m in re.finditer(r"\{\s*\"史略ID\"\s*:", s):
        start = m.start()
        depth = 0
        end = -1
        for i, ch in enumerate(s[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end < 0:
            # 截断 JSON：从该起点扫描字段
            scanned = _scan_inner_string(s[start:])
            if scanned:
                s = (s[:start].rstrip() + "\n\n" + scanned).strip()
            break
        blob = s[start:end]
        try:
            inner = _inner_from_obj(json.loads(blob))
        except json.JSONDecodeError:
            inner = _scan_inner_string(blob)
        if inner:
            s = (s[:start].rstrip() + "\n\n" + inner + "\n\n" + s[end:].lstrip()).strip()
            break
    return s


def sanitize_mother_detail(detail: str) -> str:
    text = _unwrap_nested_output_json((detail or "").strip())
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
    text = _unwrap_nested_output_json((detail or "").strip())
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
    text = heal_prose_punctuation(text)
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


_ATX_HEADING = re.compile(r"(?m)^#{1,6}\s+.*$")


def _strip_markdown_headings(text: str) -> str:
    text = _ATX_HEADING.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def sanitize_enrich_detail_full(detail: str) -> str:
    """增强版后处理：段落合并 + 去加粗 + 去章节标题 + 去分节词 + 参考著作段格式。"""
    text = sanitize_enrich_detail(detail)
    text = _strip_markdown_headings(text)
    text = _merge_short_paragraphs(text)
    text = _remove_bold_markers(text)
    text = _strip_first_second_markers(text)
    text = fix_reference_section_format(text)
    text = heal_prose_punctuation(text)
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
