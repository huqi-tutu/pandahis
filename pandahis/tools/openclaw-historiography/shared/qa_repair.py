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
    "needs_human",  # 熔断后人审
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

    if _has_any(e, ("原词锚点", "必现词", "must_phrase", "锚点须在译文中")):
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

    if _has_any(e, ("覆盖不足", "覆盖率", "M00", "母本逐句", "未覆盖")):
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

    if _has_any(e, ("前置引入", "引入重复", "intro", "开头与母本")):
        return RepairPlan(
            root_cause="INTRO_ISSUE",
            disposition="refine_scope",
            action="refine_intro",
            refine_scope="intro",
            structured_prompt=(
                "【根因：前置引入问题】\n"
                "收窄 100–200 字引入：交代时代/人物定位，不重复母本首段字面。\n"
                "勿元叙述、勿「正文不载」。"
            ),
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

    if _has_any(e, ("外部出处", "过渡段", "plan", "采用:false", "GLBL_")):
        return RepairPlan(
            root_cause="PLAN_SOURCE",
            disposition="retry_llm" if fail_count < 1 else "needs_human",
            action="fix_source_plan",
            structured_prompt=(
                "【根因：source_plan 外部补全引用无效】\n"
                "删除不存在的 GLBL·过渡段引用；仅保留真实条目或改为采用:false。\n"
                "重跑 plan 后再 Phase2。"
            ),
            invalidate=("plan",),
        )

    if _has_any(e, ("引用过碎", "母本引用过碎")):
        return RepairPlan(
            root_cause="QUOTE_FRAGMENT",
            disposition="refine_scope" if "母本" in e else "retry_llm",
            action="merge_short_quotes",
            refine_scope="mother",
            structured_prompt=(
                "【根因：书名号引用过碎】\n"
                "并列句群应整簇放入同一对「」内引用，译后统一解释；"
                "禁止大量 ≤4 字碎引用。保留母本信息点，减少「」对数。"
            ),
            max_retries=2,
        )

    if _has_any(e, ("母本引用过碎", "分块")):
        return RepairPlan(
            root_cause="CHUNK_FRAGMENT",
            disposition="retry_llm",
            action="adjust_chunk_plan",
            structured_prompt=(
                "【根因：分块后母本过碎】\n"
                "合并相邻块或放宽分块边界，保证每块上下文连贯后再译。"
            ),
            max_retries=1,
        )

    if fail_count >= 3:
        return RepairPlan(
            root_cause="RETRY_EXHAUSTED",
            disposition="needs_human",
            action="human_review",
            structured_prompt="【熔断】已重试 3 次，请人工查看 repair_ticket 与 verify 日志。",
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
            disposition="needs_human",
            action="human_review",
            structured_prompt="【熔断】请人工处理 qa_state / verify 产物。",
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
