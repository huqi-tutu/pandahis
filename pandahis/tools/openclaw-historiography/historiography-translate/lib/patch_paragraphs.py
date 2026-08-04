"""V2 段落增量补译：缺失段顺译 + 与 V1 成稿边界深度整合。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.config import paths
from lib.openclaw import run_agent_turn
from lib.source_citation import build_source_citation_from_entry
from lib.source_text import build_source_original_from_index_entry


EXCLUDED_IDS = frozenset({"GLBL_00007"})  # 卫灵公：本期不处理
DEFAULT_MANIFEST = (
    paths()["root"] / "data" / "11新标注条目翻译" / "待补全段落翻译" / "待补全清单.json"
)
DEFAULT_BASE_DIR = paths()["root"] / "data" / "11新标注条目翻译" / "待补全段落翻译"
DEFAULT_PATCH_OUTPUT_DIR = DEFAULT_BASE_DIR / "_patch_output"
DEFAULT_PROMOTE_DIR = paths()["root"] / "data" / "11新标注条目翻译"
DEFAULT_REUSE_MANIFEST = DEFAULT_PROMOTE_DIR / "翻译复用清单.json"


@dataclass
class PatchSpec:
    entry_id: str
    name: str
    side: str  # 开头 | 末尾
    missing_paras: List[int]
    v1_range: Tuple[int, int]
    v2_range: Tuple[int, int]
    work: str
    vol: str


def _norm_vol(v: str) -> str:
    s = str(v or "").strip()
    return s.zfill(3) if s.isdigit() else s


def _load_v2_index(index_path: Path | None) -> Dict[str, dict]:
    p = index_path or (paths()["root"] / "data" / "10新标注条目" / "史略索引_史记汉书.json")
    rows = json.loads(p.read_text(encoding="utf-8"))
    return {r["史略ID"]: r for r in rows}


def _moben_block(entry: dict) -> dict:
    for p in entry.get("paragraphs") or []:
        if p.get("role") == "母本":
            return p
    raise ValueError("无母本段落")


def _para_map(work: str, vol: str) -> Dict[int, str]:
    root = paths()["root"]
    fp = root / "data" / "03索引标注条目" / "段落索引" / f"{work}_{_norm_vol(vol)}.json"
    doc = json.loads(fp.read_text(encoding="utf-8"))
    return {int(p["id"]): str(p.get("text") or "") for p in doc.get("paragraphs") or []}


def load_paragraph_texts(work: str, vol: str, para_nums: List[int]) -> str:
    pm = _para_map(work, vol)
    lines = [pm[n].strip() for n in para_nums if pm.get(n, "").strip()]
    return "\n".join(lines)


def _split_body_refs(detail: str) -> Tuple[str, str]:
    if "*参考著作*" in detail:
        body, ref = detail.split("*参考著作*", 1)
        return body.strip(), "*参考著作*" + ref
    if "参考著作" in detail:
        parts = detail.rsplit("参考著作", 1)
        return parts[0].strip(), "参考著作" + parts[1]
    return detail.strip(), ""


def _body_paragraphs(body: str) -> List[str]:
    return [p.strip() for p in body.split("\n\n") if p.strip()]


def _boundary_zone(body: str, side: str, n: int) -> Tuple[str, str]:
    """返回 (将被替换的边界段, 衔接上下文摘录)。"""
    paras = _body_paragraphs(body)
    n = max(1, min(n, len(paras)))
    if side == "末尾":
        boundary = "\n\n".join(paras[-n:])
        context = "\n\n".join(paras[:-n][-2:]) if len(paras) > n else ""
        return boundary, context
    boundary = "\n\n".join(paras[:n])
    context = "\n\n".join(paras[n : n + 2]) if len(paras) > n else ""
    return boundary, context


def _clauses(text: str) -> List[str]:
    parts = re.split(r"[，。；！？、]", text)
    out = []
    for p in parts:
        c = re.sub(r'[""''\s]', "", p.strip())
        if len(c) >= 3:
            out.append(c)
    return out


def clause_overlap_ratio(missing_text: str, zone: str) -> float:
    clauses = _clauses(missing_text)
    if not clauses:
        return 0.0
    zone_clean = re.sub(r"\s", "", zone)
    hits = sum(1 for c in clauses if c in zone_clean or c[:4] in zone_clean)
    return hits / len(clauses)


def spec_from_manifest(entry_id: str, manifest: dict, v2_index: Dict[str, dict]) -> PatchSpec:
    row = next(e for e in manifest["entries"] if e["id"] == entry_id)
    v2e = v2_index[entry_id]
    moben = _moben_block(v2e)
    v2_from = int(moben["paragraph_from"])
    v2_to = int(moben["paragraph_to"])
    v1_from, v1_to = [int(x) for x in re.findall(r"P(\d+)", row.get("v1_range") or "")]
    return PatchSpec(
        entry_id=entry_id,
        name=str(row.get("name") or v2e.get("史略名称") or ""),
        side=str(row["side"]),
        missing_paras=list(row["missing_paras"]),
        v1_range=(v1_from, v1_to),
        v2_range=(v2_from, v2_to),
        work=str(moben["work"]),
        vol=_norm_vol(moben["vol"]),
    )


def build_patch_prompt(
    spec: PatchSpec,
    missing_text: str,
    context_text: str,
) -> str:
    pos = "篇首" if spec.side == "开头" else "篇末"
    ctx_label = "后接" if spec.side == "开头" else "前文"
    return f"""【historiography-translate · Phase1 缺失段顺译】

史略ID: {spec.entry_id} · {spec.name}

## 任务
仅顺译缺失母本段落 P{spec.missing_paras}，供后续与 V1 成稿边界整合。
禁止前置引入、禁止外部补全、禁止参考著作节。

## 要求
- 严格按缺失段原文句序
- **必须输出现代白话顺译**，与 V1 成稿风格一致
- **禁止**把上方「缺失母本原文」未改写的文言整句/整段搬进 patch_顺译
- 通识文言直接白话（崩→去世，立→即位；曰→说/认为）
- 不重复{ctx_label}已写事实
- 篇幅控制在缺失段信息量内
- **若缺失段为 P{spec.missing_paras} 共 {len(spec.missing_paras)} 段，patch_顺译 须用空行分段（\\n\\n），每段对应一段母本，共 {len(spec.missing_paras)} 段**

