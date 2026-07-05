#!/usr/bin/env python3
"""汉书 004 新流程脚本验证（不依赖 LLM）。"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANNOTATE = ORCH.parent / "historiography-annotate"
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(ANNOTATE))

from lib.config import paths  # noqa: E402
from lib import gates  # noqa: E402
from lib import blocks_workflow  # noqa: E402
from lib import protagonist_workflow  # noqa: E402
from lib.volume_manifest import infer_narrative_mode, uses_mechanical_blocks  # noqa: E402
from fill_fields import (  # noqa: E402
    merge_all_entries,
    build_llm_missing_report,
    reconcile_entries_coords_from_emperor,
    reconcile_entries_coord_ids,
    finalize_entries,
    build_emperor_index,
    build_regime_index,
    build_dynasty_index_from_json,
)
from coordinate_index import SCRIPT_COORD_FIELDS, FOURTH_EMPIRE_COORD_FIELD  # noqa: E402
from check_format import main as check_format_main  # noqa: E402

WORK = "02汉书"
VOL = "004"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    p = paths()
    idx = gates.load_paragraph_index(WORK, VOL)
    ann = p["annotations"]
    aw = p["annotate_work"]
    aw.mkdir(parents=True, exist_ok=True)

    # ── 1. 准备 manifest（narrative_mode=single）──
    pp = protagonist_workflow.protagonists_path(WORK, VOL)
    manifest = {
        "work": WORK,
        "vol": VOL,
        "volume_name": "高后纪",
        "volume_type_guess": "本纪",
        "narrative_mode": "single",
        "skip_reason": None,
        "protagonists": [
            {
                "name": "吕太后",
                "category": "宗戚",
                "rationale": "《高后纪》主轴为吕雉（吕太后），本纪体例下为宗戚非君王。",
            }
        ],
        "excluded_kinds_hint": ["卷首标题", "赞曰", "其他"],
    }
    pp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok_p, p_msg = protagonist_workflow.protagonists_valid(WORK, VOL, idx)
    log(f"✓ Step1a manifest: {p_msg}" if ok_p else f"✗ Step1a manifest: {p_msg}")
    if not ok_p:
        return 1
    mode = infer_narrative_mode(manifest)
    log(f"  narrative_mode={mode} · mechanical={uses_mechanical_blocks(manifest)}")

    # ── 2. 机械划块 ──
    blocks_workflow.blocks_path(WORK, VOL).unlink(missing_ok=True)
    mech_ok, mech_msg = blocks_workflow.try_mechanical_blocks_from_manifest(
        WORK, VOL, idx, manifest=manifest
    )
    log(f"✓ Step1b 机械划块: {mech_msg}" if mech_ok else f"✗ Step1b: {mech_msg}")
    if not mech_ok:
        return 1

    # ── 3. 展开 skeleton ──
    sk_path = ann / "02汉书_004_高后纪第三_skeleton.json"
    backup_dir = aw / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{sk_path.name}.bak_validate"
    if sk_path.exists():
        shutil.copy2(sk_path, backup)
        log(f"  已备份原 skeleton → {backup.relative_to(p['data'])}")

    sk_path.unlink(missing_ok=True)
    blocks_workflow.expand_blocks_to_skeleton(WORK, VOL, idx)
    ok_sk, sk_msg = gates.step1_skeleton_valid(WORK, VOL)
    log(f"✓ Step1 skeleton: {sk_msg}" if ok_sk else f"✗ Step1 skeleton: {sk_msg}")
    if not ok_sk:
        return 1

    data = json.loads(sk_path.read_text(encoding="utf-8"))
    entry = data["entries"][0]
    log(f"  条目: {entry['史略名称']} · {entry['史略分类']}")
    log(f"  段落: P{entry['paragraphs'][0]['paragraph_from']}-P{entry['paragraphs'][0]['paragraph_to']}")
    excludes = [
        f"P{a['paragraph']}={a.get('exclude_reason')}"
        for a in data["segment_attribution"]
        if a.get("exclude_reason")
    ]
    log(f"  exclude: {', '.join(excludes)}")

    # ── 4. Step4 prepare（仅四级帝王交 LLM）──
    ei = build_emperor_index()
    ri = build_regime_index()
    di = build_dynasty_index_from_json()
    merge_all_entries(
        data["entries"],
        data=data,
        json_path=str(sk_path),
        emperor_index=ei,
        dynasty_index=di,
        regime_index=ri,
        work_id=WORK,
    )
    needs = entry.get("_needs_llm") or []
    log(f"✓ Step4 prepare · _needs_llm={needs}")
    if FOURTH_EMPIRE_COORD_FIELD not in needs:
        log("✗ 预期非君王条目仅需 LLM 填四级帝王坐标")
        return 1
    for f in SCRIPT_COORD_FIELDS:
        if f in needs:
            log(f"✗ 不应要求 LLM 填 {f}")
            return 1

    report = build_llm_missing_report(data)
    if "四级帝王坐标" not in report or "一～三级" not in report:
        log("✗ Step4 报告未强调仅填四级帝王")
        return 1
    log("✓ Step4 报告含「仅填四级帝王」说明")

    # ── 5. 模拟 LLM：只写四级帝王 ──
    entry[FOURTH_EMPIRE_COORD_FIELD] = "汉高祖"
    entry.pop("_needs_llm", None)
    for f in SCRIPT_COORD_FIELDS:
        entry.pop(f, None)
    log(f"  模拟 LLM 写入: {FOURTH_EMPIRE_COORD_FIELD}=汉高祖（无一～三级）")

    sync = reconcile_entries_coords_from_emperor(data["entries"], emperor_index=ei, regime_index=ri)
    id_logs = reconcile_entries_coord_ids(
        data["entries"], emperor_index=ei, regime_index=ri, dynasty_index=di
    )
    entry = data["entries"][0]
    log(f"✓ reconcile 对齐 {len(sync)} 处 · ID {len(id_logs)} 处")
    log(f"  一级={entry.get('一级文明坐标')} 二级={entry.get('二级朝代坐标')}")
    log(f"  三级={entry.get('三级政权坐标')} 四级={entry.get('四级帝王坐标')}")
    log(f"  帝王ID={entry.get('帝王ID')}")

    if entry.get("四级帝王坐标") != "汉高祖":
        log("✗ 四级帝王坐标丢失")
        return 1
    if not all(entry.get(f) for f in SCRIPT_COORD_FIELDS):
        log("✗ 脚本未反推一～三级坐标")
        return 1
    if not entry.get("帝王ID"):
        log("✗ 帝王ID 未补全")
        return 1

    # 补全年份/优先级（模拟 LLM 其余字段）
    entry["史略开始年"] = -241
    entry["史略结束年"] = -180
    entry["优先级"] = "P0"
    entry["优先级判定理由"] = "本纪主轴宗戚"
    entry["_auto_filled"] = {
        "_坐标主轴说明": "宗戚以册封之君为准：吕雉为汉高祖皇后，册封与入宫均在高祖世；惠帝朝临朝称制不改挂惠帝。",
        "年规则": "出生年 → 去世年",
    }
    data["knowledge_provenance"] = {
        "step1": {"source": "llm", "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "step4": {"source": "llm", "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
    }
    finalize_entries(data["entries"])
    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ── 6. check_format ──
    import subprocess

    r = subprocess.run(
        [sys.executable, str(ANNOTATE / "check_format.py"), str(sk_path), "--phase", "final"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        log(f"✗ check_format final:\n{r.stdout}\n{r.stderr}")
        return 1
    log("✓ check_format --phase final 通过")

    log("\n══════════════════════════════════════")
    log("汉书 004 新流程脚本验证：全部通过")
    log("  Step1a single · Step1b 机械划块 · Step4 仅四级帝王+脚本反推")
    log(f"  skeleton: {sk_path}")
    log("══════════════════════════════════════")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
