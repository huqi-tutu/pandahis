"""史略翻译汇总 JSON：聚合单条产出。"""

from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

AGGREGATE_FILENAME = "史略翻译_汇总.json"
SCHEMA = "historiography-translate/v1"
_ENTRY_ID_RE = re.compile(r"^(GLBL_\d+|SHIJI_\d+_\d+)_")


def aggregate_path(output_dir: Path) -> Path:
    return output_dir / AGGREGATE_FILENAME


def _parse_entry_from_filename(path: Path) -> Tuple[str, str]:
    """从 {史略ID}_{史略名称}.json 解析 ID 与名称。"""
    stem = path.stem
    m = _ENTRY_ID_RE.match(stem)
    if not m:
        return "", stem
    entry_id = m.group(1)
    name = stem[len(entry_id) + 1 :]
    return entry_id, name


def _load_entry_file(path: Path) -> Dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    entry_id = str(data.get("史略ID") or "").strip()
    detail = data.get("翻译详情")
    source = data.get("史料原文")
    if not entry_id or not isinstance(detail, str) or not detail.strip():
        return None
    if not isinstance(source, dict):
        return None
    _, name_from_file = _parse_entry_from_filename(path)
    return {
        "史略ID": entry_id,
        "史略名称": name_from_file or entry_id,
        "翻译详情": detail,
        "史料原文": source,
    }


def collect_entries(output_dir: Path) -> List[Dict[str, Any]]:
    """扫描目录内全部单条 JSON（跳过 _work 与汇总文件）。"""
    if not output_dir.is_dir():
        return []
    by_id: Dict[str, Dict[str, Any]] = {}
    for path in sorted(output_dir.glob("*.json")):
        if path.name == AGGREGATE_FILENAME:
            continue
        item = _load_entry_file(path)
        if item:
            by_id[item["史略ID"]] = item
    return [by_id[k] for k in sorted(by_id)]


def build_aggregate_payload(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(entries),
        "entries": entries,
    }


def rebuild_aggregate(output_dir: Path) -> Tuple[Path, int]:
    """
    重建汇总 JSON。原子写入：失败不破坏旧文件。
    返回 (汇总路径, 条目数)。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = collect_entries(output_dir)
    payload = build_aggregate_payload(entries)
    target = aggregate_path(output_dir)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_dir,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)

    tmp_path.replace(target)
    return target, len(entries)
