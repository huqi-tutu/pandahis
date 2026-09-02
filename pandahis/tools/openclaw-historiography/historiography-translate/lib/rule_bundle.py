"""从唯一 SSOT 翻译规则.md 抽取本条 job 需要的章节，按四层结构注入 prompt。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from lib.config import paths
from lib.mother_sentences import mother_sentence_count
from lib.narrator_framing import format_narrator_section

_RULES = paths()["rules"]

# 翻译规则.md 实际 ## 标题 → 注入层级
# 规则文件使用「第零部分」「规则一」等中文序号，未按 P0/P1 等标签
_HEADING_TO_LAYER = {
    "第零部分：流水线约定": "P0",
    "执行纪律（每条翻译前）": "P0",
    "规则一：风格定位": "P1",
    "规则二：结构完整": "P1",
    "规则三：内容完整性与数据准确": "P0",
    "规则四：原文融入与引用规范（核心之一）": "P2",
    "规则四：原文融入与引用规范": "P2",
    "规则五：人物刻画": "P1",
    "规则六：纯叙事": "P1",
    "规则七：六类触发条件（含现代地名标注）": "P3",
    "规则八：六类触发条件（含现代地名标注）": "P3",
    "规则九：通假字处理": "P3",
    "规则十：逐句顺译原则（灵魂规则）": "P2",
    "规则十：逐句顺译原则": "P2",
    "规则十一：完成标准（Definition of Done）": "P3",
    # 规则十二（JSON 产出与汇总规范）纯编排器层面，不注入 LLM
}

# P0 = 硬约束，P1 = 写作风格，P2 = 流程规范，P3 = 辅助规则
# ABCD 编排：A 结构顺译 → B 文风整饰 → C 成篇装配 → D enrich
# enrich_plan: D 前置，仅外部补全决策
# legacy draft_mother / draft_enrich 保留兼容旧路径
_PHASE_SECTIONS: Dict[str, List[str]] = {
    "plan": ["P0", "P2E", "P3"],
    "enrich_plan": ["P0", "P2M", "P2E", "P3"],
    "draft_ab_merged": ["P0", "P2M", "P1_full"],
    "draft_structural": ["P0", "P2M"],
    "draft_style": ["P0", "P2M", "P1_full"],
    "draft_assemble": ["P0", "P1_style", "P2M"],
    "draft_mother": ["P0", "P2M", "P1_style"],
    "draft_enrich": ["P0", "P2M", "P2E", "P1_full", "P3"],
    "draft": ["P0", "P2M", "P2E", "P1_full", "P3"],
    "expansive_plan": ["P0", "P2E", "P3"],
    "batch_draft": ["P0", "P2M", "P2E", "P1_style", "P3"],
    "final_assemble": ["P0", "P1_style", "P2M"],
}

_PHASE_PREAMBLE: Dict[str, str] = {
    "plan": (
        "【本阶段】source_plan：只写计划 JSON，不写正文。\n"
        "【防幻觉 · plan】\n"
        "1. 事实边界=recalled 母本；母本逐句清单 M 须与母本分句一一对应，不得计划母本没有的信息点。\n"
        "2. 外部补全默认「采用:false」；仅当相对母本有异说/冲突观点/必要背景/母本未载细节/评价差异时标 true。\n"
        "3. 模型常识不得直接进正文：须在本阶段写成 plan「外部补全」项（出处+母本锚点+与母本关系）；"
        "写不出《书名·卷篇》→ 采用:false。\n"
        "4. 禁止计划与母本重复的外部补全；禁止计划虚构典籍、年号、对话、礼制步骤、亲属关系。\n"
        "5. 异说/传说须单独列项并标注补全类型，不与 hard 母本信息点混为一条。"
    ),
    "enrich_plan": (
        "【本阶段】enrich plan（D 前置）：baseline 已成稿，只计划外部补全与索引补充。"
        "baseline 已述内容不得再列为外部补全；默认采用:false。\n"
        "【防幻觉 · plan】纪律同 source_plan：须出处+母本锚点+与母本关系；不确定 → false。"
    ),
    "draft_ab_merged": (
        "【本阶段】AB 合并（短篇）：一次完成结构顺译 + 文风整饰（等同 legacy Phase1）。"
        "coverage-first + 按场景分段 + 口语 + 1–3 处轻度幽默；禁止他书、引入、结尾、参考著作。"
    ),
    "draft_structural": (
        "【本阶段】A 结构顺译：coverage-first，只写母本顺译骨架。"
        "禁止他书、引入、结尾、参考著作、通假/地名注释、幽默与风格化。"
        "按 M 清单句序；信息点 100% 覆盖；表达可白话但不必追求口语。"
    ),
    "draft_style": (
        "【本阶段】B 文风整饰：在 A 结构稿上系统性改写口气与分段。"
        "允许段落级重写，但禁止删 M 信息点、跳句、增删事实、引他书。"
        "朋友讲史式口语 + 全篇 1–4 处轻度幽默；禁论文腔与油腻梗。"
        "按场景分段；单段 120–150 字红线；引用句群后白话另起段。"
    ),
    "draft_assemble": (
        "【本阶段】C 成篇装配：LLM 创作前置引入（60–250 字）与简短结尾（1–2 句），"
        "保留 B 阶段正文信息点，组装 baseline 全文 + 参考著作（初版仅母本）。"
        "引入须宏观、口语、自然过渡到正文；禁止空泛升华与模板腔。"
        "结尾承接末段情节；退场不重复；引入段不计入母本覆盖。"
    ),
    "draft_mother": (
        "【本阶段】母本顺译（legacy Phase1）：只写母本 P 段顺译，禁止引用母本以外的著作。"
        "允许《史记》 framing；按 M 清单推进。ABCD 编排下请走 A→B。"
    ),
    "draft_enrich": (
        "【本阶段】D 知识增强（legacy）：在 baseline 上按 plan 插入补全。"
    ),
    "expansive_plan": (
        "【本阶段】发散式 plan（方案 A）：程序 M 清单已就绪；你只规划外部补全/索引/标注。"
        "尽量列全候选；采用:true 须有《书名·卷篇》且相对母本非重复。"
    ),
    "batch_draft": (
        "【本阶段】分批成稿：见下方「本步任务」与「冲突时优先级」。"
    ),
    "final_assemble": (
        "【本阶段】终稿装配：仅写前置引入（60–250 字）与结尾/总结（100–250 字）。"
        "正文已由程序拼接，勿输出正文或参考著作。"
    ),
    "draft": (
        "【本阶段】成稿：若未分两阶段，仍须母本先行、他书后补；"
        "规则与 Phase1+Phase2 合计一致。"
        "外部补全防幻觉纪律同 plan + enrich 置顶条。"
    ),
}


def _read() -> str:
    if not _RULES.is_file():
        raise FileNotFoundError(f"翻译规则 SSOT 不存在: {_RULES}")
    return _RULES.read_text(encoding="utf-8")


def _extract_sections(text: str) -> Dict[str, str]:
    """按 ## heading 切分，映射到标准层级名称（P0/P1/P2/P3）。"""
    result: Dict[str, str] = {}
    pattern = r"(^## .+$)"
    parts = re.split(pattern, text, flags=re.MULTILINE)
    current_layer = "_preamble"
    result[current_layer] = ""
    for part in parts:
        stripped = part.strip()
        if re.match(r"^## .+", stripped):
            heading = stripped.lstrip("# ").strip()
            current_layer = _heading_to_layer(heading)
            result.setdefault(current_layer, "")
        else:
            result[current_layer] = result.get(current_layer, "") + "\n" + part
    return {k: v.strip() for k, v in result.items() if v.strip()}


