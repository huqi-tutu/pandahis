"""前置引入 / 篇末收束：宏观框架硬门禁。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# 引入段若出现，多半是把母本起传写进了首段
_MOTHER_PLOT_IN_INTRO = (
    r"封为胶东王",
    r"立为太子",
    r"栗太子",
    r"降为临江王",
    r"孝景四年",
    r"孝景七年",
    r"建元元年",
    r"即位元年",
    r"斩蛇",
    r"有了身孕",
    r"梦中与神",
    r"蛟龙",
    r"中阳里",
    r"姓刘，字季",
)

# 气氛倒挂：先登基/即位场面，再补身世
_CHRONO_HOOK = (
    r"^(?:武帝|皇上|天子|孝武)?登基那年",
    r"^登基那会儿",
    r"^即位那年",
    r"^刚即位那会儿[，,].{0,40}新气象",
    r"^宫里宫外都是",
)


def _paras(detail: str) -> List[str]:
    body = (detail or "").split("参考著作")[0]
    return [p.strip() for p in body.split("\n\n") if p.strip()]


def should_enforce_intro(plan: Optional[Dict[str, Any]]) -> bool:
    if not plan:
        return True  # 无 plan 也按默认要求有宏观引入
    tier = str(plan.get("前置引入档位") or "框架引入")
    return tier in ("框架引入", "短引入", "一句过渡", "")


def detect_macro_intro_failures(
    detail: str,
    plan: Optional[Dict[str, Any]] = None,
    *,
    mother: str = "",
) -> List[str]:
    """宏观前置引入硬拦：独立段、篇幅、禁起传粘连、禁倒序钩子。"""
    if not should_enforce_intro(plan):
        return []
    paras = _paras(detail)
    tier = str((plan or {}).get("前置引入档位") or "框架引入")
    min_c, max_c = (40, 120) if tier == "一句过渡" else (100, 280)

    if len(paras) < 2:
        return [
            "前置引入缺失：须独立成段，段后空一行再进入母本叙事"
            "（先宏观介绍是谁/为何重要，再另起一段按母本开篇顺叙）"
        ]
    intro = paras[0]
    n = len(intro)
    if n < min_c:
        return [f"前置引入过短（{n} 字，须约 {min_c}–{max_c if tier != '一句过渡' else 120} 字宏观概括）"]
    if n > max_c:
        return [
            f"前置引入与正文疑似粘连（首段 {n} 字 > {max_c}）；"
            "引入段写完须空一行，母本起传另起一段"
        ]

    meta_openers = (
        r"今天要讲",
        r"咱们今天",
        r"咱们就",
        r"下面来讲",
        r"下面要讲",
        r"接下来要说",
        r"接下来讲",
        r"且听我慢慢",
        r"一件件说来",
        r"诸位看官",
        r"列位看官",
        r"各位听客",
        r"今儿个",
        r"本篇以",
        r"本文以",
        r"异同处参看",
        r"关键关节按时间线",
        r"以母本为准",
        r"这篇史略",
    )
    for pat in meta_openers:
        if re.search(pat, intro):
            return [
                f"前置引入含场次/加工元叙述（命中「{pat}」）；"
                "须宏观介绍人物，禁止看官套话与编排说明"
            ]

    for pat in _CHRONO_HOOK:
        if re.search(pat, intro):
            return [
                "前置引入时间倒挂：勿先写「登基/新气象」再补身世；"
                "首段先交代是谁、为何重要，封王立太子等起传放到下一段"
            ]

    # 起传公式
    has_name_formula = bool(
        re.search(r"姓[\u4e00-\u9fff]{1,4}(?:氏)?[，,、].{0,12}字[\u4e00-\u9fff]", intro)
        or re.search(r"[\u4e00-\u9fff]{2,6}人[，,].{0,20}姓", intro)
    )
    has_parent_birth = bool(
        re.search(r"(父亲|母亲|其父|其母|太公|有了身孕|生下了|梦中与神|盘(?:踞)?在)", intro)
    )
    if has_name_formula and has_parent_birth:
        return [
            "前置引入写成了母本开篇起传（籍贯姓字+父母身世）；"
            "引入段只做宏观定位，起传细节放到下一段"
        ]

    # 母本开篇专有情节链不应挤进引入（命中 ≥2 条）
    plot_hits = [p for p in _MOTHER_PLOT_IN_INTRO if re.search(p, intro)]
    if len(plot_hits) >= 2:
        return [
            "前置引入含母本起传情节（"
            + "、".join(plot_hits[:4])
            + "）；宏观段勿写封王/立太子等细节，留给第二段起"
        ]

    # 与母本首段过度重合 → 假引入
    if mother:
        m0 = re.split(r"\n\s*\n", mother.strip())[0] if mother.strip() else ""
        m_plain = re.sub(r"\s+", "", m0)[:120]
        i_plain = re.sub(r"\s+", "", intro)
        if len(m_plain) >= 40:
            # 简单：母本首段关键 8 字窗命中过多
            hits = 0
            for i in range(0, min(len(m_plain) - 7, 80), 8):
                gram = m_plain[i : i + 8]
                if gram and gram in i_plain:
                    hits += 1
            if hits >= 4:
                return [
                    "前置引入几乎是母本开篇改写；"
                    "须另写宏观人物定位段，母本起传从第二段原样信息改写推进"
                ]
    return []


def detect_macro_epilogue_failures(
    detail: str,
    plan: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """篇末人物收束硬拦（长文 / 框架引入默认开启）。"""
    from lib.longform_compat import is_longform

    enforce = False
    if plan and is_longform(plan):
        enforce = True
    tier = str((plan or {}).get("前置引入档位") or "")
    if tier in ("框架引入", "短引入"):
        enforce = True
    if not plan:
        # 无 plan：正文够长则要求收束
        body = (detail or "").split("参考著作")[0]
        if len(re.sub(r"\s+", "", body)) >= 8000:
            enforce = True
    if not enforce:
        return []

    paras = _paras(detail)
    if len(paras) < 3:
        return ["篇末收束缺失：须在母本身后事之后另起一段做人物总结收科"]
    last = paras[-1]
    if re.search(r"(共有八个儿子|高帝有八个儿子|高祖共有|次为燕王|最后是燕王)", last):
        return [
            "篇末缺收束总结：最后一段仍是子嗣罗列；"
            "须另起一段（约 80–220 字）点明历史位置与一生主线"
        ]
    if len(last) < 80:
        return [f"篇末收束过短（{len(last)} 字，须约 80–220 字人物总结）"]
    if len(last) > 320:
        return [f"篇末收束过长（{len(last)} 字）；应收短，勿再开新情节"]
    if re.search(r"列位看官|诸位看官|您心里|综上所述|总的来说", last):
        return ["篇末收束含看官喊话或论文腔；改为第三人称人物总结"]
    return []
