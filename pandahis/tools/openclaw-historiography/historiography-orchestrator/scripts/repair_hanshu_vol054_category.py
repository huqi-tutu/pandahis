#!/usr/bin/env python3
"""已废弃：旧版 054 君王修复脚本。

该脚本会把当前 054 宗戚成品回退到旧的「君王 + 帝王表」路径，禁止继续使用。
请改用 orchestrator 内置的 hanshu_hezhuan_autofix / identity_gate 当前链路。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ORCH = Path(__file__).resolve().parents[1]
ANN = ORCH.parent / "historiography-annotate"
sys.path.insert(0, str(ANN))
sys.path.insert(0, str(ORCH))

from detail_coords import fill_all_detail_coords  # noqa: E402
from hanshu_step4_hardening import clear_entries_without_year_basis  # noqa: E402
from identity_gate import validate_protagonists_identity, validate_skeleton_identity  # noqa: E402

from lib import db, gates  # noqa: E402
from lib.blocks_workflow import blocks_path, expand_blocks_to_skeleton  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402
from lib.work_runner import _find_or_create_pending, _run_job  # noqa: E402

WORK = "02汉书"
VOL = "054"
ROOT = ORCH.parents[2]
SKEL_DIR = ROOT / "data" / "03索引标注条目"
INDEX = SKEL_DIR / "段落索引" / "02汉书_054.json"
SK = SKEL_DIR / "02汉书_054_淮南衡山济北王传第十四_skeleton.json"

NEW_EMPERORS: List[Dict[str, Any]] = [
    {
        "帝王ID": "DW_HX_XIHAN_XIHAN_LIUCHANG",
        "帝王名称": "刘长",
        "政权": "西汉",
        "政权ID": "ZQ_HX_XIHAN_XIHAN",
        "朝代": "西汉",
        "朝代ID": "CD_HX_XIHAN",
        "文明": "华夏",
        "文明ID": "HX",
        "帝王原名": "淮南厉王",
        "庙号": "厉",
        "年号": "-",
        "即位时间": "-196",
        "退位时间": "-174",
        "在位时长": "22",
        "重要性评级": "3",
        "标签": "auto_from_skeleton",
    },
    {
        "帝王ID": "DW_HX_XIHAN_XIHAN_LIUAN",
        "帝王名称": "刘安",
        "政权": "西汉",
        "政权ID": "ZQ_HX_XIHAN_XIHAN",
        "朝代": "西汉",
        "朝代ID": "CD_HX_XIHAN",
        "文明": "华夏",
        "文明ID": "HX",
        "帝王原名": "淮南王",
        "庙号": "",
        "年号": "-",
        "即位时间": "-164",
        "退位时间": "-122",
        "在位时长": "42",
        "重要性评级": "3",
        "标签": "auto_from_skeleton",
    },
    {
        "帝王ID": "DW_HX_XIHAN_XIHAN_LIUGCI",
        "帝王名称": "刘赐",
        "政权": "西汉",
        "政权ID": "ZQ_HX_XIHAN_XIHAN",
        "朝代": "西汉",
        "朝代ID": "CD_HX_XIHAN",
        "文明": "华夏",
        "文明ID": "HX",
        "帝王原名": "衡山王",
        "庙号": "",
        "年号": "-",
        "即位时间": "-153",
        "退位时间": "-122",
        "在位时长": "31",
        "重要性评级": "3",
        "标签": "auto_from_skeleton",
    },
    {
        "帝王ID": "DW_HX_XIHAN_XIHAN_LIUBO",
        "帝王名称": "刘勃",
        "政权": "西汉",
        "政权ID": "ZQ_HX_XIHAN_XIHAN",
        "朝代": "西汉",
        "朝代ID": "CD_HX_XIHAN",
        "文明": "华夏",
        "文明ID": "HX",
        "帝王原名": "济北贞王",
        "庙号": "",
        "年号": "-",
        "即位时间": "-164",
        "退位时间": "-154",
        "在位时长": "10",
        "重要性评级": "3",
        "标签": "auto_from_skeleton",
    },
]

PROTAGONIST_RATIONALES = {
    "刘长": "淮南厉王刘长，汉高祖少子，宗室诸侯王，合传起笔传主（同荆燕吴传→君王）。",
    "刘安": "淮南王刘安，刘长之子，谋反事为本传主干，宗室诸侯王（君王）。",
    "刘赐": "衡山王刘赐，淮南厉王少子，与刘安连谋，宗室诸侯王（君王）。",
    "刘勃": "济北贞王刘勃，见于卷名，淮南厉王孙，宗室诸侯王（君王）。",
}

SHORT_BIOS = {
    "刘长": "淮南厉王，谋反废死",
    "刘安": "淮南王，谋反自杀",
    "刘赐": "衡山王，连谋自杀",
    "刘勃": "济北贞王，徙封",
}


def _emperor_json_paths() -> List[Path]:
    return [
        ANN / "reference" / "帝王.json",
        ROOT / "data" / "01历史坐标数据" / "帝王.json",
    ]


def ensure_emperors() -> List[str]:
    logs: List[str] = []
    for path in _emperor_json_paths():
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        names = {str(x.get("帝王名称") or "").strip() for x in data}
        added = 0
        for emp in NEW_EMPERORS:
            if emp["帝王名称"] in names:
                continue
            data.append(dict(emp))
            added += 1
        if added:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            logs.append(f"{path.name}: +{added} 君王")
    return logs


def repair_protagonists() -> List[str]:
    path = protagonists_path(WORK, VOL)
    data = json.loads(path.read_text(encoding="utf-8"))
    for p in data.get("protagonists") or []:
        name = (p.get("name") or "").strip()
        p["category"] = "君王"
        if name in PROTAGONIST_RATIONALES:
            p["rationale"] = PROTAGONIST_RATIONALES[name]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok, msg = validate_protagonists_identity(
        WORK, VOL, data, volume_name=data.get("volume_name", "")
    )
    if not ok:
        raise RuntimeError(msg)
    return [f"protagonists OK: {msg}"]


def rebuild_blocks_and_skeleton() -> List[str]:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    manifest = json.loads(protagonists_path(WORK, VOL).read_text(encoding="utf-8"))
    total = int(index["total"])

    draft = {
        "work": WORK,
        "vol": VOL,
        "volume_name": manifest.get("volume_name"),
        "narrative_mode": "hezhuan",
        "total_paragraphs": total,
        "excludes": [
            {"paragraph_from": 1, "paragraph_to": 1, "exclude_reason": "卷首标题"},
            {"paragraph_from": 16, "paragraph_to": 16, "exclude_reason": "赞曰"},
        ],
        "blocks": [
            {"name": "刘长", "category": "君王", "paragraph_from": 2, "paragraph_to": 7},
            {"name": "刘安", "category": "君王", "paragraph_from": 8, "paragraph_to": 13},
            {"name": "刘赐", "category": "君王", "paragraph_from": 14, "paragraph_to": 14},
            {"name": "刘勃", "category": "君王", "paragraph_from": 15, "paragraph_to": 15},
        ],
        "_mechanical": True,
        "_mechanical_hezhuan": True,
    }
    bp = blocks_path(WORK, VOL)
    bp.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sk_path = expand_blocks_to_skeleton(WORK, VOL, index, blocks_file=bp, skeleton_out=SK)
    data = json.loads(sk_path.read_text(encoding="utf-8"))

    for entry in data.get("entries") or []:
        name = (entry.get("史略名称") or "").strip()
        entry["史略分类"] = "君王"
        if name in SHORT_BIOS:
            entry["史略简介"] = SHORT_BIOS[name]
        _clear_entry_years(entry)

    clear_entries_without_year_basis(data.get("entries") or [], force_all_without_basis=True)
    fill_all_detail_coords(data, work_id=WORK, json_path=str(sk_path))

    prov = data.get("knowledge_provenance") or {}
    prov.setdefault(
        "step1",
        {
            "source": "llm",
            "at": "2026-07-02T14:04:07Z",
            "session_id": "hist-02-054-s1-863-d49879a3",
        },
    )
    prov.pop("step4", None)
    data["knowledge_provenance"] = prov
    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ok, msg = validate_skeleton_identity(WORK, VOL, data)
    if not ok:
        raise RuntimeError(msg)
    return [
        f"blocks → {bp.name}",
        f"skeleton → {sk_path.name} ({len(data.get('entries') or [])} 条)",
        f"identity: {msg}",
    ]


def _clear_entry_years(entry: dict) -> None:
    for k in (
        "史略开始年",
        "史略结束年",
        "四级帝王坐标",
        "一级文明坐标",
        "二级朝代坐标",
        "三级政权坐标",
        "文明ID",
        "朝代ID",
        "政权ID",
        "帝王ID",
    ):
        entry.pop(k, None)
    af = entry.get("_auto_filled")
    if isinstance(af, dict):
        af.clear()
    entry.pop("_needs_llm", None)


def reset_jobs() -> None:
    db.init_schema()
    for step in ("1", "2", "3"):
        db.mark_volume_steps_done(WORK, VOL, step)
    db.reset_volume_step(WORK, VOL, "4")
    gates.step4_restore_scratch(SK)


def reset_and_run_step4() -> None:
    reset_jobs()
    job = _find_or_create_pending(WORK, VOL, "4")
    if not job:
        raise RuntimeError("未找到 Step4 job")
    _run_job(WORK, job)
    refreshed = db.get_job(WORK, VOL, "4")
    sk_data = json.loads(SK.read_text(encoding="utf-8"))
    prov = sk_data.get("knowledge_provenance") or {}
    if not prov.get("step1"):
        prov["step1"] = {
            "source": "llm",
            "at": "2026-07-02T14:04:07Z",
            "session_id": "hist-02-054-s1-863-d49879a3",
        }
        sk_data["knowledge_provenance"] = prov
        SK.write_text(json.dumps(sk_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok, _ = gates.verify_step4_final(SK)
    if ok:
        gates.step4_finalize(SK)
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.update_job(refreshed["id"], status="done", finished_at=now, fail_count=0, detail="repair_vol054_junwang_ok")
        return
    if refreshed and refreshed.get("status") == "done":
        return
    detail = (refreshed or {}).get("detail", "unknown")
    raise RuntimeError(f"Step4 未完成: {detail}")


def main() -> int:
    raise SystemExit(
        "repair_hanshu_vol054_category.py 已废弃：054 现以宗戚体系为准，"
        "运行旧脚本会回退当前成品。请使用现行 hanshu_hezhuan_autofix 链路。"
    )


if __name__ == "__main__":
    raise SystemExit(main())
