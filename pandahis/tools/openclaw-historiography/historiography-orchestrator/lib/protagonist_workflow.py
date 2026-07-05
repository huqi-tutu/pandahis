"""Step1 主轴人物理解：LLM 据著作+卷名+常识先定 protagonists，再与 blocks/skeleton 双重校验。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.config import ANNOTATE_DIR, get_work_config, paths
from lib.blocks_workflow import blocks_path, volume_display_name
from lib.volume_manifest import (
    infer_narrative_mode,
    manifest_payload_errors,
    normalize_manifest,
)

sys.path.insert(0, str(ANNOTATE_DIR))
from identity_gate import (  # noqa: E402
    cross_check_protagonists_blocks,
    cross_check_protagonists_skeleton,
    validate_protagonists_identity,
)


def use_protagonist_phase(work: str) -> bool:
    cfg = get_work_config(work)
    if cfg.get("step1_protagonist_phase") is False:
        return False
    return True


def protagonists_path(work: str, vol: str) -> Path:
    vol = vol.zfill(3)
    wf = paths()["annotate_work"]
    wf.mkdir(parents=True, exist_ok=True)
    return wf / f"{work}_{vol}_protagonists.json"


def load_protagonists(work: str, vol: str) -> Optional[dict]:
    fp = protagonists_path(work, vol)
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def protagonists_payload_errors(obj: Any, *, work: str = "", vol: str = "") -> List[str]:
    return manifest_payload_errors(obj, work=work, vol=vol)


def normalize_protagonists_file(work: str, vol: str) -> List[str]:
    """君王类主轴名用帝王表别名自动归一为标准名（夏禹→禹、商汤→成汤）。

    脚本既然能解析标准名，就直接改写落盘，避免「LLM 用通称→被拦→人工」。
    返回变更日志；无法解析的名字不动（留给 identity_gate 报错）。
    """
    fp = protagonists_path(work, vol)
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    from emperor_resolve import build_emperor_info_index, resolve_emperor_label  # noqa: E402
    from category_priority import (  # noqa: E402
        normalize_category_fields,
        volume_category_overrides,
    )

    eidx = build_emperor_info_index()
    logs: List[str] = []
    changed = False
    vol_overrides = volume_category_overrides(work, vol)
    cat_logs = normalize_category_fields(
        data.get("protagonists") or [],
        emperor_index=eidx,
        volume_overrides=vol_overrides,
    )
    if cat_logs:
        logs.extend(cat_logs)
        changed = True
    for item in data.get("protagonists") or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        cat = (item.get("category") or "").strip()
        if cat != "君王" or not name or name in eidx:
            continue
        info, method = resolve_emperor_label(name, work_id=work, emperor_index=eidx)
        if info and info.get("emperor") and info["emperor"] != name:
            item["name"] = info["emperor"]
            logs.append(f"{name} → {info['emperor']} ({method})")
            changed = True
    if changed:
        fp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    volume_name = (data.get("volume_name") or "").strip()
    norm_data, norm_logs = normalize_manifest(data, volume_name=volume_name)
    if norm_logs:
        logs.extend(norm_logs)
        fp.write_text(
            json.dumps(norm_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return logs


def protagonists_valid(work: str, vol: str, index: dict) -> Tuple[bool, str]:
    fp = protagonists_path(work, vol)
    if not fp.exists():
        return False, "protagonists 文件不存在"
    normalize_protagonists_file(work, vol)
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"protagonists JSON 解析失败: {exc}"
    errs = protagonists_payload_errors(data, work=work, vol=vol)
    if errs:
        return False, "；".join(errs)
    volume_name = volume_display_name(work, vol, index)
    mode = infer_narrative_mode(data)
    if mode == "skip":
        return True, f"skip · {data.get('skip_reason') or '非叙事卷'}"
    ok_id, id_msg = validate_protagonists_identity(
        work, vol, data, volume_name=volume_name
    )
    if not ok_id:
        return False, id_msg
    n = len(data.get("protagonists") or [])
    return True, f"主轴 {n} 人 · {mode} · {id_msg}"


def validate_dual(
    work: str,
    vol: str,
    index: dict,
    *,
    blocks_data: Optional[dict] = None,
) -> Tuple[bool, str]:
    """第二道：LLM 主轴清单 ↔ blocks 人物集合须完全一致。"""
    ok_p, p_msg = protagonists_valid(work, vol, index)
    if not ok_p:
        return False, f"主轴理解未过: {p_msg}"
    manifest = load_protagonists(work, vol)
    if not manifest:
        return False, "缺少 protagonists.json"
    if blocks_data is None:
        bp = blocks_path(work, vol)
        if not bp.exists():
            return False, "blocks 不存在，无法双重校验"
        blocks_data = json.loads(bp.read_text(encoding="utf-8"))
    ok_x, x_msg = cross_check_protagonists_blocks(manifest, blocks_data)
    if not ok_x:
        return False, x_msg
    return True, f"双重校验 OK · {p_msg} · {x_msg}"


def validate_dual_skeleton(work: str, vol: str, skeleton_data: dict, *, index: dict) -> Tuple[bool, str]:
    """短卷 skeleton 模式：protagonists ↔ entries 一致。"""
    idx = index
    ok_p, p_msg = protagonists_valid(work, vol, idx)
    if not ok_p:
        return False, p_msg
    manifest = load_protagonists(work, vol)
    if not manifest:
        return False, "缺少 protagonists.json"
    ok_x, x_msg = cross_check_protagonists_skeleton(manifest, skeleton_data)
    if not ok_x:
        return False, x_msg
    return True, f"双重校验 OK · {x_msg}"


def format_manifest_for_prompt(data: dict) -> str:
    mode = infer_narrative_mode(data)
    lines = [
        "【主轴人物清单 — Step1a 已确认，Step1b blocks/entries 须逐字一致】",
        f"卷名: {data.get('volume_name') or '(见索引)'}",
        f"叙事模式 narrative_mode: {mode}",
    ]
    if mode == "skip":
        lines.append(f"skip_reason: {data.get('skip_reason') or '(须填写)'}")
        lines.append("本卷 skip，不建 blocks/entries。")
        return "\n".join(lines)
    if mode in ("single", "fanzuo"):
        lines.append(
            "本卷为单人/蕃祚整卷叙事：编排器可机械划块（排除卷首+评述），"
            "你只需确认 exclude 边界，勿逐段拆条。"
        )
    for item in data.get("protagonists") or []:
        name = (item.get("name") or "").strip()
        cat = (item.get("category") or "").strip()
        rationale = (item.get("rationale") or "").strip()
        lines.append(f"- {name!r} · {cat!r} — {rationale[:120]}")
    lines.append(
        "禁止增删改上述主轴人物；段落划分可以不同，但 blocks/entries 的 name+category 集合必须相同。"
    )
    return "\n".join(lines)


def protagonist_retry_needed(feedback: str) -> bool:
    fb = feedback or ""
    keys = (
        "主轴理解",
        "双重校验",
        "protagonists",
        "人物身份门",
        "exclude 内容门",
        "南汉高祖",
        "孝文皇帝",
        "缺少主轴",
        "name+category",
    )
    return any(k in fb for k in keys)
