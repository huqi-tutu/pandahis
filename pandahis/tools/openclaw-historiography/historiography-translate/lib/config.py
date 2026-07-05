"""翻译编排器路径与默认配置。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

import sys

TRANSLATE_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = TRANSLATE_DIR.parent
if str(SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(SKILLS_DIR))
from paths_config import (  # noqa: E402
    DEFAULT_GLOBAL_INDEX,
    histograph_paths,
)
ANNOTATE_DIR = SKILLS_DIR / "historiography-annotate"
COMPOSE_DIR = SKILLS_DIR / "historiography-compose"

DEFAULT_INDEX = DEFAULT_GLOBAL_INDEX
DEFAULT_AGENT = os.environ.get("TRANSLATE_AGENT", "hist-worker")


def load_dotenv() -> None:
    """加载 openclaw-historiography/.env（不覆盖已有环境变量）。"""
    env_file = SKILLS_DIR / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())

# 唯一翻译规则 SSOT（与 compose 共用）
RULES_FILE = COMPOSE_DIR / "references" / "翻译规则.md"


def translate_state_dir() -> Path:
    d = histograph_paths()["translate_state"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def paths() -> Dict[str, Path]:
    p = histograph_paths()
    state = translate_state_dir()
    return {
        **p,
        "state_db": state / "state.sqlite",
        "events": state / "events.jsonl",
        "rules": RULES_FILE,
    }


def default_index_path() -> Path:
    env = os.environ.get("GLOBAL_INDEX_PATH")
    if env:
        return Path(env)
    return paths()["global_index"]


def chunk_settings() -> Dict[str, int]:
    from lib.chunking import (
        MAX_CHARS_PER_CHUNK,
        MAX_PARAS_PER_CHUNK,
        MODE_MIN_MOTHER_CHARS,
        MODE_MIN_PARAGRAPHS,
    )

    return {
        "max_paras_per_chunk": MAX_PARAS_PER_CHUNK,
        "max_chars_per_chunk": MAX_CHARS_PER_CHUNK,
        "mode_min_paragraphs": MODE_MIN_PARAGRAPHS,
        "mode_min_mother_chars": MODE_MIN_MOTHER_CHARS,
    }
