"""按著作拆分 txt 实际结构，生成注入 LLM prompt 的正文结构提示（与 check_format 硬检一致）。"""

from __future__ import annotations

from typing import Dict, Optional


def work_text_structure_hint(work: str) -> str:
    """返回 Step1 / Step1a 页眉下的「正文结构」硬提示。"""
    key = (work or "").strip()
    fn = _HINTS.get(key, _hint_generic)
    return fn()


def _hint_generic() -> str:
    return (
        "【正文结构 · 通用】\n"
        "- P1 必须先读段落索引 `paragraphs[0].text`，再划块；禁止凭卷名猜段归属\n"
        "- `exclude_reason` 只能使用规范枚举字面量（见 step1_blocks.md）\n"
        "- 卷首独立标题行 → `卷首标题`；卷末论赞 → 对应著作论赞类 exclude\n"
        "- 块 `name` 须与 Step1a protagonists 完全一致；合传按传记段首划界，勿按皇帝名扩主轴"
    )


def _hint_shiji() -> str:
    return (
        "【正文结构 · 《史记》拆分 txt】\n"
        "- **无独立卷首标题行**：P1 即正文开篇（如「黄帝者…」「秦始皇帝者…」），"
        "**禁止**把 P1 标为 `卷首标题` 或 `世系链`\n"
        "- 本纪/世家开篇「X者，Y之子也」→ **主轴叙事**，归入主人公 block\n"
        "- `世系链` 仅用于卷中**纯族谱式**短段\n"
        "- 卷末以「**太史公曰**」起笔 → `exclude_reason: 太史公曰`（勿写赞曰/论赞）\n"
        "- 志书（礼书、乐书等）：全卷 skip 或全 exclude，不建人物 block"
    )


def _hint_hanshu() -> str:
    return (
        "【正文结构 · 《汉书》拆分 txt】\n"
        "- **P1 通常是卷首标题行**（如「卷四十三郦陆朱刘叔孙传第十三」「卷一上  高帝纪第一上」），"
        "无句号、非叙事 → `exclude_reason: 卷首标题`（**不是** `篇内小标题`）\n"
        "- **正文从 P2 起**（本纪亦如此：P1 标题，P2「高祖，沛…」或叙事起句）\n"
        "- 卷末论赞以「**赞曰**」起笔 → `exclude_reason: 赞曰`；"
        "含「班固曰」亦归论赞类 exclude。**禁止**标为 `太史公曰`\n"
        "- `篇内小标题` 仅用于卷中**短行**篇名（如「西域传第六十六上」，无句号）；"
        "勿把全书卷首标题误标为此类\n"
        "- **合传（hezhuan）**：按卷名人物顺序，以各传**传记段首**划块"
        "（如「郦食其，…人也」「陆贾，楚人也」「硃建，楚人也」「娄敬，齐人也」「叔孙通，薛人也」）\n"
        "- **同段接力**：上一人末句与下一人起笔可能在**同一段**；"
        "下一人 block 从含其传记段首的段落起，勿把前人末段误归下一人\n"
        "- **异名**：正文或异体字须对照 Step1a 标准名（硃建→朱建，娄敬→刘敬）\n"
        "- 原文字句：取各 entry **开篇段**（最小 paragraph_from）段首逐字摘录 ≥12 字"
    )


def _hint_sanguozhi() -> str:
    return (
        "【正文结构 · 《三国志》拆分 txt】\n"
        "- **P1 通常是卷首标题行**（如「卷一 魏书一  武帝纪第一」）→ `exclude_reason: 卷首标题`\n"
        "- **正文从 P2 起**\n"
        "- 卷末陈寿论赞以「**评曰**」起笔 → `exclude_reason: 评曰`，**不建条目、不划入事略**。"
        "只排除该段，勿把评曰之后的裴注上表等一并盲延为论赞\n"
        "- 若「评曰」粘在叙事末句后，须先拆成独立段再 exclude\n"
        "- **禁止**标为 `太史公曰` / `赞曰`\n"
        "- 合传按传记段首划块；卷末评曰总评本卷诸人，不归任何传主"
    )


_HINTS: Dict[str, callable] = {
    "01史记": _hint_shiji,
    "02汉书": _hint_hanshu,
    "04三国志": _hint_sanguozhi,
}
