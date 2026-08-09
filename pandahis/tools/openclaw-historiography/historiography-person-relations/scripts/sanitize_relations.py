#!/usr/bin/env python3
"""关系表确定性后处理：边标题归一、互斥、二级枢纽按重要/紧密截断至 ≤10。"""

from __future__ import annotations

from typing import Any

MAX_PERSONS_PER_HUB = 10

FAMILY_EDGE_WHITELIST = frozenset(
    {"", "父", "母", "妻", "妾", "妃", "夫", "子", "女", "兄", "弟", "姐", "妹", "兄弟", "姐妹"}
)

# 可确定性映射到白名单的旧称 / 近义
FAMILY_EDGE_MAP = {
    "父亲": "父",
    "母亲": "母",
    "丈夫": "夫",
    "正妻": "妻",
    "正室": "妻",
    "妻子": "妻",
    "妻室": "妻",
    "儿子": "子",
    "女儿": "女",
    "小妾": "妾",
    "侧室": "妾",
    "嫔妃": "妃",
    "正妃": "妃",
    "兄长": "兄",
    "弟弟": "弟",
    "姐姐": "姐",
    "妹妹": "妹",
    "兄弟": "兄弟",
    "姐妹": "姐妹",
}

# 不在 taxonomy 内的亲属边：丢弃该节点（及子孙）
FAMILY_EDGE_DROP = frozenset(
    {
        "祖父",
        "祖母",
        "外祖父",
        "外祖母",
        "爷爷",
        "奶奶",
        "外公",
        "外婆",
        "伯父",
        "叔父",
        "叔叔",
        "舅舅",
        "姑母",
        "姑父",
        "姨母",
        "侄",
        "侄子",
        "侄女",
        "甥",
        "外甥",
        "孙女",
        "孙子",
        "孙",
        "曾孙",
        "女婿",
        "儿媳",
        "公公",
        "婆婆",
        "岳父",
        "岳母",
        "表兄",
        "表弟",
        "堂兄",
        "堂弟",
    }
)

# 家庭边：越近亲属分越高（同枢纽内排序）
FAMILY_EDGE_SCORE = {
    "父": 100,
    "母": 100,
    "夫": 96,
    "妻": 96,
    "子": 88,
    "女": 88,
    "兄": 72,
    "弟": 72,
    "姐": 72,
    "妹": 72,
    "兄弟": 68,
    "姐妹": 68,
    "妾": 58,
    "妃": 58,
    "": 40,
}

# 枢纽本身的「紧密/核心」权重（跨 hub 不比；同 hub 内作微调）
HUB_WEIGHT = {
    "父母": 10,
    "配偶": 8,
    "兄弟姐妹": 4,
    "君王": 8,
    "同僚": 5,
    "臣子": 3,
    "内敌": 6,
    "外敌": 4,
    "老师": 7,
    "学生": 4,
    "好友": 5,
}

CLOSENESS_KEYWORDS = (
    ("皇后", 22),
    ("皇太后", 20),
    ("太子", 18),
    ("丞相", 16),
    ("宰相", 16),
    ("大将军", 14),
    ("太尉", 14),
    ("御史大夫", 12),
    ("大司马", 12),
    ("顾命", 12),
    ("辅政", 12),
    ("废", 10),
    ("杀", 10),
    ("诛", 10),
    ("反", 8),
    ("谋反", 12),
    ("师事", 10),
    ("受业", 10),
    ("友善", 8),
    ("刎颈", 12),
    ("同窗", 6),
)


def _is_hub(rec: dict[str, Any]) -> bool:
    return str(rec.get("节点类型") or "").strip() == "二级分类"


def _title(rec: dict[str, Any]) -> str:
    return str(rec.get("关系节点标题") or "").strip()


def _cat(rec: dict[str, Any]) -> str:
    return str(rec.get("关系类别") or "").strip()


def _level(rec: dict[str, Any]) -> str:
    return str(rec.get("关系层级") or "").strip()


def _edge(rec: dict[str, Any]) -> str:
    v = rec.get("上级连接线标题")
    return "" if v is None else str(v).strip()


