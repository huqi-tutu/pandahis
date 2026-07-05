#!/usr/bin/env python3
"""族史/国别史/四夷列传：卷名即集体主轴（蕃祚），年区间为政权立国至灭亡，非个人生卒。"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# 史略名称 → 固定考订字段
COLLECTIVE_SUBJECTS: Dict[str, dict] = {
    "匈奴": {
        "start": -209,
        "end": -48,
        "_年LLM依据": (
            "匈奴单于国立国约前209（冒顿统一草原），"
            "政权丧失独立地位/实质分裂约前48（五单于分立），非个人生卒"
        ),
        "_坐标主轴说明": (
            "本卷自族源至汉匈百年关系通述，从汉侧视角主轴挂汉武帝；"
            "高祖平城等见共段事略"
        ),
        "protagonist_rationale": (
            "《匈奴列传》为部族/政权族史合传，主轴是匈奴集体，"
            "分类蕃祚；年轴为政权立国至灭亡，非君王个人生卒。"
        ),
    },
    "南越": {
        "start": -203,
        "end": -111,
        "_年LLM依据": (
            "南越国立国约前203（赵佗称王），汉灭南越国前111，非个人生卒"
        ),
        "_坐标主轴说明": (
            "本卷述南越国赵氏五世及与汉关系，从汉侧视角主轴挂汉武帝；"
            "赵佗自立于秦末见共段事略"
        ),
        "protagonist_rationale": (
            "《南越列传》为国别史合传，主轴是南越政权集体，"
            "赵佗等为叙事中君主但不在帝王.json，故分类蕃祚；年轴为政权立国至灭亡。"
        ),
    },
    "东越": {
        "start": -202,
        "end": -111,
        "_年LLM依据": (
            "东越/闽越政权立国约前202（汉封闽越王），汉平东越前111，非个人生卒"
        ),
        "_坐标主轴说明": (
            "本卷述闽越、东越与汉关系，从汉侧视角主轴挂汉武帝；"
            "汉初闽越围东瓯等见共段事略"
        ),
        "protagonist_rationale": (
            "《东越列传》为越系政权合传，主轴是东越/闽越集体，"
            "非帝王.json 内单君王，故分类蕃祚；年轴为政权立国至灭亡。"
        ),
    },
    "朝鲜": {
        "start": -194,
        "end": -108,
        "_年LLM依据": (
            "卫氏朝鲜立国约前194（卫满入朝），汉灭朝鲜前108，非个人生卒"
        ),
        "_坐标主轴说明": (
            "本卷述卫氏朝鲜及与汉关系，从汉侧视角主轴挂汉武帝；"
            "卫满入朝鲜见共段事略"
        ),
        "protagonist_rationale": (
            "《朝鲜列传》为国别史合传，主轴是朝鲜政权集体，"
            "非帝王.json 内单君王，故分类蕃祚；年轴为政权立国至灭亡。"
        ),
    },
    "西南夷": {
        "start": -279,
        "end": -111,
        "_年LLM依据": (
            "西南夷诸国/部族政权格局约前279（庄蹻王滇）至前111（武帝置郡平定），"
            "合传取区域政权存续期，非个人生卒"
        ),
        "_坐标主轴说明": (
            "本卷述西南诸夷与汉关系，从汉侧视角主轴挂汉武帝；"
            "庄蹻王滇等先楚事见共段事略"
        ),
        "protagonist_rationale": (
            "《西南夷列传》为诸夷合传，主轴是西南夷族群/诸国集体，"
            "分类蕃祚；年轴为政权立国至灭亡（合传可按政权拆条）。"
        ),
    },
    "大宛": {
        "start": -130,
        "end": -101,
        "_年LLM依据": (
            "大宛王国存续约前130至前101（汉伐宛杀王），非个人生卒"
        ),
        "_坐标主轴说明": (
            "本卷述大宛及西域诸国与汉关系，从汉侧视角主轴挂汉武帝；"
            "伐宛得汗血马见共段事略"
        ),
        "protagonist_rationale": (
            "《大宛列传》为西域方国合传，主轴是大宛等政权集体，"
            "分类蕃祚；年轴为政权立国至灭亡。"
        ),
    },
}

COLLECTIVE_YEAR_RULE = "政权立国年 → 政权灭亡年"
COLLECTIVE_YEAR_RULE_NOTE = (
    "蕃祚条目：史略开始年=该政权/汗国/方国的立国（或建号、入据）之年，"
    "史略结束年=灭亡、被灭、或丧失独立地位之年；"
    "由大模型据【著作+卷名+史略名称（政权名）】与史学界主流判断，"
    "禁止用个人生卒、禁止写「生卒学界主流」，禁止仅用本卷叙事起止代替政权兴亡。"
)


def fanzuo_year_fallback_note(
    *,
    work_title: str = "",
    volume_name: str = "",
    regime_name: str = "",
) -> str:
    """Step4 LLM 提示：蕃祚 年份考订。"""
    ctx = "、".join(
        x for x in (work_title, volume_name, regime_name) if (x or "").strip()
    )
    head = f"针对【{ctx}】" if ctx else "针对本条蕃祚史略"
    return (
        f"{head}：史略开始年=政权立国年，史略结束年=政权灭亡（或被灭、丧失独立）年。"
        "须据著作体例、卷名所指政权及史学界主流兴亡年代独立考订；"
        "勿用传主生卒，勿用「叙事跨度」代替政权起亡。"
        "脚本兜底仅在人名/政权表已录入时启用，且不得覆盖已有 _年LLM依据。"
    )


def is_collective_subject(name: str, volume_name: str = "") -> bool:
    name = (name or "").strip()
    if name in COLLECTIVE_SUBJECTS:
        return True
    vn = (volume_name or "").strip()
    if vn and name and name in vn.replace("列传", ""):
        return True
    return False


def lookup_collective_subject(name: str) -> Optional[dict]:
    return COLLECTIVE_SUBJECTS.get((name or "").strip())


def collective_year_span(name: str) -> Optional[Tuple[int, int, str]]:
    """(开始, 结束, _年LLM依据)。"""
    meta = lookup_collective_subject(name)
    if not meta:
        return None
    return int(meta["start"]), int(meta["end"]), str(meta["_年LLM依据"])


def collective_provenance_fields(name: str) -> dict:
    """写入 _auto_filled 的集体条目考订字段。"""
    meta = lookup_collective_subject(name)
    if not meta:
        return {}
    return {
        "年规则": COLLECTIVE_YEAR_RULE,
        "年规则备注": COLLECTIVE_YEAR_RULE_NOTE,
        "_年LLM依据": meta["_年LLM依据"],
        "_坐标主轴说明": meta["_坐标主轴说明"],
    }


def collective_protagonist_rationale(name: str) -> str:
    meta = lookup_collective_subject(name)
    if not meta:
        return ""
    return str(meta.get("protagonist_rationale") or "")