## 缺失母本原文
{missing_text}

## 相邻母本原文（{ctx_label}）
{context_text[:1200]}

## 输出 JSON
{{"史略ID": "{spec.entry_id}", "patch_顺译": "…"}}
"""


def build_integrate_prompt(
    spec: PatchSpec,
    *,
    missing_text: str,
    patch_text: str,
    boundary: str,
    context_snippet: str,
    overlap: float,
) -> str:
    side = spec.side
    pos = "篇首" if side == "开头" else "篇末"
    patch_block = patch_text.strip() or "（边界与缺失段高度重叠：请据母本原文补入尚未覆盖的信息点，勿重复已有表述。）"
    min_paras = max(1, len(spec.missing_paras))
    return f"""【historiography-translate · Phase2 边界深度整合】

史略ID: {spec.entry_id} · {spec.name}

## 任务
V2 母本在{pos}新增 P{spec.missing_paras}（共 {len(spec.missing_paras)} 段）。V1 成稿边界段可能已部分交代同类事实（重叠约 {overlap:.0%}）。
请将「V1 边界段」与「缺失段顺译」**深度整合**为连贯的多段正文，**整体替换**原边界段。
禁止生硬追加一段；禁止整合区内外重复同一事实（如葬地、崩逝、继位等只写一次）。

## 整合要求
1. **整合区必须是现代白话**，与 V1 成稿语气一致；**严禁**复制「缺失母本原文」未译文言
2. 以「缺失段顺译（Phase1）」为主要内容来源；母本原文仅供核对信息点
3. 缺失母本的信息点必须全部覆盖
4. 保留 V1 边界段中与母本不冲突的有效表述（含合理的外部补全 enrich），删并重复句
5. 若 V1 边界末段为总结/延伸（非母本复述），整合后须保留同等 enrich 信息
6. 语序自然，读起来像一篇写成，不是两段拼贴
7. **分段（硬性）**：整合区至少 {min_paras} 个自然段；**每个缺失母本段（P{spec.missing_paras}）各占一段或清晰分段**；段与段之间必须用空行分隔（输出中用 \\n\\n）
8. **禁止**把多段内容揉成一个超长段落
9. 不写参考著作节；不改动整合区以外的正文

## 缺失母本原文
{missing_text}

## 缺失段顺译（Phase1）
{patch_block}

## V1 边界段（将被替换）
{boundary}

## 衔接上下文（仅供语气参考，勿原样复述）
{context_snippet[:1500]}

