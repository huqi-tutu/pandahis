"""史略详情来源（provenance）SSOT。

与 entry_source（条目来源）正交：
  - 史料顺译：historiography-translate 流水线（母本顺译 + enrich）
  - 大模型撰写：compose-detail / 朝代知识补全详情

JSON 字段名：详情来源
DB  字段名：detail_source
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

from entry_source import infer_entry_source, is_supplement_entry

# JSON / 业务展示
SOURCE_TRANSLATE = "史料顺译"
SOURCE_COMPOSE = "大模型撰写"

# DB 存储
DB_TRANSLATE = "translate"
DB_COMPOSE = "compose"

JSON_TO_DB = {
    SOURCE_TRANSLATE: DB_TRANSLATE,
    SOURCE_COMPOSE: DB_COMPOSE,
}
DB_TO_JSON = {v: k for k, v in JSON_TO_DB.items()}

VALID_JSON_VALUES = frozenset(JSON_TO_DB)
VALID_DB_VALUES = frozenset(DB_TO_JSON)

COMPOSE_MARKERS = frozenset(
    {
        "一期待compose",
        "薄标注待补",
        "朝代补全",
        "朝代知识补全",
        "dynasty_supplement",
        "compose-detail",
    }
)


def infer_detail_source(
    entry: Dict[str, Any],
    *,
    translate_ids: Set[str] | None = None,
    dynasty_detail_ids: Set[str] | None = None,
) -> str | None:
    """从条目字段与详情落盘集合推断详情来源。"""
    explicit = str(entry.get("详情来源") or "").strip()
    if explicit in VALID_JSON_VALUES:
        return explicit

    eid = str(entry.get("史略ID") or entry.get("id") or "").strip()
    if translate_ids and eid and eid in translate_ids:
        return SOURCE_TRANSLATE
    if dynasty_detail_ids and eid and eid in dynasty_detail_ids:
        return SOURCE_COMPOSE

    supplement_hint = str(entry.get("补全来源") or "").strip()
    if supplement_hint in COMPOSE_MARKERS:
        return SOURCE_COMPOSE

    mother = str(entry.get("母本著作") or "").strip()
    if mother in {"朝代补全", "朝代知识补全"}:
        return SOURCE_COMPOSE

    if is_supplement_entry(entry):
        return SOURCE_COMPOSE

    return None


def detail_source_to_db(value: str | None) -> str | None:
    key = str(value or "").strip()
    if not key:
        return None
    if key in JSON_TO_DB:
        return JSON_TO_DB[key]
    if key in DB_TO_JSON:
        return key
    return None


def detail_source_from_db(value: str | None) -> str:
    key = str(value or "").strip()
    return DB_TO_JSON.get(key, "")


def normalize_detail_source(entry: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(entry)
    inferred = infer_detail_source(entry)
    if inferred:
        out["详情来源"] = inferred
    return out


def backfill_detail_sources(
    entries: Iterable[Dict[str, Any]],
    *,
    translate_ids: Set[str] | None = None,
    dynasty_detail_ids: Set[str] | None = None,
) -> tuple[List[Dict[str, Any]], int]:
    changed = 0
    out: List[Dict[str, Any]] = []
    for e in entries:
        inferred = infer_detail_source(
            e,
            translate_ids=translate_ids,
            dynasty_detail_ids=dynasty_detail_ids,
        )
        item = dict(e)
        if inferred and item.get("详情来源") != inferred:
            changed += 1
            item["详情来源"] = inferred
        out.append(item)
    return out, changed