def normalize_family_edges(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """映射旧边标题；无法映射的非法家庭边 → 删节点及子孙。非家庭人物边清空。"""
    notes: list[str] = []
    drop_names: set[str] = set()
    mapped: list[dict[str, Any]] = []

    for rec in records:
        row = dict(rec)
        if _is_hub(row):
            row["上级连接线标题"] = ""
            mapped.append(row)
            continue

        cat = _cat(row)
        edge = _edge(row)
        title = _title(row)

        if cat != "家庭":
            if edge:
                notes.append(f"clear non-family edge {_cat(row)}/{title}: {edge!r}→''")
                row["上级连接线标题"] = ""
            mapped.append(row)
            continue

        if edge in FAMILY_EDGE_MAP:
            new_edge = FAMILY_EDGE_MAP[edge]
            if new_edge != edge:
                notes.append(f"map family edge {title}: {edge!r}→{new_edge!r}")
            row["上级连接线标题"] = new_edge
            mapped.append(row)
            continue

        if edge in FAMILY_EDGE_DROP or (
            edge not in FAMILY_EDGE_WHITELIST and edge != ""
        ):
            if title:
                drop_names.add(title)
            notes.append(f"drop invalid family edge {title}: {edge!r}")
            continue

        mapped.append(row)

    if not drop_names:
        return mapped, notes

    out: list[dict[str, Any]] = []
    for row in mapped:
        if _is_hub(row):
            out.append(row)
            continue
        title = _title(row)
        p2 = str(row.get("所属二级关系") or "").strip()
        p3 = str(row.get("所属三级关系") or "").strip()
        if title in drop_names or p2 in drop_names or p3 in drop_names:
            continue
        out.append(row)
    return out, notes


def apply_mutex(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """家庭 > 同僚 > 好友；家庭亦排斥师徒。"""
    notes: list[str] = []
    family = {
        _title(r)
        for r in records
        if not _is_hub(r) and _cat(r) == "家庭" and _title(r)
    }
    colleague = {
        _title(r)
        for r in records
        if not _is_hub(r) and _cat(r) == "同僚" and _title(r)
    }

    out: list[dict[str, Any]] = []
    for r in records:
        if _is_hub(r):
            out.append(r)
            continue
        cat = _cat(r)
        title = _title(r)
        if cat in {"同僚", "好友", "师徒"} and title in family:
            notes.append(f"mutex drop {cat}/{title} (kept in 家庭)")
            continue
        if cat == "好友" and title in colleague:
            notes.append(f"mutex drop 好友/{title} (kept in 同僚)")
            continue
        out.append(r)
    return out, notes


def _importance_score(
    rec: dict[str, Any],
    *,
    hub: str,
    index_names: set[str] | None,
    order: int,
) -> float:
    """分数越高越应保留：亲缘近、史料笔墨多、有独立史略、关键词显示核心关系。"""
    summary = str(rec.get("关系简述") or "").strip()
    title = _title(rec)
    edge = _edge(rec)
    cat = _cat(rec)

    score = 0.0
    score += HUB_WEIGHT.get(hub, 0)

    if cat == "家庭":
        score += FAMILY_EDGE_SCORE.get(edge, 35)
    else:
        # 非家庭：简述证据 + 关键词；原序作弱先验（模型常把更重要的写在前面）
        score += 50.0
        score += max(0.0, 20.0 - order * 1.5)

    # 简述长度 ≈ 证据厚度（封顶）
    score += min(len(summary), 240) / 4.0

    if index_names and title in index_names:
        score += 28.0

    blob = f"{title} {summary}"
    for kw, pts in CLOSENESS_KEYWORDS:
        if kw in blob:
            score += pts

    # 极弱的原序微调，避免完全同分时抖动
    score -= order * 0.01
    return score


def cap_hub_people(
    records: list[dict[str, Any]],
    *,
    index_names: set[str] | None = None,
    max_persons: int = MAX_PERSONS_PER_HUB,
) -> tuple[list[dict[str, Any]], list[str]]:
    """每个二级枢纽下直接人物按重要/紧密度保留最多 max_persons，并删其子孙。"""
    notes: list[str] = []
    by_hub: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    for i, r in enumerate(records):
        if _is_hub(r) or _level(r) != "二级":
            continue
        hub = str(r.get("所属一级关系") or "").strip()
        cat = _cat(r)
        if not hub:
            continue
        by_hub.setdefault((cat, hub), []).append((i, r))

    drop_titles: set[tuple[str, str, str]] = set()
    drop_names: set[str] = set()

    for (cat, hub), people in by_hub.items():
        if len(people) <= max_persons:
            continue
        ranked = sorted(
            people,
            key=lambda it: _importance_score(
                it[1], hub=hub, index_names=index_names, order=it[0]
            ),
            reverse=True,
        )
        kept = ranked[:max_persons]
        removed = ranked[max_persons:]
        kept_titles = [_title(r) for _, r in kept]
        removed_titles = [_title(r) for _, r in removed]
        notes.append(
            f"cap {cat}/{hub}: {len(people)}→{max_persons} "
            f"keep={kept_titles} drop={removed_titles}"
        )
        for _, r in removed:
            title = _title(r)
            drop_titles.add((cat, hub, title))
            drop_names.add(title)

    if not drop_names:
        return records, notes

    out: list[dict[str, Any]] = []
    for r in records:
        if _is_hub(r):
            out.append(r)
            continue
        cat = _cat(r)
        level = _level(r)
        title = _title(r)
        if level == "二级":
            hub = str(r.get("所属一级关系") or "").strip()
            if (cat, hub, title) in drop_titles:
                continue
            out.append(r)
            continue
        p2 = str(r.get("所属二级关系") or "").strip()
        p3 = str(r.get("所属三级关系") or "").strip()
        if p2 in drop_names or p3 in drop_names or title in drop_names:
            continue
        out.append(r)
    return out, notes


def drop_empty_hubs(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """删除其下已无二级人物的二级分类枢纽。"""
    notes: list[str] = []
    live: set[tuple[str, str]] = set()
    for r in records:
        if _is_hub(r) or _level(r) != "二级":
            continue
        hub = str(r.get("所属一级关系") or "").strip()
        if hub:
            live.add((_cat(r), hub))

    out: list[dict[str, Any]] = []
    for r in records:
        if _is_hub(r):
            key = (_cat(r), _title(r))
            if key not in live:
                notes.append(f"drop empty hub {key[0]}/{key[1]}")
                continue
        out.append(r)
    return out, notes


def sanitize_relation_records(
    records: list[dict[str, Any]],
    *,
    index_names: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """完整确定性清洗流水线。"""
    all_notes: list[str] = []
    cur = [dict(r) for r in records if isinstance(r, dict)]

    cur, notes = normalize_family_edges(cur)
    all_notes.extend(notes)

    cur, notes = apply_mutex(cur)
    all_notes.extend(notes)

    cur, notes = cap_hub_people(cur, index_names=index_names)
    all_notes.extend(notes)

    cur, notes = drop_empty_hubs(cur)
    all_notes.extend(notes)

    return cur, all_notes


def _self_check() -> None:
    sample = [
        {
            "关联史略名称": "测试帝",
            "关系ID": "HD-FAM-001",
            "关系类别": "家庭",
            "关系层级": "一级",
            "关系节点标题": "父母",
            "上级连接线标题": "",
            "关系简述": "父母枢纽",
            "节点类型": "二级分类",
        },
        {
            "关联史略名称": "测试帝",
            "关系ID": "HD-FAM-002",
            "关系类别": "家庭",
            "关系层级": "二级",
            "关系节点标题": "某祖",
            "上级连接线标题": "祖父",
            "关系简述": "祖父某某",
            "所属一级关系": "父母",
        },
        {
            "关联史略名称": "测试帝",
            "关系ID": "HD-FAM-003",
            "关系类别": "家庭",
            "关系层级": "二级",
            "关系节点标题": "某父",
            "上级连接线标题": "父亲",
            "关系简述": "生父，即位前后辅政甚力，笔墨甚多。" * 3,
            "所属一级关系": "父母",
        },
        {
            "关联史略名称": "测试帝",
            "关系ID": "HD-COL-001",
            "关系类别": "同僚",
            "关系层级": "一级",
            "关系节点标题": "臣子",
            "上级连接线标题": "",
            "关系简述": "臣子枢纽",
            "节点类型": "二级分类",
        },
    ]
    # 12 个臣子，应截到 10；含「丞相」者优先
    for i in range(12):
        sample.append(
            {
                "关联史略名称": "测试帝",
                "关系ID": f"HD-COL-{i+2:03d}",
                "关系类别": "同僚",
                "关系层级": "二级",
                "关系节点标题": f"臣{i}",
                "上级连接线标题": "政敌" if i == 0 else "",
                "关系简述": ("曾任丞相，总揽朝政。" if i == 11 else f"一般朝臣{i}"),
                "所属一级关系": "臣子",
            }
        )
    # 互斥：家庭某人同时在好友
    sample.append(
        {
            "关联史略名称": "测试帝",
            "关系ID": "HD-FRI-001",
            "关系类别": "好友",
            "关系层级": "一级",
            "关系节点标题": "好友",
            "上级连接线标题": "",
            "关系简述": "好友枢纽",
            "节点类型": "二级分类",
        }
    )
    sample.append(
        {
            "关联史略名称": "测试帝",
            "关系ID": "HD-FRI-002",
            "关系类别": "好友",
            "关系层级": "二级",
            "关系节点标题": "某父",
            "上级连接线标题": "",
            "关系简述": "误挂好友",
            "所属一级关系": "好友",
        }
    )

    out, notes = sanitize_relation_records(sample, index_names={"臣11"})
    titles = {_title(r) for r in out if not _is_hub(r)}
    assert "某祖" not in titles, titles
    assert "某父" in titles
    father = next(r for r in out if _title(r) == "某父" and _cat(r) == "家庭")
    assert _edge(father) == "父", father
    col_people = [
        r for r in out if _cat(r) == "同僚" and not _is_hub(r) and _level(r) == "二级"
    ]
    assert len(col_people) == 10, len(col_people)
    assert any(_title(r) == "臣11" for r in col_people), [_title(r) for r in col_people]
    assert not any(_cat(r) == "好友" and _title(r) == "某父" and not _is_hub(r) for r in out)
    print("sanitize_relations self-check OK")
    for n in notes:
        print(" ", n)


if __name__ == "__main__":
    _self_check()