def _heading_to_layer(heading: str) -> str:
    """将翻译规则.md 的 ## 标题映射到 P0/P1/P2/P3 层级。"""
    for prefix, layer in _HEADING_TO_LAYER.items():
        if heading.startswith(prefix):
            return layer
    return heading  # 未知标题保留原名


def _p1_style_only(p1_text: str, *, phase: str = "") -> str:
    """规则一口语 + 幽默 + 叙事/分段（batch 阶段不含前置引入/篇末）。"""
    parts: List[str] = []
    m = re.search(r"(?s)(.*?)### 幽默规范", p1_text)
    if m:
        parts.append(m.group(1).strip())
    else:
        parts.append(p1_text.strip())
    humor = re.search(r"(?s)### 幽默规范\s*(.*?)(?=---|\n## |\Z)", p1_text)
    if humor:
        block = humor.group(1).strip()
        if phase != "batch_draft":
            block = re.sub(r"\*\*好的幽默[\s\S]*?\*\*不好的幽默", "", block)
            block = re.sub(r"\*\*不好的幽默[\s\S]*?\*\*原则：\*\*", "**原则：**", block)
            block = re.sub(r"\*\*克制的分寸[\s\S]*?(?=\*\*密度|\Z)", "", block)
        if block.strip():
            parts.append("### 幽默（摘要）\n\n" + block.strip())
    narrative = re.search(
        r"(?s)(\*\*核心：\*\* 全文叙事体.*?\n\n)(?=### 前置引入)",
        p1_text,
    )
    if narrative:
        parts.append("## 叙事与分段（规则六摘要）\n\n" + narrative.group(1).strip())
    section_headers = ("### 段落节奏",)
    if phase != "batch_draft":
        section_headers = ("### 前置引入", "### 段落节奏")
    for hdr in section_headers:
        sec = re.search(rf"(?s)({hdr}.*?)(?=### |## |\Z)", p1_text)
        if sec:
            parts.append(sec.group(1).strip())
    return "\n\n".join(p for p in parts if p).strip()


