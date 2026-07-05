"""从唯一 SSOT 翻译规则.md 抽取本条 job 需要的章节，按四层结构注入 prompt。"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from lib.config import paths
from lib.mother_sentences import mother_sentence_count

_RULES = paths()["rules"]

_ALL_WRITING_RULES = list(range(1, 13))
_WRITING_SECTIONS_PLAN = [4, 10, 11]
_DONE_SECTION = 11
_CN = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]

_LAYER1_HEADINGS = ("执行优先级", "禁止事项")
_LAYER2_PART0_HEADINGS = (
    "术语",
    "顺译的定义",
    "召回纪律",
    "太史公曰 / 司马迁评述（仅翻译环节处理）",
    "翻译总流程",
    "两阶段成稿（translate 编排器）",
    "内容层级与取舍",
    "外部补全与锚点原则",
    "重复判定",
    "允许压缩（表达层）",
    "产出格式（translate 编排器）",
    "喊数（动笔前一行）",
)

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


def _extract_subsection(text: str, heading: str) -> str:
    pat = rf"(### {re.escape(heading)}[\s\S]*?)(?=\n### |\n## |\Z)"
    m = re.search(pat, text)
    return m.group(1).strip() if m else ""


def _extract_part0_block(text: str) -> str:
    m = re.search(
        r"(## 第零部分：流水线约定[\s\S]*?)(?=\n---\n\n## 执行纪律)",
        text,
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r"(## 第零部分：流水线约定[\s\S]*?)(?=\n---\n\n## 规则一)",
        text,
    )
    return m.group(1).strip() if m else ""


def _extract_discipline(text: str) -> str:
    m = re.search(
        r"(## 执行纪律[\s\S]*?)(?=\n---\n\n## 规则一)",
        text,
    )
    return m.group(1).strip() if m else ""


def _extract_rule(text: str, n: int) -> str:
    title = f"## 规则{_CN[n]}："
    m = re.search(
        rf"({re.escape(title)}[\s\S]*?)(?=\n## 规则|\n## 附录|\Z)",
        text,
    )
    return m.group(1).strip() if m else ""


def _extract_goal(text: str) -> str:
    m = re.search(r"> 总目标：[^\n]+", text)
    return m.group(0).strip() if m else "总目标：以母本为底本顺译，完整、流畅、有据地呈现一个史略。"


def _join_sections(sections: List[str]) -> str:
    return "\n\n".join(s for s in sections if s.strip())


def _writing_sections(phase: str) -> List[int]:
    if phase == "plan":
        return _WRITING_SECTIONS_PLAN
    return _ALL_WRITING_RULES


def compile_rule_bundle(recalled: Dict[str, Any], *, phase: str = "draft") -> str:
    text = _read()

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

    part0 = _extract_part0_block(text)
    part0_intro = ""
    if part0:
        intro_m = re.match(
            r"(## 第零部分：流水线约定\n\n>[^\n]+\n)",
            part0,
        )
        if intro_m:
            part0_intro = intro_m.group(1).strip()

    layer1 = _join_sections(
        [
            meta,
            "",
            "## 任务目标",
            _extract_goal(text),
            "",
            _extract_subsection(part0, "执行优先级"),
            "",
            _extract_subsection(part0, "禁止事项"),
        ]
    )

    layer2_parts: List[str] = ["## 执行流程"]
    if part0_intro:
        layer2_parts.append(part0_intro)
    for h in _LAYER2_PART0_HEADINGS:
        sec = _extract_subsection(part0, h)
        if sec:
            layer2_parts.append(sec)
    disc = _extract_discipline(text)
    if disc:
        layer2_parts.append(disc)
    layer2 = _join_sections(layer2_parts)

    writing_nums = _writing_sections(phase)
    writing_chunks = [_extract_rule(text, n) for n in writing_nums]
    layer3 = _join_sections(["## 写作规范（全部须遵守）", *writing_chunks])

    done = _extract_rule(text, _DONE_SECTION)
    layer4 = (
        _join_sections(["## 验收标准（动笔时即按此自检）", done])
        if done and phase != "plan"
        else ""
    )

    layers = [
        "【第一层】任务目标与纪律",
        layer1,
        "【第二层】执行流程",
        layer2,
        "【第三层】写作规范",
        layer3,
        "【第四层】验收",
        layer4,
    ]
    return "\n\n".join(layers)
