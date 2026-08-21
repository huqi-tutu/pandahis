"""从唯一 SSOT 翻译规则.md 按阶段切片注入 prompt。

理想分工（SSOT 正文不改，仅注入切片）：
- plan：决定跨书补什么
- Phase1 draft_mother：母本顺译（覆盖/引用/地名通假）
- Phase2 draft_enrich：先跨书补写，再润色（口语/幽默/人物/结构）

头卡（本阶段目标+硬禁区）始终置顶；避免 P0/P2 整包重复灌入。
注：SSOT 里「外部补全与锚点/防幻觉」写在第零部分；注入时归入 plan/Phase2「跨书主场」。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from lib.config import paths
from lib.mother_sentences import mother_sentence_count

_RULES = paths()["rules"]

# ## 标题前缀 → 稳定章节键（规则十二 / 附录不注入）
_CHAPTER_KEYS: Tuple[Tuple[str, str], ...] = (
    ("第零部分：流水线约定", "zero"),
    ("执行纪律（每条翻译前）", "discipline"),
    ("规则一：风格定位", "r1"),
    ("规则二：结构完整", "r2"),
    ("规则三：内容完整性与数据准确", "r3"),
    ("规则四：原文融入与引用规范", "r4"),
    ("规则五：人物刻画", "r5"),
    ("规则六：纯叙事", "r6"),
    ("规则七：六类触发条件", "r7"),
    ("规则八：太史公曰", "r8"),
    ("规则八：六类触发条件", "r7"),  # 极旧标题别名
    ("规则九：通假字处理", "r9"),
    ("规则十：逐句顺译原则", "r10"),
    ("规则十一：完成标准", "r11"),
)

# 兼容旧调用方 / CLI 摘要（逻辑名，非再灌整层）
_PHASE_SECTIONS: Dict[str, List[str]] = {
    "plan": ["head", "zero_external", "r3", "r4_light", "r10_light", "dod_plan"],
    "draft_mother": [
        "head",
        "r10",
        "r4",
        "r7",
        "r8",
        "r9",
        "r1_light",
        "r2_light",
        "r5_light",
        "r6_light",
        "dod_mother",
    ],
    "draft_enrich": [
        "head",
        "enrich_step1",
        "zero_external",
        "r3",
        "enrich_step2",
        "r1",
        "r2",
        "r5",
        "r6",
        "cover_short",
        "r7_short",
        "r9_short",
        "dod_enrich",
    ],
    "draft": [
        "head",
        "r10",
        "r4",
        "r7",
        "r8",
        "r9",
        "zero_external",
        "r3",
        "r1",
        "r2",
        "r5",
        "r6",
        "r11",
    ],
}

_PHASE_PREAMBLE: Dict[str, str] = {
    "plan": (
        "【本阶段唯一目标】只写 source_plan JSON，不写正文译文。\n"
        "【硬禁区】\n"
        "1. 不得输出翻译详情/母本顺译正文。\n"
        "2. 外部补全：宏观选题两层——"
        "①检索通道找材料（通道不是交作业清单）；"
        "②重要性门槛：须挂合法性/制度政策/战局用人/历史评价/神话辩伪等主轴，"
        "挂不上的碎闻神异一律 false；宁缺毋滥，禁止为凑通道/凑条数灌水；"
        "禁止更简平行纪、雕花、现代评述、母本同一卷。\n"
        "3. 长文禁止交空数组 `外部补全: []`；写不出 true 也须留候选并写理由；"
        "禁止用索引书目顶替跨书决策。\n"
        "4. 长文勿整表重写母本逐句清单（编排器已生成）；核心产出外部补全+索引裁决+参考著作+写作结构。\n"
        "5. 索引补充处理只裁决 recalled 已有补充块；与外部补全分工；他书不得全部「去重不用」。\n"
        "6. 禁止计划与全书母本重复的外部补全；禁止虚构典籍、年号、对话、礼制步骤、亲属关系。\n"
        "7. `采用:true` 须：合法补全类型 + 《书·卷》+「与母本关系」写清冲突/另说/背景/异评"
        "（勿写「场面更细」「异字」）；禁止 GLBL_/过渡段/「原文翻译」；禁止母本同一卷。\n"
        "【验收】参考著作（≤10，只交最重要）与写作结构非空；采用:true 属当用三类；"
        "长文外部补全非空且书目不过度锁死两书。"
    ),
    "draft_mother": (
        "【本阶段唯一目标】母本顺译：语义覆盖 + 句序 + 流畅白话；禁止他书。\n"
        "【质量宪法】守八大守恒；尤重主体四元组与认知不升级；"
        "省略可恢复，隐含不可臆造。\n"
        "【硬禁区】\n"
        "1. 禁止引用母本以外著作（不得出现《汉书》《国语》等他书名）；允许《史记》 framing。\n"
        "2. 禁止跳号、漏信息点；禁止为「好读」打乱 M 句序。\n"
        "3. 原文露出克制：绝大多数白话；「」仅金句/名言/诏令/誓词/诗赋等；"
        "用「」后优先融入接叙，反对句句 `「」——同义白话` 作业体（偶发增量破折号可用）。"
        "未译原话必须「」；白话对话用 “”（禁止弯引装文言原文）。诗赋/誓词：先概括主旨，再直角「」保留文言，禁止整段白话译诗。\n"
        "4. 对 plan 标「经典引用候选」的 M，**必须**落地直角「」原文镶嵌（融合接叙，勿默认对照体）；"
        "史料原文禁止用弯引“”；非候选勿凑数。\n"
        "5. 禁止滥用「说白了」等无意义过场词；"
        "**遇生僻/古怪处须释义旁白**（≤200字、事实白描、自然融入、不强制出处）；"
        "**著名典故/成语**（斩蛇起义、约法三章、破釜沉舟等）：情节写清后须点名对上号（先叙后点，宜短）；"
        "**禁止**对崩/薨/卒/是为等 L0 基础词做旁白过度解释；"
        "正文禁止嵌套 JSON。\n"
        "6. 本阶段不强制幽默（交给 Phase2）；笔调按说书人当面讲史。\n"
        "7. 禁止 Markdown `**加粗**`（小程序只对「」内原文自动加粗）。\n"
        "8. 直角「」须完整摘句/对话/并列句群；禁止为凑必现词砌大量短「」（质检按短引密度硬拦）。\n"
        "【验收】本批 M 覆盖达标；必现词自然出现；无他书《》；无 `**`；短「」不过密；有候选则有「」原文。"
    ),
    "draft_enrich": (
        "【本阶段两职能】① 按 plan 锚点落跨书补写 → ② **必须改表达**成说书人口语。"
        "两步不可颠倒；几乎原样誊抄 Phase1 = 职能②失败。\n"
        "【硬禁区】\n"
        "1. 仅采用 plan「采用:true」与索引「引入|异说」；禁止 plan 外新增硬史实；"
        "只写母本未载/有差异的增量；补完即回主线；禁止把母本后文已有情节 externally 再讲一遍。\n"
        "2. 索引他书不得整卷复述母本；只补年号/诏令/评价/详略等差异点；"
        "若有采用/异说，正文**必须**出现对应他书《》（质检硬拦）。\n"
        "3. 禁止削覆盖（改表达不得蒸发 Phase1 信息点）；禁止批间/章间双写"
        "（短版预告+长版重讲、换说法复述）。\n"
        "4. 原文露出克制+融合：「」仅史料金句等；用「」后优先接叙融入，"
        "反对句句 `引文——同义白话`（偶发增量破折号可用）；已是白话禁止再塞进「」；"
        "诗赋/誓词先概括主旨再「」引文言；保留 Phase1 已镶嵌的经典「」；"
        "有名言/候选则必须「」且成稿达数量下限（硬拦），无则勿硬凑。\n"
        "4b. 前置引入须独立成段（约 100–250 字宏观人物名片），禁看官/加工说明/起传粘连；"
        "篇末须另起一段人物收束（约 80–220 字）；"
        "长文篇末须另段收束总结；跨书只补有阅读价值的增量，禁无实质异文。\n"
        "5. 禁止滥用「说白了」等无意义过场词；释义旁白须自然融入（见规则一）；"
        "**著名典故/成语**情节写完后须点名对上号（先叙后点）；"
        "翻译详情禁止嵌套 JSON / 代码围栏；禁止 Markdown `**加粗**`。\n"
        "5b. 改表达守恒：专名/数字/官职/地名/年号/人数/胜负因果不许改；"
        "禁止编造**无据**对白/心理小剧场（史料已有言语可改成口语口气）。\n"
        "6. 异说须分述；文风为《明朝那些事儿》说书人笔调——短句场面，非编年直译。\n"
        "7. 无《》锚点的「传说/据说/相传/有人说」等合计 ≤5（P1）；同句有《书》才不计。"
        "「这家伙/这位爷」≤3 次。\n"
        "8. 文末「参考著作」前须空行独立成段（分章/分批本批勿写，由程序合并追加）。\n"
        "【验收】①他书补全已挂锚点；②相对 Phase1 明显改过表达（说书可读，非誊抄）；"
        "无传说配额爆表；无 `**`；未削覆盖与有信息量的「」/《》句。"
    ),
    "draft": (
        "【本阶段唯一目标】母本先行、他书后补、文风一次完成（未分两阶段时的合并包）。\n"
        "【硬禁区】同 Phase1+Phase2：流畅白话、忌同义 `「」——` 作业体主腔、禁过场词、禁嵌套 JSON。\n"
        "外部补全纪律同 plan + enrich。"
    ),
}
_COVER_SHORT = (
    "### 覆盖与引用（Phase2 短约束）\n\n"
    "- 保留 Phase1 信息点、专名、数字、真正的史料「」摘句与已插入的《书·卷》句。\n"
    "- **必须改表达**：同信息换说书人口语；禁止几乎誊抄 Phase1。\n"
    "- 禁止大段删母本事实或另起无关故事；信息点可合并短句、可删描写，**不可整段蒸发情节**。\n"
    "- 改表达时消掉同义 `「…」——…` 作业体；禁止滥用「说白了」等无意义过场词；"
    "生僻/古怪处须留释义旁白（≤200字）；著名典故/成语须点名对上号；"
    "崩/薨/卒/是为等 L0 词禁止旁白拆词；白话对话用 “”。\n"
    "- 不要再跑一遍「逐句√清单」；落盘前自检本章母本要点仍在。"
    "程序会按母本段落锚点硬检连续漏段，漏了整段会打回补洞而不是整篇重写。\n"
)

_R1_LIGHT = (
    "### 风格（Phase1 极短）\n\n"
    "用说书人当面讲史的口气把母本信息讲清楚，忌硬译堆砌。"
    "不强制幽默点与明朝风细则（Phase2 主场）。\n"
)

_R2_LIGHT = (
    "### 退场（Phase1 轻量）\n\n"
    "母本若含本传主崩/薨/卒/自沈等，本阶段自然顺译即可；"
    "不要另起他书补叙或篇末重复退场（补叙在 Phase2）。\n"
)

_R5_LIGHT = (
    "### 人物（Phase1 轻量）\n\n"
    "别写成人物说明书；性格与场面跟母本走，细节刻画留给 Phase2。\n"
)

_R6_LIGHT = (
    "### 叙事（Phase1 轻量）\n\n"
    "禁止批注体/百科腔插话；顺译正文即可。\n"
)

_R7_SHORT = (
    "### 地名等触发（补写时）\n\n"
    "本批新出现的制度/地名/专名，按规则七同样解释或标注今址；"
    "对照 `古地名今地对照.md`；勿因改腔丢掉已有标注。\n"
)

_R9_SHORT = (
    "### 通假（改腔时）\n\n"
    "改腔时保留已有通假标注；勿把「禽（通『擒』）」类标注改丢。\n"
)

_R4_LIGHT_PLAN = (
    "### 引用（plan 轻量）\n\n"
    "规划 M 清单时标注引用粒度意向即可；正文引用落地在 Phase1。"
    "异说引用须能落到可标《书·卷》的外部补全项。\n"
)

_R10_LIGHT_PLAN = (
    "### 逐句清单（plan 轻量）\n\n"
    "短文：母本逐句清单须与母本分句对应、编号连续；每条一个分句 + 必现词。\n"
    "长文：清单由编排器程序生成，你勿整表重写；只交跨书决策字段。\n"
    "不要在本阶段写译文。\n"
)

_DOD_PLAN = (
    "### 验收（plan）\n\n"
    "- 短文：M 清单覆盖母本分句；长文：决策 JSON 可合并到程序清单。\n"
    "- `参考著作`、`写作结构` 非空；`参考著作` 硬上限 ≤10（只交最重要）。\n"
    "- 采用:true：补全类型∈枚举；出处为可核验《书·卷》（禁 GLBL_/过渡段/「原文翻译」/"
    "母本同一卷）；「与母本关系」写清增量（禁仅「与母本相同/重复母本」）。\n"
    "- 长文：外部补全非空；跨书勿锁死两书；采用:true 须属异说/冲突/背景/评价差异（禁雕花与无实质异文）。\n"
    "- 他书索引补充不得全部「去重不用」。\n"
)

_DOD_MOTHER = (
    "### 验收（Phase1）\n\n"
    "- 本批 M 语义覆盖达标；必现词自然出现。\n"
    "- 无他书书名（《史记》 framing 除外）；无参考著作节。\n"
    "- 无 Markdown `**加粗**`；直角「」完整摘句为主，短「」不过密。\n"
    "- 诗赋/誓词：概括主旨 +「」文言，无整段白话译诗。\n"
    "- 「」后优先融入接叙，忌同义破折号作业体主腔；有经典引用候选则**必须**有「」落地（硬）。\n"
)

_DOD_ENRICH = (
    "### 验收（Phase2）\n\n"
    "- 职能①：采用:true / 索引异说已挂《书·卷》落地；正文可见对应他书《》（硬）；无 plan 外硬史实。\n"
    "- 职能②：说书改表达；与母本重合≥95% 视为誊抄硬失败；72%–95% 软警告（好稿约 50%）。\n"
    "- 长卷有经典引用候选则直角「」达下限（硬）。\n"
    "- 无《》的传说/据说类触发词未超配额；「这家伙/这位爷」≤3。\n"
    "- 无 Markdown `**`；参考著作独立成段（分章/分批本批除外）。\n"
    "- 未削 Phase1 覆盖与有信息量的「」/《》句。\n"
)

# 第零部分中归入「跨书主场」的子节（SSOT 正文位置在 zero，语义属外部补全）
_ZERO_EXTERNAL_TITLES = (
    "### 内容层级与取舍",
    "### 外部补全与锚点原则",
    "### 外部补全防幻觉（plan + enrich 置顶纪律）",
    "### 重复判定",
)


def _read() -> str:
    if not _RULES.is_file():
        raise FileNotFoundError(f"翻译规则 SSOT 不存在: {_RULES}")
    return _RULES.read_text(encoding="utf-8")


def _chapter_key(heading: str) -> Optional[str]:
    for prefix, key in _CHAPTER_KEYS:
        if heading.startswith(prefix):
            return key
    return None


def _extract_chapters(text: str) -> Dict[str, str]:
    """按 ## 切分为独立章节键。"""
    result: Dict[str, str] = {}
    parts = re.split(r"(^## .+$)", text, flags=re.MULTILINE)
    current: Optional[str] = None
    buf: List[str] = []
    for part in parts:
        stripped = part.strip()
        if re.match(r"^## .+", stripped):
            if current and buf:
                result[current] = "\n".join(buf).strip()
            heading = stripped.lstrip("# ").strip()
            current = _chapter_key(heading)
            buf = [stripped] if current else []
            if current is None:
                buf = []
        elif current is not None:
            buf.append(part)
    if current and buf:
        result[current] = "\n".join(buf).strip()
    return result


