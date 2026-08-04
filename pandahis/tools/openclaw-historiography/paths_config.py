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
DIR_ANNOTATIONS_V2 = "10新标注条目"
DIR_TRANSLATIONS = "04史料翻译"
DIR_TRANSLATIONS_V2 = "11新标注条目翻译"
DIR_INTERMEDIATE = "05工作流中间产物"
DIR_DYNASTY_KNOWLEDGE = "06朝代知识补全"
DIR_PERSON_RELATIONS = "07人物关系"
DIR_COMMENTARY = "08评述"
DIR_WITNESS = "09见证"

SUBDIR_INTERMEDIATE_ANNOTATE = "标注"
SUBDIR_INTERMEDIATE_ANNOTATE_V2 = "标注-v2"
SUBDIR_INTERMEDIATE_DYNASTY_KNOWLEDGE = "朝代知识补全"
SUBDIR_INTERMEDIATE_PERSON_RELATIONS = "人物关系补全"
SUBDIR_INTERMEDIATE_COMMENTARY_WITNESS = "评述见证补全"
SUBDIR_DYNASTY_KNOWLEDGE_ENTRIES = "索引条目"
SUBDIR_DYNASTY_KNOWLEDGE_DETAILS = "详情"
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
DEFAULT_GLOBAL_INDEX_V2 = "史略索引_史记汉书.json"
DEFAULT_GLOBAL_INDEX_ONLINE = "史略索引_online.json"

DIR_ONLINE_INDEX = "12线上史略索引"

VALID_ANNOTATE_TRACKS = frozenset({"v1", "v2"})
ENV_ANNOTATE_TRACK = "HIST_ANNOTATE_TRACK"
TRANSLATE_AGGREGATE_FILENAME = "史略翻译_汇总.json"
DYNASTY_KNOWLEDGE_DETAIL_AGGREGATE = "朝代知识详情_汇总.json"

# 禁止作为 HISTOGRAPH_ROOT 的外部目录（防止产出跑到 OpenClaw / 旧桌面目录）
FORBIDDEN_ROOTS = (
    Path.home() / ".openclaw-autoclaw",
    Path.home() / ".openclaw",
    Path.home() / "Desktop" / "历史图谱",
)


def get_histograph_root() -> Path:
    return Path(os.environ.get("HISTOGRAPH_ROOT", DEFAULT_HISTOGRAPH_ROOT))


def get_annotate_track() -> str:
    """标注轨道：v1 → data/03；v2 → data/10。环境变量 HIST_ANNOTATE_TRACK。"""
    track = (os.environ.get(ENV_ANNOTATE_TRACK) or "v1").strip().lower()
    if track not in VALID_ANNOTATE_TRACKS:
        raise RuntimeError(
            f"{ENV_ANNOTATE_TRACK} 非法: {track!r}，允许 {sorted(VALID_ANNOTATE_TRACKS)}"
        )
    return track


def _annotations_dir(data: Path, track: str) -> Path:
    if track == "v2":
        return data / DIR_ANNOTATIONS_V2
    return data / DIR_ANNOTATIONS


def _paragraph_index_dir(data: Path, track: str, annotations: Path) -> Path:
    """段落索引 SSOT：仅 data/03索引标注条目/段落索引/（v1/v2 共用，与原文拆分绑定）。"""
    _ = (track, annotations)  # v2 不在 10 下维护段落索引副本
    return data / DIR_ANNOTATIONS / SUBDIR_PARAGRAPH_INDEX


