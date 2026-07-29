"""source plan 落盘后的规范化：必现词、外部补全字段。"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from lib.citation_mode import enrich_checklist_citation_modes
from lib.intro_tier import inject_intro_tier
from lib.mother_sentences import extract_must_phrases, is_midword_fragment
from lib.source_citation import display_work_name, native_volume_from_source_file

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
    "重要评价": "评价差异",
    "历史评价": "评价差异",
    "评价": "评价差异",
    "史评": "评价差异",
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
        if orig:
            # 必现词一律程序化重算，不信任 LLM 填写（防卒/立等 L0 词与超限）
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
            not src
            or any(m in src for m in _INVALID_SOURCE_MARKERS)
            or "·过渡段" in src
            or re.fullmatch(r"GLBL_\d{5}(·.+)?", src)
        ):
            item["采用"] = False
            item.setdefault("理由", "出处不可核验（非正史卷篇名），自动降级为不采用")
        typ = str(item.get("补全类型") or "").strip()
        if typ in _EXTERNAL_TYPE_ALIASES:
            item["补全类型"] = _EXTERNAL_TYPE_ALIASES[typ]
        if item.get("采用") is True and not item.get("补全类型"):
            item["补全类型"] = _infer_external_type(item)
        if item.get("采用") is True and not item.get("与母本关系"):
            reason = str(item.get("理由") or "").strip()
            item["与母本关系"] = reason or "须在 enrich 阶段说明相对母本的新增信息"


def _checklist_aligned_with_recalled(
    old_list: List[Any],
    sents: List[Dict[str, Any]],
) -> bool:
    """清单须与 recalled 分句一一对应（条数 + 顺序 + 原文）。"""
    if not isinstance(old_list, list) or len(old_list) != len(sents):
        return False
    for item, sent in zip(old_list, sents):
        if not isinstance(item, dict):
            return False
        orig = str(item.get("原文摘句") or item.get("句子") or item.get("text") or "").strip()
        if orig != sent["原文摘句"]:
            return False
    return True


def ensure_mother_checklist(
    plan: Dict[str, Any],
    recalled: Dict[str, Any],
    *,
    id_start: int = 1,
) -> Dict[str, Any]:
    """以 recalled 母本分句为 SSOT 补齐/纠正 plan 清单（LLM 合并或缺字段时）。"""
    from lib.coverage_info import sanitize_info_point
    from lib.mother_sentences import extract_mother_sentences

    out = dict(plan)
    sents = extract_mother_sentences(recalled)
    if not sents:
        return out
    old_list = out.get("母本逐句清单") or []
    if isinstance(old_list, list) and _checklist_aligned_with_recalled(old_list, sents):
        return out

    old_n = len(old_list) if isinstance(old_list, list) else 0
    if old_n and old_n != len(sents):
        eid = str(out.get("史略ID") or recalled.get("史略ID") or "")
        name = str(out.get("史略名称") or recalled.get("史略名称") or "")
        print(
            f"⚠️ plan 清单与 recall 不一致，按母本重建: {eid} {name} "
            f"{old_n}→{len(sents)} 句",
            flush=True,
        )

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
            "必现词": extract_must_phrases(orig),
            "信息点": sanitize_info_point(
                str(
                    prev.get("信息点") or prev.get("回译") or prev.get("母本提示") or ""
                ).strip(),
                orig,
            ),
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
        inject_intro_tier(out, recalled)
        inject_index_supplements_plan(out, recalled)
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
    for k in (
        "史略ID",
        "史略名称",
        "母本著作",
        "索引补充处理",
        "写作结构",
        "前置引入素材",
        "前置引入档位",
        "前置引入档位说明",
    ):
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


def _block_plain_text(block: Dict[str, Any]) -> str:
    text = str(block.get("text") or "").strip()
    if text:
        return text
    paras = block.get("paragraphs") or []
    return "\n".join(str(p.get("text") or "") for p in paras if isinstance(p, dict)).strip()


def _supplement_citation(block: Dict[str, Any]) -> str:
    work = display_work_name(str(block.get("work") or ""))
    vol = str(block.get("volume") or "").strip()
    if not vol:
        vol = native_volume_from_source_file(str(block.get("source_file") or ""))
    if work and vol:
        return f"《{work}·{vol}》"
    return vol or work or "索引补充"


def _plain_overlap_ratio(shorter: str, longer: str) -> float:
    """较短文本中有多少字出现在较长文本中（去标点）。"""
    def norm(s: str) -> str:
        return re.sub(r"[\s，。、；：\"\"''「」？！]", "", s)

    a, b = norm(shorter), norm(longer)
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    hits = sum(1 for ch in a if ch in b)
    return hits / max(len(a), 1)


def inject_index_supplements_plan(plan: Dict[str, Any], recalled: Dict[str, Any]) -> None:
    """召回侧有 role=补充 block 时，若 plan 未写索引补充处理则程序化补全。"""
    existing = plan.get("索引补充处理") or []
    if isinstance(existing, list) and existing:
        return

    supplement_blocks = [
        b
        for b in (recalled.get("blocks") or [])
        if isinstance(b, dict) and str(b.get("role") or "") == "补充"
    ]
    if not supplement_blocks:
        return

    mother_work = str(recalled.get("母本著作") or plan.get("母本著作") or "").strip()
    mother_text = ""
    for block in recalled.get("blocks") or []:
        if not isinstance(block, dict) or str(block.get("role") or "母本") != "母本":
            continue
        mother_text = _block_plain_text(block)
        break

    entries: List[Dict[str, Any]] = []
    for block in supplement_blocks:
        src = _supplement_citation(block)
        sup_text = _block_plain_text(block)
        overlap = _plain_overlap_ratio(sup_text, mother_text) if mother_text else 0.0
        same_work = str(block.get("work") or "").strip() == mother_work

        if same_work or overlap >= 0.82:
            entries.append(
                {
                    "出处": src,
                    "处理": "去重不用",
                    "理由": "与母本主体/事件/结果一致，编排器自动判定",
                }
            )
        else:
            entries.append(
                {
                    "出处": src,
                    "处理": "引入",
                    "锚点": "M001 前",
                    "理由": "索引补充著作为异文或补充视角，在对应母本锚点处融入",
                }
            )

    plan["索引补充处理"] = entries


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
            raw_src = str(item.get("来源") or "母本相邻段落").strip()
            adopt = True
            if "·过渡段" in raw_src or re.fullmatch(r"GLBL_\d{5}(·.+)?", raw_src):
                raw_src = "《史记·夏本纪》"
            ext.append(
                {
                    "主题": "本传退场/收束",
                    "出处": raw_src,
                    "补全类型": "补充细节",
                    "与母本关系": "母本段落域未收录该退场句，须在正文尾部补入",
                    "母本锚点": "tail",
                    "采用": adopt,
                    "理由": text,
                }
            )
        plan["外部补全"] = ext
