"""长卷 Step1 方案 B：blocks 草稿 → expand_blocks → 标准 skeleton。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from lib.config import ANNOTATE_DIR, get_work_config, paths

sys.path.insert(0, str(ANNOTATE_DIR))
from expand_blocks import expand_blocks, merge_entry_paragraphs  # noqa: E402
from lib_config import VALID_EXCLUDE_REASONS  # noqa: E402
from protagonist_metadata import merge_protagonist_metadata  # noqa: E402

WORK_ENTRY_PREFIX: Dict[str, str] = {
    "01史记": "SHIJI",
    "01A尚书": "SHANGSHU",
    "02汉书": "HANSHU",
    "03后汉书": "HOUHANSHU",
    "04三国志": "SANGUOZHI",
}

# LLM 常见误名 → 帝王.json「帝王名称」
BLOCK_NAME_CORRECTIONS: Dict[str, str] = {
    "南汉高祖": "汉高祖",
    "孝文皇帝": "汉文帝",
}


def long_volume_threshold(work: str) -> int:
    cfg = get_work_config(work)
    return int(cfg.get("long_volume_paragraph_threshold", 40))


def entry_id_prefix(work: str) -> str:
    cfg = get_work_config(work)
    prefix = (cfg.get("entry_id_prefix") or "").strip()
    if prefix:
        return prefix
    return WORK_ENTRY_PREFIX.get(work, "ENT")


def use_blocks_step1(work: str, total_paragraphs: int) -> bool:
    cfg = get_work_config(work)
    if cfg.get("step1_blocks_mode") is False:
        return False
    return total_paragraphs >= long_volume_threshold(work)


def blocks_path(work: str, vol: str) -> Path:
    vol = vol.zfill(3)
    wf = paths()["annotate_work"]
    wf.mkdir(parents=True, exist_ok=True)
    return wf / f"{work}_{vol}_blocks.json"


def volume_display_name(work: str, vol: str, index: dict) -> str:
    src = (index.get("source_file") or "").strip()
    stem = Path(src).stem if src else f"{work}_{vol.zfill(3)}"
    prefix = f"{work}_{vol.zfill(3)}_"
    name = stem[len(prefix) :] if stem.startswith(prefix) else stem
    return re.sub(r"第[一二三四五六七八九十百零]+(?:章|节|卷)?$", "", name)


def normalize_exclude_reason(raw: str) -> Tuple[str, bool]:
    """将 LLM 可能带说明的 exclude_reason 收敛为 VALID_EXCLUDE_REASONS 枚举。"""
    s = (raw or "").strip()
    if s in VALID_EXCLUDE_REASONS:
        return s, False
    for sep in ("：", ":", "—", "－", "-", "·", "（", "("):
        head = s.split(sep, 1)[0].strip()
        if head in VALID_EXCLUDE_REASONS:
            return head, True
    for valid in sorted(VALID_EXCLUDE_REASONS, key=len, reverse=True):
        if s.startswith(valid) or valid in s:
            return valid, True
    keyword_map = (
        ("太史公", "太史公曰"),
        ("世系", "世系链"),
        ("过渡", "过渡叙事"),
        ("纪年", "纯纪年"),
        ("志书", "志书数据"),
        ("艺文", "艺文目录"),
        ("卷首", "卷首标题"),
        ("小标题", "篇内小标题"),
        ("无故事", "无故事弧"),
    )
    for kw, reason in keyword_map:
        if kw in s:
            return reason, True
    return "其他", True


def normalize_blocks_draft(
    data: dict,
    *,
    work_id: str = "",
    vol: str = "",
) -> Tuple[dict, List[str]]:
    """就地规范化 blocks 草稿（exclude_reason、君王标准名等），返回 (draft, 变更日志)。"""
    logs: List[str] = []
    draft = dict(data)
    vol_z = vol.zfill(3) if vol else ""
    new_excludes: List[dict] = []
    for item in draft.get("excludes") or []:
        if not isinstance(item, dict):
            new_excludes.append(item)
            continue
        row = dict(item)
        raw = (row.get("exclude_reason") or "").strip()
        normalized, changed = normalize_exclude_reason(raw)
        if changed:
            logs.append(f"exclude P{row.get('paragraph_from')}-P{row.get('paragraph_to')}: {raw!r} → {normalized!r}")
            row["exclude_reason"] = normalized
        new_excludes.append(row)
    draft["excludes"] = new_excludes

    if work_id:
        sys.path.insert(0, str(ANNOTATE_DIR))
        from emperor_resolve import build_emperor_info_index, resolve_emperor_label  # noqa: E402
        from category_priority import (  # noqa: E402
            normalize_category_fields,
            volume_category_overrides,
        )

        eidx = build_emperor_info_index()
        vol_overrides = volume_category_overrides(work_id, vol_z)
        cat_logs = normalize_category_fields(
            draft.get("blocks") or [],
            emperor_index=eidx,
            volume_overrides=vol_overrides,
        )
        logs.extend(cat_logs)
        new_blocks: List[dict] = []
        for item in draft.get("blocks") or []:
            if not isinstance(item, dict):
                new_blocks.append(item)
                continue
            row = dict(item)
            name = (row.get("name") or "").strip()
            cat = (row.get("category") or "").strip()
            if name in BLOCK_NAME_CORRECTIONS:
                fixed = BLOCK_NAME_CORRECTIONS[name]
                logs.append(f"block 误名 {name!r} → {fixed!r}")
                row["name"] = fixed
                name = fixed
            if cat == "君王":
                if name not in eidx:
                    info, method = resolve_emperor_label(
                        name, work_id=work_id, emperor_index=eidx
                    )
                    if info and info["emperor"] != name:
                        logs.append(f"block {name!r} → {info['emperor']!r} ({method})")
                        row["name"] = info["emperor"]
                    elif name not in eidx:
                        logs.append(f"⚠️ block 君王 {name!r} 不在帝王.json，须人工修正")
            new_blocks.append(row)
        draft["blocks"] = new_blocks

    return draft, logs


def normalize_blocks_file(blocks_file: Path, *, work_id: str = "", expected_total: int = 0) -> List[str]:
    """读取 blocks JSON，规范化后若变更则写回。返回变更日志。"""
    if not blocks_file.exists():
        return []
    vol = ""
    if not work_id:
        m = re.match(r"^(\d{2}[^_]+)_(\d{3})_", blocks_file.name)
        if m:
            work_id, vol = m.group(1), m.group(2)
    data = json.loads(blocks_file.read_text(encoding="utf-8"))
    draft, logs = normalize_blocks_draft(data, work_id=work_id, vol=vol)
    if not expected_total and work_id and vol:
        try:
            from lib import gates as _gates

            expected_total = int(_gates.load_paragraph_index(work_id, vol)["total"])
        except Exception:
            expected_total = 0
    if expected_total and draft.get("total_paragraphs") != expected_total:
        logs.append(
            f"total_paragraphs {draft.get('total_paragraphs')} → {expected_total}（段落索引）"
        )
        draft["total_paragraphs"] = expected_total
    if logs:
        blocks_file.write_text(
            json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return logs


def blocks_payload_errors(obj: Any, *, expected_total: int) -> List[str]:
    if not isinstance(obj, dict):
        return ["须为 JSON 对象"]
    errors: List[str] = []
    total = obj.get("total_paragraphs")
    if not isinstance(total, int) or total <= 0:
        errors.append("total_paragraphs 须为正整数")
    elif expected_total and total != expected_total:
        errors.append(f"total_paragraphs={total} ≠ 段落索引 {expected_total}")
    blocks = obj.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        errors.append("blocks 须为非空数组")
    else:
        for item in blocks[:5]:
            if not isinstance(item, dict):
                errors.append("blocks 每项须为对象")
                break
            for key in ("name", "category", "paragraph_from", "paragraph_to"):
                if key not in item:
                    errors.append(f"blocks 缺少 {key}")
                    break
    if "entries" in obj and obj.get("entries"):
        errors.append("blocks 草稿禁止含 entries（由脚本展开）")
    return errors


def blocks_valid(blocks_file: Path, index: dict) -> Tuple[bool, str]:
    if not blocks_file.exists():
        return False, "blocks 文件不存在"
    normalize_blocks_file(blocks_file, expected_total=int(index["total"]))
    try:
        data = json.loads(blocks_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"blocks JSON 解析失败: {exc}"
    errs = blocks_payload_errors(data, expected_total=int(index["total"]))
    if errs:
        return False, "；".join(errs)
    draft = dict(data)
    draft["total_paragraphs"] = int(index["total"])
    vol_m = re.match(r"^(\d{2}[^_]+)_(\d{3})_", blocks_file.name)
    work_id = vol_m.group(1) if vol_m else ""
    vol_z = vol_m.group(2) if vol_m else ""
    _, expand_errs = expand_blocks(draft)
    if expand_errs and work_id.startswith("01史记"):
        from shiji_blocks_autofix import try_repair_blocks_file  # noqa: E402

        if try_repair_blocks_file(blocks_file, index, work_id=work_id)[0]:
            data = json.loads(blocks_file.read_text(encoding="utf-8"))
            draft = dict(data)
            draft["total_paragraphs"] = int(index["total"])
            _, expand_errs = expand_blocks(draft)
    if expand_errs:
        return False, "expand 预检失败: " + "；".join(expand_errs[:6])
    volume_name = volume_display_name(work_id, vol_z, index) if work_id and vol_z else ""
    ok_id, id_msg = _identity_gate_validate_blocks(work_id, vol_z, draft, volume_name)
    if not ok_id:
        return False, id_msg
    para_text = _paragraph_text_map(index)
    ok_ex, ex_msg = _exclude_content_validate_blocks(work_id, draft, para_text)
    if not ok_ex and work_id.startswith("01史记"):
        from shiji_blocks_autofix import try_repair_blocks_file  # noqa: E402

        if try_repair_blocks_file(blocks_file, index, work_id=work_id)[0]:
            data = json.loads(blocks_file.read_text(encoding="utf-8"))
            draft = dict(data)
            draft["total_paragraphs"] = int(index["total"])
            ok_ex, ex_msg = _exclude_content_validate_blocks(work_id, draft, para_text)
    if not ok_ex:
        return False, ex_msg
    return True, f"{len(data.get('blocks') or [])} 块"


def try_mechanical_blocks_from_manifest(
    work: str,
    vol: str,
    index: dict,
    *,
    manifest: Optional[dict] = None,
) -> Tuple[bool, str]:
    """single/fanzuo/hezhuan：据 manifest 机械生成 blocks，跳过 LLM 逐段划块。"""
    from lib.protagonist_workflow import load_protagonists
    from lib.volume_manifest import build_mechanical_blocks, uses_mechanical_blocks

    data = manifest or load_protagonists(work, vol)
    if str(work).startswith("02汉书"):
        from lib.hanshu_hezhuan_autofix import (
            build_override_protagonists_manifest,
            ensure_prince_emperors,
            override_protagonist_keys,
            write_override_protagonists_manifest,
        )

        override_keys = override_protagonist_keys(vol)
        current_keys = [
            ((item.get("name") or "").strip(), (item.get("category") or "").strip())
            for item in (data or {}).get("protagonists", [])
            if isinstance(item, dict)
        ]
        if override_keys and current_keys != override_keys:
            override_manifest = build_override_protagonists_manifest(
                vol,
                work=work,
                volume_name=str((data or {}).get("volume_name") or "").strip(),
            )
            if override_manifest:
                data = override_manifest
                write_override_protagonists_manifest(
                    work,
                    vol,
                    volume_name=str(override_manifest.get("volume_name") or "").strip(),
                )
                ensure_prince_emperors(
                    [name for name, category in override_keys if category == "宗戚"]
                )
    if not data or not uses_mechanical_blocks(data):
        return False, "非 single/fanzuo 模式"
    para_text = _paragraph_text_map(index)
    try:
        draft = build_mechanical_blocks(
            data,
            total_paragraphs=int(index["total"]),
            para_text=para_text,
        )
    except ValueError as exc:
        if str(work).startswith("02汉书"):
            from lib.hanshu_hezhuan_autofix import (
                try_build_mechanical_blocks,
                write_override_protagonists_manifest,
            )

            draft, aut_msg = try_build_mechanical_blocks(work, vol, index, data)
            if draft:
                if aut_msg.startswith("卷级覆盖划块"):
                    ok_manifest, manifest_msg = write_override_protagonists_manifest(
                        work,
                        vol,
                        volume_name=str(data.get("volume_name") or "").strip(),
                    )
                    if not ok_manifest:
                        return False, manifest_msg
                bp = blocks_path(work, vol)
                bp.write_text(
                    json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                ok, msg = blocks_valid(bp, index)
                if ok:
                    return True, f"汉书自动划块 · {aut_msg} · {msg}"
                bp.unlink(missing_ok=True)
        return False, str(exc)
    bp = blocks_path(work, vol)
    bp.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ok, msg = blocks_valid(bp, index)
    if not ok:
        bp.unlink(missing_ok=True)
        return False, f"机械 blocks 校验未过: {msg}"
    return True, f"机械划块 · {msg}"


def _identity_gate_validate_blocks(work: str, vol: str, draft: dict, volume_name: str):
    from identity_gate import validate_blocks_identity  # noqa: E402

    return validate_blocks_identity(work, vol, draft, volume_name=volume_name)


def _exclude_content_validate_blocks(work: str, draft: dict, para_text: dict):
    from exclude_content_gate import validate_blocks_excludes  # noqa: E402

    return validate_blocks_excludes(draft, para_text, work_id=work)


def _paragraph_text_map(index: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for row in index.get("paragraphs") or []:
        pid = int(row.get("id") or 0)
        if pid:
            out[pid] = (row.get("text") or "").strip()
    return out


def _opening_quote(text: str, min_len: int = 12) -> str:
    t = (text or "").strip()
    if len(t) <= min_len:
        return t
    return t[: min(len(t), 80)]


def _entry_opening_quote(
    para_text: Dict[int, str],
    ranges: List[Tuple[int, int]],
    *,
    min_len: int = 20,
) -> str:
    """返回条目首个非空段的逐字引文，保持可被原文校验命中。"""
    parts: List[str] = []
    for pf, pt in ranges:
        for pid in range(pf, pt + 1):
            text = (para_text.get(pid, "") or "").strip()
            if not text:
                continue
            return _opening_quote(text, min_len=min_len)
    return _opening_quote("".join(parts), min_len=min_len)


def _merge_ranges(ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged: List[Tuple[int, int]] = [ranges[0]]
    for pf, pt in ranges[1:]:
        last_pf, last_pt = merged[-1]
        if pf <= last_pt + 1:
            merged[-1] = (last_pf, max(last_pt, pt))
        else:
            merged.append((pf, pt))
    return merged


def expand_blocks_to_skeleton(
    work: str,
    vol: str,
    index: dict,
    *,
    blocks_file: Path | None = None,
    skeleton_out: Path | None = None,
) -> Path:
    """blocks.json + 段落索引 → 标准 skeleton（含 segment_attribution / entries / 原文字句）。"""
    from lib.adapters.openclaw import expected_skeleton_path

    sk_path = skeleton_out or expected_skeleton_path(work, vol, index)
    if sk_path.exists():
        try:
            from lib.skeleton_seal import skeleton_step4_sealed

            existing = json.loads(sk_path.read_text(encoding="utf-8"))
            if skeleton_step4_sealed(existing):
                print(
                    f"⏭ 卷{vol} skeleton 已 Step4 封板，跳过 expand 覆盖",
                    flush=True,
                )
                return sk_path
            if any((e.get("优先级") or "").strip() for e in existing.get("entries") or []):
                return sk_path
        except (json.JSONDecodeError, OSError):
            pass

    bp = blocks_file or blocks_path(work, vol)
    norm_logs = normalize_blocks_file(bp)
    if norm_logs:
        print(f"🔧 blocks 规范化: {'; '.join(norm_logs)}", flush=True)
    ok, msg = blocks_valid(bp, index)
    if not ok:
        raise ValueError(f"blocks 无效: {msg}")

    draft = json.loads(bp.read_text(encoding="utf-8"))
    draft["total_paragraphs"] = int(index["total"])
    attribution, expand_errs = expand_blocks(draft)
    if expand_errs:
        raise ValueError("expand_blocks 失败:\n" + "\n".join(f"  - {e}" for e in expand_errs))

    vol_z = vol.zfill(3)
    volume_name = volume_display_name(work, vol, index)
    para_text = _paragraph_text_map(index)
    src_file = (index.get("source_file") or f"{work}_{vol_z}.txt").strip()
    prefix = entry_id_prefix(work)
    vol_num = int(vol_z)

    raw_entries = merge_entry_paragraphs(draft, attribution)
    entries: List[dict] = []
    for i, raw in enumerate(raw_entries, start=1):
        name = (raw.get("史略名称") or "").strip()
        cat = (raw.get("史略分类") or "君王").strip()
        para_blocks = raw.get("paragraphs") or []
        pids: List[int] = []
        for blk in para_blocks:
            fr = int(blk.get("paragraph_from") or 0)
            to = int(blk.get("paragraph_to") or fr)
            pids.extend(range(fr, to + 1))
        pids = sorted(set(p for p in pids if p > 0))
        if not pids:
            continue
        ranges = _merge_ranges([(p, p) for p in pids])
        quote = _entry_opening_quote(para_text, ranges)
        entries.append(
            {
                "史略ID": f"{prefix}_{vol_z}_{i:02d}",
                "史略名称": name,
                "史略简介": name,
                "原文字句": quote,
                "史略分类": cat,
                "主要史料出处": f"《史记·卷{vol_num}·{volume_name}》"
                if work == "01史记"
                else f"《{get_work_config(work).get('title', work)}·卷{vol_num}·{volume_name}》",
                "paragraphs": [
                    {
                        "volume": volume_name,
                        "paragraph_from": pf,
                        "paragraph_to": pt,
                    }
                    for pf, pt in ranges
                ],
            }
        )

    payload = merge_protagonist_metadata(
        {
            "volume": volume_name,
            "source_file": src_file,
            "total_paragraphs": int(index["total"]),
            "volume_type": get_work_config(work).get("volume_type_default", "纪传叙事"),
            "segment_attribution": attribution,
            "entries": entries,
        },
        work,
        vol,
    )
    sk_path.parent.mkdir(parents=True, exist_ok=True)
    sk_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if str(work).startswith("02汉书"):
        from lib.hanshu_hezhuan_autofix import apply_cobio_patches

        patched, patch_msg = apply_cobio_patches(work, vol, payload)
        if patched:
            sk_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    return sk_path


def rebuild_audit_blocks(work: str, vols: List[str] | None = None) -> List[str]:
    """从 skeleton 重建审计 MD（整文件 SSOT，去除 LLM 废话）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "historiography-pipeline"))
    from build_audit_block import build_block  # noqa: E402

    from lib.config import get_work_config

    ann = paths()["annotations"]
    if vols:
        targets = [v.zfill(3) for v in vols]
    else:
        targets = sorted(
            {
                p.name.split("_")[1]
                for p in ann.glob(f"{work}_*_skeleton.json")
                if len(p.name.split("_")) >= 2
            }
        )
    logs: List[str] = []
    blocks: List[str] = []
    for vol in targets:
        matches = sorted(ann.glob(f"{work}_{vol}_*_skeleton.json"))
        if not matches:
            logs.append(f"卷{vol}: 无 skeleton，跳过")
            continue
        sk = matches[0]
        try:
            block = build_block(work, vol, sk)
            blocks.append(block.rstrip())
            logs.append(f"卷{vol}: ✅ {sk.name}")
        except Exception as exc:
            logs.append(f"卷{vol}: ❌ {exc}")

    if blocks:
        title = get_work_config(work).get("title", work)
        audit_path = paths()["audit"] / f"{work}_标注审计.md"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(
            f"# {title} · {work} 标注审计\n\n" + "\n\n".join(blocks) + "\n",
            encoding="utf-8",
        )
        logs.append(f"写入 {audit_path}（{len(blocks)} 卷）")
    return logs