def _extract_subsections(chapter: str, titles: Tuple[str, ...]) -> str:
    if not chapter:
        return ""
    chunks: List[str] = []
    for title in titles:
        m = re.search(
            rf"(?s)({re.escape(title)}.*?)(?=\n### |\n## |\Z)", chapter
        )
        if m:
            chunks.append(m.group(1).strip())
    return _join(*chunks)


def _split_r1(r1: str) -> Tuple[str, str]:
    """规则一 → (风格定位不含幽默, 幽默规范及之后)。"""
    if not r1:
        return "", ""
    m = re.search(r"(?m)^(### 幽默规范\s*)$", r1)
    if not m:
        return r1.strip(), ""
    return r1[: m.start()].strip(), r1[m.start() :].strip()


def _strip_orchestrator_sections(text: str) -> str:
    """注入前去掉编排器附录与已迁出写作主线的运维段。"""
    text = re.sub(r"(?ms)^## 附录：编排器与运维\s*\n.*\Z", "", text)
    for pat in (
        r"### GLBL 入口与跨著作补充[\s\S]*?(?=### |\Z)",
        r"### 召回纪律[\s\S]*?(?=### |\Z)",
        r"### 喊数（动笔前一行[\s\S]*?(?=### |\Z)",
        r"### 分块翻译[\s\S]*?(?=### |\Z)",
        r"### 产出格式[\s\S]*?(?=### |\Z)",
    ):
        text = re.sub(pat, "", text)
    return text


