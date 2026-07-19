"""中文维基百科 API 客户端（仅用于朝代知识补全 compose-detail grounding）。

读取 openclaw-historiography/.env 中的 WIKI_* 变量；无 OAuth token 时仍可用匿名 API（需 User-Agent）。
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dynasty_supplement_lib as dkl

SCHEMA = "dynasty-knowledge-wikipedia/v1"
DEFAULT_LANG = "zh"
DEFAULT_API = "https://zh.wikipedia.org/w/api.php"
MAX_FULL_EXTRACT_CHARS = 12_000
MAX_SECTION_FETCH = 8
REQUEST_TIMEOUT_SEC = 30


def _wiki_settings() -> dict[str, str]:
    dkl.load_env()
    return {
        "access_token": os.environ.get("WIKI_ACCESS_TOKEN", "").strip(),
        "user_agent": os.environ.get(
            "WIKI_USER_AGENT",
            "PadanhisHistoriography/1.0 (dynasty-knowledge; local)",
        ),
        "lang": os.environ.get("WIKI_LANG", DEFAULT_LANG).strip() or DEFAULT_LANG,
    }


def _api_base(lang: str | None = None) -> str:
    code = (lang or _wiki_settings()["lang"] or DEFAULT_LANG).strip()
    return f"https://{code}.wikipedia.org/w/api.php"


def _request(params: dict[str, Any], *, lang: str | None = None) -> dict[str, Any]:
    settings = _wiki_settings()
    base = _api_base(lang)
    query = urllib.parse.urlencode({k: str(v) for k, v in params.items()})
    url = f"{base}?{query}"
    headers = {"User-Agent": settings["user_agent"]}
    token = settings["access_token"]
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            payload = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"维基 API HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"维基 API 网络错误: {exc}") from exc
    data = json.loads(payload)
    if "error" in data:
        err = data["error"]
        raise RuntimeError(f"维基 API 错误: {err.get('code')} {err.get('info')}")
    return data


def wiki_digest_path(wiki_dir: Path, entry_id: str) -> Path:
    return wiki_dir / f"{entry_id}.json"


def load_wiki_digest(wiki_dir: Path, entry_id: str) -> dict[str, Any] | None:
    path = wiki_digest_path(wiki_dir, entry_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def save_wiki_digest(wiki_dir: Path, digest: dict[str, Any]) -> Path:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    eid = str(digest.get("史略ID") or "unknown")
    path = wiki_digest_path(wiki_dir, eid)
    path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def search_titles(query: str, *, limit: int = 5, lang: str | None = None) -> list[str]:
    q = str(query or "").strip()
    if not q:
        return []
    data = _request(
        {
            "action": "opensearch",
            "format": "json",
            "search": q,
            "limit": limit,
            "namespace": 0,
        },
        lang=lang,
    )
    if not isinstance(data, list) or len(data) < 2:
        return []
    titles = data[1]
    return [str(t).strip() for t in titles if str(t).strip()]


def _page_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"


def _truncate(text: str, limit: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", str(text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def fetch_page_digest(
    title: str,
    *,
    lang: str | None = None,
    include_sections: bool = True,
) -> dict[str, Any]:
    """拉取单页 plain-text 摘要与章节结构。"""
    settings = _wiki_settings()
    wiki_lang = (lang or settings["lang"] or DEFAULT_LANG).strip()
    page_title = str(title or "").strip()
    if not page_title:
        raise ValueError("维基页面标题为空")

    query_data = _request(
        {
            "action": "query",
            "format": "json",
            "titles": page_title,
            "redirects": 1,
            "prop": "extracts|info",
            "explaintext": 1,
            "exintro": 0,
            "inprop": "url",
        },
        lang=wiki_lang,
    )
    pages = (query_data.get("query") or {}).get("pages") or {}
    if not pages:
        raise RuntimeError(f"维基未返回页面: {page_title}")
    page = next(iter(pages.values()))
    if int(page.get("ns", 0)) != 0:
        raise RuntimeError(f"非主命名空间页面: {page_title}")
    if "missing" in page:
        raise RuntimeError(f"维基无词条: {page_title}")

    resolved_title = str(page.get("title") or page_title)
    full_extract = str(page.get("extract") or "").strip()
    intro = full_extract.split("\n\n", 1)[0].strip() if full_extract else ""

    sections: list[dict[str, str]] = []
    if include_sections and resolved_title:
        parse_data = _request(
            {
                "action": "parse",
                "format": "json",
                "page": resolved_title,
                "prop": "sections",
            },
            lang=wiki_lang,
        )
        for sec in (parse_data.get("parse") or {}).get("sections") or []:
            if not isinstance(sec, dict):
                continue
            line = str(sec.get("line") or "").strip()
            if not line:
                continue
            sections.append(
                {
                    "index": str(sec.get("index") or ""),
                    "level": str(sec.get("level") or ""),
                    "title": line,
                }
            )

        for sec in sections[:MAX_SECTION_FETCH]:
            idx = sec.get("index")
            if not idx:
                continue
            sec_parse = _request(
                {
                    "action": "parse",
                    "format": "json",
                    "page": resolved_title,
                    "prop": "text",
                    "section": idx,
                },
                lang=wiki_lang,
            )
            raw_text = (sec_parse.get("parse") or {}).get("text") or ""
            if isinstance(raw_text, dict):
                html = str(raw_text.get("*") or "")
            else:
                html = str(raw_text)
            plain = _html_to_plain(html)
            plain = re.sub(r"\[编辑[^\]]*\]", "", plain)
            if plain:
                sec["text"] = _truncate(plain, 2000)

    return {
        "resolved_title": resolved_title,
        "lang": wiki_lang,
        "page_url": str(page.get("fullurl") or _page_url(wiki_lang, resolved_title)),
        "intro": _truncate(intro, 2500),
        "full_extract": _truncate(full_extract, MAX_FULL_EXTRACT_CHARS),
        "sections": sections[:MAX_SECTION_FETCH],
    }


def _html_to_plain(html: str) -> str:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = urllib.parse.unquote(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def resolve_title(query: str, *, lang: str | None = None) -> tuple[str, list[str]]:
    """返回 (最佳标题, 搜索候选列表)。"""
    q = str(query or "").strip()
    if not q:
        raise ValueError("检索词为空")
    candidates = search_titles(q, limit=5, lang=lang)
    if q in candidates:
        return q, candidates
    if candidates:
        return candidates[0], candidates
    # 直接按原名查（含重定向）
    probe = fetch_page_digest(q, lang=lang, include_sections=False)
    return str(probe["resolved_title"]), [q]


def fetch_for_entry(
    entry_id: str,
    entry_name: str,
    *,
    lang: str | None = None,
    force: bool = False,
    wiki_dir: Path | None = None,
    entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """按史略名称拉取维基并落盘 digest JSON。"""
    name = str(entry_name or "").strip()
    if not name:
        raise ValueError(f"{entry_id} 史略名称为空，无法检索维基")

    if wiki_dir is not None and not force:
        existing = load_wiki_digest(wiki_dir, entry_id)
        if existing and existing.get("full_extract"):
            if entry is not None:
                existing = apply_scope_to_digest(existing, entry)
            return existing

    resolved, candidates = resolve_title(name, lang=lang)
    page = fetch_page_digest(resolved, lang=lang, include_sections=True)
    digest: dict[str, Any] = {
        "schema": SCHEMA,
        "史略ID": entry_id,
        "query": name,
        "search_candidates": candidates,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **page,
    }
    if entry is not None:
        digest = apply_scope_to_digest(digest, entry)
    if wiki_dir is not None:
        save_wiki_digest(wiki_dir, digest)
    return digest


# ---------------------------------------------------------------------------
# 条目坐标 · 维基底稿分层（通用：史略名称 + 所属朝代）
# ---------------------------------------------------------------------------

# 维基页面导航/文献区，任何条目均排除
GLOBAL_EXCLUDE_SECTION_KEYWORDS = (
    "参见",
    "引用",
    "脚注",
    "外部链接",
    "参考资料",
    "书目",
    "注释",
)

# 标题含下列词 → 延伸层（跨时代综述/后世影响，仅合段可选）
CONTEXT_SECTION_TITLE_KEYWORDS = (
    "历史上",
    "历代",
    "后世",
    "以后",
    "以降",
    "影响",
    "评价",
    "演变",
    "沿革",
    "意义",
    "传承",
    "对后世",
)

# 标题含下列词 → 核心层（定义/过程/记载类，与条目主题直接相关）
CORE_SECTION_TITLE_HINTS = (
    "起源",
    "定义",
    "概述",
    "概说",
    "背景",
    "经过",
    "过程",
    "制度",
    "内容",
    "记载",
    "传说",
    "争议",
    "怀疑",
    "事迹",
    "战",
    "推行",
    "实施",
)

# 年表/朝代链式标题 → 排除
TIMELINE_TITLE_RE = re.compile(r"→|年表|大事记|时间表")

# 现当代专题节 → 排除（朝代知识补全条目均为历史题材）
MODERN_SECTION_KEYWORDS = (
    "中华人民共和国",
    "当代",
    "现代",
    "21世纪",
    "20世纪",
)

CONTEXT_SECTION_MAX_CHARS = 500


def _collect_match_keywords(entry: dict[str, Any]) -> list[str]:
    """从条目名、朝代、帝王、简介提取与维基章节对齐的关键词。"""
    seen: set[str] = set()
    out: list[str] = []

    def add(raw: Any) -> None:
        s = str(raw or "").strip()
        if len(s) < 2 or s in seen:
            return
        seen.add(s)
        out.append(s)

    name = str(entry.get("史略名称") or "").strip()
    add(name)
    for suffix in ("制度", "之战", "之役", "制", "法", "律", "礼", "观", "说"):
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            add(name[: -len(suffix)])

    add(entry.get("二级朝代坐标"))
    add(entry.get("朝代名称"))
    add(entry.get("四级帝王坐标"))

    intro = str(entry.get("史略简介") or "")
    for tok in re.findall(r"[\u4e00-\u9fff]{2,8}", intro):
        add(tok)

    axis = entry.get("考订依据")
    if isinstance(axis, dict):
        for tok in re.findall(r"[\u4e00-\u9fff]{2,6}", str(axis.get("坐标主轴") or "")):
            add(tok)

    return out


def build_write_scope(entry: dict[str, Any]) -> dict[str, Any]:
    """从索引条目提取写作主轴（任意朝代通用）。"""
    dynasty_id = str(entry.get("朝代ID") or "").strip()
    dynasty_name = str(entry.get("二级朝代坐标") or entry.get("朝代名称") or "").strip()
    ruler = str(entry.get("四级帝王坐标") or "").strip()
    cat = dkl.normalize_category(str(entry.get("史略分类") or ""))
    entry_name = str(entry.get("史略名称") or "").strip()
    start_y = entry.get("史略开始年")
    end_y = entry.get("史略结束年")
    year_label = ""
    if start_y is not None and end_y is not None:
        try:
            sy, ey = int(start_y), int(end_y)
            year_label = str(sy) if sy == ey else f"{sy}～{ey}"
        except (TypeError, ValueError):
            year_label = ""
    axis = ""
    cb = entry.get("考订依据")
    if isinstance(cb, dict):
        axis = str(cb.get("坐标主轴") or "").strip()

    match_keywords = _collect_match_keywords(entry)
    focus_note = (
        f"正文主轴：{dynasty_name or '（见索引）'}时期的「{entry_name}」"
        f"（{cat}）。"
        "起、承、转以本条目所属朝代为核心展开；"
        "开篇或起段可**简略**交代前续背景（更早渊源），合段可**简略**写后世影响与制度延续；"
        "前续/后世均为可选补充，有材料则写、无则不硬凑；"
        "禁止喧宾夺主或写成通史年表。"
    )

    return {
        "朝代ID": dynasty_id,
        "朝代名称": dynasty_name,
        "四级帝王坐标": ruler,
        "史略分类": cat,
        "史略名称": entry_name,
        "主要史料出处": str(entry.get("主要史料出处") or "").strip(),
        "年代表述": year_label,
        "坐标主轴": axis,
        "match_keywords": match_keywords,
        "focus_note": focus_note,
    }


def _section_tier(title: str, scope: dict[str, Any]) -> str:
    """返回 core | context | exclude（通用规则，不绑定特定朝代 ID）。"""
    t = str(title or "").strip()
    if not t:
        return "exclude"

    for kw in GLOBAL_EXCLUDE_SECTION_KEYWORDS:
        if kw in t:
            return "exclude"
    for kw in MODERN_SECTION_KEYWORDS:
        if kw in t:
            return "exclude"
    if TIMELINE_TITLE_RE.search(t):
        return "exclude"

    # 延伸层优先：标题明示跨时代综述
    for kw in CONTEXT_SECTION_TITLE_KEYWORDS:
        if kw in t:
            return "context"

    # 核心层：标题命中条目/朝代关键词，或属定义/过程/记载类
    for kw in scope.get("match_keywords") or []:
        if len(kw) >= 2 and kw in t:
            return "core"
    for hint in CORE_SECTION_TITLE_HINTS:
        if hint in t:
            return "core"

    # 默认同词条下未分类章节视为核心（由写作主轴在成稿时限定朝代）
    return "core"


def _clean_intro(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"（[^）]*拼音：[^）]*）", "", text)
    text = re.sub(r"（[^）]*注音：[^）]*）", "", text)
    return text.strip()


def _clean_section_body(text: str, *, max_chars: int | None = None) -> str:
    lines = []
    for line in str(text or "").splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if s.startswith("^"):
            continue
        if "&#91;" in s or "原始内容存档" in s:
            continue
        lines.append(s)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if max_chars:
        body = _truncate(body, max_chars)
    return body


def apply_scope_to_digest(digest: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """按条目（史略名称 + 朝代坐标）将维基章节分为 core / context / excluded。"""
    scope = build_write_scope(entry)
    core: list[dict[str, str]] = []
    context: list[dict[str, str]] = []
    excluded_titles: list[str] = []

    intro = _clean_intro(str(digest.get("intro") or ""))

    for sec in digest.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "").strip()
        tier = _section_tier(title, scope)
        body = _clean_section_body(str(sec.get("text") or ""))
        item = {"title": title, "text": body}
        if tier == "exclude":
            excluded_titles.append(title)
        elif tier == "context":
            item["text"] = _clean_section_body(body, max_chars=CONTEXT_SECTION_MAX_CHARS)
            if item["text"]:
                context.append(item)
        else:
            if body:
                core.append(item)

    scoped = {
        **digest,
        "write_scope": scope,
        "scoped": {
            "intro": intro,
            "core_sections": core,
            "context_sections": context,
            "excluded_titles": excluded_titles,
        },
    }
    return scoped


def format_scope_discipline(entry: dict[str, Any]) -> str:
    """compose prompt 中的条目主轴与篇幅纪律。"""
    scope = build_write_scope(entry)
    lines = [
        f"- 时代主轴：{scope['朝代名称'] or '（见索引）'}"
        + (f"（{scope['年代表述']}）" if scope["年代表述"] else ""),
        f"- 帝王/人物轴：{scope['四级帝王坐标']}" if scope["四级帝王坐标"] else "",
        f"- 分类：{scope['史略分类']} · {scope['史略名称']}",
        f"- 史料优先：{scope['主要史料出处']}" if scope["主要史料出处"] else "",
    ]
    if scope["坐标主轴"]:
        lines.append(f"- 坐标说明：{scope['坐标主轴']}")
    lines.extend(
        [
            f"- {scope['focus_note']}",
            "- 篇幅：起、承、转（约全文 70–85%）围绕**本条目所属朝代**",
            "- 前续背景：开篇或起段可一两句交代更早渊源（可选，有则写、无则不凑）",
            "- 后世影响：合段可收束制度史意义及对后世的影响（可选，一带而过，非第二重点）",
            "- 禁止年表式罗列；禁止整段写其他朝代",
            "- 维基底稿【延伸】层：可用于合段后世；【核心】层含「起源」等时可支撑前续背景",
            "- 维基底稿【排除】层：导航/年表/现当代专题等，勿写入正文",
            f"- 匹配关键词（章节筛选）：{'、'.join(scope.get('match_keywords') or [])[:120]}",
        ]
    )
    return "\n".join(lines)


def format_digest_for_prompt(
    digest: dict[str, Any] | None,
    entry: dict[str, Any] | None = None,
    *,
    max_chars: int = 9000,
) -> str:
    """按条目坐标分层压缩 digest，供 compose-detail 注入。"""
    if not digest:
        return ""
    if entry is not None and not digest.get("scoped"):
        digest = apply_scope_to_digest(digest, entry)

    scoped = digest.get("scoped") or {}
    parts: list[str] = [
        f"词条：{digest.get('resolved_title') or digest.get('query')}",
        f"URL：{digest.get('page_url') or ''}",
    ]

    intro = str(scoped.get("intro") or digest.get("intro") or "").strip()
    if intro:
        parts.append(f"【核心 · 摘要】\n{_clean_intro(intro)}")

    core_secs = scoped.get("core_sections")
    if core_secs is None:
        fallback_scope = build_write_scope(entry) if entry else {}
        core_secs = [
            s
            for s in (digest.get("sections") or [])
            if isinstance(s, dict)
            and _section_tier(str(s.get("title") or ""), fallback_scope) == "core"
        ]
    if core_secs:
        parts.append("【核心 · 章节】（起承转主体，须充分改写）")
        for sec in core_secs:
            if not isinstance(sec, dict):
                continue
            title = str(sec.get("title") or "").strip()
            body = str(sec.get("text") or "").strip()
            if body:
                parts.append(f"### {title}\n{body}")

    ctx_secs = scoped.get("context_sections") or []
    if ctx_secs:
        parts.append("【延伸 · 章节】（合段可用：后世影响与制度延续，一带而过，非正文重点）")
        for sec in ctx_secs:
            title = str(sec.get("title") or "").strip()
            body = str(sec.get("text") or "").strip()
            if body:
                parts.append(f"### {title}\n{body}")

    excluded = scoped.get("excluded_titles") or []
    if excluded:
        parts.append("【排除 · 勿写】\n" + "、".join(excluded[:12]))

    text = "\n\n".join(p for p in parts if p.strip())
    return _truncate(text, max_chars)
