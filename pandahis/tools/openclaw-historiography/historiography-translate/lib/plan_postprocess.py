"""source plan 落盘后的规范化：必现词、外部补全字段。"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from lib.citation_mode import enrich_checklist_citation_modes
from lib.mother_sentences import extract_must_phrases, is_midword_fragment

# 仅当与母本形成有意义差异时才允许采用
_EXTERNAL_TYPES = frozenset(
    {"异说", "冲突观点", "补充细节", "背景", "评价差异", "必要上下文"}
)

# LLM / prompt 常见别名 → 规范补全类型
_EXTERNAL_TYPE_ALIASES = {
    "必要背景": "必要上下文",
    "母本未载细节": "补充细节",
    "细节补充": "补充细节",
    "细节": "补充细节",
    "冲突观点/细节补充": "补充细节",
    "冲突": "冲突观点",
    "背景信息": "背景",
    "背景补充": "背景",
    "异说/补充细节": "异说",
    "母本未载事实": "补充细节",
    "补充说明": "补充细节",
}


def _broken_must_phrases(phrases: List[Any], orig: str) -> bool:
    """检测 n-gram 碎片式必现词（相邻片段拼接后才是原文连续子串）。"""
    if not phrases:
        return True
    orig_plain = re.sub(r"[\s，。、；：\"\"''「」]", "", orig)
    parts = [str(p).strip() for p in phrases if str(p).strip()]
    if any(is_midword_fragment(p, orig) for p in parts):
        return True
    if len(parts) >= 2:
        joined = "".join(parts)
        if joined in orig_plain and all(len(p) <= 5 for p in parts):
            return True
    hits = sum(1 for p in parts if p in orig_plain)
    return hits < max(1, len(parts) // 2)


def finalize_checklist(plan: Dict[str, Any]) -> None:
    checklist = plan.get("母本逐句清单") or []
    if not isinstance(checklist, list):
        return
    for item in checklist:
        if not isinstance(item, dict):
            continue
        orig = str(item.get("原文摘句") or item.get("text") or "").strip()
        phrases = item.get("必现词") or []
        if orig and (not phrases or _broken_must_phrases(phrases, orig)):
            item["必现词"] = extract_must_phrases(orig)
        hint = str(item.get("写作提示") or "")
        if hint and not item.get("母本提示"):
            item["母本提示"] = _strip_external_hint(hint)
        if hint and not item.get("补全提示") and _has_external_hint(hint):
            item["补全提示"] = hint


_INVALID_SOURCE_MARKERS = ("原文翻译", "等旧注", "及《史记》本文")


def finalize_external(plan: Dict[str, Any]) -> None:
    external = plan.get("外部补全") or []
    if not isinstance(external, list):
        return
    for item in external:
        if not isinstance(item, dict):
            continue
        src = str(item.get("出处") or "").strip()
        if item.get("采用") is True and (
            not src or any(m in src for m in _INVALID_SOURCE_MARKERS)
        ):
            item["采用"] = False
            item.setdefault("理由", "出处不可核验，自动降级为不采用")
        typ = str(item.get("补全类型") or "").strip()
        if typ in _EXTERNAL_TYPE_ALIASES:
            item["补全类型"] = _EXTERNAL_TYPE_ALIASES[typ]
        if item.get("采用") is True and not item.get("补全类型"):
            item["补全类型"] = _infer_external_type(item)
        if item.get("采用") is True and not item.get("与母本关系"):
            reason = str(item.get("理由") or "").strip()
            item["与母本关系"] = reason or "须在 enrich 阶段说明相对母本的新增信息"


def ensure_mother_checklist(
    plan: Dict[str, Any],
    recalled: Dict[str, Any],
    *,
    id_start: int = 1,
) -> Dict[str, Any]:
    """以 recalled 母本分句为 SSOT 补齐/纠正 plan 清单（LLM 合并或缺字段时）。"""
    from lib.mother_sentences import (
        checklist_sentence_violations,
        extract_mother_sentences,
        plan_min_sentence_ratio,
    )

    out = dict(plan)
    sents = extract_mother_sentences(recalled)
    if not sents:
        return out
    min_items = max(1, int(len(sents) * plan_min_sentence_ratio()))
    old_list = out.get("母本逐句清单") or []
    violations = checklist_sentence_violations(old_list) if isinstance(old_list, list) else ["invalid"]
    if isinstance(old_list, list) and len(old_list) >= min_items and not violations:
        return out

    old_by_orig: Dict[str, Dict[str, Any]] = {}
    if isinstance(old_list, list):
        for item in old_list:
            if not isinstance(item, dict):
                continue
            key = str(item.get("原文摘句") or item.get("句子") or item.get("text") or "").strip()
            if key:
                old_by_orig[key] = item

    new_list: List[Dict[str, Any]] = []
    for i, s in enumerate(sents, start=id_start):
        orig = s["原文摘句"]
        prev = old_by_orig.get(orig) or {}
        row: Dict[str, Any] = {
            "编号": f"M{i:03d}",
            "段落": s["段落"],
            "原文摘句": orig,
            "必现词": prev.get("必现词") or extract_must_phrases(orig),
            "信息点": str(
                prev.get("信息点") or prev.get("回译") or prev.get("母本提示") or orig
            ).strip(),
        }
        for k in ("母本提示", "补全提示", "写作提示"):
            if prev.get(k):
                row[k] = prev[k]
        new_list.append(row)
    out["母本逐句清单"] = new_list
    return out


def finalize_plan(plan: Dict[str, Any], recalled: Dict[str, Any] | None = None, *, id_start: int = 1) -> Dict[str, Any]:
    out = dict(plan)
    finalize_checklist(out)
    finalize_external(out)
    if recalled is not None:
        out = ensure_mother_checklist(out, recalled, id_start=id_start)
        enrich_checklist_citation_modes(out.get("母本逐句清单") or [])
        inject_intro_material(out, recalled)
        inject_mother_preview(out)
        inject_exit_supplements_plan(out, recalled)
    return out


def validate_external_items(plan: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for i, item in enumerate(plan.get("外部补全") or []):
        if not isinstance(item, dict):
            errors.append(f"外部补全[{i}] 不是对象")
            continue
        if item.get("采用") is not True:
            continue
        typ = str(item.get("补全类型") or "").strip()
        if typ not in _EXTERNAL_TYPES:
            resolved = _EXTERNAL_TYPE_ALIASES.get(typ)
            if resolved:
                item["补全类型"] = resolved
            else:
                errors.append(
                    f"外部补全[{i}] 补全类型无效或缺失: {typ!r} "
                    f"（须为 {sorted(_EXTERNAL_TYPES)} 之一）"
                )
        rel = str(item.get("与母本关系") or item.get("理由") or "").strip()
        if len(rel) < 8:
            errors.append(f"外部补全[{i}] 须说明「与母本关系」（为何不是重复母本）")
        if _looks_duplicate_only(rel):
            errors.append(f"外部补全[{i}] 理由似与母本重复，应标「采用:false」")
    return errors


def _infer_external_type(item: Dict[str, Any]) -> str:
    reason = str(item.get("理由") or "") + str(item.get("主题") or "")
    if any(k in reason for k in ("异说", "不同", "冲突", "另一说")):
        return "异说"
    if any(k in reason for k in ("背景", "原因", "承接")):
        return "背景"
    if any(k in reason for k in ("细节", "形象", "补充")):
        return "补充细节"
    if any(k in reason for k in ("评价", "观点")):
        return "评价差异"
    return "必要上下文"


def _looks_duplicate_only(text: str) -> bool:
    return bool(re.search(r"^(与母本相同|重复母本|母本已述|无需补充)", text))


def _has_external_hint(hint: str) -> bool:
    return "外部补全" in hint or "《" in hint


def plan_for_enrich_phase(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Phase2 用 plan：仅保留采用:true 的外部补全 + 引用白名单，去掉补全提示。"""
    out: Dict[str, Any] = {}
    for k in ("史略ID", "史略名称", "母本著作", "索引补充处理", "写作结构"):
        if k in plan:
            out[k] = plan[k]

    external: List[Dict[str, Any]] = []
    allowed: List[str] = []
    for item in plan.get("外部补全") or []:
        if not isinstance(item, dict) or item.get("采用") is not True:
            continue
        row = {k: v for k, v in item.items() if k != "采用"}
        external.append(row)
        src = str(item.get("出处") or "").strip()
        if src and src not in allowed:
            allowed.append(src)
    out["外部补全"] = external
    out["允许引用白名单"] = allowed

    refs = plan.get("参考著作") or []
    out["参考著作"] = refs if isinstance(refs, list) else []

    trimmed: List[Dict[str, Any]] = []
    for item in plan.get("母本逐句清单") or []:
        if not isinstance(item, dict):
            continue
        row = {
            k: v
            for k, v in item.items()
            if k not in ("补全提示", "写作提示", "母本提示")
        }
        trimmed.append(row)
    out["母本逐句清单"] = trimmed
    return out


