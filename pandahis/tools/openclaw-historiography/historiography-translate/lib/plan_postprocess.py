"""source plan 落盘后的规范化：必现词、外部补全字段。"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from lib.citation_mode import enrich_checklist_citation_modes
from lib.intro_tier import inject_intro_tier
from lib.mother_sentences import extract_must_phrases, is_midword_fragment
from lib.source_citation import (
    build_source_citation,
    display_work_name,
    native_volume_from_source_file,
)

# 仅当与母本形成有意义差异时才允许采用
_EXTERNAL_TYPES = frozenset(
    {"异说", "冲突观点", "补充细节", "背景", "评价差异", "必要上下文"}
)

# plan / 成稿参考著作硬上限（提示词 + 落盘截断 + 质检）
MAX_REFERENCE_WORKS = 10


def clamp_reference_works(
    refs: Any, *, limit: int = MAX_REFERENCE_WORKS
) -> List[str]:
    """去重保序，截断至 limit。"""
    if not isinstance(refs, list):
        return []
    out: List[str] = []
    for r in refs:
        s = str(r or "").strip()
        if not s or s in out:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def apply_reference_works_cap(plan: Dict[str, Any]) -> Dict[str, Any]:
    """验收通过后的安全截断（不替代门禁；门禁要求模型只交 ≤10）。"""
    out = dict(plan)
    raw = out.get("参考著作")
    if not isinstance(raw, list):
        out["参考著作"] = []
        return out
    unique: List[str] = []
    for r in raw:
        s = str(r or "").strip()
        if s and s not in unique:
            unique.append(s)
    if len(unique) > MAX_REFERENCE_WORKS:
        print(
            f"   📎 参考著作截断 {len(unique)} → {MAX_REFERENCE_WORKS}",
            flush=True,
        )
    out["参考著作"] = clamp_reference_works(raw)
    return out


# LLM / prompt 常见别名 → 规范补全类型
_EXTERNAL_TYPE_ALIASES = {
    "必要背景": "必要上下文",
    "母本未载细节": "补充细节",
    "细节补充": "补充细节",
    "细节": "补充细节",
    "冲突观点/细节补充": "补充细节",
    "冲突": "冲突观点",
    "冲突评价": "冲突观点",
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
_CITE_NOISE_RE = re.compile(r"[《》「」\s·•\.．、，,]")


def _normalize_cite_key(text: str) -> str:
    """《史记·高祖本纪》/《史记高祖本纪第一》→ 史记高祖本纪"""
    from lib.source_citation import strip_volume_ordinal

    raw = _CITE_NOISE_RE.sub("", str(text or "").strip())
    return strip_volume_ordinal(raw)


def mother_volume_cite_key(
    plan: Dict[str, Any],
    recalled: Dict[str, Any] | None = None,
) -> str:
    """正在翻译的母本卷规范化键；无则空串。"""
    cached = str(plan.get("_母本卷键") or "").strip()
    if cached:
        return cached
    if recalled:
        cite = build_source_citation(recalled)
        key = _normalize_cite_key(cite)
        if key:
            return key
    for field in ("原文出处", "主要史料出处"):
        key = _normalize_cite_key(str(plan.get(field) or ""))
        if key and len(key) >= 4:
            return key
    return ""


def is_same_mother_volume(
    source: str,
    *,
    mother_key: str = "",
    plan: Dict[str, Any] | None = None,
    recalled: Dict[str, Any] | None = None,
) -> bool:
    """出处是否正是正在翻译的同一卷（同书他卷不算）。"""
    src_key = _normalize_cite_key(source)
    if not src_key:
        return False
    m_key = mother_key or mother_volume_cite_key(plan or {}, recalled)
    if not m_key or len(m_key) < 4:
        return False
    if src_key == m_key:
        return True
    # 《高祖本纪》相对《史记高祖本纪》：较短一方须是完整卷名后缀
    shorter, longer = (src_key, m_key) if len(src_key) <= len(m_key) else (m_key, src_key)
    return len(shorter) >= 4 and longer.endswith(shorter)


def finalize_external(
    plan: Dict[str, Any],
    recalled: Dict[str, Any] | None = None,
) -> None:
    external = plan.get("外部补全") or []
    if not isinstance(external, list):
        return
    mother_key = mother_volume_cite_key(plan, recalled)
    if mother_key:
        plan["_母本卷键"] = mother_key
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
        if item.get("采用") is True and is_same_mother_volume(
            src, mother_key=mother_key, plan=plan, recalled=recalled
        ):
            item["采用"] = False
            item["理由"] = (
                str(item.get("理由") or "").strip()
                or "出处为正在翻译的母本同一卷，禁止作外部补全"
            )
            if "同一卷" not in item["理由"]:
                item["理由"] = f"{item['理由']}；母本同一卷，自动降级为不采用"
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


def apply_longform_external_floor(plan: Dict[str, Any]) -> int:
    """长文兼容：若采用:true 过少，在已有合格候选上提升至配额（不编造、不改准入标准）。

    宏观选题路径默认关闭 floor：避免为凑条数把碎闻翻回采用:true（回形针效应）。
    """
    from lib.external_macro import macro_plan_enabled
    from lib.longform_compat import checklist_size, external_adopt_quota

    if macro_plan_enabled() and os.environ.get(
        "TRANSLATE_EXTERNAL_FLOOR", "0"
    ).strip() not in ("1", "true", "True", "yes"):
        return 0

    m_count = checklist_size(plan)
    quota = external_adopt_quota(m_count)
    if quota <= 0:
        return 0

    external = plan.get("外部补全")
    if not isinstance(external, list):
        return 0

    adopted = [x for x in external if isinstance(x, dict) and x.get("采用") is True]
    if len(adopted) >= quota:
        return 0

    prefer = ("异说", "冲突观点", "评价差异", "背景", "必要上下文", "补充细节")

    def _score(item: Dict[str, Any]) -> int:
        typ = str(item.get("补全类型") or "")
        return prefer.index(typ) if typ in prefer else 99

    candidates: List[Dict[str, Any]] = []
    for item in external:
        if not isinstance(item, dict) or item.get("采用") is True:
            continue
        src = str(item.get("出处") or "").strip()
        typ = str(item.get("补全类型") or "").strip()
        rel = str(item.get("与母本关系") or item.get("理由") or "").strip()
        if not src or "《" not in src:
            continue
        if is_same_mother_volume(src, plan=plan):
            continue
        if str(item.get("_判重") or "").endswith("demote") or "全书母本信息点判重" in str(
            item.get("理由") or ""
        ) or "无实质分歧" in str(item.get("理由") or ""):
            continue
        if typ not in _EXTERNAL_TYPES:
            continue
        if len(rel) < 8 or _looks_duplicate_only(rel):
            continue
        candidates.append(item)

    candidates.sort(key=_score)
    need = quota - len(adopted)
    flipped = 0
    for item in candidates[:need]:
        item["采用"] = True
        item.setdefault(
            "理由",
            str(item.get("与母本关系") or "长文兼容：提升合格外部补全落地"),
        )
        flipped += 1
    if flipped:
        meta = plan.get("_长文兼容") if isinstance(plan.get("_长文兼容"), dict) else {}
        plan["_长文兼容"] = {**meta, "外部补全提升": flipped, "配额": quota}
    return flipped


def merge_llm_plan_decisions(
    skeleton: Dict[str, Any],
    llm_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """把 LLM 的跨书决策合并到程序骨架上；母本清单始终以骨架为准。"""
    out = dict(skeleton)
    # 母本逐句清单：程序生成，不采信 LLM 整表（长卷尤甚）
    for key in (
        "外部补全",
        "写作结构",
        "参考著作",
        "风险提示",
    ):
        if key in llm_plan and llm_plan[key] is not None:
            out[key] = llm_plan[key]
    # 索引补充：LLM 可微调处理/理由；空则保留骨架
    llm_idx = llm_plan.get("索引补充处理")
    if isinstance(llm_idx, list) and llm_idx:
        out["索引补充处理"] = llm_idx
    for meta_key in ("史略ID", "史略名称", "母本著作"):
        if llm_plan.get(meta_key) and not out.get(meta_key):
            out[meta_key] = llm_plan[meta_key]
    return out


def build_plan_skeleton(recalled: Dict[str, Any], *, id_start: int = 1) -> Dict[str, Any]:
    """程序化母本清单 + 索引补充默认；外部补全默认空（交 Phase2）。"""
    skeleton: Dict[str, Any] = {
        "史略ID": recalled.get("史略ID"),
        "史略名称": recalled.get("史略名称"),
        "母本著作": recalled.get("母本著作"),
        "母本逐句清单": [],
        "外部补全": [],
        "索引补充处理": [],
        "写作结构": [{"小节": "本传", "覆盖母本": ["见母本逐句清单"]}],
        "参考著作": [],
        "风险提示": [],
    }
    # 不跑 external floor / 不注入缺漏补全到空数组前——由 finalize 统一做
    out = ensure_mother_checklist(skeleton, recalled, id_start=id_start)
    enrich_checklist_citation_modes(out.get("母本逐句清单") or [])
    inject_intro_material(out, recalled)
    inject_intro_tier(out, recalled)
    inject_index_supplements_plan(out, recalled)
    return out


def finalize_plan(
    plan: Dict[str, Any],
    recalled: Dict[str, Any] | None = None,
    *,
    id_start: int = 1,
    external_dedupe_llm: bool = False,
) -> Dict[str, Any]:
    out = dict(plan)
    finalize_checklist(out)
    if recalled is not None:
        out = ensure_mother_checklist(out, recalled, id_start=id_start)
        enrich_checklist_citation_modes(out.get("母本逐句清单") or [])
        inject_intro_material(out, recalled)
        inject_intro_tier(out, recalled)
        inject_index_supplements_plan(out, recalled)
        inject_exit_supplements_plan(out, recalled)
    # 须在 recalled 注入后再做：禁母本同一卷、非法出处降级
    finalize_external(out, recalled)
    # 参考著作：此处不去截断——超限由 verify 拦下并促 LLM 重试只交最重要 ≤10；
    # 验收通过后再 clamp（见 runner / apply_reference_works_cap）。
    # 全书母本信息点判重：脚本粗筛；LLM 精判仅在 plan 生成路径显式开启
    from lib.external_dedupe import apply_external_mother_dedupe

    apply_external_mother_dedupe(
        out,
        entry_id=str(out.get("史略ID") or ""),
        use_llm=external_dedupe_llm,
    )
    # 禁止用索引书目伪造外部补全；空数组由 verify + LLM 重试处理
    flipped = apply_longform_external_floor(out)
    if flipped:
        print(f"   📎 长文兼容：外部补全采用提升 {flipped} 条", flush=True)
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
        row["_须落地"] = True
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
    from lib.source_citation import build_source_citation, display_work_name

    material: Dict[str, str] = {}

    name = str(recalled.get("史略名称") or "").strip()
    if name:
        material["人物名称"] = name

    category = str(recalled.get("史略分类") or "").strip()
    if category:
        material["人物类别"] = category

    dynasty = str(recalled.get("二级朝代坐标") or "").strip()
    if dynasty:
        material["朝代"] = dynasty

    regime = str(recalled.get("三级政权坐标") or "").strip()
    if regime:
        material["政权"] = regime

    source = str(recalled.get("主要史料出处") or "").strip()
    if not source:
        cite = build_source_citation(recalled).strip()
        if cite:
            source = cite if cite.startswith("《") else f"《{cite}》"
        else:
            work = display_work_name(str(recalled.get("母本著作") or ""))
            if work:
                source = f"《{work}》"
    if source:
        material["史料源头"] = source

    intro = str(recalled.get("史略简介") or "").strip()
    if intro:
        material["一句话定位"] = intro
    elif name and category:
        material["一句话定位"] = f"{name}（{category}）"

    civ = str(recalled.get("一级文明坐标") or "").strip()
    if civ:
        material["文明归属"] = civ

    if material:
        # 宏观写法提醒（程序硬检见 intro_frame；素材供模型写人物名片式首段）
        material["写法"] = (
            "独立成段宏观介绍是谁、为何重要；空一行后再写母本起传；"
            "勿把封王立太子/出生异兆写进引入；勿先登基气氛再补身世"
        )
        plan["前置引入素材"] = material

    # 去掉可能残留的禁令式写作提醒（旧字段）
    mat = plan.get("前置引入素材")
    if isinstance(mat, dict) and "写作提醒" in mat:
        mat = {k: v for k, v in mat.items() if k != "写作提醒"}
        plan["前置引入素材"] = mat


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


def _desired_index_supplement_entry(
    block: Dict[str, Any],
    *,
    mother_work: str,
    mother_text: str,
) -> Dict[str, Any]:
    """平行正史即使用字重叠高，也不得整卷「去重不用」——应筛差异点。"""
    src = _supplement_citation(block)
    sup_text = _block_plain_text(block)
    overlap = _plain_overlap_ratio(sup_text, mother_text) if mother_text else 0.0
    same_work = str(block.get("work") or "").strip() == mother_work

    if same_work:
        return {
            "出处": src,
            "处理": "去重不用",
            "理由": "与母本同著作块，编排器自动判定去重",
        }
    # 他书：即便叙事平行，仍须筛年号/诏令/评价/详略差异
    if overlap >= 0.82:
        return {
            "出处": src,
            "处理": "异说",
            "锚点": "按事件挂母本对应 M",
            "理由": (
                "平行正史与母本主体接近，禁止整卷复述；"
                "须筛年号细节、诏令全文、评价差异、史记略写而他书详写的场面，"
                "在对应锚点以《书·卷》引入"
            ),
        }
    return {
        "出处": src,
        "处理": "引入",
        "锚点": "按事件挂母本对应 M",
        "理由": "索引补充著作为异文或补充视角，在对应母本锚点处融入",
    }


def inject_index_supplements_plan(plan: Dict[str, Any], recalled: Dict[str, Any]) -> None:
    """召回侧 role=补充：程序化写入/纠偏索引补充处理（禁止他书整卷去重不用）。"""
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

    desired = [
        _desired_index_supplement_entry(
            block, mother_work=mother_work, mother_text=mother_text
        )
        for block in supplement_blocks
    ]

    existing = plan.get("索引补充处理") or []
    if not isinstance(existing, list) or not existing:
        plan["索引补充处理"] = desired
        return

    by_src = {
        str(e.get("出处") or "").strip(): e
        for e in existing
        if isinstance(e, dict) and str(e.get("出处") or "").strip()
    }
    out: List[Dict[str, Any]] = []
    used: set[str] = set()
    for d in desired:
        src = str(d.get("出处") or "").strip()
        old = by_src.get(src)
        used.add(src)
        if not old:
            out.append(d)
            continue
        old_action = str(old.get("处理") or "").strip()
        # 保留模型已写的引入/异说；纠正「他书却去重不用」
        if old_action in ("引入", "异说") and d.get("处理") != "去重不用":
            out.append(old)
        elif old_action == "去重不用" and d.get("处理") != "去重不用":
            out.append(d)
        else:
            out.append(old if old_action else d)
    # 保留 plan 中多写的、非召回块条目
    for src, e in by_src.items():
        if src not in used:
            out.append(e)
    plan["索引补充处理"] = out


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
            # GLBL_/过渡段不是可写入正文的《书·卷》；勿用《史记·夏本纪》占位（会污染武帝等非夏条目）
            if "·过渡段" in raw_src or re.fullmatch(r"GLBL_\d{5}(·.+)?", raw_src):
                mother_src = str(plan.get("母本出处") or plan.get("原文出处") or "").strip()
                struct = plan.get("写作结构")
                if not mother_src and isinstance(struct, dict):
                    mother_src = str(struct.get("母本") or "").strip()
                raw_src = mother_src if "《" in mother_src else "母本相邻段落"
                adopt = False  # 退场句由 Phase2 自检母本是否已有；勿强制锚点落地
            ext.append(
                {
                    "主题": "本传退场/收束",
                    "出处": raw_src,
                    "补全类型": "补充细节",
                    "与母本关系": "母本段落域未收录该退场句，须在正文尾部补入（1句）；若 Phase1 已译出同传主退场则禁止采用",
                    "母本锚点": "tail",
                    "采用": adopt,
                    "理由": text,
                }
            )
        plan["外部补全"] = ext
