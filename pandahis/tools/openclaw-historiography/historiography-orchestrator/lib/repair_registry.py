"""卷级确定性返工脚本注册表；verify 失败时编排器主动调用。

⚠️ 边界（硬）：
- repair 仅做机械修复（段首摘录、表志 skip、合传白名单校验、坐标 ID 同步）
- **禁止**替代 Step1/Step4 LLM 写块界、史略分类、帝王坐标、起止年
- 《汉书》叙事卷禁止 LLM 知识旁路；允许 hanshu_hezhuan_autofix 机械划块/头段/同段双归属
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from lib.config import ANNOTATE_DIR, PIPELINE_DIR, get_work_config
from lib import blocks_workflow, gates
from lib.protagonist_workflow import protagonists_path

sys.path.insert(0, str(ANNOTATE_DIR))
from knowledge_provenance import stamp_provenance  # noqa: E402


# 单卷 repair 脚本（相对 historiography-annotate/）— 仅史记特例卷
VOLUME_REPAIR_SCRIPTS = {
    ("01史记", "005"): "repair_shiji_vol005_qinbenji.py",
    ("01史记", "067"): "repair_shiji_vol067_zhongnidizi.py",
}

# (work, vol) → (batch_script, argv_suffix)
VOLUME_BATCH_REPAIRS = {
    ("01史记", "049"): ("repair_shiji_jiashi_batch.py", ["049"]),
    ("01史记", "047"): ("repair_shiji_jiashi_batch.py", ["047"]),
    ("01史记", "048"): ("repair_shiji_jiashi_batch.py", ["048"]),
    ("01史记", "124"): ("repair_shiji_vol124_129.py", ["124"]),
    ("01史记", "125"): ("repair_shiji_vol124_129.py", ["125"]),
    ("01史记", "126"): ("repair_shiji_vol124_129.py", ["126"]),
    ("01史记", "127"): ("repair_shiji_vol124_129.py", ["127"]),
    ("01史记", "128"): ("repair_shiji_vol124_129.py", ["128"]),
    ("01史记", "129"): ("repair_shiji_vol124_129.py", ["129"]),
}


def _annotate_script(name: str) -> Path:
    return ANNOTATE_DIR / name


def try_volume_repair(work: str, vol: str) -> Tuple[bool, str]:
    """运行已注册的卷级返工脚本；成功则返回 True。"""
    vol = vol.zfill(3)
    key = (work, vol)

    # 汉书合传：仅允许机械划块/头段类确定性修复，不替代 LLM 知识考订
    if work.startswith("02汉书"):
        from lib import hanshu_autofix
        from lib.hanshu_hezhuan_autofix import (
            try_repair_hanshu_hezhuan_expand,
            try_repair_hanshu_hezhuan_step1,
        )

        repaired, msg = hanshu_autofix.repair_skeleton_headers(work, vol)
        if repaired:
            return True, msg
        try:
            idx = gates.load_paragraph_index(work, vol)
            rep_ok, rep_msg = try_repair_hanshu_hezhuan_step1(work, vol, idx)
            if rep_ok:
                return True, rep_msg
            exp_ok, exp_msg = try_repair_hanshu_hezhuan_expand(work, vol, idx)
            if exp_ok:
                return True, exp_msg
        except FileNotFoundError:
            pass

    if get_work_config(work).get("require_llm_knowledge"):
        return False, f"{work} 须 LLM 知识性决策，禁止卷级 repair 旁路"

    single = VOLUME_REPAIR_SCRIPTS.get(key)
    if single:
        return _run_python_script(_annotate_script(single))

    batch = VOLUME_BATCH_REPAIRS.get(key)
    if batch:
        script_name, extra_args = batch
        return _run_python_script(_annotate_script(script_name), extra_args)

    if work.startswith("01史记"):
        try:
            idx = gates.load_paragraph_index(work, vol)
            vname = blocks_workflow.volume_display_name(work, vol, idx)
            if vname.endswith("书") or vname.endswith("表"):
                ok, msg = repair_skip_narrative_volume(work, vol, idx, vname)
                if ok:
                    return True, msg
        except FileNotFoundError:
            pass

    return False, "无卷级返工配方"


def _run_python_script(script: Path, extra_args: Optional[List[str]] = None) -> Tuple[bool, str]:
    if not script.is_file():
        return False, f"脚本不存在: {script}"
    cmd = [sys.executable, str(script)] + (extra_args or [])
    proc = subprocess.run(
        cmd,
        cwd=str(ANNOTATE_DIR),
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = out.strip()[-800:] if out.strip() else "(无输出)"
    if proc.returncode == 0:
        return True, f"{script.name} 完成: {tail}"
    return False, f"{script.name} 失败 (exit {proc.returncode}): {tail}"


def repair_skip_narrative_volume(
    work: str,
    vol: str,
    index: dict,
    volume_name: str,
) -> Tuple[bool, str]:
    """表/志书卷：全段 exclude，entries 为空。"""
    from lib.adapters.openclaw import expected_skeleton_path

    vol = vol.zfill(3)
    total = int(index.get("total") or 0)
    if total <= 0:
        return False, "段落数为 0"

    reason = "志书数据" if volume_name.endswith("书") else "无故事弧"
    vol_type = "志书数据" if volume_name.endswith("书") else "表"

    bp = blocks_workflow.blocks_path(work, vol)
    if bp.exists():
        bp.unlink()

    pp = protagonists_path(work, vol)
    if pp.exists():
        pp.unlink()

    sk_path = expected_skeleton_path(work, vol, index)
    if sk_path.exists():
        sk_path.unlink()

    sk = {
        "volume": volume_name,
        "source_file": (index.get("source_file") or f"{work}_{vol}.txt").strip(),
        "total_paragraphs": total,
        "volume_type": vol_type,
        "segment_attribution": [
            {"paragraph": p, "owners": [], "exclude_reason": reason}
            for p in range(1, total + 1)
        ],
        "entries": [],
    }
    sk_path.parent.mkdir(parents=True, exist_ok=True)
    sk_path.write_text(
        json.dumps(sk, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    stamp_provenance(
        sk_path,
        "1",
        source="skip_non_narrative",
        reason=reason,
    )
    stamp_provenance(
        sk_path,
        "4",
        source="skip_non_narrative",
        reason="无叙事条目",
    )

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(work, vol, sk_path)

    if work.startswith("01史记"):
        gates.step4_prepare(sk_path)
        gates.step4_shiji_person_fallback(sk_path, work, vol)

    ok_fin, fin_msg = gates.step4_finalize(sk_path)
    if not ok_fin:
        return False, f"skip 卷 finalize 失败: {fin_msg[-400:]}"

    for step in ("1", "2", "3", "4"):
        ok, msg = gates.verify_step(work, vol, step)
        if not ok:
            return False, f"skip 卷 Step{step} 未过: {msg[-400:]}"

    from lib import db  # noqa: WPS433

    now = db.utc_now()
    conn = db.connect()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, work, vol, step),
        )
    conn.commit()
    return True, f"卷{vol} {volume_name} 已 skip（{reason}，0 条）"
