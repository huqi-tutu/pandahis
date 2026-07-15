"""从唯一 SSOT 翻译规则.md 抽取本条 job 需要的章节，按四层结构注入 prompt。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from lib.config import paths
from lib.mother_sentences import mother_sentence_count

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
    "规则七：注音标注": "P3",
    "规则八：六类触发条件（含现代地名标注）": "P3",
    "规则九：通假字处理": "P3",
    "规则十：逐句顺译原则（灵魂规则）": "P2",
    "规则十：逐句顺译原则": "P2",
    "规则十一：完成标准（Definition of Done）": "P3",
    # 规则十二（JSON 产出与汇总规范）纯编排器层面，不注入 LLM
}

# P0 = 硬约束，P1 = 写作风格，P2 = 流程规范，P3 = 辅助规则
# plan 阶段: P0 + P2(引用+顺译) + P3(产出格式)
# Phase1 draft_mother: P0 + P2(引用+顺译) + P1(风格定位，不含幽默)
# Phase2 draft_enrich: P0 + P2(引用+顺译) + P1(全量风格@幽默) + P3(注音/地名/通假)
_PHASE_SECTIONS: Dict[str, List[str]] = {
    "plan": ["P0", "P2", "P3"],
    "draft_mother": ["P0", "P2", "P1_style"],
    "draft_enrich": ["P0", "P2", "P1_full", "P3"],
    "draft": ["P0", "P2", "P1_full", "P3"],
}

_PHASE_PREAMBLE: Dict[str, str] = {
    "plan": (
        "【本阶段】source_plan：只写计划 JSON，不写正文。"
        "外部补全默认「采用:false」；仅当相对母本有冲突/异说/必要背景/母本未载细节时标 true，"
        "并填写「补全类型」「与母本关系」。"
    ),
    "draft_mother": (
        "【本阶段】母本顺译（Phase 1）：只写母本 P 段顺译，禁止引用母本以外的著作。"
        "允许《史记》 framing；dense 句须「引母本原词 + 白话释词」逐项展开；"
        "按 plan 母本逐句清单 M 编号顺序推进。"
    ),
    "draft_enrich": (
        "【本阶段】补全成稿（Phase 2）：在 Phase 1 母本顺译稿上，"
        "仅按 plan 中「采用:true」的外部补全/索引补充，在锚点处穿插他书内容。"
        "禁止重复母本已述事实；只写异说、冲突观点、背景、母本未载细节。"
    ),
    "draft": (
        "【本阶段】成稿：若未分两阶段，仍须母本先行、他书后补；"
        "规则与 Phase1+Phase2 合计一致。"
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


def _p1_style_only(p1_text: str) -> str:
    """从 P1 全文中剥离纯风格部分（规则一核心 + 规则六纯叙事），排除幽默规范。"""
    parts = []
    m = re.search(r"(?s)(.*?)### 幽默规范", p1_text)
    if m:
        parts.append(m.group(1).strip())
    else:
        parts.append(p1_text.strip())
    return "\n\n".join(p for p in parts if p).strip()


# ── 注入优化：三个后处理函数（SSOT 翻译规则.md 原文不动，仅注入时过滤/精简）──


def _strip_orchestrator_sections(text: str) -> str:
    """从 P0/P3 中剥离编排器层面的技术细节，LLM 不需要知道。"""
    # P0 中需剥离的子章节（纯编排器技术细节）
    _P0_STRIP = [
        r"### GLBL 入口与跨著作补充[\s\S]*?(?=### |\Z)",
        r"### 召回纪律[\s\S]*?(?=### |\Z)",
        r"### 喊数（动笔前一行[\s\S]*?(?=### |\Z)",
        r"### 分块翻译[\s\S]*?(?=### |\Z)",
    ]
    for pat in _P0_STRIP:
        text = re.sub(pat, "", text)

    # 产出格式：只保留单条 JSON 三字段摘要，删除 nested JSON 结构、汇总产出等编排器细节
    text = re.sub(
        r"### 产出格式[\s\S]*?(?=### )",
        "### 产出格式\n\n单条产出固定三字段：`史略ID`、`翻译详情`（Markdown 正文 + 文末 `*参考著作：*`）、`史料原文`（编排器自动写入）。\n\n",
        text,
    )

    return text


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


def _optimize_layer(text: str, layer: str) -> str:
    """对指定层级文本执行注入优化。"""
    if not text:
        return text
    if layer == "P0":
        text = _strip_orchestrator_sections(text)
        text = _dedupe_shunyi(text)
        text = _merge_external_admission(text)
    return text


def _extract_goal(text: str) -> str:
    m = re.search(r"> \*\*总目标\*\*：[^\n]+", text)
    return m.group(0).strip() if m else "总目标：以母本为底本顺译，完整、流畅、有据地呈现一个史略。"


def _join(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p.strip())


def compile_rule_bundle(recalled: Dict[str, Any], *, phase: str = "draft") -> str:
    text = _read()
    sections = _extract_sections(text)

    supplement = sum(
        1 for b in (recalled.get("blocks") or []) if b.get("role") == "补充"
    )
    profile = "multi_source" if supplement else "single_mother"
    preamble = _PHASE_PREAMBLE.get(phase, _PHASE_PREAMBLE["draft"])
    meta = (
        f"【规则来源】historiography-compose/references/翻译规则.md（唯一 SSOT；"
        f"以下节选须在动笔时遵守，不得留到质检再补）\n"
        f"{preamble}\n"
        f"【profile】{profile}  母本分句≈{mother_sentence_count(recalled)}  "
        f"补充block={supplement}\n"
        f"【plan要求】母本逐句清单须≥母本分句数95%，每条仅含一个分句，编号M001起连续；"
        f"每条须有「必现词」"
    )

    # 按层收集并优化
    p0 = _optimize_layer(sections.get("P0", ""), "P0")
    p1 = sections.get("P1", "")
    p2 = sections.get("P2", "")
    p3 = _optimize_layer(sections.get("P3", ""), "P3")

    # 执行流程 = 规则十（逐句顺译）+ 规则四（引用规范）
    process = _join(p2)

    # P1 分两个变体：纯风格（Phase1）和全量（Phase2）
    p1_style = _p1_style_only(p1) if p1 else ""

    picked = _PHASE_SECTIONS.get(phase, _PHASE_SECTIONS["draft"])
    write_rules: List[str] = []
    for key in picked:
        if key == "P0":
            write_rules.append(p0)
        elif key == "P2":
            write_rules.append(p2)
        elif key == "P1_style":
            write_rules.append(p1_style)
        elif key == "P1_full":
            write_rules.append(p1)
        elif key == "P3":
            write_rules.append(p3)

    layer3 = _join(*write_rules)

    layers = [
        ("【第一层】硬约束 — P0（违反即失败）", _join(meta, _extract_goal(text), p0)),
        ("【第二层】执行流程", process),
        ("【第三层】写作规范", layer3),
    ]

    return "\n\n".join(
        f"## {label}\n\n{content}" for label, content in layers if content.strip()
    )


# ── 命令行验证入口 ──
# 运行方式: python -m lib.rule_bundle plan|draft_mother|draft_enrich
# 将 LLM 实际收到的规则 bundle 写入 /tmp/rule_bundle_<phase>.md 便于审查
# 同时打印统计摘要到终端

if __name__ == "__main__":
    import sys
    from pathlib import Path

    phase = sys.argv[1] if len(sys.argv) > 1 else "draft_enrich"
    if phase not in ("plan", "draft_mother", "draft_enrich", "draft"):
        print(f"用法: python -m lib.rule_bundle [plan|draft_mother|draft_enrich|draft]")
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