def plan_for_mother_phase(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Phase1 用 plan：去掉外部补全/参考著作/补全提示，避免模型提前写他书。"""
    out: Dict[str, Any] = {
        k: v
        for k, v in plan.items()
        if k not in ("外部补全", "参考著作", "风险提示")
    }
    checklist = out.get("母本逐句清单") or []
    if isinstance(checklist, list):
        trimmed: List[Dict[str, Any]] = []
        for item in checklist:
            if not isinstance(item, dict):
                continue
            row = {
                k: v
                for k, v in item.items()
                if k not in ("补全提示", "写作提示")
            }
            hint = str(row.get("母本提示") or "")
            if "外部补全" in hint or "《" in hint:
                parts = [p.strip() for p in hint.split("；") if p.strip() and "《" not in p]
                if parts:
                    row["母本提示"] = "；".join(parts)
                elif hint:
                    row["母本提示"] = hint.split("（外部")[0].strip()
            trimmed.append(row)
        out["母本逐句清单"] = trimmed
    return out


def _strip_external_hint(hint: str) -> str:
    parts = re.split(r"[；;]", hint)
    kept = [p.strip() for p in parts if p.strip() and "外部补全" not in p]
    return "；".join(kept) if kept else hint.split("（外部")[0].strip()



def inject_intro_material(plan: Dict[str, Any], recalled: Dict[str, Any]) -> None:
    """从索引结构化数据程序化注入前置引入素材，不依赖 LLM 生成。

    这些字段来自人工标注的全局索引，已被 verify 过；
    Phase2 enrich 阶段用它们来写前置引入，避免 LLM 编造错误背景。
    """
    material: Dict[str, str] = {}

    name = recalled.get("史略名称", "").strip()
    if name:
        material["人物名称"] = name

    category = recalled.get("史略分类", "").strip()
    if category:
        material["人物类别"] = category

    dynasty = recalled.get("二级朝代坐标", "").strip()
    if dynasty:
        material["朝代"] = dynasty

    regime = recalled.get("三级政权坐标", "").strip()
    if regime:
        material["政权"] = regime

    source = recalled.get("主要史料出处", "").strip()
    if source:
        material["史料源头"] = source

    intro = recalled.get("史略简介", "").strip()
    if intro:
        material["一句话定位"] = intro

    civ = recalled.get("一级文明坐标", "").strip()
    if civ:
        material["文明归属"] = civ

    if material:
        plan["前置引入素材"] = material


def inject_mother_preview(plan: Dict[str, Any]) -> None:
    """程序化写入母本前三句预览与引入禁区，避免 Phase2 与 M001–M003 重复。"""
    checklist = plan.get("母本逐句清单") or []
    if not isinstance(checklist, list) or not checklist:
        return

    preview: Dict[str, Any] = {}
    forbidden: List[str] = []
    for i, item in enumerate(checklist[:3], start=1):
        if not isinstance(item, dict):
            continue
        orig = str(item.get("原文摘句") or "").strip()
        phrases = item.get("必现词") or extract_must_phrases(orig)
        preview[f"M{i:03d}摘句"] = orig[:120]
        preview[f"M{i:03d}必现词"] = phrases[:6]
        for w in phrases:
            if len(str(w).strip()) >= 2:
                forbidden.append(str(w).strip())
        # 身世/品貌类短语
        for pat in (
            r"姓[\u4e00-\u9fff]{1,2}",
            r"名曰[\u4e00-\u9fff]{1,4}",
            r"生而神灵",
            r"弱而能言",
            r"幼而徇齐",
            r"长而敦敏",
            r"成而聪明",
        ):
            m = re.search(pat, orig)
            if m:
                forbidden.append(m.group(0))

    seen: set[str] = set()
    deduped: List[str] = []
    for w in forbidden:
        if w not in seen:
            seen.add(w)
            deduped.append(w)

    if preview:
        plan["母本首句预览"] = preview
    if deduped:
        plan["前置引入禁区"] = deduped


def inject_exit_supplements_plan(plan: Dict[str, Any], recalled: Dict[str, Any]) -> None:
    """将召回侧本传缺漏补全写入 plan，供 Phase2 尾部采用。"""
    supplements = recalled.get("本传缺漏补全") or []
    if supplements:
        plan["本传缺漏补全"] = supplements
        ext = plan.get("外部补全") or []
        if not isinstance(ext, list):
            ext = []
        for item in supplements:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            ext.append(
                {
                    "主题": "本传退场/收束",
                    "出处": str(item.get("来源") or "母本相邻段落"),
                    "补全类型": "补充细节",
                    "与母本关系": "母本段落域未收录该退场句，须在正文尾部补入",
                    "母本锚点": "tail",
                    "采用": True,
                    "理由": text,
                }
            )
        plan["外部补全"] = ext
