#!/usr/bin/env python3
"""
将旧版人物关系表迁移为文王/武王标准 schema（二级枢纽 + 层级 + 边标题规则）。

旧结构特征：人物直接挂在「关系层级=一级」，边标题承载角色（父亲/大臣/外敌…）。
新结构：一级=二级分类枢纽，二级=直接人物，三级/四级=配偶支子女/孙辈。

用法：
  python3 migrate_legacy_relations_v2.py --dynasty 夏 --dry-run
  python3 migrate_legacy_relations_v2.py --dynasty 夏
  python3 migrate_legacy_relations_v2.py --names 禹,启 --write
  python3 migrate_legacy_relations_v2.py --normalize-only --names 周文王,周武王
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))
from paths_config import histograph_paths  # noqa: E402

_PATHS = histograph_paths()
REL_DIR = _PATHS["root"] / "data" / "07人物关系"
REPORT_DIR = _PATHS["root"] / "data" / "05工作流中间产物" / "人物关系补全"

MAX_PERSONS_PER_HUB = 10

EDGE_LABEL_MAP = {
    "父亲": "父",
    "母亲": "母",
    "正妻": "妻",
    "正室": "妻",
    "正妃": "妻",
    "嫔妃": "妃",
    "妃嫔": "妃",
    "夫人": "妻",
    "王后": "妻",
    "丈夫": "夫",
    "儿子": "子",
    "女儿": "女",
    "小妾": "妾",
    "侧室": "妾",
    "妾室": "妾",
    "弟弟": "弟",
    "兄长": "兄",
    "姐姐": "姐",
    "妹妹": "妹",
}

FAMILY_EDGE_OK = {
    "父",
    "母",
    "妻",
    "妾",
    "妃",
    "夫",
    "子",
    "女",
    "兄",
    "弟",
    "姐",
    "妹",
    "兄弟",
    "姐妹",
    "",
}

CAT_MAP = {
    "君臣": "同僚",
    "师从": "师徒",
    "外敌": "敌对",
}

# 旧「一级人物」边标题 / 类别 → (关系类别, 二级枢纽, 人物边标题, 备注)
# 边标题为空表示非家庭边
L1_ROLE_MAP: dict[str, tuple[str, str, str]] = {
    "父亲": ("家庭", "父母", "父"),
    "母亲": ("家庭", "父母", "母"),
    "父": ("家庭", "父母", "父"),
    "母": ("家庭", "父母", "母"),
    "正妻": ("家庭", "配偶", "妻"),
    "正室": ("家庭", "配偶", "妻"),
    "正妃": ("家庭", "配偶", "妻"),
    "妻": ("家庭", "配偶", "妻"),
    "妾": ("家庭", "配偶", "妾"),
    "小妾": ("家庭", "配偶", "妾"),
    "侧室": ("家庭", "配偶", "妾"),
    "妾室": ("家庭", "配偶", "妾"),
    "嫔妃": ("家庭", "配偶", "妃"),
    "妃嫔": ("家庭", "配偶", "妃"),
    "妃": ("家庭", "配偶", "妃"),
    "夫人": ("家庭", "配偶", "妻"),
    "王后": ("家庭", "配偶", "妻"),
    "丈夫": ("家庭", "配偶", "夫"),
    "夫": ("家庭", "配偶", "夫"),
    "配偶": ("家庭", "配偶", "妻"),
    "兄": ("家庭", "兄弟姐妹", "兄"),
    "弟": ("家庭", "兄弟姐妹", "弟"),
    "弟弟": ("家庭", "兄弟姐妹", "弟"),
    "兄长": ("家庭", "兄弟姐妹", "兄"),
    "姐": ("家庭", "兄弟姐妹", "姐"),
    "妹": ("家庭", "兄弟姐妹", "妹"),
    "姐姐": ("家庭", "兄弟姐妹", "姐"),
    "妹妹": ("家庭", "兄弟姐妹", "妹"),
    "兄弟": ("家庭", "兄弟姐妹", "兄弟"),
    "姐妹": ("家庭", "兄弟姐妹", "姐妹"),
    "兄弟姐妹": ("家庭", "兄弟姐妹", "兄弟"),
    "君王": ("同僚", "君王", ""),
    "臣子": ("同僚", "臣子", ""),
    "大臣": ("同僚", "臣子", ""),
    "贤臣": ("同僚", "臣子", ""),
    "大夫": ("同僚", "臣子", ""),
    "臣": ("同僚", "臣子", ""),
    "相": ("同僚", "臣子", ""),
    "权臣": ("同僚", "臣子", ""),
    "嬖臣": ("同僚", "臣子", ""),
    "宦官": ("同僚", "臣子", ""),
    "力士": ("同僚", "臣子", ""),
    "侍者": ("同僚", "臣子", ""),
    "车右": ("同僚", "臣子", ""),
    "工正": ("同僚", "臣子", ""),
    "将": ("同僚", "臣子", ""),
    "将领": ("同僚", "臣子", ""),
    "将军": ("同僚", "臣子", ""),
    "正使": ("同僚", "同僚", ""),
    "同僚": ("同僚", "同僚", ""),
    "诸侯": ("同僚", "同僚", ""),
    "外敌": ("敌对", "外敌", ""),
    "敌国君主": ("敌对", "外敌", ""),
    "敌将": ("敌对", "外敌", ""),
    "敌君": ("敌对", "外敌", ""),
    "政敌": ("敌对", "内敌", ""),
    "内敌": ("敌对", "内敌", ""),
    "敌对": ("敌对", "内敌", ""),
    "命令朝见": ("敌对", "外敌", ""),
    "征伐": ("敌对", "外敌", ""),
    "老师": ("师徒", "老师", ""),
    "学生": ("师徒", "学生", ""),
    "徒弟": ("师徒", "学生", ""),
    "弟子": ("师徒", "学生", ""),
    "好友": ("好友", "好友", ""),
    "朋友": ("好友", "好友", ""),
    "知交": ("好友", "好友", ""),
    "媵妾": ("家庭", "配偶", "妾"),
    "堂兄弟": ("家庭", "兄弟姐妹", "兄弟"),
}

# 旧边标题本身是枢纽名、但人物应挂其下（父母/配偶 作边）
HUBISH_EDGE = {
    "父母": ("家庭", "父母", "父"),  # 性别不详时默认父，进歧义清单
    "配偶": ("家庭", "配偶", "妻"),
    "兄弟姐妹": ("家庭", "兄弟姐妹", "兄弟"),
}

PREFIX = {
    "家庭": "FAM",
    "同僚": "COL",
    "敌对": "FOE",
    "师徒": "MAS",
    "好友": "FRI",
}

HUB_ORDER = [
    ("家庭", "父母"),
    ("家庭", "配偶"),
    ("家庭", "兄弟姐妹"),
    ("同僚", "君王"),
    ("同僚", "同僚"),
    ("同僚", "臣子"),
    ("敌对", "内敌"),
    ("敌对", "外敌"),
    ("师徒", "老师"),
    ("师徒", "学生"),
    ("好友", "好友"),
]

# 枢纽名禁止落人物层（旧表摘要节点 / 误写）
HUB_TITLES = frozenset(h for _, h in HUB_ORDER) | {"正妻"}


def is_hub(rec: dict[str, Any]) -> bool:
    return str(rec.get("节点类型") or "").strip() == "二级分类"


def is_hub_title_leaf(rec: dict[str, Any]) -> bool:
    """标题为枢纽名且非二级分类 → 伪人物，迁移时应丢弃。"""
    return (not is_hub(rec)) and title_of(rec) in HUB_TITLES


def title_of(rec: dict[str, Any]) -> str:
    return str(rec.get("关系节点标题") or "").strip()


def normalize_category(raw: str) -> str:
    cat = (raw or "").strip()
    return CAT_MAP.get(cat, cat)


def is_new_schema(records: list[dict[str, Any]]) -> bool:
    return any(is_hub(r) for r in records)


def looks_like_battle(label: str) -> bool:
    s = (label or "").strip()
    return bool(re.search(r"之战|战役|之役", s))


def resolve_l1_role(
    rec: dict[str, Any], notes: list[str]
) -> tuple[str, str, str] | None:
    """返回 (类别, 枢纽, 边标题)；无法映射则 None。"""
    edge = str(rec.get("上级连接线标题") if rec.get("上级连接线标题") is not None else "").strip()
    cat = normalize_category(str(rec.get("关系类别") or ""))
    name = title_of(rec)

    if edge in L1_ROLE_MAP:
        return L1_ROLE_MAP[edge]
    if edge in HUBISH_EDGE:
        mapped = HUBISH_EDGE[edge]
        notes.append(f"歧义边「{edge}」→{mapped[1]}/{mapped[2]}（人物={name}）")
        return mapped

    # 战役名等：按类别落到敌对/同僚
    if looks_like_battle(edge):
        notes.append(f"战役边「{edge}」清空并归枢纽（人物={name}，原类别={cat}）")
        if cat in ("敌对",) or str(rec.get("关系类别") or "") == "外敌":
            return ("敌对", "外敌", "")
        if cat == "同僚":
            return ("同僚", "同僚", "")
        return ("敌对", "外敌", "")

    # 无边标题：按类别猜测
    if not edge:
        if cat == "家庭":
            notes.append(f"家庭无边标题，暂挂兄弟姐妹/兄弟（人物={name}）")
            return ("家庭", "兄弟姐妹", "兄弟")
        if cat == "同僚":
            return ("同僚", "同僚", "")
        if cat == "敌对":
            return ("敌对", "外敌", "")
        if cat == "师徒":
            notes.append(f"师徒无边标题，暂挂老师（人物={name}）")
            return ("师徒", "老师", "")
        if cat == "好友":
            return ("好友", "好友", "")

    # 儿子/女儿误挂一级：改挂配偶·不详
    if edge in ("儿子", "女儿", "子", "女"):
        notes.append(f"一级子女「{name}」改挂配偶/不详")
        return ("家庭", "配偶", EDGE_LABEL_MAP.get(edge, edge if edge in FAMILY_EDGE_OK else "子"))

    # 叔父等旁系 → 家庭兄弟姐妹（弱）
    if edge in ("叔父", "伯父", "族兄", "族弟", "侄子", "外甥"):
        notes.append(f"旁系「{edge}」暂归兄弟姐妹（人物={name}）")
        return ("家庭", "兄弟姐妹", "兄弟")

    # 太子：多为子女，挂不详
    if edge in ("太子",):
        notes.append(f"「太子」{name} 改挂配偶/不详 为子")
        return ("家庭", "配偶", "子")

    notes.append(f"未映射边「{edge}」类别={cat} 人物={name}")
    # 兜底
    if cat == "家庭":
        return ("家庭", "兄弟姐妹", "兄弟")
    if cat == "同僚":
        return ("同僚", "臣子", "")
    if cat in ("敌对",):
        return ("敌对", "外敌", "")
    if cat == "师徒":
        return ("师徒", "老师", "")
    if cat == "好友":
        return ("好友", "好友", "")
    return ("同僚", "同僚", "")


def normalize_edge_labels(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rec in records:
        r = dict(rec)
        cat = normalize_category(str(r.get("关系类别") or ""))
        r["关系类别"] = cat
        label = str(r.get("上级连接线标题") if r.get("上级连接线标题") is not None else "")
        label = EDGE_LABEL_MAP.get(label, label)
        if is_hub(r):
            r["上级连接线标题"] = ""
            out.append(r)
            continue
        if cat != "家庭":
            # 战役等非家庭信息挪到简述
            if label and looks_like_battle(label):
                brief = str(r.get("关系简述") or "").strip()
                if label not in brief:
                    r["关系简述"] = f"{brief}（{label}）".strip("（）") if not brief else f"{brief}（{label}）"
            r["上级连接线标题"] = ""
            out.append(r)
            continue
        if label not in FAMILY_EDGE_OK:
            r["上级连接线标题"] = ""
        else:
            r["上级连接线标题"] = label
        out.append(r)
    return out


def apply_mutex(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    titles_by_cat: dict[str, set[str]] = defaultdict(set)
    for r in records:
        if is_hub(r):
            continue
        cat = str(r.get("关系类别") or "").strip()
        t = title_of(r)
        if cat and t:
            titles_by_cat[cat].add(t)
    drop: set[tuple[str, str]] = set()
    for t in titles_by_cat["家庭"]:
        for cat in ("同僚", "好友", "师徒"):
            if t in titles_by_cat[cat]:
                drop.add((cat, t))
    for t in titles_by_cat["同僚"]:
        if t in titles_by_cat["好友"] and t not in titles_by_cat["家庭"]:
            drop.add(("好友", t))
    kept = []
    for r in records:
        if is_hub(r):
            kept.append(r)
            continue
        if (str(r.get("关系类别") or ""), title_of(r)) in drop:
            continue
        kept.append(r)
    return kept


def renumber(records: list[dict[str, Any]], subject: str) -> list[dict[str, Any]]:
    """按枢纽顺序重排并重编号关系ID。"""
    hubs = [r for r in records if is_hub(r)]
    persons = [r for r in records if not is_hub(r)]
    hub_index = {title_of(h): h for h in hubs}

    ordered_hub_keys: list[tuple[str, str]] = []
    for cat, hub in HUB_ORDER:
        if hub in hub_index and str(hub_index[hub].get("关系类别")) == cat:
            ordered_hub_keys.append((cat, hub))
    for h in hubs:
        key = (str(h.get("关系类别")), title_of(h))
        if key not in ordered_hub_keys:
            ordered_hub_keys.append(key)

    counters = {k: 0 for k in PREFIX.values()}
    out: list[dict[str, Any]] = []

    def next_id(cat: str) -> str:
        code = PREFIX.get(cat, "REL")
        counters[code] = counters.get(code, 0) + 1
        return f"HD-{code}-{counters[code]:03d}"

    # persons grouped
    by_hub: dict[str, list[dict[str, Any]]] = defaultdict(list)
    orphans: list[dict[str, Any]] = []
    for p in persons:
        hub = str(p.get("所属一级关系") or "").strip()
        if hub:
            by_hub[hub].append(p)
        else:
            orphans.append(p)

    for cat, hub_name in ordered_hub_keys:
        h = dict(hub_index[hub_name])
        h["关联史略名称"] = subject
        h["关系ID"] = next_id(cat)
        h["关系类别"] = cat
        h["关系层级"] = "一级"
        h["关系节点标题"] = hub_name
        h["上级连接线标题"] = ""
        h["节点类型"] = "二级分类"
        h["关系简述"] = h.get("关系简述") or f"{subject}之{hub_name}支。"
        # 清理所属字段
        for k in ("所属一级关系", "所属二级关系", "所属三级关系"):
            h.pop(k, None)
        out.append(h)

        kids = by_hub.get(hub_name, [])
        # 二级人物优先，再三级/四级；同层保序
        direct = [p for p in kids if str(p.get("关系层级")) == "二级"]
        deeper = [p for p in kids if str(p.get("关系层级")) != "二级"]
        # cap 二级
        if len(direct) > MAX_PERSONS_PER_HUB:
            direct = direct[:MAX_PERSONS_PER_HUB]
        for p in direct + deeper:
            nr = dict(p)
            nr["关联史略名称"] = subject
            nr["关系ID"] = next_id(cat)
            nr["关系类别"] = cat
            nr["所属一级关系"] = hub_name
            if "节点类型" in nr and nr["节点类型"] != "二级分类":
                nr.pop("节点类型", None)
            out.append(nr)

    for p in orphans:
        nr = dict(p)
        cat = str(nr.get("关系类别") or "同僚")
        nr["关联史略名称"] = subject
        nr["关系ID"] = next_id(cat)
        out.append(nr)
    return out


def migrate_old(records: list[dict[str, Any]], subject: str) -> tuple[list[dict[str, Any]], list[str]]:
    notes: list[str] = []
    # 已是人物名的一级节点（丢弃枢纽名伪人物）
    l1_persons = []
    for r in records:
        if str(r.get("关系层级") or "").strip() != "一级" or is_hub(r):
            continue
        if is_hub_title_leaf(r):
            notes.append(f"丢弃枢纽名伪人物（一级）：{title_of(r)}")
            continue
        l1_persons.append(r)
    deeper = []
    for r in records:
        if str(r.get("关系层级") or "").strip() not in ("二级", "三级", "四级") or is_hub(r):
            continue
        if is_hub_title_leaf(r):
            notes.append(f"丢弃枢纽名伪人物（{r.get('关系层级')}）：{title_of(r)}")
            continue
        deeper.append(r)

    # 标题→角色解析
    person_roles: dict[str, tuple[str, str, str, dict[str, Any]]] = {}
    for r in l1_persons:
        name = title_of(r)
        if not name:
            continue
        role = resolve_l1_role(r, notes)
        if not role:
            continue
        # 儿子挂一级：特殊——本身是子女节点
        edge = str(r.get("上级连接线标题") or "").strip()
        if edge in ("儿子", "女儿", "子", "女", "太子"):
            # 不作为二级配偶人物，后面用 deeper 逻辑挂不详
            person_roles[name] = ("家庭", "配偶", "CHILD", r)
        else:
            person_roles[name] = (*role, r)

    # 配偶名集合（用于 deeper 归属）
    spouse_names = {
        n for n, (cat, hub, edge, _) in person_roles.items() if hub == "配偶" and edge != "CHILD"
    }

    hubs_needed: set[tuple[str, str]] = set()
    new_persons: list[dict[str, Any]] = []

    # 处理一级人物
    for name, (cat, hub, edge, src) in person_roles.items():
        if edge == "CHILD":
            hubs_needed.add(("家庭", "配偶"))
            continue
        hubs_needed.add((cat, hub))
        nr = {
            "关联史略名称": subject,
            "关系类别": cat,
            "关系层级": "二级",
            "关系节点标题": name,
            "上级连接线标题": edge,
            "所属一级关系": hub,
            "关系简述": src.get("关系简述") or "",
        }
        if src.get("record_id"):
            nr["record_id"] = src["record_id"]
        # 战役边并入简述
        old_edge = str(src.get("上级连接线标题") or "").strip()
        if looks_like_battle(old_edge):
            brief = str(nr["关系简述"] or "")
            if old_edge not in brief:
                nr["关系简述"] = f"{brief}（{old_edge}）" if brief else f"（{old_edge}）"
            nr["上级连接线标题"] = ""
        new_persons.append(nr)

    # 一级误挂的子女 → 配偶/不详
    child_from_l1 = [
        (n, src)
        for n, (cat, hub, edge, src) in person_roles.items()
        if edge == "CHILD"
    ]
    if child_from_l1:
        hubs_needed.add(("家庭", "配偶"))
        need_unknown = True
    else:
        need_unknown = False

    # deeper：所属一级关系 若是配偶人名 → 三级；若是枢纽名则二级
    for r in deeper:
        name = title_of(r)
        parent = str(r.get("所属一级关系") or "").strip()
        parent2 = str(r.get("所属二级关系") or "").strip()
        edge = str(r.get("上级连接线标题") if r.get("上级连接线标题") is not None else "").strip()
        edge = EDGE_LABEL_MAP.get(edge, edge)
        cat = normalize_category(str(r.get("关系类别") or "家庭"))
        src_level = str(r.get("关系层级") or "").strip()

        if parent in spouse_names or parent == "不详":
            hubs_needed.add(("家庭", "配偶"))
            nr = {
                "关联史略名称": subject,
                "关系类别": "家庭",
                "关系层级": "三级" if src_level in ("二级", "三级") and not parent2 else src_level,
                "关系节点标题": name,
                "上级连接线标题": edge if edge in FAMILY_EDGE_OK else ("子" if "子" in edge or edge in ("儿子",) else "女" if "女" in edge else "子"),
                "所属一级关系": "配偶",
                "所属二级关系": parent,
                "关系简述": r.get("关系简述") or "",
            }
            if edge in ("子", "女"):
                nr["上级连接线标题"] = edge
            elif edge in FAMILY_EDGE_OK:
                nr["上级连接线标题"] = edge
            else:
                nr["上级连接线标题"] = "子"
            if parent2:
                nr["关系层级"] = "四级"
                nr["所属三级关系"] = parent2
            if r.get("record_id"):
                nr["record_id"] = r["record_id"]
            new_persons.append(nr)
            continue

        if parent in ("父母", "配偶", "兄弟姐妹", "君王", "同僚", "臣子", "内敌", "外敌", "老师", "学生", "好友"):
            # 已接近新结构但缺枢纽行
            hub_cat = {
                "父母": "家庭",
                "配偶": "家庭",
                "兄弟姐妹": "家庭",
                "君王": "同僚",
                "同僚": "同僚",
                "臣子": "同僚",
                "内敌": "敌对",
                "外敌": "敌对",
                "老师": "师徒",
                "学生": "师徒",
                "好友": "好友",
            }[parent]
            hubs_needed.add((hub_cat, parent))
            nr = dict(r)
            nr["关系类别"] = hub_cat
            nr["所属一级关系"] = parent
            if str(nr.get("关系层级")) == "一级":
                nr["关系层级"] = "二级"
            if hub_cat != "家庭":
                nr["上级连接线标题"] = ""
            else:
                nr["上级连接线标题"] = edge if edge in FAMILY_EDGE_OK else EDGE_LABEL_MAP.get(edge, "")
            new_persons.append(nr)
            continue

        # 所属指向未知：若像子女，挂不详
        if cat == "家庭" or edge in ("子", "女", "儿子", "女儿"):
            hubs_needed.add(("家庭", "配偶"))
            need_unknown = True
            notes.append(f"子女「{name}」原属「{parent}」不在配偶列表，改挂不详")
            nr = {
                "关联史略名称": subject,
                "关系类别": "家庭",
                "关系层级": "三级",
                "关系节点标题": name,
                "上级连接线标题": "子" if edge not in ("女", "女儿") else "女",
                "所属一级关系": "配偶",
                "所属二级关系": "不详",
                "关系简述": r.get("关系简述") or "",
            }
            if r.get("record_id"):
                nr["record_id"] = r["record_id"]
            new_persons.append(nr)
            continue

        notes.append(f"深层节点无法归属：{name} 所属一级={parent}")
        role = resolve_l1_role(r, notes)
        if role:
            cat2, hub2, edge2 = role
            hubs_needed.add((cat2, hub2))
            new_persons.append(
                {
                    "关联史略名称": subject,
                    "关系类别": cat2,
                    "关系层级": "二级",
                    "关系节点标题": name,
                    "上级连接线标题": edge2,
                    "所属一级关系": hub2,
                    "关系简述": r.get("关系简述") or "",
                }
            )

    for name, src in child_from_l1:
        need_unknown = True
        hubs_needed.add(("家庭", "配偶"))
        edge = str(src.get("上级连接线标题") or "").strip()
        edge = EDGE_LABEL_MAP.get(edge, "子")
        if edge not in ("子", "女"):
            edge = "女" if "女" in edge else "子"
        new_persons.append(
            {
                "关联史略名称": subject,
                "关系类别": "家庭",
                "关系层级": "三级",
                "关系节点标题": name,
                "上级连接线标题": edge,
                "所属一级关系": "配偶",
                "所属二级关系": "不详",
                "关系简述": src.get("关系简述") or "",
                **({"record_id": src["record_id"]} if src.get("record_id") else {}),
            }
        )

    if need_unknown or any(
        str(p.get("所属二级关系")) == "不详" for p in new_persons
    ):
        hubs_needed.add(("家庭", "配偶"))
        if not any(title_of(p) == "不详" and str(p.get("所属一级关系")) == "配偶" for p in new_persons):
            # 仅当确有挂在不详下的子女时才建「不详」配偶节点
            if any(str(p.get("所属二级关系")) == "不详" for p in new_persons):
                new_persons.insert(
                    0,
                    {
                        "关联史略名称": subject,
                        "关系类别": "家庭",
                        "关系层级": "二级",
                        "关系节点标题": "不详",
                        "上级连接线标题": "妻",
                        "所属一级关系": "配偶",
                        "关系简述": "生母不详，子女暂挂于此。",
                    },
                )

    # 建枢纽
    hub_rows: list[dict[str, Any]] = []
    for cat, hub in HUB_ORDER:
        if (cat, hub) in hubs_needed:
            hub_rows.append(
                {
                    "关联史略名称": subject,
                    "关系类别": cat,
                    "关系层级": "一级",
                    "关系节点标题": hub,
                    "上级连接线标题": "",
                    "节点类型": "二级分类",
                    "关系简述": f"{subject}之{hub}支。",
                }
            )
    for cat, hub in sorted(hubs_needed):
        if (cat, hub) not in {(c, h) for c, h in HUB_ORDER}:
            hub_rows.append(
                {
                    "关联史略名称": subject,
                    "关系类别": cat,
                    "关系层级": "一级",
                    "关系节点标题": hub,
                    "上级连接线标题": "",
                    "节点类型": "二级分类",
                    "关系简述": f"{subject}之{hub}支。",
                }
            )

    merged = hub_rows + new_persons
    merged = apply_mutex(merged)
    merged = normalize_edge_labels(merged)
    # 删空枢纽
    used_hubs = {str(p.get("所属一级关系") or "") for p in merged if not is_hub(p)}
    merged = [r for r in merged if not is_hub(r) or title_of(r) in used_hubs]
    merged = renumber(merged, subject)
    return merged, notes


def migrate_file(path: Path, *, normalize_only: bool = False) -> tuple[list[dict[str, Any]], list[str], str]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"not a list: {path}")
    subject = path.name.replace("关系表.json", "")
    if not records:
        return records, ["空表"], "empty"
    if normalize_only or is_new_schema(records):
        notes: list[str] = []
        cleaned: list[dict[str, Any]] = []
        for r in records:
            if is_hub_title_leaf(r):
                notes.append(f"丢弃枢纽名伪人物：{title_of(r)}")
                continue
            cleaned.append(r)
        if any(
            str(r.get("上级连接线标题") or "") in EDGE_LABEL_MAP
            for r in cleaned
            if not is_hub(r)
        ):
            notes.append("规范化家庭边标题为单字")
        out = normalize_edge_labels(deepcopy(cleaned))
        out = apply_mutex(out)
        out = ensure_friend_hub(out, subject)
        out = prune_empty_hubs(out)
        return out, notes, "normalize"
    out, notes = migrate_old(deepcopy(records), subject)
    out = ensure_friend_hub(out, subject)
    out = prune_empty_hubs(out)
    out = renumber(out, subject)
    return out, notes, "migrate"


def ensure_friend_hub(records: list[dict[str, Any]], subject: str) -> list[dict[str, Any]]:
    friends = [r for r in records if str(r.get("关系类别")) == "好友" and not is_hub(r)]
    if not friends:
        return [r for r in records if not (str(r.get("关系类别")) == "好友" and is_hub(r))]
    if any(is_hub(r) and title_of(r) == "好友" for r in records):
        out = []
        for r in records:
            if str(r.get("关系类别")) == "好友" and not is_hub(r):
                nr = dict(r)
                if str(nr.get("关系层级")) == "一级":
                    nr["关系层级"] = "二级"
                nr["所属一级关系"] = "好友"
                nr["上级连接线标题"] = ""
                out.append(nr)
            else:
                out.append(r)
        return out
    hub = {
        "关联史略名称": subject,
        "关系ID": "HD-FRI-000",
        "关系类别": "好友",
        "关系层级": "一级",
        "关系节点标题": "好友",
        "上级连接线标题": "",
        "节点类型": "二级分类",
        "关系简述": f"{subject}之好友支。",
    }
    out = [hub]
    for r in records:
        if str(r.get("关系类别")) == "好友" and not is_hub(r):
            nr = dict(r)
            nr["关系层级"] = "二级"
            nr["所属一级关系"] = "好友"
            nr["上级连接线标题"] = ""
            out.append(nr)
        elif not (str(r.get("关系类别")) == "好友" and is_hub(r)):
            out.append(r)
    return out


def prune_empty_hubs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    children: dict[str, int] = defaultdict(int)
    for r in records:
        if is_hub(r):
            continue
        p = str(r.get("所属一级关系") or "").strip()
        if p:
            children[p] += 1
    return [r for r in records if not is_hub(r) or children.get(title_of(r), 0) > 0]


def load_dynasty_files(dynasty: str) -> list[Path]:
    man = REL_DIR / f"{dynasty}_关系补全_manifest.json"
    if not man.exists():
        raise SystemExit(f"missing manifest: {man}")
    data = json.loads(man.read_text(encoding="utf-8"))
    paths = []
    for it in data.get("completed") or []:
        f = it.get("file") or f"{it.get('name')}关系表.json"
        paths.append(REL_DIR / f)
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dynasty", action="append", default=[], help="夏/商/西周/春秋/战国，可多次")
    ap.add_argument("--names", default="", help="逗号分隔人物名")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true", help="写入 JSON（默认 dry-run）")
    ap.add_argument("--normalize-only", action="store_true", help="仅边标题/互斥清洗（已是新表）")
    ap.add_argument("--report", default="", help="歧义报告输出路径")
    args = ap.parse_args()
    write = args.write and not args.dry_run

    paths: list[Path] = []
    if args.names:
        for n in args.names.split(","):
            n = n.strip()
            if n:
                paths.append(REL_DIR / f"{n}关系表.json")
    for d in args.dynasty:
        paths.extend(load_dynasty_files(d))
    # dedupe
    seen = set()
    uniq: list[Path] = []
    for p in paths:
        if p.resolve() in seen:
            continue
        seen.add(p.resolve())
        uniq.append(p)
    paths = uniq
    if not paths:
        ap.error("需要 --dynasty 或 --names")

    report: list[dict[str, Any]] = []
    ok = 0
    for path in paths:
        if not path.exists():
            report.append({"file": path.name, "error": "missing"})
            continue
        try:
            out, notes, mode = migrate_file(path, normalize_only=args.normalize_only)
        except Exception as e:
            report.append({"file": path.name, "error": str(e)})
            continue
        if write:
            path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ok += 1
        report.append(
            {
                "file": path.name,
                "mode": mode,
                "rows": len(out),
                "hubs": [title_of(r) for r in out if is_hub(r)],
                "notes": notes,
                "written": write,
            }
        )
        flag = "WRITE" if write else "DRY"
        print(f"[{flag}] {path.name} mode={mode} rows={len(out)} hubs={','.join(title_of(r) for r in out if is_hub(r))}")
        for n in notes[:8]:
            print(f"    - {n}")
        if len(notes) > 8:
            print(f"    … +{len(notes)-8} notes")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report) if args.report else REPORT_DIR / "legacy_migrate_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report → {report_path} ({ok}/{len(paths)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
