"""史料书目 plan：发现、摘句抓取（ctext）、校验与 compose 注入。"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "dynasty-knowledge-bibliography/v1"

# 二十四史：拓展路不 fetch 摘句（翻译详录服务）；须完整书名匹配，避免「逸周书」误中「周书」
ERSHI_SHI_TITLES = frozenset(
    {
        "史记",
        "汉书",
        "后汉书",
        "三国志",
        "晋书",
        "宋书",
        "南齐书",
        "梁书",
        "陈书",
        "魏书",
        "北齐书",
        "周书",
        "隋书",
        "南史",
        "北史",
        "旧唐书",
        "新唐书",
        "旧五代史",
        "新五代史",
        "宋史",
        "辽史",
        "金史",
        "元史",
        "明史",
    }
)

TIER_VALUES = frozenset(
    {
        "先秦文献",
        "辑佚/出土",
        "经注/杂史",
        "正史-见翻译",
        "后世综述",
    }
)

MATERIAL_TIERS = frozenset({"A", "B", "C"})

CTEXT_SEARCH_URL = "https://api.ctext.org/searchtexts"
CTEXT_GETTEXT_URL = "https://api.ctext.org/gettext"
CTEXT_READLINK_URL = "https://api.ctext.org/readlink"
CTEXT_REQUEST_DELAY_SEC = 0.35

# 出处子串 → ctext.org 章节 URL（试点；后续可沉淀为史料图谱）
CTEXT_URL_HINTS: tuple[tuple[str, str], ...] = (
    ("山海经·大荒北经", "https://ctext.org/shan-hai-jing/da-huang-bei-jing"),
    ("山海經·大荒北經", "https://ctext.org/shan-hai-jing/da-huang-bei-jing"),
    ("庄子·盗跖", "https://ctext.org/zhuangzi/dao-zhi"),
    ("莊子·盜跖", "https://ctext.org/zhuangzi/dao-zhi"),
    ("逸周书·尝麦解", "https://ctext.org/lost-book-of-zhou/chang-mai-jie"),
    ("逸周書·嘗麥解", "https://ctext.org/lost-book-of-zhou/chang-mai-jie"),
    ("尸子", "https://ctext.org/shi-zi"),
    ("史记·五帝本纪", "https://ctext.org/shi-ji/wu-di-ben-ji"),
    ("尚书·尧典", "https://ctext.org/shang-shu/yao-dian"),
    ("尚書·堯典", "https://ctext.org/shang-shu/yao-dian"),
    ("吕氏春秋·遇合", "https://ctext.org/lu-shi-chun-qiu/yu-he"),
    ("呂氏春秋·遇合", "https://ctext.org/lu-shi-chun-qiu/yu-he"),
    ("竹书纪年", "https://ctext.org/bamboo-annals"),
    ("竹書紀年", "https://ctext.org/bamboo-annals"),
    ("列女传", "https://ctext.org/lie-nu-zhuan"),
    ("列女傳", "https://ctext.org/lie-nu-zhuan"),
)

# 简繁/异体折叠（摘句校验）
_CHAR_FOLD: dict[str, str] = {
    "黃": "黄",
    "後": "后",
    "於": "于",
    "風": "风",
    "師": "师",
    "縱": "纵",
    "變": "变",
    "復": "复",
    "魃": "魃",
    "應": "应",
    "龍": "龙",
    "請": "请",
    "時": "时",
    "書": "书",
    "經": "经",
    "國": "国",
    "說": "说",
    "與": "与",
    "戰": "战",
    "斬": "斩",
    "嘗": "尝",
    "麥": "麦",
    "盜": "盗",
    "跖": "跖",
    "軒": "轩",
    "轅": "辕",
    "獲": "获",
    "殺": "杀",
    "為": "为",
    "無": "无",
    "遺": "遗",
    "懼": "惧",
    "執": "执",
    "說": "说",
}


@dataclass
class BibIssue:
    code: str
    message: str
    severity: str = "error"  # error | warn


@dataclass
class BibVerifyReport:
    passed: bool
    issues: list[BibIssue] = field(default_factory=list)
    entry_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "entry_id": self.entry_id,
            "issues": [
                {"code": i.code, "message": i.message, "severity": i.severity}
                for i in self.issues
            ],
        }


def plan_path(bibliography_dir: Path, entry_id: str) -> Path:
    return bibliography_dir / f"{entry_id}.plan.json"


def source_graph_path(source_graph_dir: Path, entry_id: str) -> Path:
    return source_graph_dir / f"{entry_id}_sources.json"


def load_plan(bibliography_dir: Path, entry_id: str) -> dict[str, Any] | None:
    path = plan_path(bibliography_dir, entry_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_plan(bibliography_dir: Path, entry_id: str, plan: dict[str, Any]) -> Path:
    bibliography_dir.mkdir(parents=True, exist_ok=True)
    plan["史略ID"] = entry_id
    plan.setdefault("schema", SCHEMA)
    path = plan_path(bibliography_dir, entry_id)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def save_source_graph(source_graph_dir: Path, entry_id: str, graph: dict[str, Any]) -> Path:
    source_graph_dir.mkdir(parents=True, exist_ok=True)
    graph["史略ID"] = entry_id
    path = source_graph_path(source_graph_dir, entry_id)
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def extract_book_title(citation: str) -> str:
    """从《书名·卷篇》取出书名（· 前）。"""
    text = str(citation or "").strip()
    m = re.search(r"《([^》]+)》", text)
    inner = m.group(1) if m else text
    return inner.split("·")[0].split("卷")[0].strip()


def is_ershi_shi_citation(citation: str) -> bool:
    return extract_book_title(citation) in ERSHI_SHI_TITLES


def normalize_for_match(text: str) -> str:
    """去空白与常见标点，简繁折叠，便于子串校验。"""
    t = str(text or "")
    t = "".join(_CHAR_FOLD.get(ch, ch) for ch in t)
    t = re.sub(r"[\s\u3000]+", "", t)
    t = re.sub(r"[，。、；：！？「」『』（）()\[\]【】《》""''·…—\-]", "", t)
    return t


def snippet_in_corpus(snippet: str, corpus: str) -> bool:
    if not snippet or not corpus:
        return False
    s = normalize_for_match(snippet)
    c = normalize_for_match(corpus)
    if len(s) < 4:
        return s in c
    # 允许摘句略短：取核心 12 字窗口
    if s in c:
        return True
    if len(s) >= 12 and s[:12] in c:
        return True
    return False


def _http_get_json(url: str, *, timeout: int = 30) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "pandahis-bibliography/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_text(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "pandahis-bibliography/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def ctext_readlink(page_url: str) -> str:
    params = urllib.parse.urlencode({"url": page_url})
    try:
        data = _http_get_json(f"{CTEXT_READLINK_URL}?{params}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return ""
    if isinstance(data, dict):
        return str(data.get("urn") or "")
    return ""


def resolve_ctext_page_url(citation: str) -> str:
    cite = str(citation or "")
    for needle, url in CTEXT_URL_HINTS:
        if needle in cite:
            return url
    return ""


def ctext_fetch_html_corpus(page_url: str) -> str:
    """从 ctext.org 章节页抽取可见古文（无需 API key）。"""
    if not page_url:
        return ""
    url = page_url if "?" in page_url else f"{page_url}?if=gb"
    try:
        html = _http_get_text(url)
    except (urllib.error.URLError, TimeoutError):
        return ""
    # 去掉 script/style
    html = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", "", html)
    parts = re.findall(r">([^<>]{6,}?[\u4e00-\u9fff][^<>]*?)<", html)
    zh = [p.strip() for p in parts if re.search(r"[\u4e00-\u9fff]{4,}", p)]
    return "".join(zh)


def ctext_gettext(urn: str) -> str:
    if not str(urn or "").strip():
        return ""
    params: dict[str, str] = {"urn": urn.strip()}
    api_key = os.environ.get("CTEXT_API_KEY", "").strip()
    if api_key:
        params["apikey"] = api_key
    url = f"{CTEXT_GETTEXT_URL}?{urllib.parse.urlencode(params)}"
    try:
        data = _http_get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    if "error" in data:
        return ""
    full = data.get("fulltext")
    if isinstance(full, list):
        return "".join(str(p) for p in full)
    return str(data.get("fulltext") or data.get("text") or "")


def ctext_fetch_corpus(citation: str, *, page_url: str = "") -> tuple[str, str]:
    """返回 (corpus, source_note)。"""
    url = page_url or resolve_ctext_page_url(citation)
    if url:
        corpus = ctext_fetch_html_corpus(url)
        if corpus:
            urn = ctext_readlink(url.split("?")[0])
            note = f"ctext HTML {url.split('?')[0]}"
            return corpus, note
    urn = ctext_readlink(url) if url else ""
    if urn:
        text = ctext_gettext(urn)
        if text:
            return text, f"ctext API {urn}"
    return "", "ctext 未命中原文"


def fetch_snippet_for_source(source: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """尝试 ctext 拉原文并校验摘句；返回更新后的 source 副本。"""
    out = dict(source)
    citation = str(out.get("出处") or "")
    tier = str(out.get("tier") or "")

    if not out.get("采用"):
        out["material_tier"] = "C"
        out["snippet_verified"] = False
        return out

    if tier == "正史-见翻译" or is_ershi_shi_citation(citation):
        out["采用"] = False
        out["material_tier"] = "C"
        out["snippet_verified"] = False
        out["fetch_note"] = "二十四史由翻译详录服务，拓展路不摘句"
        return out

    if dry_run:
        out.setdefault("fetch_note", "[dry-run] 将尝试 ctext 检索")
        return out

    proposed = str(out.get("原文摘句") or "").strip()
    corpus, fetch_note = ctext_fetch_corpus(citation)
    time.sleep(CTEXT_REQUEST_DELAY_SEC)
    page_url = resolve_ctext_page_url(citation)
    matched_urn = ctext_readlink(page_url.split("?")[0]) if page_url else ""

    if corpus and proposed and snippet_in_corpus(proposed, corpus):
        out["snippet_verified"] = True
        out["material_tier"] = "A"
        out["ctext_urn"] = matched_urn
        out["ctext_url"] = page_url.split("?")[0] if page_url else ""
        out["corpus_excerpt"] = corpus[:1200]
        out["fetch_note"] = f"摘句已通过子串校验（{fetch_note}）"
        return out

    if corpus:
        out["snippet_verified"] = False
        out["material_tier"] = "B"
        out["ctext_urn"] = matched_urn
        out["ctext_url"] = page_url.split("?")[0] if page_url else ""
        out["corpus_excerpt"] = corpus[:1200]
        if proposed and not snippet_in_corpus(proposed, corpus):
            out["原文摘句"] = ""
        out["fetch_note"] = f"已拉原文但摘句未校验，compose 仅可书目级引用（{fetch_note}）"
        return out

    out["snippet_verified"] = False
    out["material_tier"] = "B"
    out["fetch_note"] = fetch_note + "，compose 仅可书目级引用"
    return out


def fetch_all_snippets(
    plan: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """对 plan 中 采用:true 的条目执行 fetch，并汇总 material_summary。"""
    updated = dict(plan)
    sources = []
    counts = {"A": 0, "B": 0, "C": 0}
    for src in plan.get("候选著作") or []:
        if not isinstance(src, dict):
            continue
        if not src.get("采用"):
            unchanged = dict(src)
            unchanged.setdefault("material_tier", "C")
            unchanged.setdefault("snippet_verified", False)
            sources.append(unchanged)
            counts["C"] += 1
            continue
        new_src = fetch_snippet_for_source(src, dry_run=dry_run)
        tier = str(new_src.get("material_tier") or "C")
        if tier in counts:
            counts[tier] += 1
        sources.append(new_src)
    updated["候选著作"] = sources
    updated["material_summary"] = {
        "A_verified": counts["A"],
        "B_bibliography_only": counts["B"],
        "C_excluded": counts["C"],
        "overall": _overall_material_tier(counts),
    }
    return updated


def _overall_material_tier(counts: dict[str, int]) -> str:
    if counts["A"] > 0:
        return "A"
    if counts["B"] > 0:
        return "B"
    return "C"


def verify_plan(
    plan: dict[str, Any],
    *,
    entry_id: str = "",
    anchor: dict[str, Any] | None = None,
) -> BibVerifyReport:
    issues: list[BibIssue] = []
    eid = str(plan.get("史略ID") or entry_id or "")

    if plan.get("schema") != SCHEMA:
        issues.append(BibIssue("schema", f"schema 应为 {SCHEMA}", "error"))

    for i, src in enumerate(plan.get("候选著作") or []):
        if not isinstance(src, dict):
            issues.append(BibIssue("source_shape", f"候选著作[{i}] 非对象", "error"))
            continue
        prefix = f"候选[{i}]"
        citation = str(src.get("出处") or "").strip()
        if not citation or "《" not in citation:
            issues.append(
                BibIssue("citation_missing", f"{prefix} 缺少《书名》式出处", "error")
            )
        tier = str(src.get("tier") or "")
        if tier and tier not in TIER_VALUES:
            issues.append(BibIssue("tier_invalid", f"{prefix} tier 非法: {tier}", "warn"))
        if src.get("采用") and tier == "正史-见翻译":
            issues.append(
                BibIssue(
                    "ershi_adopted",
                    f"{prefix} 二十四史不可 采用:true（{citation}）",
                    "error",
                )
            )
        if src.get("采用") and is_ershi_shi_citation(citation) and tier != "正史-见翻译":
            issues.append(
                BibIssue(
                    "ershi_adopted",
                    f"{prefix} 出处似二十四史但未标 tier 正史-见翻译",
                    "error",
                )
            )
        mt = str(src.get("material_tier") or "")
        if mt and mt not in MATERIAL_TIERS:
            issues.append(BibIssue("material_tier", f"{prefix} material_tier 非法", "warn"))
        if src.get("snippet_verified") and not str(src.get("原文摘句") or "").strip():
            issues.append(
                BibIssue(
                    "verified_no_snippet",
                    f"{prefix} snippet_verified 但无摘句",
                    "error",
                )
            )
        if src.get("snippet_verified") and str(src.get("corpus_excerpt") or ""):
            snippet = str(src.get("原文摘句") or "")
            corpus = str(src.get("corpus_excerpt") or "")
            if snippet and not snippet_in_corpus(snippet, corpus):
                issues.append(
                    BibIssue(
                        "snippet_not_in_corpus",
                        f"{prefix} 摘句不在 corpus_excerpt 中",
                        "error",
                    )
                )

    adopted = [s for s in (plan.get("候选著作") or []) if isinstance(s, dict) and s.get("采用")]
    if not adopted and str(plan.get("material_summary", {}).get("overall") or "C") == "C":
        issues.append(
            BibIssue(
                "thin_material",
                "无采用条目，compose 须 C 档（留白/正史见翻译）",
                "warn",
            )
        )

    if anchor:
        forbidden = anchor.get("forbidden_inventions") or []
        for src in adopted:
            rel = str(src.get("与本主题关系") or "")
            snippet = str(src.get("原文摘句") or "")
            blob = rel + snippet
            for fb in forbidden:
                fb_s = str(fb)
                if len(fb_s) >= 4 and fb_s[:4] in blob:
                    issues.append(
                        BibIssue(
                            "anchor_forbidden",
                            f"书目/摘句触及 anchor forbidden: {fb_s[:30]}…",
                            "warn",
                        )
                    )

    errors = [i for i in issues if i.severity == "error"]
    return BibVerifyReport(passed=len(errors) == 0, issues=issues, entry_id=eid)


def normalize_plan_pools(plan: dict[str, Any]) -> dict[str, Any]:
    """为候选补 pool 标签；legend 池采用:true 最多 1 条。"""
    out = dict(plan)
    sources = []
    legend_adopted = 0
    for src in plan.get("候选著作") or []:
        if not isinstance(src, dict):
            continue
        item = dict(src)
        pool = str(item.get("pool") or "").strip()
        if pool not in ("primary", "legend"):
            tier = str(item.get("tier") or "")
            pool = "legend" if tier == "后世综述" else "primary"
        item["pool"] = pool
        if item.get("采用") and pool == "legend":
            legend_adopted += 1
            if legend_adopted > 1:
                item["采用"] = False
                item["fetch_note"] = "legend 池最多 1 条采用，已自动关闭"
        sources.append(item)
    out["候选著作"] = sources
    out["primary_sources"] = [s for s in sources if s.get("pool") == "primary"]
    out["legend_sources"] = [s for s in sources if s.get("pool") == "legend"]
    return out


def format_plan_for_prompt(plan: dict[str, Any]) -> str:
    """供 compose-detail 注入的纪律化文本。"""
    plan = normalize_plan_pools(plan)
    summary = plan.get("material_summary") or {}
    overall = summary.get("overall") or "C"
    lines = [
        f"整体材料档：**{overall}**（A=可展开摘句 B=仅书目 C=留白）",
        "",
        "### 写作结构（plan 指定）",
        str(plan.get("写作结构") or "（未指定）"),
        "",
        "### primary 池（主叙事 · 有出处优先）",
    ]
    for src in plan.get("primary_sources") or []:
        if not isinstance(src, dict):
            continue
        adopt = "✓采用" if src.get("采用") else "·未采用"
        mt = src.get("material_tier") or "?"
        verified = "verified" if src.get("snippet_verified") else "unverified"
        lines.append(
            f"- [{adopt}][{mt}/{verified}] {src.get('出处')} "
            f"（{src.get('tier') or '?'}）— {src.get('与本主题关系') or ''}"
        )
        if src.get("snippet_verified") and src.get("原文摘句"):
            lines.append(f"  原文摘句：{src.get('原文摘句')}")
    lines.append("")
    lines.append("### legend 池（低优先级 · 合段补充）")
    legend_list = plan.get("legend_sources") or []
    if not legend_list:
        lines.append("- （无）")
    for src in legend_list:
        if not isinstance(src, dict):
            continue
        adopt = "✓采用" if src.get("采用") else "·未采用"
        lines.append(f"- [{adopt}] {src.get('出处')} — {src.get('与本主题关系') or ''}")
    lines.extend(
        [
            "",
            "### compose 纪律（史料 plan）",
            "- **primary** → 起承转主叙事；**legend** → 至多 1 段合段",
            "- 传说/相传可以写（不必每句《》），但不可当家",
            "- A 档：可展开 verified 摘句；B 档：仅书目级异说",
            "- **A 档 verified 摘句**：正文须「摘句」+ 白话译述（共用规范 §6.1）",
            "- 锚点 hard_facts 须全覆盖；forbidden_inventions 仍禁止",
        ]
    )
    return "\n".join(lines)


def build_source_graph(plan: dict[str, Any]) -> dict[str, Any]:
    """审校通过后沉淀的轻量图谱。"""
    adopted = [
        {
            "出处": s.get("出处"),
            "tier": s.get("tier"),
            "material_tier": s.get("material_tier"),
            "snippet_verified": s.get("snippet_verified"),
            "ctext_urn": s.get("ctext_urn"),
        }
        for s in (plan.get("候选著作") or [])
        if isinstance(s, dict) and s.get("采用")
    ]
    return {
        "schema": "dynasty-knowledge-source-graph/v1",
        "史略ID": plan.get("史略ID"),
        "material_summary": plan.get("material_summary"),
        "sources": adopted,
    }
