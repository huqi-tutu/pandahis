#!/usr/bin/env python3
"""exclude 内容硬门：禁止把正文段误标为卷首标题 / 世系链等。

补 check_format 仅单向校验卷名行、以及 blocks expand 不读正文的漏洞。
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

from paragraph_utils import classify_paragraph_header, _looks_like_narrative_body

HEADER_EXCLUDES = frozenset({"卷首标题", "篇内小标题", "纯纪年"})

# 有独立事迹/生平信息的标记（非纯族谱「X 生 Y」）
NARRATIVE_ACTION_MARKERS = (
    "立",
    "即位",
    "代立",
    "为秦王",
    "为汉王",
    "为相",
    "将军",
    "崩",
    "薨",
    "伐",
    "攻",
    "破",
    "围",
    "封",
    "赐",
    "见",
    "梦",
    "生於",
    "生于",
    "名曰",
    "字",
    "年十",
    "迁",
    "杀",
    "起兵",
    "反",
    "悦而取",
    "质子",
)

# 本纪开篇定语句式（「X者，Y之子也」等）——仍属主轴叙事，非世系链
OPENING_IDENTITY_RE = re.compile(
    r"^.+者，.+?(?:之子|之孙|之苗裔|中子|长子|次子|幼子|微时)",
)

_CN_NUM = r"[一二三四五六七八九十百千零两〇\d]+"

_APPENDIX_GENEALOGY_RE = re.compile(
    rf"^.+(?:享国{_CN_NUM}年|公立|王生{_CN_NUM}年而立|生{_CN_NUM}年而立)"
)


def is_v2_track() -> bool:
    return os.environ.get("HIST_ANNOTATE_TRACK", "").strip().lower() == "v2"


def is_appendix_genealogy_table(text: str) -> bool:
    """卷末享国年表/他君谱系附录（v2 世系链 exclude 合法）。"""
    t = (text or "").strip()
    if not t:
        return False
    if _APPENDIX_GENEALOGY_RE.match(t):
        return True
    if re.search(rf"享国{_CN_NUM}年", t) and len(t) <= 128:
        return True
    if re.match(r"^.+(?:卒|崩|薨|葬).+(?:生|立)", t) and "享国" in t:
        return True
    return False


def is_v2_ancestral_genealogy(text: str) -> bool:
    """卷首远祖谱、契/秦之先/周后稷等（v2 benji_multi 世系链 exclude 合法）。"""
    t = (text or "").strip()
    if not t:
        return False
    if re.match(r"^(?:秦之先|殷契，母曰|大业取|大费生子|大廉玄孙|自太戊以下|其玄孙曰)", t):
        return True
    if re.match(r"^(?:周后稷|后稷卒|古公有长子曰|古公卒)", t):
        return True
    if any(k in t for k in ("后稷", "公刘", "古公亶父", "太伯", "虞仲", "姜原")) and len(t) <= 520:
        # 周本纪卷前远祖/古公让国，非文王开传（「是为西伯」起归文王 block）
        if "西伯曰文王" not in t and "是为西伯" not in t:
            return True
    if "玄孙曰" in t and t.count("生") >= 2 and len(t) <= 420:
        return True
    if re.match(r"^死，遂葬", t) and "生" in t:
        return True
    return False


def is_v2_multi_succession_chain(text: str) -> bool:
    """一段内多次崩立更替（外丙/中壬/立太甲等）。"""
    t = (text or "").strip()
    if not t:
        return False
    succ = len(re.findall(r"(?:崩|卒|薨)", t))
    install = len(re.findall(r"(?:立|代立|是为)", t))
    if succ >= 2 and install >= 2:
        return True
    if install >= 3 and succ >= 1:
        return True
    if re.search(r"(?:崩|卒)[，,](?:立|子|弟)", t) and install >= 2:
        return True
    return False


def is_v2_shiji_genealogy_exclude(text: str) -> bool:
    """非 Top5 君主段、远祖谱、继嗣链（本纪世系链 exclude 合法）。"""
    t = (text or "").strip()
    if not t or len(t) > 520:
        return False
    if is_v2_ancestral_genealogy(t):
        return True
    if is_v2_multi_succession_chain(t):
        return True
    if is_pure_succession_genealogy(t) or is_appendix_genealogy_table(t):
        return True
    if re.match(r"^帝.+", t):
        return True
    if re.match(r"^.+(?:崩|卒|薨)[，,](?:子|弟|立)", t):
        return True
    if re.search(r"(?:秦)?(?:仲|庄公|文公|武公|宁公|襄公|侯)", t) and len(t) <= 360:
        return True
    if re.match(r"^(?:十[三四五六七八九]?|二十)年，(?:齐|晋)", t):
        return True
    if re.search(r"(?:公|王|君).{0,4}年", t) and len(t) <= 400:
        return True
    if re.match(r"^(?:吴|齐|晋|楚)", t) and len(t) <= 220:
        return True
    if re.search(r"(?:出子|庶长|献公|孝文王|惠文|武王|张仪|犀首|樗里|甘茂|司马错)", t) and len(t) <= 420:
        return True
    if re.match(r"^立异母弟，是为昭襄王", t):
        return True
    if "武乙" in t and len(t) <= 160:
        return True
    if re.match(r"^汤崩", t):
        return True
    # 诸侯世家：非 Top5 小君纪年/更替/大事（仍属世系链 exclude，非 Top5 开传 block）
    if re.match(r"^(?:十|二十)[一二三四五六七八九]?年，", t) and len(t) <= 160:
        if not re.search(r"是为(?:桓公|景公|平公|襄公)", t):
            return True
    if re.search(r"(?:孝公|昭公|懿公|惠公|悼公|简公|康公).*(?:卒|崩|弑)", t) and re.search(
        r"是为(?:昭公|惠公|简公)", t
    ):
        return True
    if "迎公子元於卫，立之，是为惠公" in t:
        return True
    if "公逾墙" in t and "崔杼" in t and "弑之" in t:
        return True
    if "鲍子弑悼公" in t:
        return True
    if re.match(r"^田成子惮之", t):
        return True
    if re.match(r"^子我夕，田逆", t):
        return True
    if re.match(r"^夏五月壬申，成子兄弟", t):
        return True
    if re.search(r"康公卒.*吕氏遂绝", t):
        return True
    # 吴太伯世家：非 Top5 小君（季札聘国、僚/光夺位前等）→ 世系链 exclude 合法
    if "季札" in t and len(t) <= 520:
        if any(
            k in t
            for k in (
                "聘",
                "观周乐",
                "季札之初使",
                "徐君",
                "去鲁",
                "去齐",
                "適晋",
                "自卫如晋",
                "歌周南",
                "美哉",
            )
        ):
            return True
    # 季札聘国续段（段落索引拆行，段内可无「季札」二字）
    if len(t) <= 520 and any(
        k in t
        for k in (
            "见舞象箾",
            "见舞大武",
            "见舞韶护",
            "见舞大夏",
            "见舞招箾",
            "歌王",
            "歌郑",
            "歌齐",
            "歌秦",
            "歌小雅",
            "歌大雅",
            "歌颂",
            "歌邶",
        )
    ):
        return True
    if re.match(r"^(?:去齐，使於郑|適晋，说赵文子|自卫如晋)", t):
        return True
    if any(
        k in t
        for k in (
            "文子闻之，终身不听琴瑟",
            "君在殡而可以乐乎",
            "夫子获罪於君以在此",
            "辩而不德，必加於戮",
        )
    ):
        return True
    if re.search(r"王(?:诸樊|馀祭|馀眜|寿梦)", t) and len(t) <= 200:
        if "是为吴王阖庐" not in t and "王阖庐元年" not in t:
            return True
    if ("公子光" in t or "王僚" in t or "专诸" in t or "伍子胥" in t) and len(t) <= 220:
        if "是为吴王阖庐" not in t and "王阖庐元年" not in t:
            return True
    if re.match(r"^阴纳贤士", t):
        return True
    if "吴公子光曰" in t:
        return True
    return False


def is_pure_succession_genealogy(text: str) -> bool:
    """纯继嗣链「X卒/崩，子Y立」罗列（v2 世系链 exclude 合法）。"""
    t = (text or "").strip()
    if not t:
        return False
    if t.count("。") >= 2 and re.search(r"(?:卒|崩|薨)[，,](?:子|弟|立)", t):
        if t.count("立") >= 2 or t.count("崩") >= 2 or t.count("卒") >= 2:
            return True
    if re.search(r"(?:卒|崩)[，,]生", t) and t.count("立") >= 1:
        return True
    return False


def _snippet(text: str, n: int = 40) -> str:
    t = (text or "").strip()
    return t[:n] + ("…" if len(t) > n else "")


def is_opening_narrative_body(text: str) -> bool:
    """段落为可归属主轴的开篇叙事（含本纪定语起句）。"""
    t = (text or "").strip()
    if not t or len(t) < 16:
        return False
    if not _looks_like_narrative_body(t):
        return False
    if OPENING_IDENTITY_RE.match(t):
        return True
    if "。" in t and len(t) >= 24:
        return True
    return False


def is_mislabeled_genealogy_exclude(text: str) -> bool:
    """正文段不宜标世系链。

    v2：世系链 =「非 Step1a 主轴段」，**可含**远祖/小君叙事（逐段 α 的职责）。
    不再因「有叙事动词/像开篇」就否决世系链——否则等于用门禁否定 α。
    """
    t = (text or "").strip()
    if not t:
        return False
    if is_v2_track():
        # v2 默认不否决；白名单路径仅作文档/兼容，逻辑上直接放行
        return False
    if is_appendix_genealogy_table(t):
        return False
    if is_pure_succession_genealogy(t):
        return False
    if is_opening_narrative_body(t):
        return True
    if t.count("。") >= 2 and len(t) > 50:
        if any(m in t for m in NARRATIVE_ACTION_MARKERS):
            return True
    if any(m in t for m in ("生於", "生于", "代立", "即位", "立为", "名政", "名曰")):
        if "。" in t:
            return True
    return False


def validate_exclude_for_paragraph(
    paragraph_id: int,
    text: str,
    exclude_reason: str,
    *,
    work_id: str = "",
) -> List[str]:
    """单段 exclude 与正文是否匹配。"""
    errors: List[str] = []
    reason = (exclude_reason or "").strip()
    if not reason:
        return errors
    p = int(paragraph_id)
    t = (text or "").strip()
    header = classify_paragraph_header(t)

    if reason in HEADER_EXCLUDES:
        if header != reason:
            if header is None:
                errors.append(
                    f"P{p} 为正文（{_snippet(t)}），禁止 exclude={reason!r}"
                )
            else:
                errors.append(
                    f"P{p} 须为 exclude={header!r}，当前为 {reason!r}"
                )

    if reason == "世系链" and is_mislabeled_genealogy_exclude(t):
        errors.append(
            f"P{p} 为叙事正文（{_snippet(t)}），禁止 exclude=世系链"
        )

    if p == 1 and reason in ("卷首标题", "世系链"):
        if is_v2_track() and reason == "世系链":
            # v2：P1 亦可为远祖/享国链（如周后稷），由 α 判定；不因「像开篇」否决
            pass
        elif is_opening_narrative_body(t):
            hint = "（史记等拆分 txt 无卷首标题行）" if work_id == "01史记" else ""
            errors.append(
                f"P1 为正文开篇（{_snippet(t)}），禁止 exclude={reason!r}{hint}"
            )

    if reason == "太史公曰":
        if t.startswith("褚先生曰"):
            errors.append(
                f"P{p} 为褚先生曰，禁止 exclude=太史公曰（应标「其他」或归入三王叙事块）"
            )
        elif not t.startswith("太史公曰"):
            errors.append(
                f"P{p} 非「太史公曰」起笔（{_snippet(t)}），禁止 exclude=太史公曰"
            )

    if reason == "评曰" and not t.startswith("评曰"):
        errors.append(
            f"P{p} 非「评曰」起笔（{_snippet(t)}），禁止 exclude=评曰"
        )

    return errors


def _paragraphs_from_excludes(draft: dict) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for item in draft.get("excludes") or []:
        if not isinstance(item, dict):
            continue
        reason = (item.get("exclude_reason") or "").strip()
        pf = int(item.get("paragraph_from") or 0)
        pt = int(item.get("paragraph_to") or pf)
        for p in range(pf, pt + 1):
            out.append((p, reason))
    return out


def validate_blocks_excludes(
    draft: dict,
    para_text: Dict[int, str],
    *,
    work_id: str = "",
) -> Tuple[bool, str]:
    """blocks expand 前：excludes 须与段落正文一致。"""
    errors: List[str] = []
    for p, reason in _paragraphs_from_excludes(draft):
        text = para_text.get(p, "")
        errors.extend(
            validate_exclude_for_paragraph(p, text, reason, work_id=work_id)
        )

    # P1 被 exclude 且主轴 block 从 P2 起 → 典型误标（卷首太史公曰除外）
    # v2 世系链：远祖在前、主轴稍后开传（如文王自 P8）合法，不套用「必须从 P1/P2」
    p1_excluded = any(p == 1 for p, _ in _paragraphs_from_excludes(draft))
    p1_text = para_text.get(1, "")
    p1_reason = next(
        (r for p, r in _paragraphs_from_excludes(draft) if p == 1), ""
    )
    if p1_excluded and is_opening_narrative_body(p1_text):
        if p1_reason == "太史公曰" and p1_text.startswith("太史公曰"):
            pass
        elif is_v2_track() and p1_reason == "世系链":
            pass
        else:
            for blk in draft.get("blocks") or []:
                if not isinstance(blk, dict):
                    continue
                pf = int(blk.get("paragraph_from") or 0)
                if pf == 2:
                    name = (blk.get("name") or "").strip()
                    errors.append(
                        f"P1 误 exclude 导致主轴 {name!r} 从 P2 起，须从 P1 纳入"
                    )
                    break

    if errors:
        return False, "exclude 内容门未过:\n" + "\n".join(f"  - {e}" for e in errors[:15])
    return True, "exclude 内容 OK"


def validate_skeleton_excludes(
    data: dict,
    para_text: Dict[int, str],
    *,
    work_id: str = "",
) -> Tuple[bool, str]:
    """skeleton verify：segment_attribution excludes 与正文一致。"""
    errors: List[str] = []
    for row in data.get("segment_attribution") or []:
        reason = (row.get("exclude_reason") or "").strip()
        if not reason:
            continue
        p = int(row.get("paragraph") or 0)
        if p <= 0:
            continue
        text = para_text.get(p, "")
        errors.extend(
            validate_exclude_for_paragraph(p, text, reason, work_id=work_id)
        )

    if errors:
        return False, "exclude 内容门未过:\n" + "\n".join(f"  - {e}" for e in errors[:15])
    return True, "exclude 内容 OK"
