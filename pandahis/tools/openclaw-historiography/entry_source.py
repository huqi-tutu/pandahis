"""史略条目来源（provenance）SSOT。

区分两条生产线：
  - 史料提取：二十四史标注 → merge_global_entries → 全局索引
  - 模型补全：朝代知识补全 → append 并入全局索引

JSON 字段名：史略来源
DB  字段名：entry_source
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

# JSON / 业务展示
SOURCE_EXTRACT = "史料提取"
SOURCE_SUPPLEMENT = "模型补全"

# DB 存储（英文枚举，便于索引与 API）
DB_EXTRACT = "extract"
DB_SUPPLEMENT = "supplement"

JSON_TO_DB = {
    SOURCE_EXTRACT: DB_EXTRACT,
    SOURCE_SUPPLEMENT: DB_SUPPLEMENT,
}
DB_TO_JSON = {v: k for k, v in JSON_TO_DB.items()}

VALID_JSON_VALUES = frozenset(JSON_TO_DB)
VALID_DB_VALUES = frozenset(DB_TO_JSON)

DYNASTY_SUPPLEMENT_MARKERS = frozenset({"朝代补全", "朝代知识补全"})


def infer_entry_source(entry: Dict[str, Any]) -> str:
    """从既有字段推断史略来源（用于回填）。"""
    explicit = str(entry.get("史略来源") or "").strip()
    if explicit in VALID_JSON_VALUES:
        return explicit

    mother = str(entry.get("母本著作") or "").strip()
    if mother in DYNASTY_SUPPLEMENT_MARKERS:
        return SOURCE_SUPPLEMENT

    sources = entry.get("来源著作") or []
    if isinstance(sources, list):
        for s in sources:
            if str(s).strip() in DYNASTY_SUPPLEMENT_MARKERS:
                return SOURCE_SUPPLEMENT

    return SOURCE_EXTRACT


def normalize_entry_source(entry: Dict[str, Any]) -> Dict[str, Any]:
    """确保条目含规范 史略来源 字段（不修改原 dict）。"""
    out = dict(entry)
    out["史略来源"] = infer_entry_source(entry)
    return out


def entry_source_to_db(value: str | None) -> str:
    key = str(value or "").strip()
    if key in JSON_TO_DB:
        return JSON_TO_DB[key]
    if key in DB_TO_JSON:
        return key
    return DB_EXTRACT


def entry_source_from_db(value: str | None) -> str:
    key = str(value or "").strip()
    return DB_TO_JSON.get(key, SOURCE_EXTRACT)


def is_supplement_entry(entry: Dict[str, Any]) -> bool:
    return infer_entry_source(entry) == SOURCE_SUPPLEMENT


def is_extract_entry(entry: Dict[str, Any]) -> bool:
    return infer_entry_source(entry) == SOURCE_EXTRACT


def backfill_entries(entries: Iterable[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
    """回填 entries 列表，返回 (新列表, 变更条数)。"""
    changed = 0
    out: List[Dict[str, Any]] = []
    for e in entries:
        inferred = infer_entry_source(e)
        if e.get("史略来源") != inferred:
            changed += 1
        item = dict(e)
        item["史略来源"] = inferred
        out.append(item)
    return out, changed