# ── 注入优化：三个后处理函数（SSOT 翻译规则.md 原文不动，仅注入时过滤/精简）──


def _strip_orchestrator_sections(text: str) -> str:
    """从 P0 剥离编排器/legacy 说明，LLM 成稿阶段不需要。"""
    _P0_STRIP = [
        r"### GLBL 入口[\s\S]*?(?=### |\Z)",
        r"### 召回纪律[\s\S]*?(?=### |\Z)",
        r"### 喊数[\s\S]*?(?=### |\Z)",
        r"### 分块翻译[\s\S]*?(?=### |\Z)",
        r"### 产出格式[\s\S]*?(?=### |\Z)",
        r"### 产出与分块[\s\S]*?(?=### |\Z)",
        r"### ABCD 四阶段[\s\S]*?(?=### |\Z)",
        r"### 两阶段成稿[\s\S]*?(?=### |\Z)",
        r"### 两阶段分工[\s\S]*?(?=### |\Z)",
        r"> \*\*Legacy 路径\*\*[\s\S]*?(?=### |\Z)",
    ]
    for pat in _P0_STRIP:
        text = re.sub(pat, "", text)
    return text


def _compress_writing_layer(text: str, *, phase: str = "") -> str:
    """注入前压缩：去代码块、去冗长示例段、去「为什么存在」背景故事。"""
    if not text:
        return text
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(
        r"\*\*为什么这条规则存在\?\*\*[\s\S]*?(?=\*\*具体|\*\*核心|\*\*数据|\*\*全局)",
        "",
        text,
    )
    if phase != "batch_draft":
        text = re.sub(r"### 幽默示例[\s\S]*?(?=---|\n## |\Z)", "", text)
        text = re.sub(
            r"### 轻度口语幽默[\s\S]*?(?=### 幽默示例|---|\n## |\Z)",
            "",
            text,
        )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_batch_yishuo_duplicate(text: str) -> str:
    """分批成稿：异说纪律已并入「跨著作补充」，去掉 P2 中重复的异说小节。"""
    return re.sub(
        r"### 异说（P0 硬约束）[\s\S]*?(?=### |---|\n## |\Z)",
        "",
        text or "",
    ).strip()


def _strip_batch_phase_sections(text: str) -> str:
    """分批成稿：去掉终检 checklist、程序复检、与本阶段无关的小节。"""
    patterns = [
        r"### 验收 Checklist[\s\S]*?(?=### |\Z)",
        r"### 程序复检[\s\S]*?(?=### |\Z)",
        r"常用地名：[^\n]+\n",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text)
    return text.strip()


_BATCH_STEP_TASK = """\
- **输入**：本批「母本逐句清单」各 M 的「编号 + 原文摘句」；同块「引用粒度说明」按句型分组；第 2 批起另有批次定位 / 母本前情 / 上批末段白话。
- **输出**：JSON 的 `母本顺译`（或 `翻译详情`），**仅**本批正文段落。
- **本步禁止**：全书引入、篇末总结、参考著作列表、清单外母本句。"""

