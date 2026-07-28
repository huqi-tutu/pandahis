"""07 人物关系 JSON → box_graph_node / box_graph_edge（字段 SSOT）。"""

from __future__ import annotations

import json
import re
from typing import Any

LEVEL_NUM = {"一级": 1, "二级": 2, "三级": 3, "四级": 4}
PARENT_FIELD = {
    "二级": "所属一级关系",
    "三级": "所属二级关系",
    "四级": "所属三级关系",
}
PREV_LEVEL = {"二级": "一级", "三级": "二级", "四级": "三级"}
CENTER_KEY = "center"
LEGACY_CATEGORY = {"君臣": "同僚", "敌对": "外敌"}
CATEGORY_ORDER = ["家庭", "同僚", "师从", "外敌", "好友"]
CATEGORY_NODE_KEYS = {
    "家庭": "cat_fam",
    "同僚": "cat_col",
    "师从": "cat_mas",
    "外敌": "cat_foe",
    "好友": "cat_fri",
}


def category_node_key(cat: str) -> str:
    cat = normalize_category(cat)
    key = CATEGORY_NODE_KEYS.get(cat)
    if key:
        return key
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", cat.strip()).strip("_")
    return f"cat_{safe}" if safe else "cat_other"


def collect_categories(records: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for rec in records:
        cat = normalize_category(str(rec.get("关系类别") or ""))
        if cat and cat not in seen:
            seen.add(cat)
            ordered.append(cat)
    ordered.sort(key=lambda c: CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99)
    return ordered


def sql_escape(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


def component_id(prefix: str, box_id: str, suffix: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", suffix)[:48]
    return f"{box_id}_{prefix}_{safe}"


def box_component_columns(component: str, box_id: str, shilue_name: str) -> str:
    return f"{sql_escape(component)}, {sql_escape(box_id)}, {sql_escape(shilue_name)}, {sql_escape(box_id)}"


def normalize_category(raw: str) -> str:
    cat = str(raw or "").strip()
    return LEGACY_CATEGORY.get(cat, cat)


def node_key_from_rid(rid: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9_]+", "_", str(rid or "").strip().lower())
    return key[:60] or "rel_node"


def build_lineage(subject: str, rec: dict[str, Any]) -> str:
    parts = [subject.strip()]
    for field in ("所属一级关系", "所属二级关系", "所属三级关系"):
        val = str(rec.get(field) or "").strip()
        if val:
            parts.append(val)
    return " › ".join(parts) if len(parts) > 1 else ""


def extra_json_from_record(rec: dict[str, Any], subject: str) -> dict[str, Any]:
    """extra_json 与 07 JSON 字段对齐（SSOT）。"""
    ej: dict[str, Any] = {
        "关系ID": str(rec.get("关系ID") or "").strip(),
        "关系类别": normalize_category(str(rec.get("关系类别") or "")),
        "关系层级": str(rec.get("关系层级") or "").strip(),
        "上级连接线标题": str(rec.get("上级连接线标题") or "").strip(),
        "关系简述": str(rec.get("关系简述") or "").strip(),
    }
    for field in ("所属一级关系", "所属二级关系", "所属三级关系"):
        val = str(rec.get(field) or "").strip()
        if val:
            ej[field] = val
    chain = build_lineage(subject, rec)
    if chain:
        ej["关系链"] = chain
    rid = str(rec.get("record_id") or "").strip()
    if rid:
        ej["record_id"] = rid
    return ej


def node_type_for_category(cat: str) -> str:
    return "person"


def node_type_for_record(rec: dict[str, Any]) -> str:
    return "person"


def build_import_sql(box_id: str, subject: str, records: list[dict[str, Any]]) -> list[str]:
    if not records:
        raise ValueError("empty records")
    subject = subject.strip()
    stmts: list[str] = []

    stmts.append(f"DELETE FROM box_graph_edge WHERE box_id={sql_escape(box_id)};")
    stmts.append(f"DELETE FROM box_graph_node WHERE box_id={sql_escape(box_id)};")

    center_cid = component_id("REL", box_id, CENTER_KEY)
    stmts.append(
        "INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) "
        f"VALUES ({box_component_columns(center_cid, box_id, subject)}, {sql_escape(CENTER_KEY)}, 'event', "
        f"{sql_escape(subject)}, '{{}}');"
    )

    categories = collect_categories(records)
    cat_key_by_name: dict[str, str] = {}
    for cat in categories:
        ck = category_node_key(cat)
        cat_key_by_name[cat] = ck
        cat_cid = component_id("REL", box_id, ck)
        cat_ej = json.dumps({"关系类别": cat, "isCategoryNode": True}, ensure_ascii=False)
        stmts.append(
            "INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) "
            f"VALUES ({box_component_columns(cat_cid, box_id, subject)}, {sql_escape(ck)}, 'category', "
            f"{sql_escape(cat)}, {sql_escape(cat_ej)});"
        )
        stmts.append(
            "INSERT INTO box_graph_edge (box_id, from_node_key, to_node_key, label) "
            f"VALUES ({sql_escape(box_id)}, {sql_escape(CENTER_KEY)}, {sql_escape(ck)}, {sql_escape(cat)});"
        )

    title_level_to_key: dict[tuple[str, str], str] = {}
    parsed: list[tuple[dict[str, Any], str, str, dict[str, Any]]] = []

    for rec in records:
        title = str(rec.get("关系节点标题") or "").strip()
        level = str(rec.get("关系层级") or "").strip()
        rid = str(rec.get("关系ID") or "").strip()
        if not title or level not in LEVEL_NUM:
            raise ValueError(f"invalid record: {rid or title!r} level={level!r}")
        nk = node_key_from_rid(rid or f"{title}_{level}")
        cat = normalize_category(str(rec.get("关系类别") or ""))
        ej = extra_json_from_record(rec, subject)
        cid = component_id("REL", box_id, rid) if rid else component_id("REL", box_id, nk)
        parsed.append((rec, nk, cid, ej))
        title_level_to_key[(title, level)] = nk

    for rec, nk, cid, ej in parsed:
        title = str(rec.get("关系节点标题") or "").strip()
        level = str(rec.get("关系层级") or "").strip()
        cat = normalize_category(str(rec.get("关系类别") or ""))
        et = node_type_for_record(rec)
        ej_str = json.dumps(ej, ensure_ascii=False)
        stmts.append(
            "INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) "
            f"VALUES ({box_component_columns(cid, box_id, subject)}, {sql_escape(nk)}, {sql_escape(et)}, "
            f"{sql_escape(title)}, {sql_escape(ej_str)});"
        )

        edge_label = str(rec.get("上级连接线标题") or "关系").strip()[:32]
        if level == "一级":
            from_key = cat_key_by_name.get(cat, CENTER_KEY)
        else:
            pf = PARENT_FIELD.get(level)
            parent_title = str(rec.get(pf) or "").strip() if pf else ""
            parent_level = PREV_LEVEL.get(level, "")
            from_key = title_level_to_key.get((parent_title, parent_level), "")
            if not from_key:
                raise ValueError(
                    f"parent not found for {title!r} level={level}: "
                    f"need ({parent_title!r}, {parent_level})"
                )
        stmts.append(
            "INSERT INTO box_graph_edge (box_id, from_node_key, to_node_key, label) "
            f"VALUES ({sql_escape(box_id)}, {sql_escape(from_key)}, {sql_escape(nk)}, {sql_escape(edge_label)});"
        )

    return stmts
