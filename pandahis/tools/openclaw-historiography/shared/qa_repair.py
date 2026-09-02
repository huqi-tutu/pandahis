"""质检失败分类与修复闭环（翻译 / 朝代补全共用）。

设计原则（对齐 historiography-orchestrator failure_classifier）：
- 硬门 = 诊断器，不是终点
- 每条失败须归类 root_cause + disposition + 可执行 next_action
- LLM 可修 → 注入 structured_prompt 定向重试
- 结构不可修 → route_pipeline，不空转 token
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Disposition = Literal[
    "retry_llm",  # 同阶段带反馈重试
    "refine_scope",  # 局部改写（intro/mother/attribution）
    "script_fix",  # 规则脚本先修
    "route_pipeline",  # 转另一流水线（如朝代补全）
]


@dataclass
class RepairPlan:
    root_cause: str
    disposition: Disposition
    action: str
    structured_prompt: str = ""
    refine_scope: str = ""
    route_to: str = ""
    next_command: str = ""
    invalidate: tuple[str, ...] = ()
    max_retries: int = 2
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_any(text: str, keys: tuple[str, ...]) -> bool:
    return any(k in text for k in keys)


def classify_translate_failure(
    errors: list[str],
    *,
    stage: str = "",
    fail_count: int = 0,
) -> RepairPlan:
    """翻译流水线 verify / recall 失败归类。"""
    e = "\n".join(errors)
    s = (stage or "").strip().lower()

    if _has_any(e, ("禁止一期翻译", "史料原文合计仅", "厚度门", "<100")):
        return RepairPlan(
            root_cause="THIN_SOURCE",
            disposition="route_pipeline",
            action="defer_to_dynasty_supplement",
            route_to="dynasty_supplement",
            next_command=(
                "dynasty_supplement.py --dynasty <朝代> --step candidates-renwu "
                "→ fill-renwu → compose-detail（君王强制补全）"
            ),
            structured_prompt=(
                "【根因：史料过薄，一期顺译不可行】\n"
                "该条目母本+补充合计 <100 汉字，禁止硬翻。\n"
                "请走朝代知识补全：帝王表强制 + 薄标注注册表 → 新 GLBL（母本著作=朝代补全）。\n"
                "勿再调用 translate run-one。"
            ),
        )

    if _has_any(e, ("原词锚点", "必现词", "must_phrase", "锚点须在译文中", "命中率不足")):
        return RepairPlan(
            root_cause="MUST_PHRASE_MISS",
            disposition="retry_llm" if fail_count < 2 else "refine_scope",
            action="phase1_retry_with_miss_list",
            refine_scope="mother",
            structured_prompt=(
                "【根因：母本必现词/原词锚点缺失】\n"
                "逐项对照 plan 母本逐句清单，保留「」内原词锚点，勿漏句、勿跳段。\n"
                "仅补缺失锚点，勿改写已正确段落。"
            ),
            invalidate=("mother",) if fail_count >= 1 else (),
            max_retries=2,
        )

    if _has_any(e, ("覆盖不足", "覆盖率", "语义覆盖", "M00", "母本逐句", "未覆盖")):
        return RepairPlan(
            root_cause="COVERAGE_MISS",
            disposition="retry_llm" if fail_count < 2 else "refine_scope",
            action="phase1_or_phase2_coverage_retry",
            refine_scope="mother" if "phase1" in s or "mother" in s else "full",
            structured_prompt=(
                "【根因：母本句意覆盖不足】\n"
                "对照 plan 中未命中的 M 编号，在对应位置补译母本信息点；\n"
                "禁止用他书重复母本已述事实。"
            ),
            max_retries=2,
        )

    if _has_any(e, ("归因", "attribution", "据《", "史书称")):
        return RepairPlan(
            root_cause="ATTRIBUTION",
            disposition="script_fix",
            action="attribution_autofix",
            refine_scope="attribution",
            structured_prompt="【根因：归因格式】先跑 attribution 规则清洗，再 verify。",
        )

    if _has_any(e, ("AI味", "ai_flavor", "据悉", "值得一提的是")):
        return RepairPlan(
            root_cause="AI_FLAVOR",
            disposition="refine_scope",
            action="refine_prose",
            refine_scope="full",
            structured_prompt=(
                "【根因：AI 套话 / 编辑腔】\n"
                "删除元叙述与套话，改为《明朝那些事儿》口语叙事；保留史实与引用。"
            ),
        )

    if _has_any(e, ("传说/据说/有人说", "legend_dominance", "二手表述触发词", "连续", "传说层")):
        return RepairPlan(
            root_cause="LEGEND_DOMINANCE",
            disposition="refine_scope",
            action="reduce_legend_layer",
            refine_scope="full",
            structured_prompt=(
                "【根因：传说/二手表述过多】\n"
                "「传说」「据说」「有人说」等无《》表述已超配额或连续成段。\n"
                "优先改为「《书名·卷》载：…」；删冗余传说句；保留母本主线。"
            ),
            max_retries=2,
        )

    if _has_any(e, ("外部出处", "过渡段", "plan", "采用:false", "GLBL_")):
        return RepairPlan(
            root_cause="PLAN_SOURCE",
            disposition="retry_llm",
            action="fix_source_plan",
            structured_prompt=(
                "【根因：source_plan 外部补全引用无效】\n"
                "删除不存在的 GLBL·过渡段引用；仅保留真实条目或改为采用:false。\n"
                "重跑 plan 后再 Phase2。"
            ),
            invalidate=("plan",),
        )

    if _has_any(e, ("引用宜以完整摘句", "并列句群为单位", "引用过碎", "母本引用过碎")):
        return RepairPlan(
            root_cause="QUOTE_FRAGMENT",
            disposition="refine_scope" if "母本" in e else "retry_llm",
            action="merge_short_quotes",
            refine_scope="mother",
            structured_prompt=(
                "【引用方式】「」用于完整史料摘句、人物对话或并列句群，译后统一解释；"
                "叙事句中专名与数字融入白话叙述。"
            ),
            max_retries=2,
        )

    if _has_any(e, ("字数不足", "字数偏少", "低于下限")):
        if _has_any(e, ("母本顺译", "母本", "Phase1")) or "phase1" in s or "mother" in s:
            return RepairPlan(
                root_cause="WORD_COUNT_PHASE1",
                disposition="retry_llm" if fail_count < 2 else "refine_scope",
                action="phase1_expand_mother",
                refine_scope="mother",
                structured_prompt=(
                    "【根因：母本顺译字数不足】\n"
                    "对照 plan 母本逐句清单补全漏句，勿删已有正确锚点。"
                ),
                max_retries=2,
            )
        return RepairPlan(
            root_cause="WORD_COUNT_FINAL",
            disposition="retry_llm" if fail_count < 2 else "refine_scope",
            action="phase2_expand_enrich",
            refine_scope="full",
            structured_prompt=(
                "【根因：成稿字数不足】\n"
                "在母本顺译基础上补全 Phase2 他书补全与叙述，勿重复母本已述事实。"
            ),
            extra={"from_phase": "phase2"},
            max_retries=2,
        )

    if _has_any(e, ("母本引用过碎", "分块")):
        return RepairPlan(
            root_cause="CHUNK_FRAGMENT",
            disposition="retry_llm",
            action="adjust_chunk_plan",
            structured_prompt=(
                "【分块边界】合并相邻块或放宽分块边界，保证每块上下文连贯后再译。"
            ),
            max_retries=1,
        )

    if _has_any(e, ("plan 外部补全", "采用:true", "未在正文引用")):
        return RepairPlan(
            root_cause="PLAN_ADOPTED_MISS",
            disposition="retry_llm" if fail_count < 2 else "refine_scope",
            action="phase2_adopted_external",
            refine_scope="full",
            structured_prompt=(
                "【根因：plan 采用:true 的外部补全未写入正文】\n"
                "对照 source_plan 外部补全，在母本锚点处补《书名·卷》引用；\n"
                "缺项补写，勿重复母本已述事实。"
            ),
            extra={"from_phase": "phase2"},
            max_retries=2,
        )

    if _has_any(e, ("篇末空泛升华", "时代翻篇", "由此而来", "共同起点")):
        return RepairPlan(
            root_cause="SUMMARY_ENDING",
            disposition="refine_scope",
            action="fix_tail_transition",
            refine_scope="tail",
            structured_prompt=(
                "【根因：篇末总结腔】\n"
                "删「翻篇/由此而来」等空泛升华；用承接上一情节的 1–2 句叙事收束。"
            ),
            max_retries=2,
        )

    if _has_any(e, ("段落过碎", "单句成段")):
        return RepairPlan(
            root_cause="PARAGRAPH_FRAGMENT",
            disposition="refine_scope",
            action="merge_paragraphs",
            refine_scope="full",
            structured_prompt=(
                "【根因：段落过碎】\n"
                "合并连续单句段为叙事段；保留场景切换处分段，勿刷屏。"
            ),
            max_retries=2,
        )

    if _has_any(e, ("参考著作节书目", "参考著作与正文")):
        return RepairPlan(
            root_cause="REFERENCE_FORMAT",
            disposition="refine_scope",
            action="fix_reference_section",
            refine_scope="full",
            structured_prompt=(
                "【根因：参考著作格式】\n"
                "正文末与「参考著作」之间空一行；书目与正文引用一致。"
            ),
            max_retries=2,
        )

    if fail_count >= 3:
        return RepairPlan(
            root_cause="RETRY_EXHAUSTED",
            disposition="retry_llm",
            action="generic_retry",
            structured_prompt=(
                "【已多次重试，须换写法】\n"
                "勿重复上一轮相同表述；逐项对照下方原始错误修正。\n"
                + e[:1200]
            ),
            max_retries=5,
        )

    return RepairPlan(
        root_cause="UNKNOWN",
        disposition="retry_llm",
        action="generic_retry",
        structured_prompt=(
            "【根因未分类】请据下列 verify 错误逐项修正，勿重复上一轮相同写法。\n"
            + e[:1200]
        ),
        max_retries=2,
    )


def classify_dynasty_failure(
    errors: list[str],
    *,
    stage: str = "",
    fail_count: int = 0,
) -> RepairPlan:
    """朝代知识补全 verify / gate 失败归类。"""
    e = "\n".join(errors)
    s = (stage or "").strip().lower()

    if _has_any(e, ("缺少强制君王", "帝王表")):
        return RepairPlan(
            root_cause="EMPEROR_GAP",
            disposition="route_pipeline",
            action="inject_mandatory_juwang",
            route_to="candidates-renwu",
            next_command="dynasty_supplement.py --step candidates-renwu（脚本已强制注入君王）",
            structured_prompt="【根因：帝王表君王未补全】运行 candidates-renwu → fill-renwu → compose-detail。",
        )

    if _has_any(e, ("字数", "低于下限", "translation_detail")) and "compose" in s:
        return RepairPlan(
            root_cause="DETAIL_TOO_SHORT",
            disposition="retry_llm",
            action="compose_revise",
            structured_prompt=(
                "【根因：详情字数不足 / 结构不全】\n"
                "按人物详情撰写规则补「起承转合」与记忆点，勿元叙述。"
            ),
            max_retries=2,
        )

    if _has_any(e, ("AI味", "ai_flavor", "元叙述")):
        return RepairPlan(
            root_cause="AI_FLAVOR",
            disposition="retry_llm",
            action="compose_revise",
            structured_prompt="【根因：AI 套话】删套话，改口语叙事，保留史实。",
            max_retries=2,
        )

    if fail_count >= 3:
        return RepairPlan(
            root_cause="RETRY_EXHAUSTED",
            disposition="retry_llm",
            action="compose_revise",
            structured_prompt=(
                "【已多次重试，须换写法】\n"
                "据 verify 错误逐项修订详情，勿重复上一轮写法。\n"
                + e[:1200]
            ),
            max_retries=5,
        )

    return RepairPlan(
        root_cause="UNKNOWN",
        disposition="retry_llm",
        action="compose_revise",
        structured_prompt="【根因未分类】据 verify 错误逐项修订详情。\n" + e[:1200],
        max_retries=2,
    )


def format_repair_feedback(plan: RepairPlan, errors: list[str], *, max_raw: int = 1200) -> str:
    raw = "\n".join(errors).strip()
    if len(raw) > max_raw:
        raw = raw[-max_raw:]
    body = (plan.structured_prompt or "").strip()
    if raw:
        body += f"\n\n---\n【原始错误】\n{raw}"
    return body


def format_retry_feedback(
    plan: RepairPlan,
    errors: list[str],
    *,
    max_errors: int = 8,
    max_raw: int = 800,
) -> str:
    """重试专用反馈：保留 structured_prompt，压缩重复 verify 堆栈（规则 bundle 仍在主 prompt）。"""
    uniq: list[str] = []
    seen: set[str] = set()
    for err in errors:
        line = str(err).strip()
        if not line or line in seen:
            continue
        seen.add(line)
        uniq.append(line)
        if len(uniq) >= max_errors:
            break
    return format_repair_feedback(plan, uniq, max_raw=max_raw)


def infer_translate_retry_from_phase(
    errors: list[str],
    *,
    stage: str = "",
    mother_verified: bool = False,
) -> str | None:
    """retry_llm 时推断 from_phase；None 表示全量 run-one。"""
    s = (stage or "").strip().lower()
    e = "\n".join(errors)
    if not mother_verified:
        return None
    if s.startswith("phase2") or "enrich" in s or s == "verify":
        return "phase2"
    if _has_any(e, ("字数不足", "字数偏少", "低于下限")) and "母本" not in e:
        return "phase2"
    if _has_any(e, ("参考著作", "史料原文", "未授权引用", "AI味", "传说层")):
        return "phase2"
    return None