def _dedupe_shunyi(text: str) -> str:
    replacement = (
        "### 顺译的定义\n\n"
        "**顺译**的权威定义见规则十。简言之：句序守恒、信息点守恒、表达可重写。\n"
    )
    return re.sub(r"### 顺译的定义[\s\S]*?(?=### |\Z)", replacement, text)


def _merge_external_admission(text: str) -> str:
    return re.sub(
        r"\*\*外部补全准入\*\*[^\n]*\n?",
        "",
        text,
        count=1,
    )


def _optimize_zero_blob(text: str) -> str:
    if not text:
        return text
    text = _strip_orchestrator_sections(text)
    text = _dedupe_shunyi(text)
    text = _merge_external_admission(text)
    return text.strip()


def _extract_goal(text: str) -> str:
    m = re.search(r">\s*(?:\*\*)?总目标(?:\*\*)?：[^\n]+", text)
    return (
        m.group(0).lstrip("> ").strip()
        if m
        else "总目标：以母本为底本顺译，完整、流畅、有据地呈现一个史略。"
    )


def _join(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p and p.strip())


def _priority_snip(zero: str, *, phase: str) -> str:
    """终稿质量维度 + 冲突裁决 + 禁止 + 写作纪律/阈值表。

    Phase1 注入终稿七维（知终稿目标）+ 本阶段主责；不要求本阶段写他书/幽默。
    """
    raw = _extract_subsections(
        zero,
        (
            "### 终稿质量维度（七项）",
            "### 成稿硬门槛（七项并列 · 缺一不可）",  # 旧标题兼容
            "### 冲突裁决序",
            "### 执行优先级",  # 更旧标题兼容
            "### 禁止事项（硬 / 软）",
            "### 写作纪律与程序阈值（模型必知）",
        ),
    )
    if not raw:
        return raw
    if phase == "draft_mother":
        # 他书相关硬禁的「动笔」留给 Phase2；七维条文仍保留（终稿目标）
        raw = re.sub(r"(?m)^- 无出处发挥[^\n]+\n?", "", raw)
        raw = re.sub(r"(?m)^- 调和异说[^\n]+\n?", "", raw)
        raw = re.sub(
            r"(?m)^- 用正在翻译的\*\*母本同一卷\*\*[^\n]+\n?",
            "",
            raw,
        )
        raw += (
            "\n\n**【本阶段主责】** 落实终稿质量维度 1–4 的骨架"
            "（信息完整、顺序守恒、事实准确、白话融合）；"
            "5–7 在 Phase2 补齐。"
            "须用说书人白话写顺——"
            "**禁止**写成「先凑覆盖、文风以后再说」的干巴对照体；"
            "**禁止**本阶段写他书或硬塞幽默。"
        )
    return raw.strip()


