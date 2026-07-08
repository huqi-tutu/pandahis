#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 data/史略索引_01至02.json 全量同步到 histomap.historical_box。

约定：
  - id = 史略ID（主键，唯一业务 ID）
  - parent_entry_id = 母本史略ID（可检索，非唯一）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "03索引标注条目" / "史略索引_01至02.json"
DEFAULT_EMPEROR_JSON = ROOT / "data" / "01历史坐标数据" / "帝王.json"

CIV_CODE_TO_ID: dict[str, int] = {
    "HX": 1, "CX": 2, "RB": 3, "DNY": 4, "ZY": 5, "BY": 6, "NY": 7, "XY": 8,
    "NO": 9, "DO": 10, "XO": 11, "BO": 12, "BF": 13, "XF": 14, "DF": 15,
    "ZM": 16, "BM": 17, "NM": 18,
}

# 标注 v3 七类 → historical_box.category_key（与 BoxCategorySupport.java 一致）
CATEGORY_MAP: dict[str, str] = {
    "君王": "junji",
    "君纪": "junji",  # 旧称兼容
    "宗戚": "zongqi",
    "宦官": "huanguan",
    "文臣": "wenchen",
    "武将": "wujiang",
    "蕃祚": "fanzhu",
    "庶众": "shuzhong",
    # 旧 skeleton / 其他著作（当前 560 条合并索引不含，保留映射供后续导入）
    "士臣": "shichen",
    "典制": "dianzhi",
    "事略": "shilue",
    "民录": "minlu",
    "论著": "lunzhu",
}

CATEGORY_LABELS: dict[str, str] = {
    "junji": "君王",
    "zongqi": "宗戚",
    "huanguan": "宦官",
    "wenchen": "文臣",
    "wujiang": "武将",
    "fanzhu": "蕃祚",
    "shuzhong": "庶众",
    "shichen": "士臣",
    "dianzhi": "典制",
    "shilue": "事略",
    "minlu": "民录",
    "lunzhu": "论著",
}

PRIORITY_TO_LEVEL: dict[str, int] = {
    "P0": 0,
    "P1": 1,
    "P2": 2,
    "P3": 3,
}

CHILD_TABLES = ("box_graph_edge", "box_graph_node", "box_critique", "box_relic")
USER_BOX_TABLES = ("user_favorite_box", "user_footprint", "user_box_tab_read")

BOX_FK_RESTORE: tuple[tuple[str, str], ...] = (
    ("box_graph_node", "fk_graph_node_box"),
    ("box_graph_edge", "fk_graph_edge_box"),
    ("box_critique", "fk_critique_box"),
    ("box_relic", "fk_relic_box"),
)


def load_emperor_name_index(json_path: Path) -> dict[str, str]:
    """帝王名称 → 帝王ID（唯一命中时用于修正 skeleton 旧 ID）。"""
    if not json_path.is_file():
        return {}
    data = json.loads(json_path.read_text(encoding="utf-8"))
    buckets: dict[str, list[str]] = {}
    for item in data:
        name = str(item.get("帝王名称", "")).strip()
        eid = str(item.get("帝王ID", "")).strip()
        if name and eid:
            buckets.setdefault(name, []).append(eid)
    return {name: ids[0] for name, ids in buckets.items() if len(ids) == 1}


def ensure_emperor_refs(cursor, rows: list[dict], emperor_json: Path) -> dict[str, int]:
    """确保 historical_emperor 含 box 引用的帝王（先按名称修正 ID，再补 stub）。"""
    stats = {"resolved_by_name": 0, "inserted_stub": 0}
    name_index = load_emperor_name_index(emperor_json)
    cursor.execute("SELECT id FROM historical_emperor")
    existing = {r["id"] for r in cursor.fetchall()}

    for row in rows:
        eid = str(row["emperor_id"]).strip()
        if eid in existing:
            continue
        name = str(row["emperor_name"]).strip()
        mapped = name_index.get(name)
        if mapped and mapped in existing:
            row["emperor_id"] = mapped
            stats["resolved_by_name"] += 1
            continue
        if mapped and mapped not in existing:
            eid = mapped
            row["emperor_id"] = mapped

        civ_code = str(row["civilization_code"]).strip()
        civ_id = CIV_CODE_TO_ID.get(civ_code)
        if civ_id is None:
            raise ValueError(f"未知文明ID: {civ_code}（帝王 {eid}）")

        cursor.execute(
            """
            INSERT INTO historical_emperor (
              id, name, ruler_name, regime_id, regime_name, dynasty_id, dynasty_name,
              civilization_l1_id, civilization_name, civilization_code,
              enthronement_year, abdication_year, reign_duration, tags,
              card_image_url, sort_order, status
            ) VALUES (
              %s, %s, NULL, %s, %s, %s, %s,
              %s, %s, %s,
              %s, %s, NULL, NULL,
              NULL, 0, 1
            )
            ON DUPLICATE KEY UPDATE name=VALUES(name)
            """,
            (
                eid,
                name,
                row["regime_id"],
                row["regime_name"],
                row["dynasty_id"],
                row["dynasty_name"],
                civ_id,
                row["civilization_name"],
                civ_code,
                row["start_year"],
                row["end_year"],
            ),
        )
        existing.add(eid)
        stats["inserted_stub"] += 1
    return stats


