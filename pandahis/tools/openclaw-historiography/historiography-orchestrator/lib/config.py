"""Orchestrator 路径与 catalog 加载。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import sys

ORCH_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = ORCH_DIR.parent
if str(SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(SKILLS_DIR))
from paths_config import histograph_paths  # noqa: E402
ANNOTATE_DIR = SKILLS_DIR / "historiography-annotate"
PIPELINE_DIR = SKILLS_DIR / "historiography-pipeline"
AUDIT_DIR = SKILLS_DIR / "historiography-audit"
CATALOG_PATH = ORCH_DIR / "catalog" / "works.json"


def orch_state_dir() -> Path:
    d = histograph_paths()["state_root"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def paths() -> Dict[str, Path]:
    p = histograph_paths()
    state = orch_state_dir()
    return {
        **p,
        "state_db": state / "state.sqlite",
        "events": state / "events.jsonl",
        "locks": state / "locks",
    }


def load_catalog() -> Dict[str, Any]:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_work_config(work_id: str) -> Dict[str, Any]:
    cat = load_catalog()
    works = cat.get("works", {})
    if work_id not in works:
        raise KeyError(f"catalog 中未配置著作: {work_id}")
    return works[work_id]


def queue_order() -> List[str]:
    return load_catalog().get("queue_order", [])
