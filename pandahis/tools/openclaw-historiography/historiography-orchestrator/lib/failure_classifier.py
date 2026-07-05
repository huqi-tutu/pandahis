"""将 verify / 编排失败归类为根因，并给出失效产物与结构化重试指令。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class FailurePlan:
    root_cause: str
    redo_step1a: bool = False
    invalidate: Tuple[str, ...] = ()
    action: str = ""
    structured_prompt: str = ""
    try_blocks_autofix: bool = False
    try_volume_repair: bool = False


def _has_any(text: str, keys: Tuple[str, ...]) -> bool:
    return any(k in text for k in keys)


def _exclude_content_gate_failed(text: str) -> bool:
    """exclude 内容门仅在实际未过时才算 blocks 错误（日志里常有 ✅ 通过行）。"""
    if "exclude 内容门" not in text and "📄 exclude" not in text:
        return False
    if "✅ exclude 内容 OK" in text:
        return False
    return _has_any(
        text,
        (
            "禁止 exclude=",
            "非「太史公曰」起笔",
            "非「赞曰」起笔",
            "非「论赞」起笔",
            "exclude 内容门未过",
        ),
    )


_ATTRIBUTION_KEYS: Tuple[str, ...] = (
    "卷首标题",
    "不得设 owners",
    "须 exclude_reason=",
    "segment_attribution 行数",
    "segment_attribution 缺少",
    "segment_attribution 为空",
    "归属 category=",
    "owners 为空但未声明",
    "有 owners 时不应同时设 exclude_reason",
    "在 entries 中无对应条目",
    "纯纪年",
    "篇内小标题",
)

_STEP4_ROLLBACK_CAUSES: frozenset[str] = frozenset(
    {
        "WRONG_PROTAGONIST",
        "ATTRIBUTION_LAYOUT",
        "BLOCKS_LAYOUT",
        "HEZHUAN_NAMES",
        "EVIDENCE_QUOTE",
    }
)


def should_rollback_from_step4(plan: FailurePlan, step: str) -> bool:
    """Step4 失败但根因在 Step1 blocks/归属时，打回 Step1 而非空转 Step4。"""
    return step.strip() == "4" and plan.root_cause in _STEP4_ROLLBACK_CAUSES


def classify_failure(
    step: str,
    err_str: str,
    *,
    work: str = "",
    vol: str = "",
    fail_count: int = 0,
) -> FailurePlan:
    """根据错误文本推断根因与修复动作。"""
    e = err_str or ""
    s = step.strip()

    if _has_any(
        e,
        (
            "主轴理解",
            "双重校验",
            "protagonists",
            "人物身份门",
            "缺少主轴",
            "禁止增删改上述主轴",
            "name+category 集合",
        ),
    ):
        return FailurePlan(
            root_cause="WRONG_PROTAGONIST",
            redo_step1a=True,
            invalidate=("protagonists", "blocks", "skeleton"),
            action="redo_step1a_then_blocks",
            structured_prompt=(
                "【根因：卷主人公 / Step1a 主轴错误】\n"
                "1. 删除旧 protagonists，仅据著作+卷名重列主人公（禁止读段猜帝王）。\n"
                "2. 再按新清单划 blocks；name+category 须与 protagonists 逐字一致。\n"
                "3. 卷名特例：弟子列传禁止孔子；外戚世家吕太后主轴在009本纪；"
                "志书/表卷应整卷 skip、entries 为空。"
            ),
            try_volume_repair=fail_count >= 2,
        )

    if s == "4" and _has_any(
        e,
        (
            "Step4 LLM 后字段仍缺失",
            "Step4 字段校验失败",
            "史略开始年",
            "四级帝王",
            "优先级",
            "优先级判定理由",
            "_坐标主轴说明",
            "跨时期人物",
            "非法优先级",
            "knowledge_provenance",
        ),
    ):
        return FailurePlan(
            root_cause="STEP4_FIELDS",
            invalidate=(),
            action="step4_hardening",
            structured_prompt=(
                "【根因：Step4 字段 / 坐标 / 年份】\n"
                "按 _needs_llm 逐条补正式字段；跨时期人物须写 _auto_filled._坐标主轴说明；"
                "禁止删 _auto_filled。"
            ),
            try_volume_repair=fail_count >= 2,
        )

    if _has_any(e, _ATTRIBUTION_KEYS) or (
        "归属表检查" in e and "❌" in e
    ):
        return FailurePlan(
            root_cause="ATTRIBUTION_LAYOUT",
            redo_step1a=False,
            invalidate=("blocks", "skeleton"),
            action="fix_attribution",
            structured_prompt=(
                "【根因：逐段归属 / 卷首标题 / exclude 标注错误】\n"
                "1. 卷首标题段 P1 须 owners=[]、exclude_reason=卷首标题。\n"
                "2. 太史公曰/赞曰/论赞 仅用于对应起笔段；汉书用赞曰/论赞，勿标太史公曰。\n"
                "3. blocks+expand 后 segment_attribution 须与 entries.paragraphs 双向一致。\n"
                "4. 勿改 protagonists 清单（除非同时报主轴错误）。"
            ),
            try_volume_repair=fail_count >= 2,
        )

    if _has_any(
        e,
        (
            "blocks 无效",
            "未覆盖",
            "expand",
            "total_paragraphs",
            "重叠",
        ),
    ) or _exclude_content_gate_failed(e):
        return FailurePlan(
            root_cause="BLOCKS_LAYOUT",
            redo_step1a=False,
            invalidate=("blocks", "skeleton"),
            action="fix_blocks",
            structured_prompt=(
                "【根因：blocks / exclude 布局错误】\n"
                "1. 修正 blocks+excludes，覆盖 P1～Ptotal 每一段且无重叠。\n"
                "2. 史记 P1 多为正文开篇，禁止误标世系链/卷首标题。\n"
                "3. 太史公曰仅用于以「太史公曰」起笔的段落。\n"
                "4. 勿改 protagonists 清单（除非上条同时报主轴错误）。"
            ),
            try_blocks_autofix=True,
            try_volume_repair=fail_count >= 2,
        )

    if _has_any(e, ("原文字句", "原文挑战", "逐字")):
        return FailurePlan(
            root_cause="EVIDENCE_QUOTE",
            invalidate=("skeleton",),
            action="fix_quotes",
            structured_prompt=(
                "【根因：原文字句 / 开篇引用】\n"
                "修正每条 entry 开篇段「原文字句」：从段落索引逐字摘录段首≥12字。"
            ),
        )

    if _has_any(e, ("合传", "史略名称", "禁止把卷名", "假士臣", "兼容条目")):
        return FailurePlan(
            root_cause="HEZHUAN_NAMES",
            invalidate=("blocks", "skeleton"),
            action="fix_hezhuan_entries",
            structured_prompt=(
                "【根因：合传人物命名 / 条目拆分】\n"
                "按卷名与合传规则为每位传主建独立条目；禁止卷名简称作史略名。"
            ),
            try_volume_repair=fail_count >= 2,
        )

    if s == "2":
        return FailurePlan(
            root_cause="SKELETON_FORMAT",
            invalidate=("blocks", "skeleton"),
            action="redo_step1b",
            structured_prompt=(
                "【根因：Step2 skeleton 硬检】\n"
                "修正 segment_attribution 与 entries 一致性后重跑 Step1。"
            ),
            try_volume_repair=fail_count >= 2,
        )

    return FailurePlan(
        root_cause="UNKNOWN",
        invalidate=("skeleton",) if s == "1" else (),
        action="generic_retry",
        structured_prompt="【根因未分类】请据下列原始错误逐项修正，勿重复上一轮相同改法。",
        try_blocks_autofix=s == "1" and work.startswith("01史记"),
        try_volume_repair=fail_count >= 2,
    )


def format_verify_feedback(plan: FailurePlan, err_str: str, *, max_raw: int = 1200) -> str:
    raw = (err_str or "").strip()
    if len(raw) > max_raw:
        raw = raw[-max_raw:]
    body = plan.structured_prompt.strip()
    if raw:
        body += f"\n\n---\n【原始错误摘要】\n{raw}"
    return body
