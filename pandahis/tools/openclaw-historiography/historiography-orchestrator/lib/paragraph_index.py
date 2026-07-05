"""批生成段落索引 JSON。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

from lib.config import ANNOTATE_DIR, get_work_config, paths

_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_SKILLS_DIR))
from paths_config import resolve_split_dir  # noqa: E402

sys.path.insert(0, str(ANNOTATE_DIR))
from paragraph_utils import split_paragraphs, split_mode_for_work  # noqa: E402


def list_volume_files(work_id: str) -> List[Tuple[str, Path]]:
    """返回 [(vol_3d, path), ...] 按卷号排序。"""
    cfg = get_work_config(work_id)
    split = resolve_split_dir(cfg["split_dir"])
    if not split.is_dir():
        raise FileNotFoundError(f"拆分目录不存在: {split}")

    out: List[Tuple[str, Path]] = []
    for fp in sorted(split.glob(f"{work_id}_*.txt")):
        m = re.search(rf"{re.escape(work_id)}_(\d{{3}})_", fp.name)
        if m:
            out.append((m.group(1), fp))
    return out


def build_index_for_file(work_id: str, vol: str, src: Path, mode: str) -> dict:
    text = src.read_text(encoding="utf-8")
    paras = split_paragraphs(text, mode)
    return {
        "work": work_id,
        "vol": vol,
        "source_file": src.name,
        "source_path": str(src.relative_to(paths()["data"])),
        "paragraph_mode": mode,
        "total": len(paras),
        "paragraphs": [
            {"id": i, "text": t}
            for i, t in enumerate(paras, 1)
        ],
    }


def write_index(work_id: str, vol: str, data: dict) -> Path:
    out_dir = paths()["paragraph_index"]
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = out_dir / f"{work_id}_{vol}.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fp


def bootstrap_indexes(work_id: str) -> List[str]:
    cfg = get_work_config(work_id)
    mode = cfg.get("paragraph_mode") or split_mode_for_work(work_id)
    vols = []
    for vol, fp in list_volume_files(work_id):
        data = build_index_for_file(work_id, vol, fp, mode)
        write_index(work_id, vol, data)
        vols.append(vol)
    return vols
