#!/usr/bin/env python3
"""《史记》无君王卷 Step4 兜底：传主坐标自动补全；年份仅 LLM 未填时脚本兜底。

坐标（四级帝王）优先级：
1. PERSON_PATCH 精确人名
2. PERSON_PATCH 卷名（如「魏其武安侯列传」→ 合传缺人时用卷级 patron）
3. 同卷已补全条目的多数 patron（多遍兜底）
4. _auto_filled._主轴参考 中的帝王猜测（非 regime_default）
5. infer_spindle_emperor 原文推断（拒绝五帝 regime_default）

年份与卷内是否有君王无关；生卒优先 PERSON_PATCH / 学界表，再 person_year_fallback（不覆盖 _年LLM依据）。
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from coordinate_index import build_regime_index, coords_and_ids_from_emperor
from emperor_resolve import build_emperor_info_index, infer_spindle_emperor
from lib_config import (
    PERSON_SPINDLE_RATIONALE_MIN_LEN,
    detect_cross_regime_person,
    person_spindle_rationale,
    validate_year_quality,
)
from person_year_fallback import (
    entry_has_complete_years,
    entry_has_llm_year_basis,
    apply_person_year_fallback,
    normalize_partial_person_years,
)

# regime_default 常误落五帝，须拒绝
REJECT_DEFAULT_EMPERORS = frozenset(
    {"黄帝", "颛顼", "帝喾", "尧", "舜", "禹", "启"}
)

from category_v3 import SPINDLE_CATEGORIES, OFFICIAL_CATEGORIES

SPINDLE_FALLBACK_CATS = SPINDLE_CATEGORIES - {"君王", "宗戚", "蕃祚"}

# 士臣/庶众：patron=四级帝王锚点（坐标用）；生卒年由 LLM 填写，patch 内 start/end 已弃用
PERSON_PATCH: Dict[str, dict] = {
    # ── 西汉世家（士臣）──
    "萧何": {"patron": "汉高祖", "start": -210, "end": -193},
    "曹参": {"patron": "汉高祖", "start": -210, "end": -190},
    "张良": {"patron": "汉高祖", "start": -250, "end": -186},
    "陈平": {"patron": "汉高祖", "start": -250, "end": -178},
    "周勃": {"patron": "汉高祖", "start": -242, "end": -169},
    "樊哙": {"patron": "汉高祖", "start": -242, "end": -189},
    "夏侯婴": {"patron": "汉高祖", "start": -246, "end": -165},
    "滕公": {"patron": "汉高祖", "start": -246, "end": -165},
    "灌婴": {"patron": "汉高祖", "start": -231, "end": -176},
    "郦商": {"patron": "汉高祖", "start": -268, "end": -180},
    "陈涉": {"patron": "秦二世", "start": -209, "end": -196},
    "孔子": {"patron": "鲁定公", "start": -551, "end": -479},
    "颜回": {"patron": "鲁定公", "start": -521, "end": -481},
    "子贡": {"patron": "鲁定公", "start": -520, "end": -456},
    "子路": {"patron": "鲁定公", "start": -542, "end": -480},
    "子夏": {"patron": "魏文侯", "start": -507, "end": -420},
    # ── 列传 061–063 ──
    "伯夷": {"patron": "周武王", "start": -1046, "end": -1046},
    "管仲": {"patron": "齐桓公", "start": -685, "end": -643},
    "晏婴": {"patron": "齐景公", "start": -581, "end": -500},
    "老子": {"patron": "周敬王", "start": -570, "end": -480},
    "韩非": {"patron": "秦始皇", "start": -280, "end": -233},
    # ── 列传 064–090 ──
    "司马穰苴": {"patron": "齐景公", "start": -556, "end": -490},
    "孙武": {"patron": "吴王阖闾", "start": -512, "end": -496},
    "孙子": {"patron": "吴王阖闾", "start": -512, "end": -496},
    "吴起": {"patron": "魏武侯", "start": -440, "end": -381},
    "伍子胥": {"patron": "吴王阖闾", "start": -559, "end": -484},
    "商鞅": {"patron": "秦孝公", "start": -390, "end": -338},
    "苏秦": {"patron": "燕昭王", "start": -340, "end": -284},
    "张仪": {"patron": "秦惠文王", "start": -339, "end": -309},
    "樗里子": {"patron": "秦惠文王", "start": -337, "end": -307},
    "甘茂": {"patron": "秦昭襄王", "start": -306, "end": -284},
    "穰侯": {"patron": "秦昭襄王", "start": -306, "end": -251},
    "魏冉": {"patron": "秦昭襄王", "start": -306, "end": -251},
    "白起": {"patron": "秦昭襄王", "start": -329, "end": -257},
    "王翦": {"patron": "秦始皇", "start": -230, "end": -214},
    "孟子": {"patron": "梁惠王", "start": -372, "end": -289},
    "荀卿": {"patron": "赵孝成王", "start": -313, "end": -238},
    "孟尝君": {"patron": "齐湣王", "start": -323, "end": -279},
    "平原君": {"patron": "赵孝成王", "start": -307, "end": -251},
    "虞卿": {"patron": "赵孝成王", "start": -265, "end": -245},
    "信陵君": {"patron": "魏安釐王", "start": -276, "end": -243},
    "魏公子": {"patron": "魏安釐王", "start": -276, "end": -243},
    "春申君": {"patron": "楚考烈王", "start": -262, "end": -238},
    "范睢": {"patron": "秦昭襄王", "start": -306, "end": -251},
    "蔡泽": {"patron": "秦昭襄王", "start": -306, "end": -251},
    "乐毅": {"patron": "燕昭王", "start": -311, "end": -279},
    "廉颇": {"patron": "赵惠文王", "start": -298, "end": -266},
    "蔺相如": {"patron": "赵惠文王", "start": -298, "end": -266},
    "田单": {"patron": "齐襄王", "start": -283, "end": -265},
    "屈原": {"patron": "楚怀王", "start": -340, "end": -278},
    "贾谊": {"patron": "汉文帝", "start": -200, "end": -169},
    "吕不韦": {"patron": "秦始皇", "start": -250, "end": -235},
    "荆轲": {"patron": "燕王喜", "start": -240, "end": -227},
    "李斯": {"patron": "秦始皇", "start": -246, "end": -208},
    "蒙恬": {"patron": "秦始皇", "start": -246, "end": -210},
    "张耳": {"patron": "汉高祖", "start": -209, "end": -202},
    "陈馀": {"patron": "汉高祖", "start": -209, "end": -204},
    "魏豹": {"patron": "汉高祖", "start": -205, "end": -204},
    "彭越": {"patron": "汉高祖", "start": -205, "end": -196},
    "黥布": {"patron": "汉高祖", "start": -204, "end": -195},
    "韩信": {"patron": "汉高祖", "start": -231, "end": -196},
    "韩王信": {"patron": "汉高祖", "start": -206, "end": -196},
    "卢绾": {"patron": "汉高祖", "start": -206, "end": -194},
    "田儋": {"patron": "秦二世", "start": -230, "end": -208},
    "田荣": {"patron": "项羽", "start": -210, "end": -205},
    "田横": {"patron": "汉高祖", "start": -220, "end": -202},
    # ── 列传 091–130 常见传主 ──
    "郦食其": {"patron": "汉高祖", "start": -209, "end": -203},
    "陆贾": {"patron": "汉高祖", "start": -209, "end": -170},
    "叔孙通": {"patron": "汉高祖", "start": -209, "end": -194},
    "刘敬": {"patron": "汉高祖", "start": -209, "end": -194},
    "季布": {"patron": "汉高祖", "start": -209, "end": -166},
    "栾布": {"patron": "汉高祖", "start": -209, "end": -166},
    "袁盎": {"patron": "汉文帝", "start": -180, "end": -143},
    "晁错": {"patron": "汉景帝", "start": -200, "end": -154},
    "张释之": {"patron": "汉文帝", "start": -180, "end": -143},
    "冯唐": {"patron": "汉武帝", "start": -180, "end": -120},
    "刘濞": {"patron": "汉景帝", "start": -216, "end": -154},
    "窦婴": {"patron": "汉武帝", "start": -180, "end": -131},
    "灌夫": {"patron": "汉武帝", "start": -200, "end": -132},
    "田蚡": {"patron": "汉武帝", "start": -180, "end": -131},
    "韩安国": {"patron": "汉武帝", "start": -180, "end": -131},
    "李广": {"patron": "汉武帝", "start": -184, "end": -119},
    "卫青": {"patron": "汉武帝", "start": -180, "end": -106},
    "霍去病": {"patron": "汉武帝", "start": -140, "end": -117},
    "公孙弘": {"patron": "汉武帝", "start": -180, "end": -121},
    "主父偃": {"patron": "汉武帝", "start": -180, "end": -126},
    "司马相如": {"patron": "汉武帝", "start": -179, "end": -117},
    "刘安": {"patron": "汉武帝", "start": -179, "end": -122},
    "刘长": {"patron": "汉文帝", "start": -198, "end": -174},
    "汲黯": {"patron": "汉武帝", "start": -180, "end": -112},
    "郑当时": {"patron": "汉武帝", "start": -180, "end": -120},
    "邓通": {"patron": "汉文帝", "start": -180, "end": -118},
    "朱家": {"patron": "汉高祖", "start": -209, "end": -180},
    "郭解": {"patron": "汉武帝", "start": -180, "end": -127},
    "优孟": {"patron": "楚庄王", "start": -613, "end": -591},
    "优旃": {"patron": "秦始皇", "start": -246, "end": -210},
    "淳于髡": {"patron": "齐威王", "start": -378, "end": -320},
    "优伶": {"patron": "汉武帝", "start": -140, "end": -87},
    "司马迁": {"patron": "汉武帝", "start": -145, "end": -87},
    # 全名 / 异名别名
    "平原君赵胜": {"patron": "赵孝成王", "start": -307, "end": -251},
    "信陵君魏无忌": {"patron": "魏安釐王", "start": -276, "end": -243},
    "春申君黄歇": {"patron": "楚考烈王", "start": -262, "end": -238},
    "穰侯魏冉": {"patron": "秦昭襄王", "start": -306, "end": -251},
    "鲁仲连": {"patron": "齐湣王", "start": -287, "end": -265},
    "邹阳": {"patron": "梁孝王", "start": -178, "end": -154},
}

from shiji_person_patch_077_130 import (  # noqa: E402
    PERSON_PATCH_077_130,
    SPINDLE_RATIONALES_077_130,
)

PERSON_PATCH = {**PERSON_PATCH, **PERSON_PATCH_077_130}

# 跨时期人物：史略ID → 主轴说明（合传/跨度≥30年）
SPINDLE_RATIONALES: Dict[str, str] = {
    **SPINDLE_RATIONALES_077_130,
    "SHIJI_094_01": "本卷以田儋狄人起兵自立齐王、救魏战死临济为主线，主轴挂秦二世；田荣、田横见共段事略。",
    "SHIJI_094_02": "本卷以田横守齐、亡走海岛至高祖召见自刭为主线，主轴挂汉高祖；田儋、田荣见共段事略。",
    "SHIJI_094_03": "本卷以田荣拒助项梁、自立齐王与项羽争齐为主线，主轴挂项羽；田儋段见共段事略。",
    "SHIJI_090_01": "本卷以彭越从汉击楚、梁地游击为主线，主轴挂汉高祖；早年聚盗见共段事略。",
    "SHIJI_090_02": "本卷以魏豹降汉复叛、河东据守为主线，主轴挂汉高祖；陈涉起事封王见共段事略。",
    "SHIJI_091_01": "本卷以汉高祖朝破楚、封淮南王至叛诛为主线，主轴挂汉高祖；早年从项梁、项羽见共段事略。",
    "SHIJI_092_01": "本卷以汉高祖朝拜将、定三秦、破赵燕齐楚为主线，主轴挂汉高祖；早年从项梁、项羽及封齐异姓王见共段事略。",
    "SHIJI_093_01": "本卷以卢绾从高祖定天下、封燕王至叛逃为主线，主轴挂汉高祖；韩王信传见共段事略。",
    "SHIJI_093_02": "本卷以韩王信封韩王、徙太原守边至叛入匈奴为主线，主轴挂汉高祖；卢绾传见共段事略。",
    "SHIJI_095_01": "本卷以樊哙从高祖征战、鸿门护主至封侯为主线，主轴挂汉高祖；郦商、滕公、灌婴见共段事略。",
    "SHIJI_095_02": "本卷以夏侯婴（滕公）御车从高祖定天下为主线，主轴挂汉高祖；樊哙、郦商、灌婴见共段事略。",
    "SHIJI_095_03": "本卷以灌婴从汉击楚、封侯及景帝朝事为主线，主轴挂汉高祖；樊哙、郦商、滕公见共段事略。",
    "SHIJI_095_04": "本卷以郦商从高祖定天下、封曲周侯为主线，主轴挂汉高祖；樊哙、滕公、灌婴见共段事略。",
    "SHIJI_096_01": "本卷以任敖沛县旧吏从高祖封广阿侯为主线，主轴挂汉高祖；张苍、周昌、申屠嘉见共段事略。",
    "SHIJI_096_02": "本卷以匡衡由博士至丞相封乐安侯为主线，主轴挂汉元帝；韦玄成等宣元诸相见共段事略。",
    "SHIJI_096_03": "本卷以周昌护太子、相赵王至吕后时卒为主线，主轴挂汉高祖；赵尧、任敖见共段事略。",
    "SHIJI_096_04": "本卷以张苍从高祖至文帝朝为丞相、定律历为主线，主轴挂汉高祖；周昌、任敖、申屠嘉见共段事略。",
    "SHIJI_096_05": "本卷以申屠嘉文帝景帝时为丞相、刚直守节为主线，主轴挂汉文帝；张苍、晁错事见共段事略。",
    "SHIJI_096_06": "本卷以邴吉宣帝时为丞相、明于政事为主线，主轴挂汉宣帝；魏相、黄霸见共段事略。",
    "SHIJI_096_07": "本卷以韦玄成继父为丞相、容容随俗为主线，主轴挂汉宣帝；韦贤、匡衡见共段事略。",
    "SHIJI_096_08": "本卷以韦贤由大鸿胪至丞相、子玄成让国为主线，主轴挂汉宣帝；魏相、邴吉见共段事略。",
    "SHIJI_096_09": "本卷以魏相宣帝时为丞相、好武执法为主线，主轴挂汉宣帝；邴吉、黄霸见共段事略。",
    "SHIJI_096_10": "本卷以黄霸颍川治绩至宣帝朝为丞相为主线，主轴挂汉宣帝；邴吉、韦玄成见共段事略。",
    "SHIJI_097_01": "本卷以郦食其说沛公、说齐至亨死为主线，主轴挂汉高祖；陈留说降见补叙段。",
    "SHIJI_097_02": "本卷以陆贾说南越、著新语及诛吕有功为主线，主轴挂汉高祖；平原君朱建见共段事略。",
    "SHIJI_098_01": "本卷以傅宽从高祖定天下封阳陵侯为主线，主轴挂汉高祖；靳歙、蒯成见共段事略。",
    "SHIJI_098_02": "本卷以蒯成侯周緤参乘从高祖至文帝朝为主线，主轴挂汉高祖；傅宽、靳歙见共段事略。",
    "SHIJI_098_03": "本卷以靳歙从高祖征战封信武侯为主线，主轴挂汉高祖；傅宽、蒯成见共段事略。",
    "SHIJI_105_01": "本卷以淳于意（仓公）行医、缇萦救父及医案记录为主线，主轴挂汉文帝；扁鹊传见前段。",
    "SHIJI_105_02": "本卷以扁鹊行医传说及遇刺为主线，主轴挂周平王（年代兜底）；仓公见共段事略。",
    "SHIJI_107_01": "本卷以灌夫刚直任侠、与魏其侯交好至骂座被斩为主线，主轴挂汉武帝；窦婴、田蚡见共段事略。",
    "SHIJI_107_02": "本卷以田蚡武帝时为丞相、与魏其灌夫争锋为主线，主轴挂汉武帝；窦婴、灌夫见共段事略。",
    "SHIJI_107_03": "本卷以窦婴景帝封魏其侯、武帝朝与田蚡灌夫廷辩为主线，主轴挂汉武帝；灌夫、田蚡见共段事略。",
}

_SPINDLE_HINT_RE = re.compile(r"「([^」]+)」")
_METHOD_HINT_RE = re.compile(r"（([^）]+)）")


def _parse_spindle_hint(entry: dict) -> Tuple[Optional[str], Optional[str]]:
    ref = (entry.get("_auto_filled") or {}).get("_主轴参考", "")
    if not ref:
        return None, None
    m = _SPINDLE_HINT_RE.search(ref)
    if not m:
        return None, None
    method = None
    mm = _METHOD_HINT_RE.search(ref)
    if mm:
        method = mm.group(1)
    return m.group(1).strip(), method


def _lookup_patch_or_scholarly_years(
    entry: dict,
    data: Optional[dict] = None,
) -> Optional[Tuple[int, int, str]]:
    """PERSON_PATCH / 学界表 / 蕃祚政权兴亡 / 卷名PATCH → (开始, 结束, 依据)。"""
    if entry_has_llm_year_basis(entry):
        return None
    name = (entry.get("史略名称") or "").strip()
    vol_name = (data.get("volume") or "").strip() if data else ""
    try:
        from collective_volume_subjects import collective_year_span, is_collective_subject

        if is_collective_subject(name, vol_name):
            span = collective_year_span(name)
            if span is not None:
                return span
    except ImportError:
        pass
    patch = lookup_person_patch(name)
    if patch and patch.get("start") is not None and patch.get("end") is not None:
        s, e = int(patch["start"]), int(patch["end"])
        note = f"{name}生卒学界主流约前{abs(s)}–前{abs(e)}"
        if s > 0 or e > 0:
            note = f"{name}生卒据PERSON_PATCH {s}～{e}"
        return s, e, note
    try:
        from shiji_scholarly_lifespans import lookup_scholarly_lifespan

        span = lookup_scholarly_lifespan(entry)
        if span is not None:
            return span
    except ImportError:
        pass
    if data is not None:
        return _lookup_volume_patch_years(entry, data)
    return None


def _lookup_volume_patch_years(
    entry: dict, data: dict
) -> Optional[Tuple[int, int, str]]:
    """人名/学界均无年时，用卷名 PATCH 活跃期（合传漏人时的最后脚本兜底）。"""
    vol_patch = lookup_volume_patch(data)
    if not vol_patch:
        return None
    if vol_patch.get("start") is None or vol_patch.get("end") is None:
        return None
    name = (entry.get("史略名称") or "").strip()
    vol_name = (data.get("volume") or "").strip()
    s, e = int(vol_patch["start"]), int(vol_patch["end"])
    note = f"{name}活跃期取本卷{vol_name}PATCH约前{abs(s)}–前{abs(e)}"
    if s > 0 or e > 0:
        note = f"{name}活跃期取本卷PATCH {s}～{e}"
    return s, e, note


def _write_person_years_with_basis(
    entry: dict, start: int, end: int, note: str, *, data: Optional[dict] = None
) -> None:
    entry["史略开始年"] = int(start)
    entry["史略结束年"] = int(end)
    af = dict(entry.get("_auto_filled") or {})
    af["_年LLM依据"] = note
    name = (entry.get("史略名称") or "").strip()
    vol_name = (data.get("volume") or "").strip() if data else ""
    try:
        from collective_volume_subjects import (
            collective_provenance_fields,
            is_collective_subject,
        )

        if is_collective_subject(name, vol_name):
            af.update(collective_provenance_fields(name))
        else:
            cat = (entry.get("史略分类") or "").strip()
            if not af.get("年规则"):
                from lib_config import year_range_label  # noqa: WPS433

                af["年规则"] = year_range_label(cat)
            if not af.get("年规则备注") and cat in SPINDLE_FALLBACK_CATS | {"宗戚"}:
                from person_year_fallback import person_year_fallback_note  # noqa: WPS433

                af["年规则备注"] = person_year_fallback_note()
    except ImportError:
        cat = (entry.get("史略分类") or "").strip()
        if not af.get("年规则"):
            from lib_config import year_range_label  # noqa: WPS433

            af["年规则"] = year_range_label(cat)
        if not af.get("年规则备注") and cat in SPINDLE_FALLBACK_CATS | {"宗戚"}:
            from person_year_fallback import person_year_fallback_note  # noqa: WPS433

            af["年规则备注"] = person_year_fallback_note()
    for k in ("_年兜底级别", "_年兜底依据", "_死亡年锚定", "_年待LLM"):
        af.pop(k, None)
    entry["_auto_filled"] = af
    needs = [n for n in (entry.get("_needs_llm") or []) if n not in (
        "史略开始年", "史略结束年",
    )]
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)


def apply_person_years_from_tables(data: dict) -> int:
    """为缺 _年LLM依据 的人物写入 PERSON_PATCH / 学界表生卒。返回写入条数。"""
    n = 0
    for entry in data.get("entries") or []:
        cat = (entry.get("史略分类") or "").strip()
        if cat not in SPINDLE_FALLBACK_CATS and cat != "宗戚":
            continue
        span = _lookup_patch_or_scholarly_years(entry, data)
        if span is None:
            continue
        s, e, note = span
        cur_s, cur_e = entry.get("史略开始年"), entry.get("史略结束年")
        if cur_s == s and cur_e == e and entry_has_llm_year_basis(entry):
            continue
        _write_person_years_with_basis(entry, s, e, note, data=data)
        n += 1
    return n


def _infer_active_years(
    entry: dict,
    emperor_info: dict,
    data: Optional[dict] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """人物年份脚本兜底：PERSON_PATCH / 学界表优先，再 person_year_fallback。"""
    if entry_has_llm_year_basis(entry):
        return None, None
    span = _lookup_patch_or_scholarly_years(entry, data)
    if span is not None:
        return span[0], span[1]
    ys, ye, _, _ = apply_person_year_fallback(entry, emperor_info=emperor_info)
    return ys, ye


def _volume_noun(volume_name: str) -> str:
    if "列传" in volume_name:
        return "列传"
    if "世家" in volume_name:
        return "世家"
    return "叙事"


def _fine_coord(entry: dict, vol: str, cat: str) -> str:
    """五级细坐标须与当前史略分类一致；分类变更后重算。"""
    existing = (entry.get("五级细坐标") or "").strip()
    eid = (entry.get("史略ID") or "").strip()
    suffix = eid.rsplit("_", 1)[-1] if "_" in eid else "01"
    expected = f"史记·卷{vol.zfill(3)}·{cat}·{suffix}"
    if existing:
        parts = existing.split("·")
        if len(parts) >= 4 and parts[2] == cat and parts[3] == suffix:
            return existing
    return expected


def lookup_person_patch(name: str) -> Optional[dict]:
    """精确名或前缀匹配（如 平原君 → 平原君赵胜）。"""
    name = (name or "").strip()
    if not name:
        return None
    if name in PERSON_PATCH:
        return PERSON_PATCH[name]
    best_key = ""
    for key in PERSON_PATCH:
        if name.startswith(key) and len(key) > len(best_key):
            best_key = key
    if best_key:
        return PERSON_PATCH[best_key]
    for key in PERSON_PATCH:
        if key.startswith(name) and len(name) >= 2:
            return PERSON_PATCH[key]
    return None


def lookup_volume_patch(data: dict) -> Optional[dict]:
    """卷名级 PATCH（合传未逐人录入时，用「××列传」兜底 patron/年）。"""
    vol_name = (data.get("volume") or "").strip()
    if not vol_name:
        return None
    patch = lookup_person_patch(vol_name)
    if patch:
        return patch
    if not vol_name.endswith("列传"):
        return lookup_person_patch(f"{vol_name}列传")
    return None


def _infer_patron_from_volume_siblings(
    entry: dict,
    data: dict,
    emperor_index: Dict[str, dict],
) -> Optional[str]:
    """同卷其他已补全士臣/庶众的多数四级帝王（多遍兜底第二趟可用）。"""
    patrons: List[str] = []
    for peer in data.get("entries") or []:
        if peer is entry:
            continue
        cat = (peer.get("史略分类") or "").strip()
        if cat not in SPINDLE_FALLBACK_CATS:
            continue
        p = (peer.get("四级帝王坐标") or "").strip()
        if p and p in emperor_index:
            patrons.append(p)
    if not patrons:
        return None
    return Counter(patrons).most_common(1)[0][0]


def resolve_person_fallback(
    entry: dict,
    data: dict,
    emperor_index: Dict[str, dict],
    *,
    work_id: str = "01史记",
) -> Optional[dict]:
    """为单条士臣/庶众推断 Step4 兜底包；无法推断时返回 None。"""
    cat = (entry.get("史略分类") or "").strip()
    if cat not in SPINDLE_FALLBACK_CATS:
        return None

    name = (entry.get("史略名称") or "").strip()
    patch = lookup_person_patch(name)
    patron: Optional[str] = None
    method = "person_patch"

    if patch:
        patron = patch["patron"]
    else:
        vol_patch = lookup_volume_patch(data)
        if vol_patch and vol_patch.get("patron"):
            patron = vol_patch["patron"]
            method = "volume_patch"

    if not patron:
        sibling = _infer_patron_from_volume_siblings(entry, data, emperor_index)
        if sibling:
            patron = sibling
            method = "volume_sibling"

    if not patron:
        hint_name, hint_method = _parse_spindle_hint(entry)
        if (
            hint_name
            and hint_method != "regime_default"
            and hint_name in emperor_index
            and hint_name not in REJECT_DEFAULT_EMPERORS
        ):
            patron = hint_name
            method = f"spindle_hint:{hint_method}"

    if not patron:
        info, inf_method = infer_spindle_emperor(
            entry, data, emperor_index, work_id=work_id
        )
        if info:
            em = (info.get("emperor") or "").strip()
            if inf_method == "regime_default" and em in REJECT_DEFAULT_EMPERORS:
                em = ""
            elif inf_method == "regime_default":
                em = ""
            if em and em in emperor_index:
                patron = em
                method = inf_method

    if not patron or patron not in emperor_index:
        return None

    emperor_info = emperor_index[patron]
    span = _lookup_patch_or_scholarly_years(entry, data)
    if span is not None:
        start, end = span[0], span[1]
    elif entry_has_complete_years(entry) or entry_has_llm_year_basis(entry):
        start, end = entry.get("史略开始年"), entry.get("史略结束年")
    else:
        start, end = _infer_active_years(entry, emperor_info, data)

    if start is None or end is None:
        ys, ye, _, _ = apply_person_year_fallback(entry, emperor_info=emperor_info)
        if start is None:
            start = ys
        if end is None:
            end = ye
    if start is None or end is None:
        return None

    regime_index = build_regime_index()
    coords = coords_and_ids_from_emperor(emperor_info, regime_index)
    return {
        "patron": patron,
        "start": start,
        "end": end,
        "coords": coords,
        "method": method,
    }


def _spindle_rationale_text(entry: dict, patron: str) -> str:
    eid = (entry.get("史略ID") or "").strip()
    if eid in SPINDLE_RATIONALES:
        return SPINDLE_RATIONALES[eid]
    name = (entry.get("史略名称") or "").strip()
    return f"本卷以{name}主要功业/仕宦事{patron}为最著，四级帝王取{patron}；他朝/他帝段落见共段事略。"


def ensure_spindle_rationale(entry: dict, data: dict) -> bool:
    """跨时期人物补 _坐标主轴说明；已满足则清 _needs_llm。"""
    entries = data.get("entries") or []
    reason = detect_cross_regime_person(entry, entries)
    if not reason:
        return False
    if len(person_spindle_rationale(entry)) >= PERSON_SPINDLE_RATIONALE_MIN_LEN:
        needs = [n for n in (entry.get("_needs_llm") or []) if n != "_坐标主轴说明"]
        entry["_needs_llm"] = needs
        return True
    patron = (entry.get("四级帝王坐标") or "").strip()
    if not patron:
        return False
    af = dict(entry.get("_auto_filled") or {})
    af["_坐标主轴说明"] = _spindle_rationale_text(entry, patron)
    af.pop("_坐标主轴待说明", None)
    entry["_auto_filled"] = af
    needs = [n for n in (entry.get("_needs_llm") or []) if n != "_坐标主轴说明"]
    entry["_needs_llm"] = needs
    return True


def apply_entry_step4_fallback(
    entry: dict,
    data: dict,
    vol: str,
    fallback: dict,
) -> None:
    """将兜底包写入单条条目（不 finalize）。"""
    vol_name = (data.get("volume") or "").strip()
    name = (entry.get("史略名称") or "").strip()
    cat = (entry.get("史略分类") or "").strip()
    paras = entry.get("paragraphs") or []
    if not paras:
        return
    pf = paras[0]["paragraph_from"]
    pt = paras[-1]["paragraph_to"]
    n = pt - pf + 1

    entry.update(fallback["coords"])
    span = _lookup_patch_or_scholarly_years(entry, data)
    if span is not None:
        _write_person_years_with_basis(entry, span[0], span[1], span[2], data=data)
    elif not entry_has_complete_years(entry):
        ys, ye = fallback.get("start"), fallback.get("end")
        if ys is not None and ye is not None:
            entry["史略开始年"] = ys
            entry["史略结束年"] = ye
    entry["五级细坐标"] = _fine_coord(entry, vol, cat)
    entry["六级段落锚点"] = f"[P{pf}-P{pt}]"
    entry["原文出处"] = f"{vol_name}·P{pf}-P{pt}"

    af = dict(entry.get("_auto_filled") or {})
    try:
        from collective_volume_subjects import (
            collective_provenance_fields,
            is_collective_subject,
        )

        if is_collective_subject(name, vol_name):
            af.update(collective_provenance_fields(name))
        elif len((af.get("_坐标主轴说明") or "").strip()) < PERSON_SPINDLE_RATIONALE_MIN_LEN:
            af["_坐标主轴说明"] = _spindle_rationale_text(entry, fallback["patron"])
    except ImportError:
        if len((af.get("_坐标主轴说明") or "").strip()) < PERSON_SPINDLE_RATIONALE_MIN_LEN:
            af["_坐标主轴说明"] = _spindle_rationale_text(entry, fallback["patron"])
    af.pop("_坐标主轴待说明", None)
    entry["_auto_filled"] = af
    ensure_spindle_rationale(entry, data)
    needs = [n for n in (entry.get("_needs_llm") or []) if n not in (
        "史略开始年", "史略结束年",
    )] if entry_has_complete_years(entry) else list(entry.get("_needs_llm") or [])
    if not entry_has_complete_years(entry):
        for f in ("史略开始年", "史略结束年"):
            if f not in needs:
                needs.append(f)
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)


def prepare_year_quality_repatch(data: dict) -> int:
    """年份质检失败：清空错误年 → 优先 PERSON_PATCH/学界表自动回填，其余交 LLM。"""
    issues = validate_year_quality(data.get("entries") or [])
    if not issues:
        return 0
    flagged = 0
    for entry in data.get("entries") or []:
        eid = (entry.get("史略ID") or "").strip()
        name = (entry.get("史略名称") or "").strip()
        if not any(eid in msg or name in msg for msg in issues):
            continue
        entry.pop("史略开始年", None)
        entry.pop("史略结束年", None)
        af = dict(entry.get("_auto_filled") or {})
        af.pop("_年LLM依据", None)
        entry["_auto_filled"] = af
        span = _lookup_patch_or_scholarly_years(entry, data)
        if span is not None:
            _write_person_years_with_basis(entry, span[0], span[1], span[2], data=data)
            continue
        needs = list(entry.get("_needs_llm") or [])
        for f in ("史略开始年", "史略结束年"):
            if f not in needs:
                needs.append(f)
        entry["_needs_llm"] = needs
        flagged += 1
    return flagged


def apply_volume_step4_fallback(
    data: dict,
    vol: str,
    *,
    work_id: str = "01史记",
) -> Tuple[int, List[str]]:
    """
    对本卷所有待补士臣/庶众尝试兜底。
    返回 (成功条数, 日志行列表)。
    """
    yr_prefill = apply_person_years_from_tables(data)
    emperor_index = build_emperor_info_index()
    ok_count = 0
    logs: List[str] = []
    if yr_prefill:
        logs.append(f"学界/PATCH 生卒预填 {yr_prefill} 条")
    entries = data.get("entries") or []
    for pass_no in range(3):
        pass_ok = 0
        for entry in entries:
            cat = (entry.get("史略分类") or "").strip()
            if cat not in SPINDLE_FALLBACK_CATS:
                continue
            name = (entry.get("史略名称") or "").strip()
            missing = not (entry.get("四级帝王坐标") or "").strip()
            cross = detect_cross_regime_person(entry, entries)
            needs_rationale = (
                bool(cross)
                and len(person_spindle_rationale(entry))
                < PERSON_SPINDLE_RATIONALE_MIN_LEN
            )

            if missing:
                fb = resolve_person_fallback(
                    entry, data, emperor_index, work_id=work_id
                )
                if not fb:
                    if pass_no == 2:
                        logs.append(f"SKIP {name}({cat})")
                    continue
                apply_entry_step4_fallback(entry, data, vol, fb)
                pass_ok += 1
                ok_count += 1
                logs.append(f"OK {name} → {fb['patron']} ({fb['method']})")
            elif needs_rationale:
                if ensure_spindle_rationale(entry, data):
                    pass_ok += 1
                    ok_count += 1
                    logs.append(f"OK {name} 主轴说明")
                elif pass_no == 2:
                    logs.append(f"SKIP {name} 主轴说明")
        if pass_ok == 0:
            break
    return ok_count, logs
