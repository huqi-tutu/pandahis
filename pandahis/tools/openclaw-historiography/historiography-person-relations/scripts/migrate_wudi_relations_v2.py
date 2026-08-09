#!/usr/bin/env python3
"""按新 taxonomy 清洗五帝人物关系表：边标题单字、好友二级枢纽、互斥、黄帝孙辈。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))
from paths_config import histograph_paths  # noqa: E402

EDGE_LABEL_MAP = {
    "父亲": "父",
    "母亲": "母",
    "正妻": "妻",
    "正室": "妻",
    "正妃": "妻",
    "嫔妃": "妃",
    "丈夫": "夫",
    "儿子": "子",
    "女儿": "女",
    "小妾": "妾",
    "侧室": "妾",
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

# 非家庭类非法边标题 → 清空
NON_FAMILY_CLEAR = True

WUDI_NAMES = [
    "尧",
    "帝喾",
    "舜",
    "颛顼",
    "黄帝",
    "嫘祖",
    "嫫母",
    "娥皇",
    "女英",
    "丹朱",
    "皋陶",
    "伯益",
    "契",
    "弃",
    "夔",
    "许由",
    "炎帝",
    "少昊",
    "蚩尤",
    "共工",
    "彭祖",
]

# 有据孙辈补全（仅主题人物图谱）
GRANDCHILDREN: dict[str, list[dict[str, Any]]] = {
    "黄帝": [
        {
            "关系ID": "HD-FAM-010",
            "关系节点标题": "颛顼",
            "上级连接线标题": "子",
            "所属一级关系": "配偶",
            "所属二级关系": "嫘祖",
            "所属三级关系": "昌意",
            "关系简述": "昌意之子，见于《史记·五帝本纪》，继黄帝为帝。",
            "record_id": "rec_huangdi_zhuanxu_gc",
        },
        {
            "关系ID": "HD-FAM-011",
            "关系节点标题": "蟜极",
            "上级连接线标题": "子",
            "所属一级关系": "配偶",
            "所属二级关系": "嫘祖",
            "所属三级关系": "玄嚣",
            "关系简述": "玄嚣之子，见于《史记·五帝本纪》，帝喾之父。",
            "record_id": "rec_huangdi_jiaji_gc",
        },
    ],
}


def is_hub(rec: dict[str, Any]) -> bool:
    return str(rec.get("节点类型") or "").strip() == "二级分类"


def person_title(rec: dict[str, Any]) -> str:
    return str(rec.get("关系节点标题") or "").strip()


def normalize_edge_labels(records: list[dict[str, Any]]) -> None:
    for rec in records:
        cat = str(rec.get("关系类别") or "").strip()
        label = str(rec.get("上级连接线标题") if rec.get("上级连接线标题") is not None else "")
        label = EDGE_LABEL_MAP.get(label, label)
        if cat != "家庭":
            if NON_FAMILY_CLEAR and label.strip():
                rec["上级连接线标题"] = ""
            else:
                rec["上级连接线标题"] = label
            continue
        if is_hub(rec):
            rec["上级连接线标题"] = ""
            continue
        if label not in FAMILY_EDGE_OK:
            # 无法映射的家庭边标题：尽量清空以免校验失败（如「先祖」）
            rec["上级连接线标题"] = ""
        else:
            rec["上级连接线标题"] = label


def ensure_friend_hub(records: list[dict[str, Any]], subject: str) -> list[dict[str, Any]]:
    friends = [
        r
        for r in records
        if str(r.get("关系类别") or "").strip() == "好友" and not is_hub(r)
    ]
    if not friends:
        # 去掉空的好友枢纽
        return [
            r
            for r in records
            if not (
                str(r.get("关系类别") or "").strip() == "好友"
                and is_hub(r)
                and person_title(r) == "好友"
            )
        ]

    has_hub = any(
        str(r.get("关系类别") or "").strip() == "好友"
        and is_hub(r)
        and person_title(r) == "好友"
        for r in records
    )
    out: list[dict[str, Any]] = []
    if not has_hub:
        out.append(
            {
                "关联史略名称": subject,
                "关系ID": "HD-FRI-000",
                "关系类别": "好友",
                "关系层级": "一级",
                "关系节点标题": "好友",
                "上级连接线标题": "",
                "节点类型": "二级分类",
                "关系简述": f"{subject}之好友支",
                "record_id": f"rec_{subject}_fri_hub",
            }
        )

    used_ids = {str(r.get("关系ID") or "") for r in records}
    for r in records:
        if str(r.get("关系类别") or "").strip() != "好友" or is_hub(r):
            out.append(r)
            continue
        # 人物挂到二级枢纽下
        nr = dict(r)
        if str(nr.get("关系层级") or "").strip() == "一级":
            nr["关系层级"] = "二级"
            nr["所属一级关系"] = "好友"
        elif not str(nr.get("所属一级关系") or "").strip():
            nr["所属一级关系"] = "好友"
        nr["上级连接线标题"] = ""
        # 避免与枢纽 ID 冲突
        if str(nr.get("关系ID") or "") == "HD-FRI-000":
            i = 1
            while f"HD-FRI-{i:03d}" in used_ids:
                i += 1
            nr["关系ID"] = f"HD-FRI-{i:03d}"
            used_ids.add(nr["关系ID"])
        out.append(nr)
    return out


def apply_mutex(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """家庭 > 同僚 > 好友；家庭亦排斥师徒。敌对可共现。"""
    titles_by_cat: dict[str, set[str]] = {
        "家庭": set(),
        "同僚": set(),
        "敌对": set(),
        "师徒": set(),
        "好友": set(),
    }
    for r in records:
        if is_hub(r):
            continue
        cat = str(r.get("关系类别") or "").strip()
        title = person_title(r)
        if cat in titles_by_cat and title:
            titles_by_cat[cat].add(title)

    drop_keys: set[tuple[str, str]] = set()
    for title in titles_by_cat["家庭"]:
        for cat in ("同僚", "好友", "师徒"):
            if title in titles_by_cat[cat]:
                drop_keys.add((cat, title))
    for title in titles_by_cat["同僚"]:
        if title in titles_by_cat["好友"] and ( "好友", title) not in drop_keys:
            if title not in titles_by_cat["家庭"]:
                drop_keys.add(("好友", title))

    kept: list[dict[str, Any]] = []
    for r in records:
        if is_hub(r):
            kept.append(r)
            continue
        cat = str(r.get("关系类别") or "").strip()
        title = person_title(r)
        if (cat, title) in drop_keys:
            continue
        kept.append(r)
    return kept


def prune_empty_hubs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """删除没有任何二级人物挂靠的二级枢纽。"""
    children_of: dict[str, int] = {}
    for r in records:
        if is_hub(r):
            continue
        p = str(r.get("所属一级关系") or "").strip()
        if p:
            children_of[p] = children_of.get(p, 0) + 1

    out: list[dict[str, Any]] = []
    for r in records:
        if not is_hub(r):
            out.append(r)
            continue
        if children_of.get(person_title(r), 0) > 0:
            out.append(r)
    return out


def add_grandchildren(records: list[dict[str, Any]], subject: str) -> list[dict[str, Any]]:
    extras = GRANDCHILDREN.get(subject)
    if not extras:
        return records
    existing = {
        (str(r.get("关系节点标题") or ""), str(r.get("关系层级") or ""), str(r.get("关系类别") or ""))
        for r in records
    }
    out = list(records)
    for g in extras:
        key = (g["关系节点标题"], "四级", "家庭")
        if key in existing:
            continue
        # 父节点须存在
        parent = g["所属三级关系"]
        if not any(
            person_title(r) == parent and str(r.get("关系层级") or "") == "三级"
            for r in records
        ):
            continue
        rec = {
            "关联史略名称": subject,
            "关系类别": "家庭",
            "关系层级": "四级",
            **g,
        }
        out.append(rec)
        existing.add(key)
    return out


def renumber_ids(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counters = {"家庭": 0, "同僚": 0, "敌对": 0, "师徒": 0, "好友": 0}
    prefix = {
        "家庭": "HD-FAM",
        "同僚": "HD-COL",
        "敌对": "HD-FOE",
        "师徒": "HD-MAS",
        "好友": "HD-FRI",
    }
    # 保持相对顺序：先枢纽后人物，按原顺序
    hubs = [r for r in records if is_hub(r)]
    people = [r for r in records if not is_hub(r)]
    # 按层级排序人物，保证父先于子（写文件时仍用合并顺序）
    level_order = {"一级": 1, "二级": 2, "三级": 3, "四级": 4}
    people.sort(key=lambda r: level_order.get(str(r.get("关系层级") or ""), 9))

    ordered = hubs + people
    # 实际：按类别分组更清晰——保持原相对顺序即可
    ordered = records
    out: list[dict[str, Any]] = []
    for r in ordered:
        cat = str(r.get("关系类别") or "").strip()
        if cat not in counters:
            out.append(r)
            continue
        counters[cat] += 1
        nr = dict(r)
        nr["关系ID"] = f"{prefix[cat]}-{counters[cat]:03d}"
        out.append(nr)
    return out


def migrate_file(path: Path) -> tuple[int, int, list[str]]:
    notes: list[str] = []
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"{path}: root not array")
    subject = next(
        (str(r.get("关联史略名称") or "").strip() for r in records if r.get("关联史略名称")),
        path.name.replace("关系表.json", ""),
    )
    before = len(records)

    normalize_edge_labels(records)
    records = ensure_friend_hub(records, subject)
    records = apply_mutex(records)
    records = prune_empty_hubs(records)
    records = add_grandchildren(records, subject)
    # 互斥后再清一次空枢纽（好友被删光时）
    records = prune_empty_hubs(records)
    records = ensure_friend_hub(records, subject)
    records = renumber_ids(records)

    # 统一关联史略名称
    for r in records:
        r["关联史略名称"] = subject

    path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    notes.append(f"{before}→{len(records)}")
    return before, len(records), notes


def main() -> int:
    paths = histograph_paths()
    root = paths["root"] / "data" / "07人物关系"
    ok = 0
    for name in WUDI_NAMES:
        path = root / f"{name}关系表.json"
        if not path.is_file():
            print(f"MISSING {name}")
            continue
        b, a, notes = migrate_file(path)
        print(f"OK {name}: {b}→{a} ({', '.join(notes)})")
        ok += 1
    print(f"\nDone: {ok}/{len(WUDI_NAMES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