## 输出 JSON（二选一，推荐数组）
{{"integrated_paragraphs": ["第1段…", "第2段…"]}}
或 {{"integrated_zone": "第1段…\\n\\n第2段…"}}
"""


def _normalize_cmp(text: str) -> str:
    return re.sub(r'[\s""''「」《》、，。；：！？]', "", text or "")


def _contains_verbatim_mother(output: str, mother: str, *, min_len: int = 24) -> bool:
    """检测输出是否含未译母本长片段。"""
    o = _normalize_cmp(output)
    m = _normalize_cmp(mother)
    if not o or not m:
        return False
    span = max(min_len, min(48, len(m) // 2))
    for i in range(0, max(1, len(m) - span + 1), 6):
        chunk = m[i : i + span]
        if len(chunk) >= min_len and chunk in o:
            return True
    return False


def _min_integrated_paragraphs(spec: PatchSpec) -> int:
    """整合区最少段落数：每个缺失母本段至少一段。"""
    return max(1, len(spec.missing_paras))


def _parse_integrated_output(obj: Dict[str, Any]) -> str:
    paras = obj.get("integrated_paragraphs")
    if isinstance(paras, list):
        parts = [str(p).strip() for p in paras if str(p).strip()]
        if parts:
            return "\n\n".join(parts)
    return str(obj.get("integrated_zone") or "").strip()


def _ensure_paragraph_structure(integrated: str, spec: PatchSpec, patch_text: str) -> str:
    """整合结果为单段时，尝试按 Phase1 分段界补回空行。"""
    min_paras = _min_integrated_paragraphs(spec)
    if len(_body_paragraphs(integrated)) >= min_paras:
        return integrated

    patch_paras = _body_paragraphs(patch_text)
    if len(patch_paras) >= min_paras:
        split = _split_by_patch_anchors(integrated, patch_paras)
        if len(_body_paragraphs(split)) >= min_paras:
            return split

    return integrated


def _split_by_patch_anchors(integrated: str, patch_paras: List[str]) -> str:
    """用 Phase1 各段开头片段在整合文本中切分段落。"""
    text = integrated.strip()
    if not text or len(patch_paras) <= 1:
        return text

    anchors: List[Tuple[int, str]] = []
    for para in patch_paras:
        probe = re.sub(r"\s", "", para)[:18]
        if len(probe) < 8:
            continue
        pos = 0
        found = -1
        compact = re.sub(r"\s", "", text)
        idx = compact.find(probe)
        if idx != -1:
            # 近似映射回原文位置
            count = 0
            for i, ch in enumerate(text):
                if not ch.isspace():
                    if count == idx:
                        found = i
                        break
                    count += 1
        if found >= 0:
            anchors.append((found, para))

    anchors.sort(key=lambda x: x[0])
    if len(anchors) < 2:
        return text

    cuts = [a[0] for a in anchors]
    chunks: List[str] = []
    for i, start in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
    return "\n\n".join(chunks) if len(chunks) >= 2 else text


def _run_integrate_phase(
    spec: PatchSpec,
    *,
    missing_text: str,
    patch_text: str,
    boundary: str,
    context_snippet: str,
    overlap: float,
    entry_id: str,
    retry_note: str = "",
) -> Tuple[str | None, str]:
    p2 = build_integrate_prompt(
        spec,
        missing_text=missing_text,
        patch_text=patch_text,
        boundary=boundary,
        context_snippet=context_snippet,
        overlap=overlap,
    )
    if retry_note:
        p2 = retry_note + "\n\n" + p2
    obj2 = _run_llm_json(p2, "p2", entry_id)
    if not obj2:
        return None, "Phase2 整合 LLM 未返回有效 JSON"
    integrated = _parse_integrated_output(obj2)
    if not integrated:
        return None, "Phase2 输出缺少 integrated_zone / integrated_paragraphs"
    if _contains_verbatim_mother(integrated, missing_text):
        return None, "Phase2 输出含未译母本原文"
    min_paras = _min_integrated_paragraphs(spec)
    if len(_body_paragraphs(integrated)) < min_paras:
        return None, f"Phase2 整合区未分段（需至少 {min_paras} 段）"
    return integrated, "llm_integrate"


def _extract_json(text: str) -> Dict[str, Any] | None:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("{"), text.rfind("}")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return None
    for candidate in (raw, _escape_newlines_in_json_strings(raw)):
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            continue
    # 兜底：按字段名提取（LLM 常在字符串值内输出真实换行）
    out: Dict[str, Any] = {}
    for field in ("integrated_zone", "patch_顺译", "母本顺译", "史略ID"):
        val = _extract_json_string_field(raw, field)
        if val is not None:
            out[field] = val
    # integrated_paragraphs 数组
    m_arr = re.search(r'"integrated_paragraphs"\s*:\s*\[(.*)\]\s*\}', raw, re.DOTALL)
    if m_arr and "integrated_paragraphs" not in out:
        try:
            arr = json.loads("[" + m_arr.group(1) + "]")
            if isinstance(arr, list):
                out["integrated_paragraphs"] = arr
        except json.JSONDecodeError:
            pass
    return out or None


def _escape_newlines_in_json_strings(raw: str) -> str:
    """将 JSON 字符串值内的裸换行替换为 \\n。"""
    out: List[str] = []
    in_str = False
    esc = False
    for ch in raw:
        if not in_str:
            out.append(ch)
            if ch == '"':
                in_str = True
            continue
        if esc:
            out.append(ch)
            esc = False
            continue
        if ch == "\\":
            out.append(ch)
            esc = True
            continue
        if ch == '"':
            out.append(ch)
            in_str = False
            continue
        if ch == "\n":
            out.append("\\n")
            continue
        if ch == "\r":
            continue
        out.append(ch)
    return "".join(out)


def _extract_json_string_field(raw: str, field: str) -> str | None:
    marker = f'"{field}"'
    idx = raw.find(marker)
    if idx == -1:
        return None
    start = raw.find('"', idx + len(marker))
    if start == -1:
        return None
    start += 1
    buf: List[str] = []
    esc = False
    i = start
    while i < len(raw):
        ch = raw[i]
        if esc:
            buf.append(ch)
            esc = False
            i += 1
            continue
        if ch == "\\":
            esc = True
            i += 1
            continue
        if ch == '"':
            return "".join(buf)
        buf.append(ch)
        i += 1
    return "".join(buf) if buf else None


def _is_prepend_before_v1(spec: PatchSpec) -> bool:
    """缺失母本段 entirely 在 V1 母本范围之前（如 P27 而 V1 从 P28 起）。"""
    return spec.side == "开头" and max(spec.missing_paras) < spec.v1_range[0]


def _is_append_after_v1(spec: PatchSpec) -> bool:
    """缺失母本段 entirely 在 V1 母本范围之后（如 P41 而 V1 到 P40）。"""
    return spec.side == "末尾" and min(spec.missing_paras) > spec.v1_range[1]


def resolve_patch_mode(spec: PatchSpec) -> str:
    """prepend | append | integrate"""
    if _is_prepend_before_v1(spec):
        return "prepend"
    if _is_append_after_v1(spec):
        return "append"
    return "integrate"


def compute_boundary_paras(spec: PatchSpec) -> int:
    """integrate 模式才需要替换边界；append/prepend 不删 V1 段落。"""
    mode = resolve_patch_mode(spec)
    if mode in ("append", "prepend"):
        return 0
    n = len(spec.missing_paras)
    return max(1, min(n, 2))


_ENRICH_MARKERS = (
    "至此",
    "回顾",
    "侧面反映",
    "完美呼应",
    "盖棺",
    "换句话说",
    "主脉络",
    "最高处",
    "传奇",
    "在先秦时期",
    "活成了",
    "不可忽视",
)


def _is_likely_enrich_para(para: str, *, mother_hint: str = "") -> bool:
    if not para.strip():
        return False
    hits = sum(1 for m in _ENRICH_MARKERS if m in para)
    if hits == 0:
        return False
    if mother_hint and clause_overlap_ratio(para, mother_hint) >= 0.45:
        return False
    return True


def _is_likely_intro_para(para: str) -> bool:
    intro_markers = ("我们要讲", "事情还得", "在这", "战国", "乱世里", "国际舞台", "古史的叙事")
    return any(m in para[:120] for m in intro_markers)


def _split_tail_enrich(paras: List[str], *, v1_last_mother: str) -> Tuple[List[str], str]:
    """若末段为纯 enrich 总结，拆出以便 append 后保留；母本与 enrich 混合段不拆。"""
    if not paras:
        return paras, ""
    last = paras[-1]
    if not _is_likely_enrich_para(last, mother_hint=v1_last_mother):
        return paras, ""
    if v1_last_mother:
        overlap = clause_overlap_ratio(v1_last_mother, last)
        if overlap >= 0.35:
            return paras, ""
    return paras[:-1], last


def merge_prepend_head(body: str, head_zone: str, *, preserve_intro: bool) -> str:
    """段首 prepend：保留 V1 引言段，在其后插入缺失段译文，再接余下正文。"""
    paras = _body_paragraphs(body)
    head_paras = _body_paragraphs(head_zone.strip())
    if preserve_intro and paras and _is_likely_intro_para(paras[0]):
        return "\n\n".join([paras[0], *head_paras, *paras[1:]])
    return "\n\n".join([*head_paras, *paras])


def merge_append_tail(body: str, new_zone: str, *, enrich_tail: str = "") -> str:
    """段末 append：保留全部 V1 正文，追加缺失段；enrich 总结置于最末。"""
    paras = _body_paragraphs(body)
    new_paras = _body_paragraphs(new_zone.strip())
    merged = [*paras, *new_paras]
    if enrich_tail.strip():
        merged.append(enrich_tail.strip())
    return "\n\n".join(merged)


def _extract_clause_names(clause: str) -> set[str]:
    """从母本子句提取人名（帝X、X崩、弟X立、生子曰X）。"""
    names: set[str] = set()
    for m in re.finditer(r"帝([一-龥]{1,2})(?:崩|立|，|,|$)", clause):
        names.add(m.group(1))
    for m in re.finditer(r"([一-龥]{2})(?:崩|薨)", clause):
        names.add(m.group(1))
    for m in re.finditer(r"弟([一-龥]{1,2})立", clause):
        names.add(m.group(1))
    for m in re.finditer(r"生子曰([一-龥]{1,3})", clause):
        names.add(m.group(1))
    for m in re.finditer(r"([一-龥]{2})立", clause):
        names.add(m.group(1))
    return names


def _clause_likely_covered(clause: str, preceding: str) -> bool:
    """启发式：母本子句的核心信息是否已在 V1 末段（白话）出现。"""
    c = re.sub(r"\s", "", clause)
    p = re.sub(r"\s", "", preceding)
    if not c or not p:
        return False
    names = _extract_clause_names(c)
    if not names:
        if "衰" in c and "衰" in p:
            return True
        return False
    name_hits = sum(1 for n in names if n in p)
    if name_hits < max(1, len(names) * 0.5):
        return False
    checks: List[bool] = []
    if re.search(r"崩|薨", c):
        dm = re.search(r"([一-龥]{2})(?:崩|薨)", c)
        if dm:
            dead = dm.group(1)
            checks.append(
                dead in p and any(x in p for x in ("崩", "去世", "死后", "驾崩"))
            )
        else:
            checks.append(any(x in p for x in ("崩", "去世", "死后", "驾崩")))
    if re.search(r"立|即", c):
        checks.append(any(x in p for x in ("即位", "继位", "接替", "立", "继承")))
    if "衰" in c:
        checks.append("衰" in p)
    if "作" in c and "盘庚" in c:
        checks.append("《盘庚》" in p or "三篇" in p or ("百姓" in p and "盘庚" in p and "作" in p))
    if "生子" in c:
        sm = re.search(r"生子曰([一-龥]+)", c)
        if sm:
            son = sm.group(1)
            checks.append(son in p and ("儿子" in p or "名叫" in p or "生" in p))
    if not checks:
        return name_hits >= len(names) * 0.8
    return all(checks)


def compute_missing_delta(missing_mother: str, preceding: str) -> Tuple[List[str], List[str]]:
    """返回 (已覆盖子句, 待追加子句)。"""
    raw = [c.strip() for c in re.split(r"[。；]", missing_mother) if c.strip()]
    clauses: List[str] = []
    for part in raw:
        subs = [s.strip() for s in part.split("，") if s.strip()]
        clauses.extend(subs if len(subs) > 1 else [part])
    covered, delta = [], []
    for clause in clauses:
        if _clause_likely_covered(clause, preceding):
            covered.append(clause)
        else:
            delta.append(clause)
    return covered, delta


def audit_append_redundancy(preceding: str, append: str) -> List[str]:
    """检测追加段是否重复 V1 末段的继位/崩逝叙述。"""
    issues: List[str] = []
    if not preceding.strip() or not append.strip():
        return issues
    death_pat = r"(.{1,6})(?:死后|去世后|去世|驾崩|崩)"
    m1, m2 = re.search(death_pat, preceding), re.search(death_pat, append)
    if m1 and m2:
        subj1, subj2 = m1.group(1).strip(), m2.group(1).strip()
        if subj1 in subj2 or subj2 in subj1 or subj1[-2:] == subj2[-2:]:
            if re.search(r"(即位|继位|接替|立)", preceding) and re.search(r"(即位|继位|接替|立)", append):
                issues.append(f"重复继位叙述：{subj1}→继任者在末段与追加段各写一次")
    if re.search(r"(衰|衰落|中衰)", preceding) and re.search(r"(衰|衰落|中衰)", append):
        if m1 and m2:
            issues.append("重复衰落叙述：末段与追加段均写国势衰落")
    return issues


def audit_prepend_transition(intro: str, prepend: str) -> List[str]:
    """检测 prepend 段与 V1 引言是否频道错位。"""
    issues: List[str] = []
    if not intro.strip() or not prepend.strip():
        return issues
    if re.search(r"(然而|但是|不过)，?\s*(?:晋|楚|郑|韩|魏|卫|宋|秦|周|帝|公|王)", prepend[:48]):
        if re.search(r"(让我们|顺着|记载|往下看|如何|怎样|登上历史舞台)", intro):
            issues.append("prepend 以「然而+前代君主」起笔，与引言频道冲突")
    if prepend.strip().startswith("然而") and len(intro) > 80:
        issues.append("prepend 不宜以「然而」硬接引言")
    return issues


def build_prepend_integrate_prompt(
    spec: PatchSpec,
    *,
    missing_text: str,
    patch_text: str,
    anchor_mother: str,
    next_body_snippet: str,
    v1_intro_snippet: str = "",
) -> str:
    intro_block = ""
    if v1_intro_snippet.strip():
        intro_block = f"""