def load_entries(json_path: Path) -> list[dict]:
    with json_path.open(encoding="utf-8") as fp:
        payload = json.load(fp)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("JSON 顶层须含 entries 数组")
    return entries


def category_key(raw: str) -> str:
    key = CATEGORY_MAP.get(str(raw).strip())
    if key is None:
        raise ValueError(f"未知史略分类: {raw}")
    return key


def priority_level(raw: str | None) -> int | None:
    if raw is None:
        return None
    return PRIORITY_TO_LEVEL.get(str(raw).strip())


def build_original_ref_json(item: dict) -> str:
    payload = {
        "primarySource": item.get("主要史料出处"),
        "originalText": item.get("原文字句"),
        "originalLocation": item.get("原文出处"),
        "fineCoordinate": item.get("五级细坐标"),
        "paragraphAnchor": item.get("六级段落锚点"),
        "paragraphs": item.get("paragraphs", []),
        "mergeSources": item.get("合并来源", []),
        "sourceWorks": item.get("来源著作", []),
        "parentWork": item.get("母本著作"),
        "parentEntryId": item.get("母本史略ID"),
    }
    return json.dumps(payload, ensure_ascii=False)


def build_box_rows(entries: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, item in enumerate(entries):
        priority = str(item.get("优先级", "")).strip() or None
        rows.append(
            {
                "id": str(item["史略ID"]).strip(),
                "parent_entry_id": str(item["母本史略ID"]).strip(),
                "emperor_id": str(item["帝王ID"]).strip(),
                "regime_id": str(item["政权ID"]).strip(),
                "dynasty_id": str(item["朝代ID"]).strip(),
                "civilization_code": str(item["文明ID"]).strip(),
                "civilization_name": str(item["一级文明坐标"]).strip(),
                "dynasty_name": str(item["二级朝代坐标"]).strip(),
                "regime_name": str(item["三级政权坐标"]).strip(),
                "emperor_name": str(item["四级帝王坐标"]).strip(),
                "title": str(item["史略名称"]).strip(),
                "category_key": category_key(item["史略分类"]),
                "blurb": str(item["史略简介"]).strip(),
                "start_year": int(item["史略开始年"]),
                "end_year": int(item["史略结束年"]),
                "priority_code": priority,
                "priority_reason": str(item.get("优先级判定理由", "")).strip() or None,
                "importance_level": priority_level(priority),
                "peak_year": int(item["峰值年"]) if item.get("峰值年") is not None else None,
                "peak_reason": str(item.get("峰值原因", "")).strip() or None,
                "peak_type": str(item.get("峰值类型", "")).strip() or None,
                "primary_source": str(item.get("主要史料出处", "")).strip() or None,
                "original_text": str(item.get("原文字句", "")).strip() or None,
                "original_location": str(item.get("原文出处", "")).strip() or None,
                "fine_coordinate": str(item.get("五级细坐标", "")).strip() or None,
                "paragraph_anchor": str(item.get("六级段落锚点", "")).strip() or None,
                "parent_work": str(item.get("母本著作", "")).strip() or None,
                "source_entry_count": int(item.get("来源条目数", 0)),
                "paragraph_block_count": int(item.get("段落域数", 0)),
                "paragraphs_json": json.dumps(item.get("paragraphs", []), ensure_ascii=False),
                "merge_sources_json": json.dumps(item.get("合并来源", []), ensure_ascii=False),
                "source_works_json": json.dumps(item.get("来源著作", []), ensure_ascii=False),
                "original_ref_json": build_original_ref_json(item),
                "detail_md": None,
                "detail_md_flash": None,
                "detail_md_pro": None,
                "auto_filled": 1 if item.get("_auto_filled") else 0 if "_auto_filled" in item else None,
                "needs_llm": 1 if item.get("_needs_llm") else 0 if "_needs_llm" in item else None,
                "sort_order": index,
                "status": 1,
            }
        )
    return rows


def table_exists(cursor, name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """,
        (name,),
    )
    return cursor.fetchone()["cnt"] > 0


def drop_fk_if_exists(cursor, table: str, constraint: str) -> None:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
        """,
        (table, constraint),
    )
    if cursor.fetchone()["cnt"]:
        cursor.execute(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{constraint}`")


def drop_fks_referencing(cursor, referenced_table: str) -> None:
    cursor.execute(
        """
        SELECT TABLE_NAME, CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME = %s
        """,
        (referenced_table,),
    )
    for row in cursor.fetchall():
        drop_fk_if_exists(cursor, row["TABLE_NAME"], row["CONSTRAINT_NAME"])


def restore_box_child_fks(cursor) -> None:
    for table, constraint in BOX_FK_RESTORE:
        if not table_exists(cursor, table):
            continue
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt FROM information_schema.TABLE_CONSTRAINTS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
            """,
            (table, constraint),
        )
        if cursor.fetchone()["cnt"]:
            continue
        cursor.execute(
            f"ALTER TABLE `{table}` ADD CONSTRAINT `{constraint}` "
            f"FOREIGN KEY (box_id) REFERENCES historical_box (id)"
        )


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (table, column),
    )
    return cursor.fetchone()["cnt"] > 0


def index_exists(cursor, table: str, index_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        (table, index_name),
    )
    return cursor.fetchone()["cnt"] > 0


def create_historical_box(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE historical_box (
          id VARCHAR(64) PRIMARY KEY COMMENT '史略ID',
          parent_entry_id VARCHAR(64) NULL COMMENT '母本史略ID',
          emperor_id VARCHAR(128) NOT NULL COMMENT '帝王ID',
          regime_id VARCHAR(128) NOT NULL COMMENT '政权ID',
          dynasty_id VARCHAR(64) NOT NULL COMMENT '朝代ID',
          civilization_code VARCHAR(16) NOT NULL COMMENT '文明ID',
          civilization_name VARCHAR(64) NULL COMMENT '一级文明坐标',
          dynasty_name VARCHAR(128) NULL COMMENT '二级朝代坐标',
          regime_name VARCHAR(128) NULL COMMENT '三级政权坐标',
          emperor_name VARCHAR(128) NULL COMMENT '四级帝王坐标',
          title VARCHAR(128) NOT NULL COMMENT '史略名称',
          category_key VARCHAR(16) NOT NULL COMMENT '史略分类编码',
          blurb VARCHAR(64) NULL COMMENT '史略简介',
          start_year INT NOT NULL COMMENT '史略开始年',
          end_year INT NOT NULL COMMENT '史略结束年',
          priority_code VARCHAR(8) NULL COMMENT '优先级 P0-P3',
          priority_reason TEXT NULL COMMENT '优先级判定理由',
          importance_level TINYINT NULL COMMENT '由优先级推导',
          peak_year INT NULL COMMENT '峰值年',
          peak_reason TEXT NULL COMMENT '峰值原因',
          peak_type VARCHAR(64) NULL COMMENT '峰值类型',
          primary_source VARCHAR(256) NULL COMMENT '主要史料出处',
          original_text TEXT NULL COMMENT '原文字句',
          original_location VARCHAR(128) NULL COMMENT '原文出处',
          fine_coordinate VARCHAR(128) NULL COMMENT '五级细坐标',
          paragraph_anchor VARCHAR(256) NULL COMMENT '六级段落锚点',
          parent_work VARCHAR(32) NULL COMMENT '母本著作',
          source_entry_count INT NULL COMMENT '来源条目数',
          paragraph_block_count INT NULL COMMENT '段落域数',
          paragraphs_json LONGTEXT NULL COMMENT 'paragraphs',
          merge_sources_json LONGTEXT NULL COMMENT '合并来源',
          source_works_json LONGTEXT NULL COMMENT '来源著作',
          original_ref_json LONGTEXT NULL COMMENT 'API 兼容原文引用',
          detail_md TEXT NULL,
          detail_md_flash TEXT NULL,
          detail_md_pro TEXT NULL,
          auto_filled TINYINT NULL COMMENT '自动补全年份',
          needs_llm TINYINT NULL COMMENT '待 LLM 补全',
          sort_order INT NOT NULL DEFAULT 0,
          status TINYINT NOT NULL DEFAULT 1,
          INDEX idx_box_parent_entry (parent_entry_id),
          INDEX idx_box_emperor (emperor_id),
          INDEX idx_box_regime (regime_id),
          INDEX idx_box_dynasty (dynasty_id),
          INDEX idx_box_category (category_key),
          CONSTRAINT fk_box_emperor FOREIGN KEY (emperor_id) REFERENCES historical_emperor (id),
          CONSTRAINT fk_box_regime FOREIGN KEY (regime_id) REFERENCES historical_regime (id),
          CONSTRAINT fk_box_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='史略'
        """
    )


def ensure_schema(cursor) -> None:
    if not table_exists(cursor, "historical_box"):
        create_historical_box(cursor)
        restore_box_child_fks(cursor)
        return

    if index_exists(cursor, "historical_box", "uk_historical_box_business_code"):
        cursor.execute("ALTER TABLE historical_box DROP INDEX uk_historical_box_business_code")

    if column_exists(cursor, "historical_box", "business_code") and not column_exists(
        cursor, "historical_box", "parent_entry_id"
    ):
        cursor.execute(
            "ALTER TABLE historical_box CHANGE COLUMN business_code parent_entry_id "
            "VARCHAR(64) NULL COMMENT '母本史略ID'"
        )

    if column_exists(cursor, "historical_box", "parent_entry_id") and not index_exists(
        cursor, "historical_box", "idx_box_parent_entry"
    ):
        cursor.execute("ALTER TABLE historical_box ADD INDEX idx_box_parent_entry (parent_entry_id)")

    if not column_exists(cursor, "historical_box", "peak_year"):
        cursor.execute("ALTER TABLE historical_box ADD COLUMN peak_year INT NULL COMMENT '峰值年' AFTER importance_level")
    if not column_exists(cursor, "historical_box", "peak_reason"):
        cursor.execute("ALTER TABLE historical_box ADD COLUMN peak_reason TEXT NULL COMMENT '峰值原因' AFTER peak_year")
    if not column_exists(cursor, "historical_box", "peak_type"):
        cursor.execute("ALTER TABLE historical_box ADD COLUMN peak_type VARCHAR(64) NULL COMMENT '峰值类型' AFTER peak_reason")


def rebuild_schema(cursor) -> None:
    for table in CHILD_TABLES:
        if table_exists(cursor, table):
            cursor.execute(f"DELETE FROM `{table}`")

    for table in USER_BOX_TABLES:
        if table_exists(cursor, table):
            cursor.execute(f"DELETE FROM `{table}`")

    drop_fks_referencing(cursor, "historical_box")

    if table_exists(cursor, "historical_box"):
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'historical_box'
              AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """
        )
        for row in cursor.fetchall():
            drop_fk_if_exists(cursor, "historical_box", row["CONSTRAINT_NAME"])
        cursor.execute("DROP TABLE historical_box")

    create_historical_box(cursor)
    restore_box_child_fks(cursor)


def upsert_boxes(cursor, rows: list[dict]) -> int:
    sql = """
        INSERT INTO historical_box (
          id, parent_entry_id, emperor_id, regime_id, dynasty_id,
          civilization_code, civilization_name, dynasty_name, regime_name, emperor_name,
          title, category_key, blurb, start_year, end_year,
          priority_code, priority_reason, importance_level, peak_year, peak_reason, peak_type,
          primary_source, original_text, original_location, fine_coordinate, paragraph_anchor,
          parent_work, source_entry_count, paragraph_block_count,
          paragraphs_json, merge_sources_json, source_works_json, original_ref_json,
          detail_md, detail_md_flash, detail_md_pro,
          auto_filled, needs_llm, sort_order, status
        ) VALUES (
          %(id)s, %(parent_entry_id)s, %(emperor_id)s, %(regime_id)s, %(dynasty_id)s,
          %(civilization_code)s, %(civilization_name)s, %(dynasty_name)s, %(regime_name)s, %(emperor_name)s,
          %(title)s, %(category_key)s, %(blurb)s, %(start_year)s, %(end_year)s,
          %(priority_code)s, %(priority_reason)s, %(importance_level)s, %(peak_year)s, %(peak_reason)s, %(peak_type)s,
          %(primary_source)s, %(original_text)s, %(original_location)s, %(fine_coordinate)s, %(paragraph_anchor)s,
          %(parent_work)s, %(source_entry_count)s, %(paragraph_block_count)s,
          %(paragraphs_json)s, %(merge_sources_json)s, %(source_works_json)s, %(original_ref_json)s,
          %(detail_md)s, %(detail_md_flash)s, %(detail_md_pro)s,
          %(auto_filled)s, %(needs_llm)s, %(sort_order)s, %(status)s
        )
        ON DUPLICATE KEY UPDATE
          parent_entry_id = VALUES(parent_entry_id),
          emperor_id = VALUES(emperor_id),
          regime_id = VALUES(regime_id),
          dynasty_id = VALUES(dynasty_id),
          civilization_code = VALUES(civilization_code),
          civilization_name = VALUES(civilization_name),
          dynasty_name = VALUES(dynasty_name),
          regime_name = VALUES(regime_name),
          emperor_name = VALUES(emperor_name),
          title = VALUES(title),
          category_key = VALUES(category_key),
          blurb = VALUES(blurb),
          start_year = VALUES(start_year),
          end_year = VALUES(end_year),
          priority_code = VALUES(priority_code),
          priority_reason = VALUES(priority_reason),
          importance_level = VALUES(importance_level),
          peak_year = VALUES(peak_year),
          peak_reason = VALUES(peak_reason),
          peak_type = VALUES(peak_type),
          primary_source = VALUES(primary_source),
          original_text = VALUES(original_text),
          original_location = VALUES(original_location),
          fine_coordinate = VALUES(fine_coordinate),
          paragraph_anchor = VALUES(paragraph_anchor),
          parent_work = VALUES(parent_work),
          source_entry_count = VALUES(source_entry_count),
          paragraph_block_count = VALUES(paragraph_block_count),
          paragraphs_json = VALUES(paragraphs_json),
          merge_sources_json = VALUES(merge_sources_json),
          source_works_json = VALUES(source_works_json),
          original_ref_json = VALUES(original_ref_json),
          auto_filled = VALUES(auto_filled),
          needs_llm = VALUES(needs_llm),
          sort_order = VALUES(sort_order),
          status = VALUES(status)
    """
    count = 0
    for row in rows:
        cursor.execute(sql, row)
        count += 1
    return count


def update_priority_peak_fields(cursor, rows: list[dict]) -> int:
    sql = """
        UPDATE historical_box
        SET priority_code = %(priority_code)s,
            priority_reason = %(priority_reason)s,
            importance_level = %(importance_level)s,
            peak_year = %(peak_year)s,
            peak_reason = %(peak_reason)s,
            peak_type = %(peak_type)s
        WHERE id = %(id)s
    """
    count = 0
    for row in rows:
        cursor.execute(sql, row)
        count += cursor.rowcount
    return count


def delete_child_rows_for_boxes(cursor, box_ids: list[str]) -> dict[str, int]:
    """删除引用 historical_box 的子表行（FK 为 NO ACTION，须先于父表删除）。"""
    if not box_ids:
        return {}
    stats: dict[str, int] = {}
    chunk_size = 500
    for i in range(0, len(box_ids), chunk_size):
        chunk = box_ids[i : i + chunk_size]
        placeholders = ", ".join(["%s"] * len(chunk))
        for table in (*CHILD_TABLES, "historical_box_detail"):
            if not table_exists(cursor, table):
                continue
            cursor.execute(f"DELETE FROM `{table}` WHERE box_id IN ({placeholders})", chunk)
            stats[table] = stats.get(table, 0) + cursor.rowcount
    return stats


def purge_user_refs_for_boxes(cursor, box_ids: list[str]) -> dict[str, int]:
    if not box_ids:
        return {}
    stats: dict[str, int] = {}
    chunk_size = 500
    for i in range(0, len(box_ids), chunk_size):
        chunk = box_ids[i : i + chunk_size]
        placeholders = ", ".join(["%s"] * len(chunk))
        for table in USER_BOX_TABLES:
            if not table_exists(cursor, table):
                continue
            cursor.execute(f"DELETE FROM `{table}` WHERE box_id IN ({placeholders})", chunk)
            stats[table] = stats.get(table, 0) + cursor.rowcount
    return stats


def list_orphan_box_ids(cursor, json_ids: list[str]) -> list[str]:
    if not json_ids:
        cursor.execute("SELECT id FROM historical_box")
        return [row["id"] for row in cursor.fetchall()]
    placeholders = ", ".join(["%s"] * len(json_ids))
    cursor.execute(
        f"SELECT id FROM historical_box WHERE id NOT IN ({placeholders})",
        json_ids,
    )
    return [row["id"] for row in cursor.fetchall()]


def delete_orphans(cursor, rows: list[dict]) -> int:
    json_ids = [row["id"] for row in rows]
    orphan_ids = list_orphan_box_ids(cursor, json_ids)
    if orphan_ids:
        purge_user_refs_for_boxes(cursor, orphan_ids)
        delete_child_rows_for_boxes(cursor, orphan_ids)
    placeholders = ", ".join(["%s"] * len(json_ids))
    cursor.execute(
        f"DELETE FROM historical_box WHERE id NOT IN ({placeholders})",
        json_ids,
    )
    return cursor.rowcount


def cleanup_reused_box_ids(cursor, json_ids: list[str]) -> dict[str, int]:
    """同 GLBL 编号换人：清除旧翻译/子表，避免错挂到新人物。"""
    if not json_ids:
        return {}
    stats = delete_child_rows_for_boxes(cursor, json_ids)
    stats.update(purge_user_refs_for_boxes(cursor, json_ids))
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--emperor-json", type=Path, default=DEFAULT_EMPEROR_JSON)
    parser.add_argument("--rebuild", action="store_true", help="重建表并清空子表/用户足迹")
    parser.add_argument("--mysql-host", default="49.235.165.220")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-user", default="histomap_admin")
    parser.add_argument("--mysql-password", default="pandahis#666")
    parser.add_argument("--mysql-db", default="histomap")
    parser.add_argument(
        "--priority-peak-only",
        action="store_true",
        help="只按 JSON 更新优先级/判定理由/峰值字段，不清理子表、不更新其他列",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    entries = load_entries(args.json)
    rows = build_box_rows(entries)

    if args.dry_run:
        cats: dict[str, int] = {}
        for row in rows:
            cats[row["category_key"]] = cats.get(row["category_key"], 0) + 1
        print(f"dry-run: 将导入 {len(rows)} 条史略到 historical_box")
        print("分类分布:", cats)
        return 0

    try:
        import pymysql
    except ImportError:
        print("需要: pip install pymysql", file=sys.stderr)
        return 1

    conn = pymysql.connect(
        host=args.mysql_host,
        port=args.mysql_port,
        user=args.mysql_user,
        password=args.mysql_password,
        database=args.mysql_db,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=15,
        read_timeout=300,
        write_timeout=300,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            if args.rebuild:
                rebuild_schema(cursor)
            else:
                ensure_schema(cursor)
            if args.priority_peak_only:
                updated = update_priority_peak_fields(cursor, rows)
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM historical_box WHERE peak_year IS NOT NULL"
                )
                peak_count = cursor.fetchone()["cnt"]
                conn.commit()
                print(f"完成: 更新优先级/峰值字段 {updated} 条，peak_year 非空 {peak_count} 条")
                return 0
            json_ids = [row["id"] for row in rows]
            emperor_stats = ensure_emperor_refs(cursor, rows, args.emperor_json)
            if emperor_stats:
                print("帝王 FK 预处理:", emperor_stats)
            reused_stats = cleanup_reused_box_ids(cursor, json_ids)
            if reused_stats:
                print("已清理复用 ID 子表/用户引用:", reused_stats)
            upserted = upsert_boxes(cursor, rows)
            deleted = delete_orphans(cursor, rows)
            cursor.execute("SELECT COUNT(*) AS cnt FROM historical_box")
            final_count = cursor.fetchone()["cnt"]
            cursor.execute(
                "SELECT category_key, COUNT(*) AS cnt FROM historical_box GROUP BY category_key ORDER BY cnt DESC"
            )
            categories = cursor.fetchall()
        conn.commit()
        print(
            f"完成: 导入/更新 {upserted} 条史略，"
            f"删除多余 {deleted} 条，"
            f"historical_box 共 {final_count} 条"
        )
        for row in categories:
            print(f"  {row['category_key']}: {row['cnt']}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