def _strip_leading_h2(body: str) -> str:
    """章节正文自带 ## 标题时，外层已有【主场】标题，去掉内层重复 H2。"""
    return re.sub(r"^## .+\n+", "", body.strip(), count=1)


def compile_rule_bundle(recalled: Dict[str, Any], *, phase: str = "draft") -> str:
    if phase not in _PHASE_PREAMBLE:
        phase = "draft"

    text = _read()
    ch = _extract_chapters(text)
    zero = ch.get("zero", "")

    supplement = sum(
        1 for b in (recalled.get("blocks") or []) if b.get("role") == "补充"
    )
    profile = "multi_source" if supplement else "single_mother"
    preamble = _PHASE_PREAMBLE[phase]
    head = (
        f"【规则来源】historiography-compose/references/翻译规则.md（唯一 SSOT；"
        f"以下为本阶段切片，须动笔时遵守）\n\n"
        f"{preamble}\n\n"
        f"【profile】{profile}  母本分句≈{mother_sentence_count(recalled)}  "
        f"补充block={supplement}\n"
        f"【plan要求】短文：母本逐句清单须≥母本分句数95%、每条仅一个分句、编号连续；"
        f"长文：清单由编排器生成，你输出外部补全等决策字段即可。"
        f"必现词落盘时程序重算。\n\n"
        f"{_extract_goal(text)}"
    )

    r3 = _strip_leading_h2(ch.get("r3", ""))
    r4 = _strip_leading_h2(ch.get("r4", ""))
    r7 = _strip_leading_h2(ch.get("r7", ""))
    r8 = _strip_leading_h2(ch.get("r8", ""))
    r9 = _strip_leading_h2(ch.get("r9", ""))
    r10 = _strip_leading_h2(ch.get("r10", ""))
    r11 = _strip_leading_h2(ch.get("r11", ""))
    r2 = _strip_leading_h2(ch.get("r2", ""))
    r5 = _strip_leading_h2(ch.get("r5", ""))
    r6 = _strip_leading_h2(ch.get("r6", ""))
    disc = _strip_leading_h2(ch.get("discipline", ""))
    r1_full = _strip_leading_h2(ch.get("r1", ""))
    zero_snip = _priority_snip(zero, phase=phase)
    # 跨书主场：第零·外部补全相关 + 规则三数据准确（SSOT 章节分置，注入合并）
    zero_external = _optimize_zero_blob(
        _extract_subsections(zero, _ZERO_EXTERNAL_TITLES)
    )
    cross_book = _join(zero_external, r3)
    # 虚词陷阱：写作必知，专灌顺译阶段（plan/enrich 不灌，避免挤占跨书注意力）
    xuci = _extract_subsections(zero, ("### 文言虚词误读陷阱",))

    if phase == "plan":
        blocks = [
            ("【头卡】本阶段目标与硬禁区", head),
            ("【共用】优先级与禁止（短摘）", zero_snip),
            ("【主场】跨书决策 · 外部补全与内容准确", cross_book),
            ("【轻量】规则十 · 清单要求", _R10_LIGHT_PLAN),
            ("【轻量】规则四 · 引用意向", _R4_LIGHT_PLAN),
            ("【验收】", _DOD_PLAN),
            ("【执行纪律】", disc),
        ]
    elif phase == "draft_mother":
        from lib.quality_constitution import constitution_snip

        blocks = [
            ("【头卡】本阶段目标与硬禁区", head),
            ("【质量宪法】八大守恒 · Phase1", constitution_snip(phase="draft_mother")),
            ("【共用】优先级 · 禁止 · 纪律阈值", zero_snip),
            ("【主场】规则十 · 逐句顺译", r10),
            ("【主场】文言虚词误读陷阱", xuci),
            ("【主场】规则四 · 原文引用", r4),
            ("【主场】规则七 · 地名等触发", r7),
            ("【主场】规则八 · 论赞", r8),
            ("【主场】规则九 · 通假", r9),
            ("【轻量】规则一 · 白话可读", _R1_LIGHT),
            ("【轻量】退场", _R2_LIGHT),
            ("【轻量】人物", _R5_LIGHT),
            ("【轻量】叙事", _R6_LIGHT),
            ("【验收】", _DOD_MOTHER),
            ("【执行纪律】", disc),
        ]
    elif phase == "draft_enrich":
        from lib.quality_constitution import constitution_snip

        blocks = [
            ("【头卡】本阶段目标与硬禁区", head),
            ("【质量宪法】八大守恒 · Phase2", constitution_snip(phase="draft_enrich")),
            # 说书主场前置：避免大段禁令/补全书把改表达挤没
            ("【主场 · 改表达】规则一 · 风格+幽默", r1_full),
            ("【主场 · 改表达】规则五 · 人物", r5),
            ("【主场 · 改表达】规则六 · 纯叙事", r6),
            ("【短约束】覆盖与引用（必须改表达+守恒）", _COVER_SHORT),
            (
                "【辅 · 锚点补全】",
                "先落 plan 采用/异说再改表达；补完回主线。"
                "正文须出现对应他书《》。",
            ),
            ("【辅 · 锚点补全】外部补全与内容准确", cross_book),
            ("【辅】规则二 · 结构/退场", r2),
            ("【辅】地名", _R7_SHORT),
            ("【辅】通假", _R9_SHORT),
            ("【共用】纪律频率（勿压过说书主场）", zero_snip),
            ("【验收】", _DOD_ENRICH),
            ("【执行纪律】", disc),
        ]

    else:
        from lib.quality_constitution import constitution_snip

        blocks = [
            ("【头卡】本阶段目标与硬禁区", head),
            ("【质量宪法】八大守恒", constitution_snip(phase="draft")),
            ("【共用】优先级 · 禁止 · 纪律阈值", zero_snip),
            ("【顺译】规则十", r10),
            ("【顺译】文言虚词误读陷阱", xuci),
            ("【顺译】规则四", r4),
            ("【顺译】规则七", r7),
            ("【顺译】规则八", r8),
            ("【顺译】规则九", r9),
            ("【补写】跨书与内容准确", cross_book),
            ("【润色】规则一", r1_full),
            ("【润色】规则二", r2),
            ("【润色】规则五", r5),
            ("【润色】规则六", r6),
            ("【验收】规则十一", r11),
            ("【执行纪律】", disc),
        ]

    return "\n\n".join(
        f"## {title}\n\n{body}" for title, body in blocks if body and str(body).strip()
    )


