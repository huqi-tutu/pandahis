#!/usr/bin/env python3
"""Step1 人物身份硬门：blocks / skeleton 须与帝王.json 标准名及卷主轴一致。

补 check_format「名在表中即可过」的漏洞（如 南汉高祖 误标 高祖本纪）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from coordinate_index import normalize_entry_category
from emperor_resolve import (
    build_alias_to_canonical,
    build_emperor_info_index,
    resolve_emperor_label,
)
from fanzuo_volumes import fanzuo_category_errors

_ALIAS_TO_CANON: Optional[Dict[str, str]] = None


def _alias_map() -> Dict[str, str]:
    global _ALIAS_TO_CANON
    if _ALIAS_TO_CANON is None:
        _ALIAS_TO_CANON = build_alias_to_canonical()
    return _ALIAS_TO_CANON


def _canon_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return n
    return _alias_map().get(n, n)

# LLM 常见误名（全局禁止作为 blocks/君王 最终名）
FORBIDDEN_JUNWANG_NAMES: frozenset[str] = frozenset(
    {
        "南汉高祖",
        "孝文皇帝",
    }
)

# (work, vol) → 卷级硬规则
VOLUME_IDENTITY_RULES: Dict[Tuple[str, str], dict] = {
    ("01史记", "008"): {
        "volume_hint": "高祖本纪 → 主轴须为「汉高祖」(西汉)，禁止「南汉高祖」",
        "required": [{"name": "汉高祖", "category": "君王"}],
        "forbidden_names": ["南汉高祖"],
        "junwang_dynasties": {"西汉", "秦末汉初"},
    },
    ("01史记", "009"): {
        "volume_hint": "吕太后本纪 → 主轴「吕太后」须为 category=宗戚（临朝太后），禁止君王",
        "required": [{"name": "吕太后", "category": "宗戚"}],
    },
    ("02汉书", "004"): {
        "volume_hint": "《高后纪》→ 主轴「吕太后」须为宗戚（临朝太后立纪），禁止君王；"
        "虽立本纪、帝王表有「吕太后」条目，史略分类仍取宗戚",
        "required": [{"name": "吕太后", "category": "宗戚"}],
    },
    ("02汉书", "054"): {
        "volume_hint": "淮南衡山济北王传 → 汉室宗室诸侯王合传（同荆燕吴传），主轴须为宗戚；"
        "禁止蕃祚（非四夷/域外方国卷，见蕃祚卷型.md）",
        "required": [
            {"name": "刘长", "category": "宗戚"},
            {"name": "刘安", "category": "宗戚"},
            {"name": "刘赐", "category": "宗戚"},
            {"name": "刘勃", "category": "宗戚"},
        ],
        "forbidden_categories": ["蕃祚"],
    },
    ("02汉书", "057"): {
        "volume_hint": "文三王传 → 汉文帝三王合传，刘参、梁孝王、刘揖均须为宗戚；禁止回退为单主角或君王口径",
        "required": [
            {"name": "刘参", "category": "宗戚"},
            {"name": "梁孝王", "category": "宗戚"},
            {"name": "刘揖", "category": "宗戚"},
        ],
        "min_protagonists": 3,
    },
    ("01史记", "010"): {
        "volume_hint": "孝文本纪 → 主轴须为帝王表标准名「汉文帝」，禁止自造「孝文皇帝」",
        "required": [{"name": "汉文帝", "category": "君王"}],
        "forbidden_names": ["孝文皇帝"],
    },
    ("01史记", "033"): {
        "volume_hint": "鲁周公世家 → 主轴须为帝王表「周公旦」category=君王（鲁国始祖）；士臣与君王冲突时按优先级链取君王",
        "required": [{"name": "周公旦", "category": "君王"}],
        "forbidden_names": ["鲁公伯禽", "鲁考公"],
    },
    ("01史记", "047"): {
        "volume_hint": "孔子世家 → 主轴「孔子」须为文臣（至圣先师，非帝王叙事）；禁止君王",
        "required": [{"name": "孔子", "category": "文臣"}],
        "forbidden_names": [],
    },
    ("01史记", "048"): {
        "volume_hint": "陈涉世家 → 主轴「陈涉」须为庶众（起义未称帝）；禁止君王",
        "required": [{"name": "陈涉", "category": "庶众"}],
    },
    ("01史记", "049"): {
        "volume_hint": (
            "外戚世家 → 主轴为外戚女性（宗戚），按薄太后/窦太后/王太后/卫子夫分块；"
            "P1–3 卷首总论（吕后事）exclude，吕太后主轴在 009 本纪；"
            "禁止以汉高祖/汉文帝/汉武帝为 protagonist"
        ),
        "required": [
            {"name": "薄太后", "category": "宗戚"},
            {"name": "窦太后", "category": "宗戚"},
            {"name": "王太后", "category": "宗戚"},
            {"name": "卫子夫", "category": "宗戚"},
        ],
        "forbidden_names": ["汉高祖", "汉文帝", "汉武帝", "吕太后"],
        "min_protagonists": 4,
    },
    ("01史记", "059"): {
        "volume_hint": (
            "五宗世家 → 景帝五母宗支合传（栗姬/程姬/贾夫人/唐姬/儿姁），"
            "主轴为宗戚（同母宗亲），按五母分块；禁止藩王、汉景帝为 protagonist"
        ),
        "required": [
            {"name": "栗姬", "category": "宗戚"},
            {"name": "程姬", "category": "宗戚"},
            {"name": "贾夫人", "category": "宗戚"},
            {"name": "唐姬", "category": "宗戚"},
            {"name": "儿姁", "category": "宗戚"},
        ],
        "forbidden_names": [
            "汉景帝",
            "河间献王",
            "鲁共王",
            "赵王彭祖",
            "长沙定王",
            "常山宪王",
            "临江闵王荣",
        ],
        "min_protagonists": 5,
    },
    ("01史记", "060"): {
        "volume_hint": (
            "三王世家 → 齐王刘闳、燕王旦、广陵王刘胥 各一块；"
            "P12–17 为三王册命策，P18 仅太史公曰 exclude，"
            "P19 起褚先生补述须归入三王块（禁止整段误标太史公曰）；"
            "禁止以汉武帝为 protagonist"
        ),
        "forbidden_names": ["汉武帝"],
        "min_protagonists": 3,
    },
}

# 卷名模式兜底（vol 未配置时）
VOLUME_NAME_PATTERNS: List[dict] = [
    {
        "name_re": r"吕太后|高后纪|高后",
        "required": [{"name": "吕太后", "category": "宗戚"}],
        "hint": "吕太后/高后纪主轴为宗戚（立纪太后≠史略分类君王）",
    },
    {
        "name_re": r"高祖本纪",
        "not_re": r"南汉",
        "required": [{"name": "汉高祖", "category": "君王"}],
        "forbidden_names": ["南汉高祖"],
        "junwang_dynasties": {"西汉", "秦末汉初"},
        "hint": "高祖本纪主轴为西汉汉高祖",
    },
    {
        "name_re": r"孝文本纪",
        "required": [{"name": "汉文帝", "category": "君王"}],
        "forbidden_names": ["孝文皇帝"],
        "hint": "孝文本纪主轴为汉文帝",
    },
    {
        "name_re": r"鲁周公世家",
        "required": [{"name": "周公旦", "category": "君王"}],
        "forbidden_names": ["鲁公伯禽", "鲁考公"],
        "hint": "鲁周公世家主轴为周公旦（君王），伯禽等鲁国后世君主归入本卷叙事块，不另立主轴",
    },
    {
        "name_re": r"淮南衡山济北王传",
        "required": [
            {"name": "刘长", "category": "宗戚"},
            {"name": "刘安", "category": "宗戚"},
            {"name": "刘赐", "category": "宗戚"},
            {"name": "刘勃", "category": "宗戚"},
        ],
        "forbidden_categories": ["蕃祚"],
        "hint": "宗室诸侯王合传 → 宗戚（同荆燕吴传）；禁止蕃祚",
    },
    {
        "name_re": r"文三王传",
        "required": [
            {"name": "刘参", "category": "宗戚"},
            {"name": "梁孝王", "category": "宗戚"},
            {"name": "刘揖", "category": "宗戚"},
        ],
        "min_protagonists": 3,
        "hint": "文帝三王合传 → 刘参、梁孝王、刘揖三主轴并立，分类为宗戚",
    },
    {
        "name_re": r"匈奴传",
        "required": [{"name": "匈奴", "category": "蕃祚"}],
        "forbidden_names": ["冒顿", "头曼", "老上单"],
        "hint": "匈奴传主轴为匈奴部族/政权集体（蕃祚）；年=政权立国至灭亡，非个人生卒",
    },
    {
        "name_re": r"匈奴列传",
        "required": [{"name": "匈奴", "category": "蕃祚"}],
        "forbidden_names": ["冒顿", "头曼", "老上单"],
        "hint": "匈奴列传主轴为匈奴部族/政权集体（蕃祚）；年=政权立国至灭亡，非个人生卒",
    },
    {
        "name_re": r"南越列传",
        "required": [{"name": "南越", "category": "蕃祚"}],
        "forbidden_names": ["赵佗", "尉佗"],
        "hint": "南越列传主轴为南越政权集体（蕃祚）；年=政权立国至灭亡，非赵佗个人生卒",
    },
    {
        "name_re": r"东越列传",
        "required": [{"name": "东越", "category": "蕃祚"}],
        "forbidden_names": ["闽越王", "驺郢"],
        "hint": "东越列传主轴为东越/闽越政权集体（蕃祚）；年=政权立国至灭亡",
    },
    {
        "name_re": r"朝鲜列传",
        "required": [{"name": "朝鲜", "category": "蕃祚"}],
        "forbidden_names": ["卫满", "卫右渠"],
        "hint": "朝鲜列传主轴为朝鲜政权集体（蕃祚）；年=政权立国至灭亡",
    },
    {
        "name_re": r"大宛列传",
        "required": [{"name": "大宛", "category": "蕃祚"}],
        "forbidden_names": ["大宛列传"],
        "hint": "大宛列传主轴为西域方国集体（蕃祚）；年=政权立国至灭亡",
    },
    {
        "name_re": r"仲尼弟子列传",
        "required": [
            {"name": "颜回", "category": "文臣"},
            {"name": "子路", "category": "文臣"},
            {"name": "宰予", "category": "文臣"},
            {"name": "子贡", "category": "文臣"},
            {"name": "子夏", "category": "文臣"},
        ],
        "forbidden_names": ["孔子", "仲尼弟子列传", "仲尼"],
        "min_protagonists": 10,
        "hint": "仲尼弟子列传：仅有独立叙事段的弟子为传主；P116 起名册/仅年名字一句带过须 exclude，禁止立条；禁止以孔子为卷主轴",
    },
    {
        "name_re": r"儒林列传",
        "required": [
            {"name": "申公", "category": "文臣"},
            {"name": "辕固生", "category": "文臣"},
            {"name": "伏生", "category": "文臣"},
            {"name": "董仲舒", "category": "文臣"},
        ],
        "forbidden_names": ["孔子", "儒林列传"],
        "min_protagonists": 4,
        "hint": "儒林列传记汉代经师合传，禁止以孔子或卷名为唯一主轴",
    },
    {
        "name_re": r"酷吏列传",
        "required": [
            {"name": "郅都", "category": "文臣"},
            {"name": "张汤", "category": "文臣"},
            {"name": "杜周", "category": "文臣"},
        ],
        "forbidden_names": ["酷吏列传", "酷吏"],
        "min_protagonists": 3,
        "hint": "酷吏列传记郅都、张汤等个体酷吏，禁止以卷名或抽象词为唯一主轴",
    },
    {
        "name_re": r"游侠列传",
        "required": [
            {"name": "朱家", "category": "庶众"},
            {"name": "郭解", "category": "庶众"},
        ],
        "forbidden_names": ["游侠列传", "游侠"],
        "min_protagonists": 2,
        "hint": "游侠列传记朱家、郭解等侠士，禁止以卷名或抽象词为唯一主轴",
    },
    {
        "name_re": r"西南夷列传",
        "required": [{"name": "西南夷", "category": "蕃祚"}],
        "forbidden_names": ["庄蹻"],
        "hint": "西南夷列传主轴为西南夷族群/诸国集体（蕃祚）；年=政权立国至灭亡",
    },
    {
        "name_re": r"佞幸列传",
        "required": [
            {"name": "邓通", "category": "文臣"},
            {"name": "李延年", "category": "宦官"},
        ],
        "forbidden_names": ["佞幸列传"],
        "min_protagonists": 2,
        "hint": "佞幸列传：士人宠臣归文臣，阉人近幸归宦官（司马迁等受宫刑士人不算宦官）",
    },
]


def _rule_for(work: str, vol: str, volume_name: str) -> Optional[dict]:
    vol_z = vol.zfill(3)
    key = (work, vol_z)
    if key in VOLUME_IDENTITY_RULES:
        return VOLUME_IDENTITY_RULES[key]
    vn = (volume_name or "").strip()
    for pat in VOLUME_NAME_PATTERNS:
        if not re.search(pat["name_re"], vn):
            continue
        if pat.get("not_re") and re.search(pat["not_re"], vn):
            continue
        return pat
    return None


def identity_hint_for_protagonist_prompt(
    work: str, vol: str, volume_name: str = "", *, work_title: str = ""
) -> str:
    """Step1a 主轴理解：只给原则与常识提示，不脚本预填答案。"""
    title = work_title or work
    vn = volume_name or "(见段落索引卷名)"
    return (
        "【主轴人物理解 — 须凭著作+卷名+史学常识自行判断】\n"
        f"著作：《{title}》（{work}）  本卷卷名：「{vn}」\n"
        "请判断本卷叙事主轴人物（排除太史公曰、世系链、卷首标题等）。\n"
        "⚠️ 分类链只用于同一人定 entry 分类，不用于选卷主轴（见 Step1a「史略分类 v3」）。\n"
        "正文出现的皇帝/太后不等于主人公；须据卷名判断（如五宗世家→景帝五母宗戚宗支，非藩王君王）。\n"
        "君王 name 须与帝王.json「帝王名称」逐字一致；禁止自造名、禁止跨朝代同名误配。\n"
        "常识提示（非脚本结论，仍须你自行核对帝王表）：\n"
        "- 高祖本纪 → 西汉汉高祖（≠南汉高祖）\n"
        "- 孝文本纪 → 汉文帝（≠孝文皇帝）\n"
        "- 吕太后本纪 / 汉书高后纪 → 吕太后 + 宗戚（≠君王；立纪不等于君王分类；"
        "name 优先写帝王表标准名「吕太后」）\n"
        "- 五宗世家 → 栗姬/程姬/贾夫人/唐姬/儿姁 五母宗戚（≠藩王君王、≠汉景帝）\n"
        "- 三王世家 → 齐王刘闳、燕王刘旦、广陵王刘胥（≠汉武帝）\n"
        "- 仲尼弟子列传 → 主轴=有独立叙事段的弟子；P116 起名册一笔带过须 exclude、不立条；禁止孔子为卷主轴\n"
        "- 匈奴/南越/东越/朝鲜/西南夷列传（史记）及汉书匈奴传/西南夷两粤朝鲜传/西域传 → "
        "主轴=卷名所指族/国/诸夷集体，category=蕃祚（非帝王.json单君王）；年轴=政权立国至灭亡\n"
        "- 汉书诸侯王合传（如荆燕吴传、淮南衡山济北王传）→ 宗戚，禁止蕃祚\n"
        "每位 protagonist 须写 rationale，说明依据卷名/常识为何是主轴。"
    )


def _collect_protagonists(data: dict) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for item in data.get("protagonists") or []:
        if not isinstance(item, dict):
            continue
        out.append(
            (
                _canon_name(item.get("name") or ""),
                (item.get("category") or "").strip(),
            )
        )
    return out


def validate_protagonists_identity(
    work: str,
    vol: str,
    data: dict,
    *,
    volume_name: str = "",
) -> Tuple[bool, str]:
    """Step1a 落盘硬检：主轴清单须过帝王表与卷级规则（脚本第二道）。"""
    work_id = work
    eidx = build_emperor_info_index()
    pairs = _collect_protagonists(data)
    if not pairs:
        return False, "protagonists 为空"
    errors: List[str] = []
    rule = _rule_for(work, vol, volume_name or (data.get("volume_name") or ""))
    vn = volume_name or (data.get("volume_name") or data.get("volume") or "")
    errors.extend(fanzuo_category_errors(work, vol, vn, pairs, prefix="protagonist "))
    if rule:
        errors.extend(
            _apply_volume_rule(
                rule, pairs, work_id=work_id, eidx=eidx, prefix="protagonist "
            )
        )
    else:
        for name, cat in pairs:
            if cat == "君王":
                errors.extend(
                    _validate_junwang_name(
                        name,
                        work_id=work_id,
                        eidx=eidx,
                        label=f"protagonist {name!r}",
                    )
                )
    if errors:
        return False, "主轴人物身份门未过:\n" + "\n".join(f"  - {e}" for e in errors[:12])
    return True, f"主轴 {len(pairs)} 人身份 OK"


def cross_check_protagonists_blocks(
    protagonists: dict, blocks: dict
) -> Tuple[bool, str]:
    """双重校验：Step1a 清单 ↔ Step1b blocks 人物集合须完全一致。"""
    p_set = {(n, c) for n, c in _collect_protagonists(protagonists) if n}
    b_set = {(n, c) for n, c in _collect_blocks(blocks) if n}
    if p_set == b_set:
        return True, f"protagonists↔blocks {len(p_set)} 人一致"
    msgs: List[str] = []
    only_p = p_set - b_set
    only_b = b_set - p_set
    if only_p:
        msgs.append(f"blocks 缺少或未对齐: {sorted(only_p)!r}")
    if only_b:
        msgs.append(f"blocks 多出或未对齐: {sorted(only_b)!r}")
    return False, "双重校验未过:\n" + "\n".join(f"  - {m}" for m in msgs)


def cross_check_protagonists_skeleton(
    protagonists: dict, skeleton: dict
) -> Tuple[bool, str]:
    """短卷：Step1a 清单 ↔ skeleton entries 一致。"""
    p_set = {(n, c) for n, c in _collect_protagonists(protagonists) if n}
    e_set = {(n, c) for n, c in _collect_entries(skeleton) if n}
    if p_set == e_set:
        return True, f"protagonists↔entries {len(p_set)} 人一致"
    msgs: List[str] = []
    only_p = p_set - e_set
    only_e = e_set - p_set
    if only_p:
        msgs.append(f"entries 缺少或未对齐: {sorted(only_p)!r}")
    if only_e:
        msgs.append(f"entries 多出或未对齐: {sorted(only_e)!r}")
    return False, "双重校验未过:\n" + "\n".join(f"  - {m}" for m in msgs)


def identity_hint_for_prompt(work: str, vol: str, volume_name: str = "") -> str:
    """注入 Step1 LLM prompt 的卷主轴提示。"""
    rule = _rule_for(work, vol, volume_name)
    if not rule:
        return (
            "【人物身份】君王 block 的 name 必须与 reference/帝王.json「帝王名称」**逐字一致**；"
            "禁止自造名、禁止跨朝代同名误匹配（如高祖本纪≠南汉高祖）。"
            "写 blocks 前须核对帝王表。"
        )
    lines = [
        "【本卷人物身份 — 硬门控，违反则 Step1 失败】",
        rule.get("volume_hint") or rule.get("hint", ""),
    ]
    for req in rule.get("required") or []:
        lines.append(
            f"- 须含 block: name={req['name']!r} category={req['category']!r}"
        )
    forb = rule.get("forbidden_names") or []
    if forb:
        lines.append(f"- 禁止 block 名: {', '.join(forb)}")
    lines.append(
        "君王 name 只能填帝王.json 已有「帝王名称」；不确定时查表，勿凭卷内称呼自造。"
    )
    return "\n".join(lines)


def _emperor_dynasty(info: dict) -> str:
    return (info.get("dynasty") or "").strip()


def _validate_junwang_name(
    name: str,
    *,
    work_id: str,
    eidx: Dict[str, dict],
    label: str,
) -> List[str]:
    errors: List[str] = []
    n = (name or "").strip()
    if not n:
        errors.append(f"{label}: 君王名为空")
        return errors
    if n in FORBIDDEN_JUNWANG_NAMES:
        errors.append(f"{label}: 禁止误名 {n!r}（须查帝王.json 标准名）")
    if n not in eidx:
        resolved, method = resolve_emperor_label(n, work_id=work_id, emperor_index=eidx)
        if resolved:
            canon = resolved["emperor"]
            errors.append(
                f"{label}: 君王名 {n!r} 须改为帝王表标准名 {canon!r}（{method}）"
            )
        else:
            errors.append(
                f"{label}: 君王名 {n!r} 不在帝王.json 且无法解析；禁止自造/乱填"
            )
    return errors


def _collect_blocks(draft: dict) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for item in draft.get("blocks") or []:
        if not isinstance(item, dict):
            continue
        out.append(
            (
                _canon_name(item.get("name") or ""),
                (item.get("category") or "").strip(),
            )
        )
    return out


def _collect_entries(data: dict) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for entry in data.get("entries") or []:
        out.append(
            (
                _canon_name(entry.get("史略名称") or ""),
                normalize_entry_category(entry.get("史略分类", "")),
            )
        )
    return out


def _apply_volume_rule(
    rule: dict,
    pairs: List[Tuple[str, str]],
    *,
    work_id: str,
    eidx: Dict[str, dict],
    prefix: str,
) -> List[str]:
    errors: List[str] = []
    name_to_cat = {n: c for n, c in pairs if n}

    for req in rule.get("required") or []:
        want_name = req["name"]
        want_cat = req["category"]
        if want_name not in name_to_cat:
            errors.append(f"{prefix}缺少主轴 block/entry: {want_name!r} ({want_cat})")
        elif name_to_cat.get(want_name) != want_cat:
            errors.append(
                f"{prefix}{want_name!r} 须为 category={want_cat!r}，"
                f"当前为 {name_to_cat.get(want_name)!r}"
            )

    for forb in rule.get("forbidden_names") or []:
        if forb in name_to_cat:
            errors.append(f"{prefix}禁止出现误名 {forb!r}")

    for forb_cat in rule.get("forbidden_categories") or []:
        for name, cat in pairs:
            if cat == forb_cat:
                errors.append(
                    f"{prefix}{name!r} 禁止 category={forb_cat!r}；"
                    f"{rule.get('volume_hint') or rule.get('hint', '')}"
                )

    min_p = rule.get("min_protagonists")
    if min_p and len([n for n, _ in pairs if n]) < int(min_p):
        errors.append(
            f"{prefix}主轴人数不足：须至少 {min_p} 人，当前 {len(pairs)} 人"
        )

    dyn_allow: Optional[Set[str]] = rule.get("junwang_dynasties")
    if dyn_allow:
        for name, cat in pairs:
            if cat != "君王" or name not in eidx:
                continue
            dyn = _emperor_dynasty(eidx[name])
            if dyn and dyn not in dyn_allow:
                errors.append(
                    f"{prefix}君王 {name!r} 朝代={dyn!r} 与本卷时代不符"
                    f"（允许: {', '.join(sorted(dyn_allow))}）"
                )

    for name, cat in pairs:
        if cat == "君王":
            errors.extend(
                _validate_junwang_name(
                    name, work_id=work_id, eidx=eidx, label=f"{prefix}{name!r}"
                )
            )
    return errors


def validate_blocks_identity(
    work: str,
    vol: str,
    draft: dict,
    *,
    volume_name: str = "",
) -> Tuple[bool, str]:
    """blocks 落盘/expand 前硬检。"""
    work_id = work
    eidx = build_emperor_info_index()
    pairs = _collect_blocks(draft)
    errors: List[str] = []

    rule = _rule_for(work, vol, volume_name)
    errors.extend(fanzuo_category_errors(work, vol, volume_name, pairs, prefix="blocks "))
    if rule:
        errors.extend(
            _apply_volume_rule(rule, pairs, work_id=work_id, eidx=eidx, prefix="blocks ")
        )
    else:
        for name, cat in pairs:
            if cat == "君王":
                errors.extend(
                    _validate_junwang_name(
                        name, work_id=work_id, eidx=eidx, label=f"blocks {name!r}"
                    )
                )

    if errors:
        return False, "人物身份门未过:\n" + "\n".join(f"  - {e}" for e in errors[:12])
    return True, f"{len(pairs)} 块身份 OK"


def validate_skeleton_identity(
    work: str,
    vol: str,
    data: dict,
) -> Tuple[bool, str]:
    """Step1 verify：skeleton entries + 段归属 category 一致。"""
    work_id = work
    eidx = build_emperor_info_index()
    volume_name = (data.get("volume") or "").strip()
    errors: List[str] = []

    pairs = _collect_entries(data)
    rule = _rule_for(work, vol, volume_name)
    errors.extend(fanzuo_category_errors(work, vol, volume_name, pairs, prefix="entry "))
    if rule:
        errors.extend(
            _apply_volume_rule(
                rule, pairs, work_id=work_id, eidx=eidx, prefix="entry "
            )
        )
    else:
        for name, cat in pairs:
            if cat == "君王":
                errors.extend(
                    _validate_junwang_name(
                        name, work_id=work_id, eidx=eidx, label=f"entry {name!r}"
                    )
                )

    # segment_attribution 与 entry 分类一致
    entry_cats = {n: c for n, c in pairs if n}
    for row in data.get("segment_attribution") or []:
        pid = row.get("paragraph")
        for owner in row.get("owners") or []:
            oname = _canon_name(owner.get("name") or "")
            ocat = (owner.get("category") or "").strip()
            if oname in FORBIDDEN_JUNWANG_NAMES:
                errors.append(f"P{pid} 归属禁止误名 {oname!r}")
            if oname in entry_cats and ocat != entry_cats[oname]:
                errors.append(
                    f"P{pid} 归属 category={ocat!r} 与 entry {oname!r}="
                    f"{entry_cats[oname]!r} 不一致"
                )
            if ocat == "君王":
                errors.extend(
                    _validate_junwang_name(
                        oname,
                        work_id=work_id,
                        eidx=eidx,
                        label=f"P{pid} 君王",
                    )
                )

    if errors:
        return False, "人物身份门未过:\n" + "\n".join(f"  - {e}" for e in errors[:15])
    return True, "skeleton 人物身份 OK"
