"""通识文言禁释词表（L0）与浅释检测：顺译时直接融入白话，禁止「X就是Y」/「善。」——好。"""

from __future__ import annotations

import re
from typing import List

# L0：通识字词，直接顺译，禁止单独引号+解释 / 旁白拆词
L0_GLOSS_WORDS = frozenset(
    {
        "崩",
        "薨",
        "卒",
        "殂",
        "立",
        "即位",
        "咸",
        "弗",
        "莫",
        "不",
        "从",
        "服",
        "诸侯",
        "天子",
        "帝王",
        "百姓",
        "万民",
        "天下",
        "乃",
        "遂",
        "于是",
        "既",
        "已",
        "未",
        "皆",
        "悉",
        "弗能",
        "莫能",
        "莫不",
        "咸来",
        "咸归",
        "咸尊",
        "宾从",
        "从服",
        # 「是为」系：正确顺译，禁止旁白解释字面
        "是为",
        "是谓",
        "是乃",
        "此之谓",
        "命之曰",
        "号之曰",
        # 浅显应答：禁止「善。」——好
        "善",
        "诺",
        "唯",
        "然",
        "否",
        "可",
    }
)

# L0 组合短语
L0_GLOSS_PHRASES = (
    "莫不从服",
    "莫能伐",
    "弗能征",
    "咸来宾从",
    "咸归轩辕",
    "咸尊轩辕",
    "三战",
    "然后得其志",
)

# 检测「「崩」就是去世」「崩，就是天子死」/「是为」字面注释 类冗余解释
_FORBIDDEN_GLOSS_PATTERNS = [
    re.compile(r"「崩」[^。]{0,20}(?:去世|逝世|死亡|驾崩)"),
    re.compile(r"「薨」[^。]{0,20}(?:去世|逝世|死亡)"),
    re.compile(r"「卒」[^。]{0,20}(?:去世|逝世|死亡)"),
    re.compile(r"崩[，,]?\s*(?:就是|即|指的是|意思是)[^。]{0,12}(?:去世|逝世|死亡|驾崩|天子)"),
    re.compile(r"薨[，,]?\s*(?:就是|即|指的是|意思是)[^。]{0,12}(?:去世|逝世|死亡|诸侯)"),
    re.compile(r"卒[，,]?\s*(?:就是|即|指的是|意思是)[^。]{0,8}(?:去世|逝世|死亡|死)"),
    re.compile(r"「?是为」?[^。]{0,16}(?:就是|意思是|指的是)[^。]{0,12}(?:这就是|称作|叫做)"),
    re.compile(r"「莫不从服」[^。]{0,40}(?:无不|没有不|都)"),
    re.compile(r"「咸」[^。]{0,12}(?:都|皆|全部)"),
    re.compile(r"「弗」[^。]{0,12}(?:不|没有)"),
    re.compile(r"「诸侯」[^。]{0,20}(?:各|部落|首领)"),
    re.compile(r"「天子」[^。]{0,20}(?:皇帝|君主|天子)"),
    re.compile(
        r"「([\u4e00-\u9fff])」[^。]{0,8}(?:就是|即|指的是|意思是)"
    ),
]

# 「短文言」——短白话：浅显同义回声
_TRIVIAL_QUOTE_GLOSS = re.compile(
    r"「([^」]{1,4})」\s*——\s*([^\n。！？；]{1,6})"
)

# 引号+破折号：默认同义作业体倾向（verify 软警告；增量破折号可保留）
_QUOTE_DASH_GLOSS = re.compile(
    r"[「“]([^」”]{1,100})[」”]\s*——\s*([^\n]{1,100})"
)

_TRIVIAL_ACK = frozenset(
    {
        "善",
        "善。",
        "诺",
        "诺。",
        "唯",
        "唯。",
        "然",
        "然。",
        "否",
        "否。",
        "可",
        "可。",
        "已",
        "已。",
    }
)

