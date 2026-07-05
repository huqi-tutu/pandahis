"""历史图谱工作流路径（项目 data 目录 SSOT）。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

# pandahis/pandahis/tools/openclaw-historiography/paths_config.py → pandahis/pandahis
DEFAULT_HISTOGRAPH_ROOT = Path(__file__).resolve().parents[2]

DIR_DATA = "data"
DIR_AUTH_SOURCES = "00原文母本"
SUBDIR_AUTH_SOURCES = "二十四史原文"
DIR_SOURCES = "02二十四史拆分后"
DIR_ANNOTATIONS = "03索引标注条目"
DIR_TRANSLATIONS = "04史料翻译"
DIR_INTERMEDIATE = "05工作流中间产物"

SUBDIR_INTERMEDIATE_ANNOTATE = "标注"
SUBDIR_INTERMEDIATE_TRANSLATE = "翻译"
SUBDIR_INTERMEDIATE_ORCHESTRATOR = "编排"
SUBDIR_TRANSLATE_QUEUE = "队列"
SUBDIR_ORCHESTRATOR_DECISIONS = "decisions"

SUBDIR_PARAGRAPH_INDEX = "段落索引"
SUBDIR_PROGRESS = "标注进度"
SUBDIR_AUDIT = "标注审计"
SUBDIR_STATS = "标注统计"
SUBDIR_REFS = "参考文献"

DEFAULT_GLOBAL_INDEX = "史略索引_01至02.json"
TRANSLATE_AGGREGATE_FILENAME = "史略翻译_汇总.json"

# 禁止作为 HISTOGRAPH_ROOT 的外部目录（防止产出跑到 OpenClaw / 旧桌面目录）
FORBIDDEN_ROOTS = (
    Path.home() / ".openclaw-autoclaw",
    Path.home() / ".openclaw",
    Path.home() / "Desktop" / "历史图谱",
)


def get_histograph_root() -> Path:
    return Path(os.environ.get("HISTOGRAPH_ROOT", DEFAULT_HISTOGRAPH_ROOT))


def ensure_workflow_data_dirs(data: Path) -> None:
    """确保 data 下各产出 / 中间产物目录存在。"""
    for name in (DIR_SOURCES, DIR_ANNOTATIONS, DIR_TRANSLATIONS, DIR_INTERMEDIATE):
        (data / name).mkdir(parents=True, exist_ok=True)
    intermediate = data / DIR_INTERMEDIATE
    for sub in (
        SUBDIR_INTERMEDIATE_ANNOTATE,
        SUBDIR_INTERMEDIATE_TRANSLATE,
        SUBDIR_INTERMEDIATE_ORCHESTRATOR,
    ):
        (intermediate / sub).mkdir(parents=True, exist_ok=True)
    (intermediate / SUBDIR_INTERMEDIATE_TRANSLATE / SUBDIR_TRANSLATE_QUEUE).mkdir(
        parents=True, exist_ok=True
    )
    (intermediate / SUBDIR_INTERMEDIATE_ORCHESTRATOR / SUBDIR_ORCHESTRATOR_DECISIONS).mkdir(
        parents=True, exist_ok=True
    )
    (intermediate / SUBDIR_INTERMEDIATE_ORCHESTRATOR / "locks").mkdir(
        parents=True, exist_ok=True
    )
    (data / DIR_AUTH_SOURCES / SUBDIR_AUTH_SOURCES).mkdir(parents=True, exist_ok=True)


def validate_histograph_root(root: Path | None = None) -> Path:
    """确保数据根目录落在项目内，禁止误指 OpenClaw 或旧桌面目录。"""
    resolved = (root or get_histograph_root()).resolve()
    expected = DEFAULT_HISTOGRAPH_ROOT.resolve()

    if os.environ.get("HISTOGRAPH_ALLOW_EXTERNAL_ROOT") == "1":
        return resolved

    if resolved != expected:
        raise RuntimeError(
            "HISTOGRAPH_ROOT 必须指向项目 data 根目录。\n"
            f"  当前: {resolved}\n"
            f"  期望: {expected}\n"
            "请勿使用 pandahis/pandahis 或 OpenClaw 目录。"
            "若确需临时例外，可设 HISTOGRAPH_ALLOW_EXTERNAL_ROOT=1。"
        )

    for forbidden in FORBIDDEN_ROOTS:
        forbidden_resolved = forbidden.resolve()
        if resolved == forbidden_resolved or forbidden_resolved in resolved.parents:
            raise RuntimeError(f"HISTOGRAPH_ROOT 指向禁止目录: {resolved}")

    data = resolved / DIR_DATA
    for name in (DIR_SOURCES, DIR_ANNOTATIONS, DIR_TRANSLATIONS):
        sub = data / name
        if not sub.is_dir():
            raise RuntimeError(
                f"项目 data 子目录缺失: {sub}\n"
                "请确认在 pandahis/pandahis/data 下已创建 02/03/04 目录。"
            )

    ensure_workflow_data_dirs(data)
    return resolved


def histograph_paths() -> Dict[str, Path]:
    root = validate_histograph_root()
    data = root / DIR_DATA
    sources = data / DIR_SOURCES
    annotations = data / DIR_ANNOTATIONS
    translations = data / DIR_TRANSLATIONS
    intermediate = data / DIR_INTERMEDIATE
    orchestrator_state = intermediate / SUBDIR_INTERMEDIATE_ORCHESTRATOR
    translate_work = intermediate / SUBDIR_INTERMEDIATE_TRANSLATE
    translate_state = translate_work / SUBDIR_TRANSLATE_QUEUE
    return {
        "root": root,
        "data": data,
        "auth_sources": data / DIR_AUTH_SOURCES / SUBDIR_AUTH_SOURCES,
        "sources": sources,
        "annotations": annotations,
        "paragraph_index": annotations / SUBDIR_PARAGRAPH_INDEX,
        "translate_output": translations,
        "intermediate": intermediate,
        "annotate_work": intermediate / SUBDIR_INTERMEDIATE_ANNOTATE,
        "translate_work": translate_work,
        "translate_state": translate_state,
        "global_index": annotations / DEFAULT_GLOBAL_INDEX,
        "stats": annotations / SUBDIR_STATS,
        "refs": annotations / SUBDIR_REFS / "参考资料清单.md",
        "audit": annotations / SUBDIR_AUDIT,
        "progress": annotations / SUBDIR_PROGRESS,
        "state_root": orchestrator_state,
        "decisions": orchestrator_state / SUBDIR_ORCHESTRATOR_DECISIONS,
        "allow_force": orchestrator_state / "allow_force",
    }


def resolve_split_dir(split_dir: str) -> Path:
    """catalog split_dir → 原文拆分目录。"""
    p = Path(split_dir)
    paths = histograph_paths()
    if p.is_absolute():
        return p
    # 新格式：01史记_拆分后
    if p.parts == (p.name,) or "/" not in split_dir.replace("\\", "/"):
        return paths["sources"] / split_dir
    # 兼容旧格式：data/02二十四史拆分后/01史记_拆分后 或 data/02.../01史记_拆分后
    if split_dir.startswith(DIR_SOURCES):
        return paths["data"] / split_dir
    legacy = paths["data"] / DIR_SOURCES / split_dir.split("/")[-1]
    if legacy.is_dir():
        return legacy
    return paths["data"] / split_dir