_BATCH_PRIORITY_COMPACT = """\
规则冲突时从高到低（与 SSOT 七条一致；细则见对应 P2 小节）：

1. **母本覆盖** — 本批每条 M 须有白话对应；禁止跳号、漏句、把后续 M 提前写进本批。
2. **逐句顺译** — 严格 M001→…，不跳句重组；**名句/金句/关键评价**须「」摘录原文再白话（见 P2「何时引/何时不引」）。
3. **数据准确** — 数字、年代、人名事件不编造；写不出卷篇则不写该条硬史实。
4. **多史料融合** — 顺译中遇异说/背景/母本未载细节，锚点句后 1–3 句《》引用、回主线（见 P2「跨著作补充」）。
5. **口语风格** — 朋友讲史式短句；禁止论文摘要腔与百科条目腔。
6. **幽默** — 本批至少 1 处、全书累计 2–4 处；来自史实反差，不硬塞梗。
7. **延伸补充** — 须母本未载或母本未详述、挂锚点、有《书名·卷篇》；不替代句序（见 P2「跨著作补充」）。"""

_BATCH_CROSS_WORK = """\
### 跨著作补充（分批成稿执行 · =「外部补全与多源融入」）

> **与 SSOT 关系：** 翻译规则「外部补全与多源融入」是**全书概念**（三层来源、锚点、去重）；**本节**是分拆成稿时的**唯一执行入口**——P0 术语表保留名词解释，此处不再重复三层长文。含异说分述（不再另设异说小节）。

**三层（写前先定位）：** ① **母本层** — 本批 M 顺译主线，100% 覆盖 ② **索引补充层** — recall 中 role=补充 的 block，异说/新视角，锚点插入 ③ **外部补全层** — 你主动检索的他书材料，须《书名·卷篇》

**母本去重门禁（写前必问）** — 拟补充的每条，先对照 **当前母本著作、当前卷** 的原文（本批 M「原文摘句」及同卷上下文）：
- 该事实/细节/背景在母本中 **已有且够清楚** → **不补**（重复无意义）
- **未载**，或母本 **仅一笔带过、读者会懵** → 可从他书补，须《书名·卷篇》
- **异说** → 仅当与他书在叙述/时间/因果上 **确有不同** 时写；母本已详述且无冲突说法的不补

**检索范围**（不是等 plan、不是被动「据说」）：
- 索引已合并的 **补充著作**（profile 补充=1 时，优先同传主相关卷篇如《汉书》）
- 同事件在他书中的 **异说、系年、背景、制度解释**
- 母本略写但理解本传 **不可缺少** 的人物关系、前因后果、政策语境
- 有典籍出处的 **故事、传说、后世评价**（须分述，禁止与母本调和成一个版本）

**五类准入**（须通过母本去重门禁，且能写《书名·卷篇》）：
1. **背景** — 制度、礼仪、地名、官制、时代语境
2. **异说** — 与他书说法不同；**母本先述，再「《某书·某卷》则…」**；禁止融合折中
3. **母本未载细节** — 他书有载、且有助于理解本条要点
4. **人物首现/关系** — 母本未解释清楚的身份、亲属、政治关系
5. **评价差异** — 不同史家评判；分述，不替读者裁决

**三级力度**：一级（缺了会懵）｜二级（影响理解线/同时代参照）｜三级（延伸典故，慎补且仍挂母本锚点）

**写法**：母本句后 **1–3 句** → 立刻回主线；禁止百科大段、禁止「此外《某书》还记载…」拼接感。

**禁止**：无《书名·卷篇》的「据说/相传」；母本已有详述内容的重复叙述；编造对话、年号、礼制步骤。"""

_BATCH_HARD_BANS = """\
- **AI 文学腔**：见 `shared/ai_flavor_words.py`，同一篇 ≥5 次 → verify fail。
- **结构重组**：开篇大段脱离母本、先讲背景再进正文。
- **资料拼接**：重复叙述、语义打架、批注式【】、百科体。"""


