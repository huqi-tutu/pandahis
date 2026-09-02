"""人工确认后 promote 至 11 _versions，与 sync 分离。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from lib.verify import load_output


def _next_version(versions_dir: Path, entry_id: str, entry_name: str) -> str:
    stem = f"{entry_id}_{entry_name}" if entry_name else entry_id
    pattern = re.compile(rf"^{re.escape(stem)}\.v(\d+)\.json$")
    max_n = 0
    if versions_dir.is_dir():
        for p in versions_dir.iterdir():
            m = pattern.match(p.name)
            if m:
                max_n = max(max_n, int(m.group(1)))
    return f"v{max_n + 1}"


def promote_to_versions(
    entry_id: str,
    source_file: Path,
    *,
    versions_root: Path,
    entry_name: str = "",
    version: str | None = None,
    note: str = "",
) -> Tuple[bool, str, Path]:
    """复制产出到 11/_versions，标记为已确认。"""
    if not source_file.is_file():
        return False, f"源文件不存在: {source_file}", Path()
    data: Dict[str, Any] = json.loads(source_file.read_text(encoding="utf-8"))
    folder = versions_root / f"{entry_id}_{entry_name}" if entry_name else versions_root / entry_id
    folder.mkdir(parents=True, exist_ok=True)
    ver = (version or "").strip() or _next_version(folder, entry_id, entry_name)
    if not ver.startswith("v"):
        ver = f"v{ver}"
    data["翻译版本"] = ver
    meta = data.get("_pipeline_meta")
    if not isinstance(meta, dict):
        meta = {}
    meta = {
        **meta,
        "status": "confirmed",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(source_file),
    }
    data["_pipeline_meta"] = meta
    if note:
        data["_版本说明"] = note
    target = folder / f"{entry_id}_{entry_name}.{ver}.json" if entry_name else folder / f"{entry_id}.{ver}.json"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 同步标记源产出，便于后续 sync 读取
    if source_file.resolve() != target.resolve():
        src_meta = json.loads(source_file.read_text(encoding="utf-8"))
        src_meta["翻译版本"] = ver
        src_meta["_pipeline_meta"] = meta
        if note:
            src_meta["_版本说明"] = note
        source_file.write_text(json.dumps(src_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, f"已 promote → {target}（{ver}）", target


def stamp_pending_review(source_file: Path) -> None:
    """试跑产出标记 pending_review，阻断误 sync。"""
    if not source_file.is_file():
        return
    data: Dict[str, Any] = json.loads(source_file.read_text(encoding="utf-8"))
    meta = data.get("_pipeline_meta")
    if not isinstance(meta, dict):
        meta = {}
    if str(meta.get("status") or "").strip() == "confirmed":
        return
    meta = {**meta, "status": "pending_review"}
    data["_pipeline_meta"] = meta
    source_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def promote_from_output_dir(
    entry_id: str,
    out_dir: Path,
    *,
    versions_root: Path,
    entry_name: str = "",
    version: str | None = None,
    note: str = "",
) -> Tuple[bool, str, Path]:
    ok, data, errs = load_output(entry_id, out_dir, entry_name)
    if not ok:
        return False, "; ".join(errs) or "无法读取产出", Path()
    from lib.verify import output_path, resolve_output_path

    src = resolve_output_path(entry_id, out_dir, entry_name)
    if not src.is_file():
        src = output_path(entry_id, out_dir, entry_name)
    return promote_to_versions(
        entry_id,
        src,
        versions_root=versions_root,
        entry_name=entry_name,
        version=version,
        note=note,
    )