_TRIVIAL_GLOSS_TARGETS = frozenset(
    {
        "好",
        "好的",
        "是",
        "对",
        "行",
        "可以",
        "同意",
        "嗯",
        "不",
        "不行",
        "不对",
    }
)


def is_l0_word(word: str) -> bool:
    w = word.strip().strip("「」")
    return w in L0_GLOSS_WORDS or w in L0_GLOSS_PHRASES


def _norm_ack(s: str) -> str:
    return re.sub(r"[。．.！？\s]", "", (s or "").strip())


def detect_trivial_quote_gloss(text: str) -> List[str]:
    """「≤4 字文言」——≤6 字白话 且高度同义（含应答浅释）。"""
    issues: List[str] = []
    for m in _TRIVIAL_QUOTE_GLOSS.finditer(text or ""):
        quoted = m.group(1).strip()
        gloss = m.group(2).strip()
        qn, gn = _norm_ack(quoted), _norm_ack(gloss)
        if quoted in _TRIVIAL_ACK or qn in {_norm_ack(x) for x in _TRIVIAL_ACK}:
            if gn in _TRIVIAL_GLOSS_TARGETS or len(gn) <= 2:
                issues.append(f"浅显应答禁止「」+译述: {m.group(0)[:40]}")
                continue
        if len(qn) <= 2 and gn in _TRIVIAL_GLOSS_TARGETS:
            issues.append(f"短词同义浅释: {m.group(0)[:40]}")
            continue
        if qn and gn and (qn == gn or gn in qn or qn in gn):
            issues.append(f"同义回声译述: {m.group(0)[:40]}")
    return issues


def detect_quote_dash_gloss(text: str) -> List[str]:
    """引号+破折号：软警告（忌同义作业体主腔；偶发增量不硬拦）。"""
    issues: List[str] = []
    for m in _QUOTE_DASH_GLOSS.finditer(text or ""):
        issues.append(
            f"引号+破折号：宜优先融入叙述，忌同义再译主腔: {m.group(0)[:48]}"
        )
    return issues


def detect_forbidden_gloss(text: str) -> List[str]:
    """硬拦：L0 通识浅释、短引同义回声。一般破折号对照不在此列。"""
    issues: List[str] = []
    for pat in _FORBIDDEN_GLOSS_PATTERNS:
        for m in pat.finditer(text):
            issues.append(f"通识词冗余解释: {m.group(0)[:40]}")
    issues.extend(detect_trivial_quote_gloss(text))
    return issues


def gloss_rules_prompt_block() -> str:
    return (
        "禁释词（L0 · 禁止旁白过度解释）：崩/薨/卒/殂/立、是为/是谓/是乃、"
        "咸/弗/莫/皆/乃/遂/于是、诸侯/天子/天下/百姓，以及善/诺等浅显应答——"
        "直接写成白话，禁止「崩就是去世」「是为的意思是这就是」式注释。"
        "「莫不从服」等固定短语整体顺译，禁止拆词逐字解释。"
        "原文露出克制：绝大多数白话；「」仅金句等；用「」后优先融入接叙，"
        "反对句句同义「引文」——白话作业体（偶发增量破折号可用）。"
        "跨书只补有阅读价值的冲突/另说/背景/异评，禁止把用字异写当补全。"
        "浅显应答禁止「善。」——好；已是白话禁止再解释一遍。"
        "【释义旁白】生僻字/词、古文词/古语、古官职制度、人名身份、地名今地、"
        "器物礼制、异名谐音、看起来奇怪或不合常理处，须自然融入说书旁白："
        "单处≤200字，只做事实性白描，不发长篇议论，不强制出处；"
        "过渡用接叙/破折号点破，禁止滥用「说白了」等无意义过场词。"
        "【著名典故/成语】情节写清后须点名对上号（先叙后点，宜短）；"
        "如斩蛇起义、约法三章、破釜沉舟、四面楚歌等通行熟语。"
        "旁白解释的是名物称谓、古怪处，以及「情节写了但没对上号」的典故；"
        "不是给基础文言虚词做词典。"
    )