## V1 引言段（保留在全文最前，你的输出紧接其后）
{v1_intro_snippet[:1000]}

## 过渡段写法（重要）
缺失母本 P{spec.missing_paras} 若是 **前代君主末路→本传主即位** 的过渡段：
1. **承上**：用一两句从引言自然切入（如「要弄清{{name}}如何即位，须先回看前朝最后一幕」），勿与引言重复已说结论
2. **弱化前代**：前代君主（如厉公）只作背景，一笔带过其败局，勿展开前朝细节、勿抢戏
3. **快速归本传主**：段末必须落到 **{{name}}** 被立/即位，语气转向当前人物
4. **禁止**以「然而，某某公……」起笔硬顺译母本——引言已在讲本传主，prepend 不是另起炉灶
5. **禁止**段首使用与引言同频道冲突的转折词（然而/但是）直接回到前代主线
6. 后接 P{spec.v1_range[0]} 已写的内容勿重复（见下方摘录）
""".format(name=spec.name)
    return f"""【historiography-translate · Phase2 段首 prepend 过渡整合】

史略ID: {spec.entry_id} · {spec.name}
{intro_block}
## 任务
V2 母本在 V1 范围之前新增了 P{spec.missing_paras}。请润色为 **过渡段**，输出 prepend 到引言段之后。
V1 引言段 **保留不动**；你只输出接在引言后的段落。