# ── 兼容旧名 ──


def _extract_sections(text: str) -> Dict[str, str]:
    ch = _extract_chapters(text)
    return {
        "P0": _join(ch.get("zero", ""), ch.get("discipline", ""), ch.get("r3", "")),
        "P1": _join(ch.get("r1", ""), ch.get("r2", ""), ch.get("r5", ""), ch.get("r6", "")),
        "P2": _join(ch.get("r4", ""), ch.get("r10", "")),
        "P3": _join(ch.get("r7", ""), ch.get("r8", ""), ch.get("r9", ""), ch.get("r11", "")),
    }


def _heading_to_layer(heading: str) -> str:
    key = _chapter_key(heading)
    return {
        "zero": "P0",
        "discipline": "P0",
        "r3": "P0",
        "r1": "P1",
        "r2": "P1",
        "r5": "P1",
        "r6": "P1",
        "r4": "P2",
        "r10": "P2",
        "r7": "P3",
        "r8": "P3",
        "r9": "P3",
        "r11": "P3",
    }.get(key or "", heading)


def _p1_style_only(p1_text: str) -> str:
    style, _ = _split_r1(p1_text)
    return style


if __name__ == "__main__":
    import sys
    from pathlib import Path

    phase = sys.argv[1] if len(sys.argv) > 1 else "draft_enrich"
    if phase not in ("plan", "draft_mother", "draft_enrich", "draft"):
        print(
            "用法: python -m lib.rule_bundle "
            "[plan|draft_mother|draft_enrich|draft]"
        )
        sys.exit(1)

    recalled = {"id": "DUMP_VERIFY", "blocks": [], "母本内容": []}
    bundle = compile_rule_bundle(recalled, phase=phase)

    out_path = Path(f"/tmp/rule_bundle_{phase}.md")
    out_path.write_text(bundle, encoding="utf-8")
    print(f"文件: {_RULES}")
    print(f"阶段: {phase}")
    print(f"注入量: {len(bundle)} 字符 ≈ {len(bundle)//4} tokens")
    print(f"写入: {out_path}")
    for line in bundle.splitlines():
        if line.startswith("## "):
            print(line)
