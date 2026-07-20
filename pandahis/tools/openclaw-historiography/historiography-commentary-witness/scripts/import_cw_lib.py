"""08评述 / 09见证 JSON → box_critique / box_relic。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def sql_escape(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


def truncate(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def make_summary(description: str, max_len: int = 80) -> str:
    """从文物介绍截取简介（DB summary 字段）。"""
    text = re.sub(r"\s+", "", description or "")
    if not text:
        return ""
    return truncate(text, max_len)


def build_critique_sql(doc: dict[str, Any]) -> list[str]:
    box_id = str(doc.get("史略ID") or "").strip()
    name = str(doc.get("史略名称") or "").strip()
    if not box_id:
        raise ValueError("缺少史略ID")
    stmts = [
        f"DELETE FROM box_critique WHERE box_id={sql_escape(box_id)};",
    ]
    entries = doc.get("entries") or []
    if not entries:
        return stmts
    for i, e in enumerate(entries, start=1):
        cid = str(e.get("评述ID") or f"{box_id}_P{i:02d}").strip()
        title = truncate(str(e.get("评述标题") or "").strip(), 128)
        author = truncate(str(e.get("评述人") or "").strip() or "佚名", 64)
        era = truncate(str(e.get("评述年代") or "").strip() or "年代不详", 64)
        content = str(e.get("评述内容") or "").strip()
        source = truncate(str(e.get("评述著作") or "").strip(), 256) or None
        blurb = truncate(str(e.get("评述简介") or "").strip(), 256) or None
        if not content:
            continue
        stmts.append(
            "INSERT INTO box_critique "
            "(component_id, shilue_id, shilue_name, box_id, title, author, era_text, year_value, content, source, blurb, sort_order) "
            f"VALUES ({sql_escape(cid)}, {sql_escape(box_id)}, {sql_escape(name)}, {sql_escape(box_id)}, "
            f"{sql_escape(title)}, {sql_escape(author)}, {sql_escape(era)}, NULL, "
            f"{sql_escape(content)}, {sql_escape(source)}, {sql_escape(blurb)}, {i});"
        )
    return stmts


def build_relic_sql(doc: dict[str, Any]) -> list[str]:
    box_id = str(doc.get("史略ID") or "").strip()
    name = str(doc.get("史略名称") or "").strip()
    if not box_id:
        raise ValueError("缺少史略ID")
    stmts = [
        f"DELETE FROM box_relic WHERE box_id={sql_escape(box_id)};",
    ]
    entries = doc.get("entries") or []
    if not entries:
        return stmts
    for i, e in enumerate(entries, start=1):
        cid = str(e.get("文物ID") or f"{box_id}_W{i:02d}").strip()
        title = truncate(str(e.get("文物标题") or "").strip(), 128)
        museum = truncate(str(e.get("现藏地点") or "").strip(), 128) or None
        desc = str(e.get("文物介绍") or "").strip()
        img = str(e.get("文物图片") or "").strip()
        img_sql = "NULL" if not img else sql_escape(truncate(img, 512))
        pcode = truncate(str(e.get("文物优先级") or "").strip(), 8) or None
        preason = str(e.get("优先级判定理由") or "").strip() or None
        summary = make_summary(desc, 80) or None
        if not title:
            continue
        stmts.append(
            "INSERT INTO box_relic "
            "(component_id, shilue_id, shilue_name, box_id, name, image_url, summary, description, museum, priority_code, priority_reason, sort_order) "
            f"VALUES ({sql_escape(cid)}, {sql_escape(box_id)}, {sql_escape(name)}, {sql_escape(box_id)}, "
            f"{sql_escape(title)}, {img_sql}, {sql_escape(summary)}, {sql_escape(desc) if desc else 'NULL'}, "
            f"{sql_escape(museum)}, {sql_escape(pcode)}, {sql_escape(preason)}, {i});"
        )
    return stmts


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def execute_mysql(stmts: list[str], *, host: str, port: int, user: str, password: str, db: str) -> None:
    import pymysql  # type: ignore

    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            for sql in stmts:
                cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