## 要求
1. 覆盖 P{spec.missing_paras} 母本全部信息点（现代白话）
2. 禁止复制未译母本原文
3. 与引言、后接 P{spec.v1_range[0]} 形成 **同一叙事频道**，读起来像一段连贯叙述
4. 输出 1 段为宜（过渡段宜紧凑），段间用 \\n\\n

## 缺失母本原文
{missing_text}

## 缺失段顺译（Phase1）
{patch_text}

## 后接母本原文（P{spec.v1_range[0]}，勿重复）
{anchor_mother[:800]}

## 后接成稿摘录（勿重复）
{next_body_snippet[:800]}

## 输出 JSON
{{"integrated_paragraphs": ["…"]}} 或 {{"integrated_zone": "…\\n\\n…"}}
"""


def build_append_integrate_prompt(
    spec: PatchSpec,
    *,
    missing_text: str,
    patch_text: str,
    preceding_snippet: str,
    enrich_tail: str,
    v1_last_mother: str,
    delta_clauses: List[str],
    covered_clauses: List[str],
) -> str:
    min_paras = max(1, len(spec.missing_paras)) if delta_clauses else 0
    enrich_block = (
        f"\n## V1 末段 enrich 总结（须原样保留在全文最末，整合区勿改写、勿重复）\n{enrich_tail[:1200]}"
        if enrich_tail.strip()
        else ""
    )
    if not delta_clauses:
        delta_block = """
## 增量判定（重要）
V1 末段 **已完整覆盖** 缺失母本 P{ps} 的全部信息点。
请输出空数组：{{"integrated_paragraphs": []}}
不要输出任何追加段落。
""".format(ps=",".join(str(p) for p in spec.missing_paras))
        min_paras = 0
    else:
        delta_block = f"""
## 增量判定（重要）
V1 末段 **已写过** 以下母本子句（追加区严禁用任何措辞重复）：
{chr(10).join(f"- {c}" for c in covered_clauses) or "（无）"}

追加区 **只需** 顺译以下尚未出现的信息点：
{chr(10).join(f"- {c}" for c in delta_clauses)}

禁止重写「谁去世/谁即位/国势衰落」等已在末段出现的事件；禁止同义改写。
"""
    return f"""【historiography-translate · Phase2 段末 append 增量整合】

史略ID: {spec.entry_id} · {spec.name}

## 任务
V2 母本在 V1 范围 P{spec.v1_range[0]}-P{spec.v1_range[1]} **之后**新增了 P{spec.missing_paras}。
V1 已有译文 **全部保留**；你只输出「待追加的增量段落」，不得重复 V1 末段已写语义。
{delta_block}

## 要求
1. 仅翻译增量信息点（现代白话）；已覆盖子句一字不提
2. 禁止复制未译母本原文
3. 与 V1 末段衔接自然，但不要复述末段任何事件
4. 输出 integrated_paragraphs 数组；若无增量则输出 []
5. 不写参考著作节{"" if not enrich_tail else "；enrich 总结由系统保留"}

## 缺失母本原文（全文，仅供对照）
{missing_text}

## 缺失段顺译（Phase1，需按增量裁剪）
{patch_text}

## V1 末段母本 P{spec.v1_range[1]}
{v1_last_mother[:800]}

## V1 成稿末段（已写，严禁重复其语义）
{preceding_snippet[:1200]}
{enrich_block}