def _slim_batch_p0(p0_text: str) -> str:
    """分批成稿 P0：去掉与「叙述者/本步任务/冲突优先级」重复的流水线大段。"""
    if not p0_text:
        return ""
    strip_patterns = [
        r"### 执行优先级[\s\S]*?(?=### |\Z)",
        r"### 禁止事项[\s\S]*?(?=### |\Z)",
        r"### 精简四步成稿[\s\S]*?(?=### |\Z)",
        r"### 外部补全与多源融入（权威）[\s\S]*?(?=### |\Z)",
        r"\*\*叙述者 framing\*\*[^\n]*\n",
        r"> translate 编排器注入[^\n]*\n",
        r"> \*\*总目标\*\*：[^\n]+\n",
        r"总目标：以母本为底本顺译[^\n]+\n",
    ]
    text = p0_text
    for pat in strip_patterns:
        text = re.sub(pat, "", text)
    text = _strip_orchestrator_sections(text)
    text = _dedupe_shunyi(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _dedupe_shunyi(p0_text: str) -> str:
    """顺译定义归一到规则十：P0 中只留一行引用，完整定义仅存于 P2 规则十。"""
    replacement = (
        "### 顺译的定义\n\n"
        "**顺译**的权威定义见规则十（逐句顺译原则）。简言之：句序守恒、信息点守恒、表达可重写。\n"
    )
    p0_text = re.sub(
        r"### 顺译的定义[\s\S]*?(?=### )",
        replacement,
        p0_text,
    )
    return p0_text


def _merge_external_admission(p0_text: str) -> str:
    """外部补全准入合并：「两阶段成稿」中的准入条件精简为引用，「外部补全与锚点原则」保留三级体系为权威。"""
    # 「两阶段成稿」中 L142 的准入条件整句替换为短引用
    p0_text = re.sub(
        r"\*\*外部补全准入\*\*（plan 与 enrich 均须遵守）：仅当相对母本存在 \*\*异说、冲突观点、必要背景、母本未载细节、评价差异\*\* 之一时方可采用；与母本主体/事件/结果相同的内容视为重复，\*\*不得\*\*以外部补全再写一遍。",
        "**外部补全准入**见下文「外部补全与锚点原则」（含三级补充体系）。",
        p0_text,
    )
    return p0_text


def _optimize_layer(text: str, layer: str, *, phase: str = "") -> str:
    """对指定层级文本执行注入优化。"""
    if not text:
        return text
    if layer == "P0":
        text = _strip_orchestrator_sections(text)
        text = _dedupe_shunyi(text)
        text = _merge_external_admission(text)
    if layer in ("P1", "P2M", "P2E", "P3"):
        text = _compress_writing_layer(text, phase=phase)
    if phase == "batch_draft" and layer == "P3":
        text = _strip_batch_phase_sections(text)
    return text


def _extract_goal(text: str) -> str:
    m = re.search(r"> \*\*总目标\*\*：[^\n]+", text)
    return m.group(0).strip() if m else "总目标：以母本为底本顺译，完整、流畅、有据地呈现一个史略。"


def _split_p2_layers(p2: str) -> Tuple[str, str, str]:
    """P2 → 规则四母本引用 / 规则四他书异说 / 规则十顺译。"""
    if not p2:
        return "", "", ""
    m10 = re.search(r"(## 规则十[\s\S]*)", p2)
    shunyi = m10.group(1).strip() if m10 else ""
    rest = p2[: m10.start()].strip() if m10 else p2.strip()
    m_ext = re.search(r"### 真实性优先", rest)
    if m_ext:
        mother = rest[: m_ext.start()].strip()
        external = rest[m_ext.start() :].strip()
    else:
        mother = rest
        external = ""
    return mother, external, shunyi


def _join_p2m(mother: str, shunyi: str) -> str:
    return _join(mother, shunyi)


def _join(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p.strip())


def compile_rule_bundle(
    recalled: Dict[str, Any],
    *,
    phase: str = "draft",
    batch_m_count: int | None = None,
) -> str:
    text = _read()
    sections = _extract_sections(text)

    supplement = sum(
        1 for b in (recalled.get("blocks") or []) if b.get("role") == "补充"
    )
    profile = "multi_source" if supplement else "single_mother"
    m_count = batch_m_count if batch_m_count is not None else mother_sentence_count(recalled)
    preamble = _PHASE_PREAMBLE.get(phase, _PHASE_PREAMBLE["draft"])
    meta = (
        f"【规则来源】翻译规则.md（SSOT 要点节选）\n{preamble}\n"
        f"【profile】{profile}  M≈{m_count}  补充={supplement}"
    )

    # 按层收集并优化
    p0 = _optimize_layer(sections.get("P0", ""), "P0", phase=phase)
    p1 = _compress_writing_layer(sections.get("P1", ""), phase=phase)
    p2_raw = sections.get("P2", "")
    p2m_cite, p2e_cite, p2_shunyi = _split_p2_layers(p2_raw)
    p2m = _optimize_layer(_join_p2m(p2m_cite, p2_shunyi), "P2M", phase=phase)
    p2e = _optimize_layer(p2e_cite, "P2E", phase=phase)
    p3 = _optimize_layer(sections.get("P3", ""), "P3", phase=phase)

    p1_style = _p1_style_only(p1, phase=phase) if p1 else ""

    layer_map = {
        "P0": p0,
        "P2M": p2m,
        "P2E": p2e,
        "P1_style": p1_style,
        "P1_full": p1,
        "P3": p3,
    }

    picked = _PHASE_SECTIONS.get(phase, _PHASE_SECTIONS["draft"])
    style_keys = {"P1_style", "P1_full"}
    process_keys = {"P2M", "P2E"}
    style_blocks: List[str] = []
    process_blocks: List[str] = []
    other_blocks: List[str] = []
    for key in picked:
        block = layer_map.get(key, "")
        if not block:
            continue
        if key in style_keys:
            style_blocks.append(block)
        elif key in process_keys:
            process_blocks.append(block)
        elif key != "P0":
            other_blocks.append(block)

    parts: List[str] = []
    narrator = format_narrator_section(phase)
    if narrator.strip():
        parts.append(narrator)

    if phase == "batch_draft":
        parts.append(f"## 本步任务\n\n{_BATCH_STEP_TASK}")
        parts.append(f"## 冲突时优先级\n\n{_BATCH_PRIORITY_COMPACT}")
        slim_p0 = _slim_batch_p0(p0)
        profile_line = f"【profile】{profile}  M≈{m_count}  补充={supplement}"
        head = _join(
            profile_line,
            f"### 硬禁令\n\n{_BATCH_HARD_BANS}",
            slim_p0,
        )
        if head.strip():
            parts.append(f"## 校验与术语（P0 摘要）\n\n{head}")
        p2m_batch = _strip_batch_yishuo_duplicate(p2m)
        proc = _join(p2m_batch, _BATCH_CROSS_WORK, p2e)
        if proc.strip():
            parts.append(f"## 引用与顺译（P2）\n\n{proc}")
    else:
        head = _join(meta, _extract_goal(text), p0)
        if head.strip():
            parts.append(f"## 硬约束（P0）\n\n{head}")
        proc = _join(*process_blocks)
        if proc.strip():
            parts.append(f"## 引用与顺译（P2）\n\n{proc}")
    writing = _join(*(style_blocks + other_blocks))
    if writing.strip():
        parts.append(f"## 写作规范（P1/P3）\n\n{writing}")
    return "\n\n".join(parts)


# ── 命令行验证入口 ──
# 运行方式: python -m lib.rule_bundle plan|draft_mother|draft_enrich
# 将 LLM 实际收到的规则 bundle 写入 /tmp/rule_bundle_<phase>.md 便于审查
# 同时打印统计摘要到终端

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _PHASES = (
        "plan",
        "enrich_plan",
        "draft_mother",
        "draft_enrich",
        "draft",
        "expansive_plan",
        "batch_draft",
        "final_assemble",
    )
    phase = sys.argv[1] if len(sys.argv) > 1 else "batch_draft"
    if phase not in _PHASES:
        print(f"用法: python -m lib.rule_bundle [{'|'.join(_PHASES)}]")
        sys.exit(1)

    recalled = {"id": "DUMP_VERIFY", "blocks": [], "母本内容": []}
    bundle = compile_rule_bundle(recalled, phase=phase)

    out_path = Path(f"/tmp/rule_bundle_{phase}.md")
    out_path.write_text(bundle, encoding="utf-8")
    print(f"文件: {_RULES}")
    print(f"阶段: {phase}")
    print(f"注入量: {len(bundle)} 字符 ≈ {len(bundle)//4} tokens")
    print(f"写入: {out_path}")
    print(f"打开: open {out_path}")
