"""朝代知识补全：LLM 调用、JSON 解析、ID 与坐标工具。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

OPENCLAW_ROOT = Path(__file__).resolve().parents[2]
ANNOTATE_REF = OPENCLAW_ROOT / "historiography-annotate" / "reference"

PERSON_CATEGORIES = ("君王", "宗戚", "宦官", "文臣", "武将", "庶众")
PERSON_INDEX_CATEGORIES = frozenset({*PERSON_CATEGORIES, "蕃祚"})


def load_env() -> None:
    env_file = OPENCLAW_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def llm_model_label() -> str:
    load_env()
    try:
        from llm.config import provider_label  # noqa: WPS433

        return provider_label()
    except Exception:
        return "DeepSeek (未加载)"


def call_llm(
    prompt: str,
    *,
    session_prefix: str,
    timeout_sec: int = 600,
    temperature: float | None = 0.2,
) -> str:
    load_env()
    from llm.provider import run_agent_turn  # noqa: WPS433

    sid = session_prefix + hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
    res = run_agent_turn(
        prompt,
        session_id=sid,
        timeout_sec=timeout_sec,
        temperature=temperature,
    )
    return str(res.get("result") or "").strip()


def extract_json_array(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("["), text.rfind("]")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("{"), text.rfind("}")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def max_glbl_num(histograph_root: Path) -> int:
    index_path = histograph_root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    supplement_glob = list(
        (histograph_root / "data" / "06朝代知识补全" / "索引条目").glob("*.json")
    )
    nums: list[int] = []
    for path in [index_path, *supplement_glob]:
        if not path.is_file():
            continue
        root = json.loads(path.read_text(encoding="utf-8"))
        entries = root.get("entries") if isinstance(root, dict) else root
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            m = re.match(r"GLBL_(\d+)", str(e.get("史略ID", "")))
            if m:
                nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def allocate_glbl_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"GLBL_{counter[0]:05d}"


def load_emperors(histograph_root: Path, dynasty_id: str) -> list[dict[str, Any]]:
    path = histograph_root / "data" / "01历史坐标数据" / "帝王.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in rows if str(r.get("朝代ID", "")).strip() == dynasty_id]


def resolve_emperor(
    name: str,
    emperors: list[dict[str, Any]],
) -> dict[str, str] | None:
    name = (name or "").strip()
    if not name:
        return None
    for row in emperors:
        if name in (
            str(row.get("帝王名称", "")).strip(),
            str(row.get("帝王原名", "")).strip(),
        ):
            return {
                "四级帝王坐标": str(row.get("帝王名称", "")).strip(),
                "帝王ID": str(row.get("帝王ID", "")).strip(),
                "政权ID": str(row.get("政权ID", "")).strip(),
            }
    return None


def apply_coord_defaults(entry: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    out = dict(entry)
    out.setdefault("一级文明坐标", context.get("文明") or "华夏")
    out.setdefault("二级朝代坐标", context.get("朝代名称"))
    out.setdefault("三级政权坐标", context.get("朝代名称"))
    out.setdefault("文明ID", context.get("文明ID") or "HX")
    out.setdefault("朝代ID", context.get("朝代ID"))
    out.setdefault("政权ID", "ZQ_HX_WUDI_WUDI")
    out.setdefault("母本著作", "朝代补全")
    out.setdefault("来源著作", ["朝代补全"])
    out.setdefault("史略来源", "模型补全")
    out.setdefault("来源条目数", 1)
    out.setdefault("段落域数", 0)
    out.setdefault("原文字句", None)
    out.setdefault("paragraphs", [])
    return out


MIN_DETAIL_CHARS = {
    ("事略", "P0"): 1000,
    ("事略", "P1"): 700,
    ("事略", "P2"): 400,
    ("事略", "P3"): 200,
    ("典制", "P0"): 700,
    ("典制", "P1"): 500,
    ("典制", "P2"): 300,
    ("典制", "P3"): 150,
    ("论著", "P0"): 700,
    ("论著", "P1"): 500,
    ("论著", "P2"): 300,
    ("论著", "P3"): 150,
    ("君王", "P0"): 1000,
    ("君王", "P1"): 700,
    ("君王", "P2"): 400,
    ("君王", "P3"): 200,
    ("宗戚", "P0"): 700,
    ("宗戚", "P1"): 500,
    ("宗戚", "P2"): 300,
    ("宗戚", "P3"): 150,
    ("宦官", "P0"): 700,
    ("宦官", "P1"): 500,
    ("宦官", "P2"): 300,
    ("宦官", "P3"): 150,
    ("文臣", "P0"): 700,
    ("文臣", "P1"): 500,
    ("文臣", "P2"): 300,
    ("文臣", "P3"): 150,
    ("武将", "P0"): 700,
    ("武将", "P1"): 500,
    ("武将", "P2"): 300,
    ("武将", "P3"): 150,
    ("庶众", "P0"): 500,
    ("庶众", "P1"): 400,
    ("庶众", "P2"): 250,
    ("庶众", "P3"): 150,
}

PERSON_CAT_SLUG = {
    "君王": "JUNWANG",
    "宗戚": "ZONGQI",
    "宦官": "HUANGUAN",
    "文臣": "WENCHEN",
    "武将": "WUJIANG",
    "庶众": "SHUZHONG",
}


def detail_min_chars(category: str, priority: str) -> int:
    return MIN_DETAIL_CHARS.get((category, priority), 400)


def detail_compose_temperature(category: str) -> float:
    """详情撰写温度：事略/人物偏叙事 0.3，典制/论著偏准确 0.2。"""
    if category in ("事略", *PERSON_CATEGORIES):
        return 0.3
    return 0.2


def strip_detail_body(text: str) -> str:
    body = text
    for marker in ("*参考著作", "参考著作"):
        if marker in body:
            body = body.split(marker, 1)[0]
    return body.strip()


# 二期朝代知识详情：默认全文不注音（高级读物，非识字教辅）
# 仅下列词条因含罕用字，允许保留注音；其余一律删除
_ALLOW_PINYIN_WORDS = frozenset(
    {
        "颛顼",
        "帝喾",
        "瞽叟",
        "瞽瞍",
        "娵訾",
        "妫汭",
        "獬廌",
        "獬豸",
        "饕餮",
        "梼杌",
        "穷奇",
        "浑沌",
        "魑魅",
        "少皞",
    }
)

def _normalize_allowed_pinyin(word: str, pinyin: str) -> str:
    """允许词条的注音规范化（如帝喾只保留喾音）。"""
    if word == "帝喾":
        parts = re.split(r"[\s,，]+", pinyin.strip())
        if parts and re.match(r"d[iìíǐ]", parts[0], re.I):
            rest = " ".join(parts[1:]).strip()
            return f"帝喾（{rest}）" if rest else "帝喾"
    return f"{word}（{pinyin.strip()}）"


_PINYIN_ANNOT_RE = re.compile(
    r"([\u4e00-\u9fff]{1,12})[（(]([^）)]+)[）)]"
)
_LATIN_OR_TONE_RE = re.compile(
    r"[A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]"
)
_PAREN_ANNOT_RE = re.compile(r"[（(]([^）)]+)[）)]")


def _chinese_run_before(text: str, idx: int, *, max_len: int = 8) -> str:
    chars: list[str] = []
    j = idx - 1
    while j >= 0 and len(chars) < max_len:
        c = text[j]
        if "\u4e00" <= c <= "\u9fff":
            chars.insert(0, c)
            j -= 1
        else:
            break
    return "".join(chars)


def _annotation_word(text: str, paren_start: int) -> tuple[str, int]:
    """从括号前截取被注音/标注的词头（避免「发生在阪泉（」整段误匹配）。"""
    run = _chinese_run_before(text, paren_start)
    if not run:
        return "", paren_start
    if len(run) <= 4:
        return run, paren_start - len(run)
    # 长串取末尾 2～4 字为词（阪泉、颛顼、姬水等）
    for n in (2, 3, 4):
        if len(run) >= n:
            return run[-n:], paren_start - n
    return run, paren_start - len(run)


def _is_modern_location_only(inner: str) -> bool:
    s = inner.strip()
    if s.startswith("今"):
        return _LATIN_OR_TONE_RE.search(s) is None
    return False


def _looks_like_pinyin_annotation(inner: str, word: str) -> bool:
    """仅处理注音/今属地；跳过长篇括注说明。"""
    s = inner.strip()
    if not s:
        return False
    if _is_modern_location_only(s):
        return True
    if _LATIN_OR_TONE_RE.search(s):
        return True
    if word in _ALLOW_PINYIN_WORDS and len(s) <= 24:
        return True
    # 纯拼音音节（短）
    if len(s) <= 16 and re.fullmatch(
        r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z\s·]+", s
    ):
        return True
    return False


def _resolve_annotation(word: str, inner: str, original: str) -> str:
    if not word:
        return original
    if _is_modern_location_only(inner):
        return f"{word}（{inner.strip()}）"

    if _LATIN_OR_TONE_RE.search(inner):
        loc_m = re.search(r"今[^）)]+", inner)
        if loc_m:
            return f"{word}（{loc_m.group(0)}）"
        if word in _ALLOW_PINYIN_WORDS:
            py = re.sub(r"[^a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z\s]", "", inner)
            py = py.strip()
            if py:
                return _normalize_allowed_pinyin(word, py)
        return word

    if word in _ALLOW_PINYIN_WORDS:
        return _normalize_allowed_pinyin(word, inner)
    return word


def clean_over_pinyin(text: str) -> tuple[str, list[str]]:
    """删除一切非白名单注音；保留纯「今属地」标注。"""
    changes: list[str] = []
    parts: list[str] = []
    last = 0
    for m in _PAREN_ANNOT_RE.finditer(text):
        parts.append(text[last : m.start()])
        inner = m.group(1)
        word, word_start = _annotation_word(text, m.start())
        original = text[word_start : m.end()]
        if not _looks_like_pinyin_annotation(inner, word):
            parts.append(original)
            last = m.end()
            continue
        resolved = _resolve_annotation(word, inner, original)
        if resolved != original:
            changes.append(f"{original} → {resolved}")
        parts.append(resolved)
        last = m.end()
    parts.append(text[last:])
    return "".join(parts), changes


def detect_over_pinyin(body: str) -> list[str]:
    """检出一切非白名单注音（gate 用）；「今属地」不报错。"""
    issues: list[str] = []
    for m in _PAREN_ANNOT_RE.finditer(body):
        inner = m.group(1)
        word, word_start = _annotation_word(body, m.start())
        original = body[word_start : m.end()]
        if not _looks_like_pinyin_annotation(inner, word):
            continue
        if _is_modern_location_only(inner):
            continue
        if word in _ALLOW_PINYIN_WORDS:
            continue
        if _resolve_annotation(word, inner, original) == original:
            issues.append(f"禁止注音：{original}")
    return issues


def load_person_alias_maps() -> dict[str, str]:
    """标注名/异名 → 标准名（帝王别名 + 宗戚别名）。"""
    out: dict[str, str] = {}
    for rel in ("帝王别名.json", "宗戚别名.json"):
        path = ANNOTATE_REF / rel
        if not path.is_file():
            continue
        cfg = json.loads(path.read_text(encoding="utf-8"))
        for alias, canonical in (cfg.get("global") or {}).items():
            a, c = str(alias).strip(), str(canonical).strip()
            if a and c:
                out[a] = c
    return out


def normalize_person_name(name: str, alias_map: dict[str, str]) -> str:
    n = (name or "").strip()
    if not n:
        return n
    seen: set[str] = set()
    cur = n
    while cur not in seen:
        seen.add(cur)
        nxt = alias_map.get(cur)
        if not nxt or nxt == cur:
            break
        cur = nxt
    return cur


def load_phase1_person_index(
    histograph_root: Path,
    dynasty_id: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """一期已标注人物（本朝）+ 别名→标准名索引。"""
    alias_map = load_person_alias_maps()
    index_path = histograph_root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    if not index_path.is_file():
        return [], alias_map

    root = json.loads(index_path.read_text(encoding="utf-8"))
    entries = root.get("entries") if isinstance(root, dict) else root
    persons: list[dict[str, Any]] = []
    canonical_to_aliases: dict[str, set[str]] = {}

    emperor_path = histograph_root / "data" / "01历史坐标数据" / "帝王.json"
    orig_to_std: dict[str, str] = {}
    if emperor_path.is_file():
        for row in json.loads(emperor_path.read_text(encoding="utf-8")):
            std = str(row.get("帝王名称", "")).strip()
            orig = str(row.get("帝王原名", "")).strip()
            if std and orig:
                orig_to_std[orig] = std

    if not isinstance(entries, list):
        return [], alias_map

    for e in entries:
        if not isinstance(e, dict):
            continue
        if str(e.get("朝代ID", "")).strip() != dynasty_id:
            continue
        cat = str(e.get("史略分类", "")).strip()
        if cat not in PERSON_INDEX_CATEGORIES:
            continue
        name = str(e.get("史略名称", "")).strip()
        if not name:
            continue
        canonical = normalize_person_name(name, alias_map)
        persons.append(
            {
                "史略ID": e.get("史略ID"),
                "史略名称": name,
                "标准名": canonical,
                "史略分类": cat,
            }
        )
        canonical_to_aliases.setdefault(canonical, set()).add(name)
        for alias, std in alias_map.items():
            if std == canonical or std == name:
                canonical_to_aliases[canonical].add(alias)
        if name in orig_to_std:
            canonical_to_aliases[canonical].add(orig_to_std[name])
        for orig, std in orig_to_std.items():
            if std == canonical:
                canonical_to_aliases[canonical].add(orig)

    alias_index: dict[str, str] = {}
    for canonical, aliases in canonical_to_aliases.items():
        for a in aliases:
            if a:
                alias_index[a] = canonical
        alias_index[canonical] = canonical

    phase1_canonical_set = {str(p["标准名"]) for p in persons}
    for alias, std in alias_map.items():
        if std in phase1_canonical_set or std in {str(p["史略名称"]) for p in persons}:
            alias_index[alias] = std

    return persons, alias_index


def load_emperor_gaps(
    histograph_root: Path,
    dynasty_id: str,
    alias_index: dict[str, str],
) -> list[dict[str, str]]:
    """帝王.json 中一期未覆盖者（别名归一后，含宗戚已覆盖的太后等）。"""
    phase1, alias_map = load_phase1_person_index(histograph_root, dynasty_id)
    phase1_canonical = {str(p["标准名"]) for p in phase1}
    phase1_names = {str(p["史略名称"]) for p in phase1}

    gaps: list[dict[str, str]] = []
    for row in load_emperors(histograph_root, dynasty_id):
        name = str(row.get("帝王名称", "")).strip()
        if not name:
            continue
        canon = alias_index.get(name) or normalize_person_name(name, alias_map)
        if canon in phase1_canonical or name in phase1_names or canon in phase1_names:
            continue
        gaps.append({"帝王名称": name, "补全理由": "帝王表条目、一期无对应人物条"})
    return gaps