## 输出 JSON
{{"integrated_paragraphs": ["…"]}} 或 {{"integrated_paragraphs": []}}
"""


def merge_integrated_zone(body: str, integrated_zone: str, side: str, boundary_n: int) -> str:
    paras = _body_paragraphs(body)
    n = max(1, min(boundary_n, len(paras)))
    integrated_paras = _body_paragraphs(integrated_zone.strip())
    if side == "末尾":
        kept = paras[:-n] if len(paras) > n else []
        merged = [*kept, *integrated_paras]
    else:
        rest = paras[n:] if len(paras) > n else []
        merged = [*integrated_paras, *rest]
    return "\n\n".join(merged)


def update_source_fields(data: dict, v2_entry: dict) -> None:
    data_root = paths()["data"]
    data["史料原文"] = build_source_original_from_index_entry(v2_entry, data_root=data_root)
    citation = build_source_citation_from_entry(v2_entry)
    if citation:
        data["原文出处"] = citation


def resolve_base_path(entry_id: str, base_dir: Path) -> Path:
    matches = list(base_dir.glob(f"{entry_id}_*.json"))
    if not matches:
        raise FileNotFoundError(f"未找到基稿: {base_dir}/{entry_id}_*.json")
    return matches[0]


def resolve_patch_output_path(entry_id: str, patch_file: Path | None = None) -> Path:
    """定位待 promote 的 patch 产出；基稿已清理时仍可从 _patch_output 找到。"""
    if patch_file and patch_file.is_file():
        return patch_file
    matches = list(DEFAULT_PATCH_OUTPUT_DIR.glob(f"{entry_id}_*.json"))
    if not matches:
        raise FileNotFoundError(f"未找到 patch 产出: {DEFAULT_PATCH_OUTPUT_DIR}/{entry_id}_*.json")
    return matches[0]


def _run_llm_json(prompt: str, session_suffix: str, entry_id: str) -> Dict[str, Any] | None:
    result = run_agent_turn(prompt, session_id=f"patch-{session_suffix}-{entry_id}", timeout_sec=600)
    raw = str(result.get("result") or "").strip()
    return _extract_json(raw)


def patch_paragraphs(
    entry_id: str,
    *,
    base_file: Path | None = None,
    output_dir: Path | None = None,
    manifest_path: Path | None = None,
    index_path: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    skip_llm: bool = False,
    boundary_paras: int | None = None,
) -> Tuple[bool, str]:
    if entry_id in EXCLUDED_IDS:
        return False, f"{entry_id} 在本期排除列表，跳过"

    manifest_path = manifest_path or DEFAULT_MANIFEST
    if not manifest_path.is_file():
        return False, f"清单不存在: {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not any(e["id"] == entry_id for e in manifest.get("entries") or []):
        return False, f"{entry_id} 不在待补全清单中"

    v2_index = _load_v2_index(index_path)
    if entry_id not in v2_index:
        return False, f"{entry_id} 不在 V2 索引"

    spec = spec_from_manifest(entry_id, manifest, v2_index)
    v2_entry = v2_index[entry_id]

    base_path = base_file or resolve_base_path(entry_id, DEFAULT_BASE_DIR)
    base = json.loads(base_path.read_text(encoding="utf-8"))
    detail = str(base.get("翻译详情") or "").strip()
    if not detail:
        return False, "基稿缺少翻译详情"

    body, refs = _split_body_refs(detail)
    missing_text = load_paragraph_texts(spec.work, spec.vol, spec.missing_paras)
    if not missing_text.strip():
        return False, f"缺失段 P{spec.missing_paras} 无原文"

    pm = _para_map(spec.work, spec.vol)
    anchor_pn = spec.v1_range[0] if spec.side == "开头" else spec.v1_range[1]
    anchor_mother = pm.get(anchor_pn, "")

    patch_mode = resolve_patch_mode(spec)
    effective_boundary = boundary_paras if boundary_paras is not None else compute_boundary_paras(spec)

    prepend_mode = patch_mode == "prepend"
    append_mode = patch_mode == "append"
    integrate_mode = patch_mode == "integrate"

    body_paras = _body_paragraphs(body)
    enrich_tail = ""
    merge_body = body
    covered_clauses: List[str] = []
    delta_clauses: List[str] = []
    v1_intro_snippet = ""
    if append_mode:
        v1_last_mother = pm.get(spec.v1_range[1], "")
        kept, enrich_tail = _split_tail_enrich(body_paras, v1_last_mother=v1_last_mother)
        merge_body = "\n\n".join(kept)
        preceding_snippet = kept[-1] if kept else ""
        covered_clauses, delta_clauses = compute_missing_delta(missing_text, preceding_snippet)
        boundary = ""
        context_snippet = preceding_snippet
        overlap = 0.0
    elif prepend_mode:
        next_snippet = body_paras[1] if len(body_paras) > 1 else ""
        v1_intro_snippet = ""
        if body_paras and _is_likely_intro_para(body_paras[0]):
            v1_intro_snippet = body_paras[0]
            next_snippet = body_paras[1] if len(body_paras) > 1 else body_paras[0]
        boundary = ""
        context_snippet = next_snippet
        overlap = 0.0
    else:
        boundary, context_snippet = _boundary_zone(body, spec.side, effective_boundary)
        overlap = clause_overlap_ratio(missing_text, boundary)
        preceding_snippet = context_snippet

    out_dir = output_dir or DEFAULT_PATCH_OUTPUT_DIR
    out_path = out_dir / base_path.name

    if dry_run:
        return True, (
            f"dry-run {entry_id} {spec.name}: mode={patch_mode} missing=P{spec.missing_paras} "
            f"boundary_paras={effective_boundary} enrich_tail={'有' if enrich_tail else '无'} "
            f"delta={len(delta_clauses)} covered={len(covered_clauses)} "
            f"→ {out_path}（基稿保留在待补全段落翻译/，待人工确认后再 promote）"
        )

    patch_text = ""
    patch_source = "llm_integrate"
    integrate_source = "llm_integrate"

    if skip_llm:
        patch_text = f"[skip-llm 占位] P{spec.missing_paras}"
        if append_mode:
            integrated_zone = patch_text
        elif prepend_mode:
            integrated_zone = patch_text
        else:
            integrated_zone = merge_integrated_zone(body, patch_text, spec.side, effective_boundary)
        integrate_source = "skip_llm"
    else:
        # Phase1: 缺失段顺译（高重叠时可跳过独立顺译，直接整合）
        if overlap >= 0.5 and not force:
            patch_text = ""
            patch_source = "skipped_patch_dedup"
        else:
            p1 = build_patch_prompt(spec, missing_text, anchor_mother)
            obj1 = _run_llm_json(p1, "p1", entry_id)
            if not obj1:
                return False, "Phase1 LLM 未返回有效 JSON"
            patch_text = str(obj1.get("patch_顺译") or obj1.get("母本顺译") or "").strip()
            patch_source = "llm_patch"
            if not patch_text:
                return False, "Phase1 输出缺少 patch_顺译"
            if len(spec.missing_paras) > 1 and len(_body_paragraphs(patch_text)) < len(spec.missing_paras):
                obj1p = _run_llm_json(
                    f"上次顺译未按母本分段。必须输出 {len(spec.missing_paras)} 段，段间用 \\n\\n。\n\n" + p1,
                    "p1p",
                    entry_id,
                )
                if obj1p:
                    patch_text = str(obj1p.get("patch_顺译") or obj1p.get("母本顺译") or "").strip()
            if _contains_verbatim_mother(patch_text, missing_text):
                obj1r = _run_llm_json(
                    "上次顺译含未译文言原文，必须全部改为现代白话。\n\n" + p1,
                    "p1r",
                    entry_id,
                )
                if obj1r:
                    patch_text = str(obj1r.get("patch_顺译") or obj1r.get("母本顺译") or "").strip()
                if not patch_text or _contains_verbatim_mother(patch_text, missing_text):
                    return False, "Phase1 顺译仍含未译母本原文"

        # Phase2: 边界深度整合（必做，含未译文言检测与重试）
        integrated_zone = None
        integrate_source = "llm_integrate"
        retry_note = ""
        for attempt in range(3):
            if append_mode:
                p2 = build_append_integrate_prompt(
                    spec,
                    missing_text=missing_text,
                    patch_text=patch_text,
                    preceding_snippet=preceding_snippet,
                    enrich_tail=enrich_tail,
                    v1_last_mother=pm.get(spec.v1_range[1], ""),
                    delta_clauses=delta_clauses,
                    covered_clauses=covered_clauses,
                )
                if retry_note:
                    p2 = retry_note + "\n\n" + p2
                obj2 = _run_llm_json(p2, "p2-app", entry_id)
                if not obj2:
                    integrated_zone, err = None, "Phase2 append LLM 未返回有效 JSON"
                else:
                    paras_out = obj2.get("integrated_paragraphs")
                    if isinstance(paras_out, list) and len(paras_out) == 0:
                        integrated_zone = ""
                        err = ""
                    else:
                        integrated_zone = _parse_integrated_output(obj2)
                        err = ""
                    if delta_clauses and not integrated_zone:
                        err = err or "Phase2 有增量但未输出追加段落"
                    elif integrated_zone and _contains_verbatim_mother(integrated_zone, missing_text):
                        integrated_zone, err = None, "Phase2 输出含未译母本原文"
                    elif integrated_zone:
                        redun = audit_append_redundancy(preceding_snippet, integrated_zone)
                        if redun:
                            integrated_zone, err = None, "Phase2 追加段与 V1 末段语义重复：" + "；".join(redun)
            elif prepend_mode:
                p2 = build_prepend_integrate_prompt(
                    spec,
                    missing_text=missing_text,
                    patch_text=patch_text,
                    anchor_mother=anchor_mother,
                    next_body_snippet=next_snippet,
                    v1_intro_snippet=v1_intro_snippet,
                )
                if retry_note:
                    p2 = retry_note + "\n\n" + p2
                obj2 = _run_llm_json(p2, "p2-pre", entry_id)
                if not obj2:
                    integrated_zone, err = None, "Phase2 prepend LLM 未返回有效 JSON"
                else:
                    integrated_zone = _parse_integrated_output(obj2)
                    err = ""
                    if not integrated_zone:
                        err = "Phase2 输出缺少 integrated_zone"
                    elif _contains_verbatim_mother(integrated_zone, missing_text):
                        integrated_zone, err = None, "Phase2 输出含未译母本原文"
                    elif integrated_zone and v1_intro_snippet:
                        trans = audit_prepend_transition(v1_intro_snippet, integrated_zone)
                        if trans:
                            integrated_zone, err = None, "Phase2 prepend 过渡段与引言频道错位：" + "；".join(trans)
            else:
                integrated_zone, err = _run_integrate_phase(
                    spec,
                    missing_text=missing_text,
                    patch_text=patch_text,
                    boundary=boundary,
                    context_snippet=context_snippet,
                    overlap=overlap,
                    entry_id=entry_id,
                    retry_note=retry_note,
                )
            if integrated_zone is not None:
                if integrated_zone:
                    integrated_zone = _ensure_paragraph_structure(integrated_zone, spec, patch_text)
                break
            if append_mode and "语义重复" in (err or ""):
                retry_note = (
                    "【纠错】追加段重复了 V1 末段已写事件（继位/崩逝/衰落）。"
                    "只写增量信息点，已覆盖子句一律删除，禁止同义改写。"
                )
            elif prepend_mode and "频道错位" in (err or ""):
                retry_note = (
                    "【纠错】过渡段与引言不在同一频道。勿以「然而+前代君主」起笔；"
                    "先从引言自然承接，弱化前代、快速落到本传主即位。"
                )
            elif "未分段" in (err or ""):
                retry_note = (
                    "【纠错】上次整合把所有内容揉成一个段落。"
                    f"必须输出至少 { _min_integrated_paragraphs(spec) } 个自然段，"
                    "每个缺失母本段（P"
                    + ",".join(str(p) for p in spec.missing_paras)
                    + "）各占一段，段间用 \\n\\n 或 integrated_paragraphs 数组。"
                )
            else:
                retry_note = (
                    "【纠错】上次整合输出含未译文言原文或格式无效。"
                    "整合区必须是现代白话，严禁复制母本原文；请基于 Phase1 顺译重写并正确分段。"
                )
        if not integrated_zone and integrated_zone != "":
            if append_mode and not delta_clauses:
                integrated_zone = ""
            elif patch_text:
                integrated_zone = _ensure_paragraph_structure(patch_text, spec, patch_text)
                integrate_source = "fallback_patch_only"
            else:
                return False, err or "Phase2 整合失败"

    merged_body = (
        merge_append_tail(merge_body, integrated_zone, enrich_tail=enrich_tail)
        if append_mode
        else merge_prepend_head(
            body,
            integrated_zone,
            preserve_intro=bool(body_paras and _is_likely_intro_para(body_paras[0])),
        )
        if prepend_mode
        else merge_integrated_zone(body, integrated_zone, spec.side, effective_boundary)
    )

    audit = audit_v1_mother_preservation(
        str(base.get("翻译详情") or ""),
        merged_body + (f"\n\n{refs}" if refs else ""),
        spec,
        pm,
    )
    if audit.get("lost_clauses"):
        return False, (
            f"合并后 V1 母本信息丢失（P{spec.v1_range[0]}-P{spec.v1_range[1]}）："
            + "；".join(audit["lost_clauses"][:5])
        )

    merged_detail = merged_body + (f"\n\n{refs}" if refs else "")

    out_dir.mkdir(parents=True, exist_ok=True)
    out = dict(base)
    out["翻译详情"] = merged_detail
    update_source_fields(out, v2_entry)
    out["_patch_meta"] = {
        "schema": "paragraph_patch/v2",
        "patched_at": datetime.now(timezone.utc).isoformat(),
        "side": spec.side,
        "missing_paras": spec.missing_paras,
        "v1_range": f"P{spec.v1_range[0]}-P{spec.v1_range[1]}",
        "v2_range": f"P{spec.v2_range[0]}-P{spec.v2_range[1]}",
        "boundary_paras": effective_boundary,
        "patch_mode": patch_mode,
        "dedup_overlap": round(overlap, 4),
        "patch_source": patch_source if not skip_llm else "skip_llm",
        "integrate_source": integrate_source,
        "prepend_mode": prepend_mode,
        "append_mode": append_mode,
        "enrich_tail_preserved": bool(enrich_tail),
        "delta_clauses": delta_clauses,
        "covered_clauses": covered_clauses,
        "integrated_paragraph_count": len(_body_paragraphs(integrated_zone)),
        "min_integrated_paragraphs": _min_integrated_paragraphs(spec),
        "base_file": str(base_path),
        "output_file": str(out_path),
        "status": "pending_review",
        "note": "产出在 _patch_output，基稿未动；人工确认后再 promote 至 11 第一层",
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, (
        f"patch+integrate 完成 → {out_path} "
        f"(mode={patch_mode}, overlap={overlap:.0%}, boundary={effective_boundary}；基稿仍保留，待人工确认)"
    )


def _v1_mother_text(spec: PatchSpec, pm: Dict[int, str]) -> str:
    parts = [pm.get(n, "").strip() for n in range(spec.v1_range[0], spec.v1_range[1] + 1)]
    return "\n".join(p for p in parts if p)


def audit_v1_mother_preservation(
    v1_detail: str,
    patch_detail: str,
    spec: PatchSpec,
    pm: Dict[int, str],
) -> Dict[str, Any]:
    """检测 patch 产出是否丢失 V1 范围内母本的关键信息。"""
    v1_body = _split_body_refs(v1_detail)[0]
    patch_body = _split_body_refs(patch_detail)[0]
    mother = _v1_mother_text(spec, pm)
    if not mother.strip():
        return {"lost_clauses": [], "ratio": 1.0}

    v1_norm = _normalize_cmp(v1_body)
    patch_norm = _normalize_cmp(patch_body)
    clauses = _clauses(mother)
    if not clauses:
        return {"lost_clauses": [], "ratio": 1.0}

    lost: List[str] = []
    for c in clauses:
        if len(c) < 6:
            continue
        if c in v1_norm and c not in patch_norm:
            lost.append(c[:40])

    ratio = 1.0 - (len(lost) / max(1, len([x for x in clauses if len(x) >= 6])))
    return {"lost_clauses": lost, "ratio": ratio, "lost_count": len(lost)}


def promote_source_only(
    entry_id: str,
    *,
    base_file: Path | None = None,
    output_dir: Path | None = None,
    index_path: Path | None = None,
) -> Tuple[bool, str]:
    """仅补全史料原文/出处，不改翻译详情；默认写入 _patch_output 待审。"""
    v2_index = _load_v2_index(index_path)
    if entry_id not in v2_index:
        return False, f"{entry_id} 不在 V2 索引"
    v2_entry = v2_index[entry_id]
    base_path = base_file or resolve_base_path(entry_id, DEFAULT_BASE_DIR)
    data = json.loads(base_path.read_text(encoding="utf-8"))
    update_source_fields(data, v2_entry)
    out_dir = output_dir or DEFAULT_PATCH_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / base_path.name
    data["_patch_meta"] = {
        "schema": "paragraph_patch/v2",
        "patched_at": datetime.now(timezone.utc).isoformat(),
        "patch_source": "source_only",
        "note": "翻译详情未改，仅补全史料原文；待人工确认后再 promote",
        "base_file": str(base_path),
        "output_file": str(out_path),
        "status": "pending_review",
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, f"史料原文补全（待审）→ {out_path}（基稿未动）"


def promote_patched_entry(
    entry_id: str,
    *,
    patch_file: Path | None = None,
    note: str = "",
) -> Tuple[bool, str]:
    """
    人工确认后 promote：复制至 11 第一层，更新复用清单，清理待补全目录。
    """
    import shutil

    src = resolve_patch_output_path(entry_id, patch_file)
    base_matches = list(DEFAULT_BASE_DIR.glob(f"{entry_id}_*.json"))
    base_path = base_matches[0] if base_matches else src
    if not src.is_file():
        alt = DEFAULT_PROMOTE_DIR / src.name
        if alt.is_file():
            src = alt
        else:
            return False, f"未找到待 promote 产出: {src}"

    data = json.loads(src.read_text(encoding="utf-8"))
    name = base_path.stem.split("_", 1)[-1] if "_" in base_path.stem else entry_id

    dst = DEFAULT_PROMOTE_DIR / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)

    if DEFAULT_REUSE_MANIFEST.is_file():
        reuse = json.loads(DEFAULT_REUSE_MANIFEST.read_text(encoding="utf-8"))
    else:
        reuse = {
            "schema": "v2-reuse-translations/v1",
            "source": "data/04史料翻译 + patch",
            "target": "data/11新标注条目翻译",
            "entries": [],
        }
    entries = reuse.get("entries") or []
    row = next((e for e in entries if e.get("id") == entry_id), None)
    if row:
        row["file"] = dst.name
        if note:
            row["note"] = note
    else:
        entries.append({
            "id": entry_id,
            "name": name,
            "file": dst.name,
            **({"note": note} if note else {}),
        })
    entries.sort(key=lambda x: x["id"])
    reuse["entries"] = entries
    reuse["count"] = len(entries)
    DEFAULT_REUSE_MANIFEST.write_text(json.dumps(reuse, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if DEFAULT_MANIFEST.is_file():
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        removed = [e for e in manifest.get("entries") or [] if e.get("id") == entry_id]
        manifest["entries"] = [e for e in manifest.get("entries") or [] if e.get("id") != entry_id]
        manifest["count"] = len(manifest["entries"])
        completed = manifest.setdefault("completed", [])
        if not any(c.get("id") == entry_id for c in completed):
            completed.append(
                {
                    "id": entry_id,
                    "name": removed[0]["name"] if removed else name,
                    "promoted_to": str(dst),
                    "method": "patch-integrate",
                }
            )
        DEFAULT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 已确认：删除待补全基稿与 _patch_output 副本
    if base_path.is_file():
        base_path.unlink()
    patch_copy = DEFAULT_PATCH_OUTPUT_DIR / base_path.name
    if patch_copy.is_file() and patch_copy.resolve() != src.resolve():
        patch_copy.unlink()
    if src.resolve() != dst.resolve() and src.is_file():
        src.unlink()

    return True, f"已 promote → {dst}，已从待补全段落翻译/ 清理"
