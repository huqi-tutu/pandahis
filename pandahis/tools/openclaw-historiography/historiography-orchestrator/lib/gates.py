"""封装现有脚本硬门 + 段落索引校验。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

from lib.config import ANNOTATE_DIR, AUDIT_DIR, PIPELINE_DIR, get_work_config, paths

sys.path.insert(0, str(ANNOTATE_DIR))
from paragraph_utils import check_paragraph_count  # noqa: E402


def run_cmd(cmd: list) -> Tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def load_paragraph_index(work: str, vol: str) -> dict:
    fp = paths()["paragraph_index"] / f"{work}_{vol}.json"
    if not fp.exists():
        raise FileNotFoundError(f"缺少段落索引: {fp}")
    return json.loads(fp.read_text(encoding="utf-8"))


def verify_paragraph_index(work: str, vol: str, skeleton: Path) -> Tuple[bool, str]:
    idx = load_paragraph_index(work, vol)
    data = json.loads(skeleton.read_text(encoding="utf-8"))
    expected = idx["total"]
    actual = data.get("total_paragraphs")
    if actual != expected:
        return False, f"total_paragraphs={actual} ≠ 索引 {expected}"
    ok, msg, _, _ = check_paragraph_count(data, skeleton)
    if not ok:
        return False, msg
    return True, f"段落与索引一致 ({expected})"


def verify_step(work: str, vol: str, step: str) -> Tuple[bool, str]:
    cmd = [
        sys.executable,
        str(PIPELINE_DIR / "run_volume_pipeline.py"),
        "verify",
        "--work",
        work,
        "--vol",
        vol,
        "--step",
        step,
    ]
    code, out = run_cmd(cmd)
    if code != 0:
        return False, out[-3000:]
    return True, out.strip().split("\n")[-1] if out.strip() else "ok"


def skeleton_path(work: str, vol: str) -> Path | None:
    vol = vol.zfill(3)
    matches = sorted(paths()["annotations"].glob(f"{work}_{vol}_*_skeleton.json"))
    return matches[0] if matches else None


def llm_step_hard_floor(work: str) -> int:
    """Step1/3 荒谬快硬门槛（秒）；低于此值编排器直接失败。"""
    cfg = get_work_config(work)
    return int(cfg.get("llm_step_seconds_hard_floor", 5))


def min_step1_duration(work: str, vol: str) -> int:
    """建议用时（仅告警，0=关闭）；硬失败仅 llm_step_hard_floor；质量以 verify 为准。"""
    cfg = get_work_config(work)
    if cfg.get("step1_seconds_advisory") is False:
        return 0
    floor = int(cfg.get("step1_seconds_floor", 0))
    per = float(cfg.get("step1_seconds_per_para", 0))
    cap = int(cfg.get("step1_seconds_cap", 0))
    if floor <= 0 and per <= 0:
        return 0
    idx = load_paragraph_index(work, vol)
    raw = max(floor, int(idx["total"] * per + 0.999))
    if cap <= 0:
        return raw
    return min(cap, raw)


def min_step3_duration(work: str, vol: str) -> int:
    """建议用时（仅告警，0=关闭）。"""
    cfg = get_work_config(work)
    if cfg.get("step3_seconds_advisory") is False:
        return 0
    floor = int(cfg.get("step3_seconds_floor", 0))
    per = float(cfg.get("step3_seconds_per_para", 0))
    cap = int(cfg.get("step3_seconds_cap", 0))
    if floor <= 0 and per <= 0:
        return 0
    idx = load_paragraph_index(work, vol)
    raw = max(floor, int(idx["total"] * per + 0.999))
    if cap <= 0:
        return raw
    return min(cap, raw)


def max_retries_per_step(work: str, step: str | None = None) -> int:
    cfg = get_work_config(work)
    base = int(cfg.get("max_retries_per_step", 2))
    if step == "3":
        return int(cfg.get("step3_max_retries", max(base, 4)))
    if step == "4":
        return int(cfg.get("step4_max_retries", max(base, 4)))
    if step == "1":
        return int(cfg.get("step1_max_retries", max(base, 4)))
    return base


def evidence_spot_count(work: str) -> int:
    cfg = get_work_config(work)
    return int(cfg.get("evidence_spot_check_paragraphs", 8))


def verify_skeleton_format(skeleton: Path) -> Tuple[bool, str]:
    code, out = run_cmd(
        [
            sys.executable,
            str(ANNOTATE_DIR / "check_format.py"),
            str(skeleton),
            "--phase",
            "skeleton",
        ]
    )
    if code != 0:
        return False, out[-2000:]
    return True, "check_format skeleton exit 0"


def step1_skeleton_valid(work: str, vol: str) -> Tuple[bool, str]:
    """已有 skeleton 且段落索引 + 格式硬检均通过 → 可跳过 Step1 LLM。"""
    sk = skeleton_path(work, vol)
    if not sk:
        return False, "无 skeleton"
    ok, msg = verify_paragraph_index(work, vol, sk)
    if not ok:
        return False, msg
    ok, msg = verify_skeleton_format(sk)
    if not ok:
        return False, msg
    return True, str(sk.name)


def _fill_fields_cmd(skeleton: Path, *extra: str) -> Tuple[int, str]:
    cmd = [sys.executable, str(ANNOTATE_DIR / "fill_fields.py"), str(skeleton), *extra]
    return run_cmd(cmd)


def step2_prepare(skeleton: Path) -> Tuple[bool, str]:
    """
    Step2 硬检前：合并帝王待补录、从 skeleton 自动补帝王表、对齐君王标准名。
    失败不阻断 verify（仅记录）；补录成功可消除「不在帝王.json」类错误。
    """
    sys.path.insert(0, str(ANNOTATE_DIR))
    from emperor_resolve import (  # noqa: E402
        align_skeleton_emperors,
        auto_supplement_emperors_from_skeleton,
        merge_supplements_into_emperor_json,
    )

    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)

    parts: list[str] = []
    sup_n, sup_logs = merge_supplements_into_emperor_json()
    if sup_n:
        parts.append(f"帝王待补录合并 {sup_n} 条")

    added, patched, auto_logs = auto_supplement_emperors_from_skeleton(data)
    if added or patched:
        parts.append(f"自动补帝王表 +{added} 修补 {patched}")
    for ln in (sup_logs or []) + (auto_logs or []):
        if ln and ("补录" in ln or "跳过" in ln or "合并" in ln):
            parts.append(ln)

    data, align_changes = align_skeleton_emperors(data, only_junji=True)
    if align_changes:
        skeleton.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        parts.append(f"君王名对齐 {len(align_changes)} 处")

    from protagonist_metadata import merge_protagonist_metadata, parse_work_vol_from_skeleton  # noqa: E402

    work, vol = parse_work_vol_from_skeleton(skeleton)
    if work and vol:
        merged = merge_protagonist_metadata(data, work, vol)
        if merged != data:
            skeleton.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            data = merged
            parts.append("已合并 Step1a LLM 卷型/主轴人数")

    if not parts:
        return True, "step2_prepare: 无需补帝王表"
    return True, "step2_prepare: " + "; ".join(parts[:8])


def is_step2_emperor_reference_only_error(err_str: str) -> bool:
    """Step2 失败是否仅因帝王参考表/君王命名（非 skeleton 结构或归属问题）。"""
    if not err_str:
        return False
    structural = (
        "segment_attribution",
        "段数",
        "entries 为空",
        "格式不符",
        "段号重复",
        "重复归属",
        "缺少段落",
        "合传",
        "paragraph",
        "total_paragraphs",
    )
    if any(k in err_str for k in structural):
        return False
    emperor_only = (
        "不在帝王.json",
        "应改为帝王表标准名",
        "帝王ID 重复",
        "君王名",
        "君王「",
        "四级帝王坐标",
    )
    return any(k in err_str for k in emperor_only)


def step3_write_audit_block(work: str, vol: str, skeleton: Path) -> Tuple[bool, str]:
    """从 skeleton 生成标准审计块（SSOT），覆盖 LLM 可能写入的残缺/计划文字。"""
    code, out = run_cmd(
        [
            sys.executable,
            str(PIPELINE_DIR / "build_audit_block.py"),
            "--work",
            work,
            "--vol",
            vol.zfill(3),
            "--skeleton",
            str(skeleton),
        ]
    )
    if code != 0:
        return False, out[-2000:]
    return True, "step3 audit block written from skeleton"


def step4_prepare(skeleton: Path) -> Tuple[bool, str]:
    """fill_fields + merge-auto；失败时恢复 scratch 标记。"""
    code, out = _fill_fields_cmd(skeleton)
    if code != 0:
        return False, out[-2000:]
    code, out2 = _fill_fields_cmd(skeleton, "--merge-auto")
    if code != 0:
        return False, out2[-2000:]
    return True, "fill_fields + merge-auto ok"


def step4_reconcile(skeleton: Path) -> Tuple[bool, str]:
    """LLM 补字段后：merge-auto + 帝王表坐标链对齐，再校验。"""
    code, out = _fill_fields_cmd(skeleton, "--merge-auto")
    if code != 0:
        return False, out[-3000:]
    return True, "step4 reconcile ok"


def step4_priority_gap_count(skeleton: Path) -> int:
    """统计仍缺优先级的君王条目数（merge-auto 后）。"""
    sys.path.insert(0, str(ANNOTATE_DIR))
    from coordinate_index import normalize_entry_category  # noqa: E402

    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)
    n = 0
    for entry in data.get("entries") or []:
        if normalize_entry_category(entry.get("史略分类", "")) != "君王":
            continue
        if not (entry.get("优先级") or "").strip():
            n += 1
    return n


def step4_collect_decisions(skeleton: Path) -> dict:
    sys.path.insert(0, str(ANNOTATE_DIR))
    from fill_fields import collect_coord_decisions  # noqa: E402

    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)
    return collect_coord_decisions(data)


def step4_verify_fields(skeleton: Path, *, require_clean: bool = False) -> Tuple[bool, str]:
    args = ["--verify"]
    if require_clean:
        args.append("--require-clean")
    code, out = _fill_fields_cmd(skeleton, *args)
    if code != 0:
        return False, out[-3000:]
    return True, "step4 fields ok"


def step4_finalize(skeleton: Path) -> Tuple[bool, str]:
    code, out = _fill_fields_cmd(skeleton, "--finalize")
    if code != 0:
        return False, out[-3000:]
    return True, "step4 finalized"


def step4_restore_scratch(skeleton: Path) -> None:
    """失败重试前仅刷新 _needs_llm；不重建 _auto_filled，避免抹掉 LLM 主轴说明等考订字段。"""
    _fill_fields_cmd(skeleton, "--refresh-needs")


def step4_shiji_person_fallback(
    skeleton: Path, work: str, vol: str
) -> Tuple[int, list]:
    """《史记》Step4 脚本加固（坐标/年份/考订字段）。"""
    if not str(work).startswith("01史记"):
        return 0, []
    from step4_hardening import harden_shiji_step4_skeleton  # noqa: E402

    n, logs = harden_shiji_step4_skeleton(skeleton, vol, work_id=work)
    return n, logs


def step4_hanshu_clear_placeholder_years(skeleton: Path) -> Tuple[int, list]:
    """《汉书》Step4：清空无考订依据的人物占位年生卒，逼完整 LLM。"""
    sk = Path(skeleton)
    if not sk.name.startswith("02汉书"):
        return 0, []
    sys.path.insert(0, str(ANNOTATE_DIR))
    from hanshu_step4_hardening import clear_entries_without_year_basis  # noqa: E402

    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries") or []
    n, logs = clear_entries_without_year_basis(entries, force_all_without_basis=True)
    if n:
        data["entries"] = entries
        with open(skeleton, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return n, logs


def step4_recover_before_fail(
    skeleton: Path, work: str, vol: str
) -> Tuple[bool, list]:
    """check_format final 失败前最后一轮脚本修复。"""
    if not str(work).startswith("01史记"):
        return False, []
    from step4_hardening import try_recover_step4_final  # noqa: E402

    return try_recover_step4_final(
        skeleton,
        vol,
        work_id=work,
        finalize_fn=step4_finalize,
        verify_final_fn=verify_step4_final,
    )


def step4_missing_report(skeleton: Path) -> str:
    code, out = _fill_fields_cmd(skeleton, "--report-missing")
    return out if code == 0 else ""


def step4_year_quality_issues(skeleton: Path) -> list:
    """check_format final 中的年代质量项（批量占位等），可在 finalize 前预检。"""
    sys.path.insert(0, str(ANNOTATE_DIR))
    from lib_config import validate_year_quality  # noqa: E402

    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)
    return validate_year_quality(data.get("entries") or [])


def step4_peak_year(skeleton: Path, *, use_llm: bool = True) -> Tuple[Dict[str, int], list]:
    """Step4d：年份终态后标注峰值年（规则 → LLM 分批 → 兜底）。失败不抛异常。"""
    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)
    if not (data.get("entries") or []):
        return {"total": 0, "skipped_empty": 1}, ["无 entries，跳过峰值年"]

    sys.path.insert(0, str(ANNOTATE_DIR))
    from peak_year import annotate_skeleton  # noqa: E402

    review_dir = paths()["annotate_work"]
    stats, logs = annotate_skeleton(
        skeleton,
        use_llm=use_llm,
        review_dir=review_dir,
    )
    return stats, logs


def step4_peak_verify(skeleton: Path) -> Tuple[bool, str]:
    """峰值年硬校验（缺字段/越界/非法类型）；低置信仅待审，不 fail。"""
    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries") or []
    if not entries:
        return True, "无 entries，跳过峰值校验"

    sys.path.insert(0, str(ANNOTATE_DIR))
    from peak_year import verify_entries_peak  # noqa: E402

    ok, issues = verify_entries_peak(entries)
    if ok:
        return True, "峰值年硬校验通过"
    return False, "\n".join(issues[:30])


def verify_step4_final(skeleton: Path) -> Tuple[bool, str]:
    code, out = run_cmd(
        [
            sys.executable,
            str(ANNOTATE_DIR / "check_format.py"),
            str(skeleton),
            "--phase",
            "final",
        ]
    )
    if code != 0:
        return False, out[-3000:]
    return True, "check_format final exit 0"