def ensure_workflow_data_dirs(data: Path) -> None:
    """确保 data 下各产出 / 中间产物目录存在。"""
    for name in (
        DIR_SOURCES,
        DIR_ANNOTATIONS,
        DIR_ANNOTATIONS_V2,
        DIR_TRANSLATIONS,
        DIR_INTERMEDIATE,
        DIR_DYNASTY_KNOWLEDGE,
        DIR_PERSON_RELATIONS,
        DIR_COMMENTARY,
        DIR_WITNESS,
        DIR_ONLINE_INDEX,
    ):
        (data / name).mkdir(parents=True, exist_ok=True)
    intermediate = data / DIR_INTERMEDIATE
    for sub in (
        SUBDIR_INTERMEDIATE_ANNOTATE,
        SUBDIR_INTERMEDIATE_ANNOTATE_V2,
        SUBDIR_INTERMEDIATE_DYNASTY_KNOWLEDGE,
        SUBDIR_INTERMEDIATE_TRANSLATE,
        SUBDIR_INTERMEDIATE_ORCHESTRATOR,
    ):
        (intermediate / sub).mkdir(parents=True, exist_ok=True)
    ann_v1 = data / DIR_ANNOTATIONS
    for sub in (SUBDIR_PARAGRAPH_INDEX, SUBDIR_PROGRESS, SUBDIR_AUDIT, SUBDIR_STATS):
        (ann_v1 / sub).mkdir(parents=True, exist_ok=True)
    ann_v2 = data / DIR_ANNOTATIONS_V2
    for sub in (SUBDIR_PROGRESS, SUBDIR_AUDIT, SUBDIR_STATS):
        (ann_v2 / sub).mkdir(parents=True, exist_ok=True)
    (intermediate / SUBDIR_INTERMEDIATE_TRANSLATE / SUBDIR_TRANSLATE_QUEUE).mkdir(
        parents=True, exist_ok=True
    )
    (intermediate / SUBDIR_INTERMEDIATE_ORCHESTRATOR / SUBDIR_ORCHESTRATOR_DECISIONS).mkdir(
        parents=True, exist_ok=True
    )
    (intermediate / SUBDIR_INTERMEDIATE_ORCHESTRATOR / "locks").mkdir(
        parents=True, exist_ok=True
    )
    dynasty_root = data / DIR_DYNASTY_KNOWLEDGE
    (dynasty_root / SUBDIR_DYNASTY_KNOWLEDGE_ENTRIES).mkdir(parents=True, exist_ok=True)
    (dynasty_root / SUBDIR_DYNASTY_KNOWLEDGE_DETAILS).mkdir(parents=True, exist_ok=True)
    (data / DIR_PERSON_RELATIONS).mkdir(parents=True, exist_ok=True)
    (data / DIR_COMMENTARY).mkdir(parents=True, exist_ok=True)
    (data / DIR_WITNESS).mkdir(parents=True, exist_ok=True)
    (intermediate / SUBDIR_INTERMEDIATE_PERSON_RELATIONS / "logs").mkdir(parents=True, exist_ok=True)
    (intermediate / SUBDIR_INTERMEDIATE_COMMENTARY_WITNESS / "logs").mkdir(parents=True, exist_ok=True)
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
    track = get_annotate_track()
    sources = data / DIR_SOURCES
    annotations = _annotations_dir(data, track)
    annotations_v1 = data / DIR_ANNOTATIONS
    global_index_name = (
        DEFAULT_GLOBAL_INDEX_V2 if track == "v2" else DEFAULT_GLOBAL_INDEX
    )
    translations = data / DIR_TRANSLATIONS
    intermediate = data / DIR_INTERMEDIATE
    orchestrator_state = intermediate / SUBDIR_INTERMEDIATE_ORCHESTRATOR
    translate_work = intermediate / SUBDIR_INTERMEDIATE_TRANSLATE
    translate_state = translate_work / SUBDIR_TRANSLATE_QUEUE
    annotate_work = (
        intermediate / SUBDIR_INTERMEDIATE_ANNOTATE_V2
        if track == "v2"
        else intermediate / SUBDIR_INTERMEDIATE_ANNOTATE
    )
    return {
        "root": root,
        "data": data,
        "annotate_track": track,  # type: ignore[dict-item]
        "auth_sources": data / DIR_AUTH_SOURCES / SUBDIR_AUTH_SOURCES,
        "sources": sources,
        "annotations": annotations,
        "annotations_v1": annotations_v1,
        "paragraph_index": _paragraph_index_dir(data, track, annotations),
        "translate_output": translations,
        "translate_output_v2": data / DIR_TRANSLATIONS_V2,
        "intermediate": intermediate,
        "annotate_work": annotate_work,
        "dynasty_knowledge_work": intermediate / SUBDIR_INTERMEDIATE_DYNASTY_KNOWLEDGE,
        "dynasty_knowledge": data / DIR_DYNASTY_KNOWLEDGE,
        "dynasty_knowledge_entries": data / DIR_DYNASTY_KNOWLEDGE / SUBDIR_DYNASTY_KNOWLEDGE_ENTRIES,
        "dynasty_knowledge_details": data / DIR_DYNASTY_KNOWLEDGE / SUBDIR_DYNASTY_KNOWLEDGE_DETAILS,
        "dynasty_knowledge_detail_aggregate": (
            data / DIR_DYNASTY_KNOWLEDGE / SUBDIR_DYNASTY_KNOWLEDGE_DETAILS / DYNASTY_KNOWLEDGE_DETAIL_AGGREGATE
        ),
        "person_relations": data / DIR_PERSON_RELATIONS,
        "person_relations_work": intermediate / SUBDIR_INTERMEDIATE_PERSON_RELATIONS,
        "commentary": data / DIR_COMMENTARY,
        "witness": data / DIR_WITNESS,
        "commentary_witness_work": intermediate / SUBDIR_INTERMEDIATE_COMMENTARY_WITNESS,
        "translate_work": translate_work,
        "translate_state": translate_state,
        "global_index": annotations / global_index_name,
        "global_index_online": data / DIR_ONLINE_INDEX / DEFAULT_GLOBAL_INDEX_ONLINE,
        "online_index_dir": data / DIR_ONLINE_INDEX,
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
