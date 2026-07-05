#!/usr/bin/env python3
"""单卷标注流水线调度（白名单脚本，禁止 agent 自写批量标注脚本）。

用法:
  python3 run_volume_pipeline.py status --work 01史记
  python3 run_volume_pipeline.py init --work 01史记 [--scan]
  python3 run_volume_pipeline.py next --work 01史记
  python3 run_volume_pipeline.py verify --work 01史记 --vol 001 [--step 2]
  python3 run_volume_pipeline.py run --work 01史记 --vol 001 --through 4
  python3 run_volume_pipeline.py mark --work 01史记 --vol 001 --step 1 --status done
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent
ANNOTATE_DIR = SKILL_DIR.parent / "historiography-annotate"
AUDIT_DIR = SKILL_DIR.parent / "historiography-audit"

sys.path.insert(0, str(ANNOTATE_DIR))
from lib_config import get_histograph_root, paths  # noqa: E402
from paragraph_utils import check_paragraph_count, resolve_source_file  # noqa: E402

from hist_gates import (  # noqa: E402
    GateError,
    PIPELINE_STEPS,
    can_register_volume,
    enforce_pipeline,
    gate_fail,
    repair_mode,
)

from semantic_audit_verify import verify_semantic_audit  # noqa: E402
from evidence_verify import (  # noqa: E402
    verify_step1_evidence,
    verify_step3_evidence,
    DEFAULT_SPOT_COUNT,
)

STEPS = PIPELINE_STEPS
STEP_LABELS = {
    "1": "Step1 标注(LLM)",
    "2": "Step2 格式硬门",
    "3": "Step3 质检审计",
    "4": "Step4 字段补全+终检",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def progress_path(work: str) -> Path:
    p = paths()["progress"]
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{work}_progress.json"


def load_progress(work: str) -> dict:
    fp = progress_path(work)
    if not fp.exists():
        return {"work": work, "updated_at": None, "volumes": {}}
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    return _migrate_progress(data)


def _migrate_progress(data: dict) -> dict:
    """移除已废止的 Step5，并按四步重算 overall。"""
    for vol_rec in data.get("volumes", {}).values():
        steps = vol_rec.get("steps", {})
        if "5" in steps:
            steps.pop("5", None)
        vol_rec["overall"] = overall_status(steps)
    return data


def save_progress(work: str, data: dict) -> Path:
    data["work"] = work
    data["updated_at"] = utc_now()
    fp = progress_path(work)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fp


def find_skeletons(work: str) -> List[Path]:
    ann = paths()["annotations"]
    return sorted(ann.glob(f"{work}_*_skeleton.json"))


def parse_skeleton_name(path: Path, work: str) -> Tuple[str, str]:
    """返回 (vol_num_3d, volume_slug) 从 01史记_001_五帝本纪_skeleton.json"""
    stem = path.stem.replace("_skeleton", "")
    prefix = f"{work}_"
    if not stem.startswith(prefix):
        raise ValueError(f"文件名与著作前缀不匹配: {path.name}")
    rest = stem[len(prefix) :]
    m = re.match(r"^(\d{3})_(.+)$", rest)
    if not m:
        raise ValueError(f"无法解析卷号: {path.name}")
    return m.group(1), m.group(2)


def skeleton_for(work: str, vol: str) -> Optional[Path]:
    vol = vol.zfill(3)
    matches = sorted(paths()["annotations"].glob(f"{work}_{vol}_*_skeleton.json"))
    return matches[0] if matches else None


def load_paragraph_index(work: str, vol: str) -> dict:
    fp = paths()["paragraph_index"] / f"{work}_{vol.zfill(3)}.json"
    if not fp.exists():
        raise FileNotFoundError(f"缺少段落索引: {fp}")
    return json.loads(fp.read_text(encoding="utf-8"))


def load_skeleton_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evidence_spot_count() -> int:
    import os

    return int(os.environ.get("HIST_EVIDENCE_SPOT_COUNT", DEFAULT_SPOT_COUNT))


def resolve_src_dir(data: dict, skeleton: Optional[Path] = None) -> Optional[Path]:
    src = resolve_source_file(data, skeleton) if skeleton else resolve_source_file(data)
    if src and src.is_file():
        return src.parent
    root = get_histograph_root()
    rel = data.get("原文路径") or data.get("source_file") or ""
    if not rel:
        return None
    rel_path = Path(rel)
    if rel_path.is_absolute():
        return rel_path.parent if rel_path.suffix else rel_path
    full = paths()["data"] / rel_path
    if full.is_file():
        return full.parent
    if full.parent.exists():
        return full.parent
    legacy = root / "史料合集" / rel_path
    if legacy.is_file():
        return legacy.parent
    if legacy.parent.exists():
        return legacy.parent
    sources = paths()["sources"]
    for sub in sources.iterdir():
        if sub.is_dir():
            candidate = sub / rel_path.name
            if candidate.exists():
                return sub
    return sources


def step_record(status: str = "pending", **extra: Any) -> dict:
    rec = {"status": status, "at": utc_now() if status == "done" else None}
    rec.update(extra)
    return rec


def ensure_volume(progress: dict, work: str, vol: str, skeleton: Optional[Path] = None) -> dict:
    vol = vol.zfill(3)
    volumes = progress.setdefault("volumes", {})
    if vol not in volumes:
        volumes[vol] = {
            "skeleton_file": skeleton.name if skeleton else None,
            "volume_name": None,
            "steps": {s: step_record() for s in STEPS},
            "overall": "not_started",
            "blocked_reason": None,
        }
    if skeleton:
        volumes[vol]["skeleton_file"] = skeleton.name
        try:
            data = load_skeleton_json(skeleton)
            volumes[vol]["volume_name"] = data.get("volume")
        except (json.JSONDecodeError, OSError):
            pass
    return volumes[vol]


def overall_status(steps: dict) -> str:
    if all(steps.get(s, {}).get("status") == "done" for s in STEPS):
        return "done"
    if any(steps.get(s, {}).get("status") == "failed" for s in STEPS):
        return "failed"
    if any(steps.get(s, {}).get("status") == "done" for s in STEPS):
        return "in_progress"
    return "not_started"


def run_script(cmd: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def verify_step1(skeleton: Path) -> Tuple[bool, str]:
    if not skeleton.exists():
        return False, f"skeleton 不存在: {skeleton}"
    try:
        data = load_skeleton_json(skeleton)
    except json.JSONDecodeError as e:
        return False, f"JSON 无效: {e}"
    for key in ("volume", "source_file", "total_paragraphs", "segment_attribution", "entries"):
        if key not in data:
            return False, f"缺少顶层字段: {key}"
    n = data["total_paragraphs"]
    attr = data["segment_attribution"]
    if len(attr) != n:
        return False, f"segment_attribution 段数 {len(attr)} != total_paragraphs {n}"
    if not data.get("entries") and data.get("volume_type") not in (
        "表", "志书数据", "目录艺文", "艺文目录", "非人物叙事"
    ):
        return False, "entries 为空"
    ok_para, para_msg, _, actual = check_paragraph_count(data, skeleton)
    if not ok_para:
        return False, para_msg
    from evidence_verify import _validate_skeleton_schema  # noqa: WPS433

    schema_errs = _validate_skeleton_schema(data)
    if schema_errs:
        return False, "Step1 skeleton 格式不符：\n" + "\n".join(
            f"  - {e}" for e in schema_errs
        )
    hint = f"，原文 {actual} 段" if actual > 0 else ""
    from identity_gate import validate_skeleton_identity  # noqa: WPS433

    work_m = re.search(r"^(\d{2}[^_]+)_(\d{3})_", skeleton.name)
    if work_m:
        ok_id, id_msg = validate_skeleton_identity(work_m.group(1), work_m.group(2), data)
        if not ok_id:
            return False, id_msg
    from exclude_content_gate import validate_skeleton_excludes  # noqa: WPS433
    from paragraph_utils import resolve_source_file, split_mode_for_work, split_paragraphs

    src = resolve_source_file(data, skeleton)
    if src and src.is_file():
        raw = src.read_text(encoding="utf-8")
        work = work_m.group(1) if work_m else ""
        lines = split_paragraphs(raw, split_mode_for_work(work, raw))
        para_text = {i + 1: ln for i, ln in enumerate(lines)}
        ok_ex, ex_msg = validate_skeleton_excludes(data, para_text, work_id=work)
        if not ok_ex:
            return False, ex_msg
    return True, f"骨架就绪: {len(data.get('entries', []))} 条, {n} 段{hint}"


def verify_step2(skeleton: Path, data: dict) -> Tuple[bool, str]:
    src = resolve_src_dir(data, skeleton)
    if not src:
        return False, "无法定位原文目录，请补全 原文路径"
    orch_lib = SKILL_DIR.parent / "historiography-orchestrator" / "lib"
    sys.path.insert(0, str(orch_lib))
    try:
        from gates import step2_prepare  # noqa: WPS433

        step2_prepare(skeleton)
    except Exception:
        pass
    cmd = [
        sys.executable,
        str(ANNOTATE_DIR / "check_format.py"),
        str(skeleton),
        "--phase",
        "skeleton",
        "--src-dir",
        str(src),
    ]
    code, out = run_script(cmd)
    if code != 0:
        return False, f"check_format skeleton 失败 (exit {code})\n{out[-2000:]}"
    return True, "check_format skeleton 通过"


def verify_step3_precheck(skeleton: Path) -> Tuple[bool, str]:
    cmd = [sys.executable, str(AUDIT_DIR / "audit_precheck.py"), str(skeleton)]
    code, out = run_script(cmd)
    if code != 0:
        return False, f"audit_precheck 失败 (exit {code})\n{out[-2000:]}"
    return True, "audit_precheck 通过"


def verify_step3_semantic(work: str, vol: str, data: dict) -> Tuple[bool, str]:
    volume = data.get("volume", "")
    total = int(data.get("total_paragraphs") or 0)
    audit_file = paths()["audit"] / f"{work}_标注审计.md"
    if not audit_file.exists():
        return False, f"缺少审计 MD: {audit_file}（需 historiography-audit Step3 落盘）"
    text = audit_file.read_text(encoding="utf-8")
    return verify_semantic_audit(
        text,
        work=work,
        vol=vol.zfill(3),
        volume_name=volume,
        total_paragraphs=total,
    )


def verify_step4_final(skeleton: Path, data: dict) -> Tuple[bool, str]:
    src = resolve_src_dir(data, skeleton)
    if not src:
        return False, "无法定位原文目录"
    cmd = [
        sys.executable,
        str(ANNOTATE_DIR / "check_format.py"),
        str(skeleton),
        "--phase",
        "final",
        "--src-dir",
        str(src),
    ]
    code, out = run_script(cmd)
    if code != 0:
        return False, f"check_format final 失败 (exit {code})\n{out[-2000:]}"
    return True, "check_format final 通过（含优先级/年份/归属）"


def verify_step(work: str, vol: str, step: str) -> Tuple[bool, str]:
    skeleton = skeleton_for(work, vol)
    if not skeleton:
        return False, f"未找到 skeleton: {work}_{vol.zfill(3)}_*_skeleton.json"
    data = load_skeleton_json(skeleton)
    if step == "1":
        ok, msg = verify_step1(skeleton)
        if not ok:
            return ok, msg
        try:
            idx = load_paragraph_index(work, vol)
        except FileNotFoundError as e:
            return False, str(e)
        return verify_step1_evidence(
            work, vol, skeleton, idx, spot_count=evidence_spot_count()
        )
    if step == "2":
        ok, msg = verify_step1(skeleton)
        if not ok:
            return ok, f"Step1 未就绪: {msg}"
        return verify_step2(skeleton, data)
    if step == "3":
        ok, msg = verify_step2(skeleton, data)
        if not ok:
            return ok, f"Step2 未通过: {msg}"
        ok2, msg2 = verify_step3_precheck(skeleton)
        if not ok2:
            return ok2, msg2
        ok3, msg3 = verify_step3_semantic(work, vol, data)
        if not ok3:
            return ok3, msg3
        audit_file = paths()["audit"] / f"{work}_标注审计.md"
        audit_text = audit_file.read_text(encoding="utf-8")
        try:
            idx = load_paragraph_index(work, vol)
        except FileNotFoundError as e:
            return False, str(e)
        return verify_step3_evidence(
            work,
            vol,
            data,
            audit_text,
            idx,
            spot_count=evidence_spot_count(),
        )
    if step == "4":
        ok, msg = verify_step(work, vol, "3")
        if not ok:
            return ok, f"Step3 未完成: {msg}"
        return verify_step4_final(skeleton, data)
    return False, f"未知 step: {step}（有效步: {', '.join(STEPS)}）"


def update_step(progress: dict, vol: str, step: str, ok: bool, detail: str) -> None:
    vol = vol.zfill(3)
    rec = progress["volumes"][vol]["steps"][step]
    rec["status"] = "done" if ok else "failed"
    rec["at"] = utc_now()
    rec["detail"] = detail.strip()[:2000]
    progress["volumes"][vol]["overall"] = overall_status(progress["volumes"][vol]["steps"])


def cmd_init(work: str, scan: bool) -> int:
    progress = load_progress(work)
    if scan:
        registered = 0
        skipped = 0
        for sk in find_skeletons(work):
            vol, _ = parse_skeleton_name(sk, work)
            vol = vol.zfill(3)
            if vol in progress.get("volumes", {}):
                ensure_volume(progress, work, vol, sk)
                continue
            if repair_mode():
                ensure_volume(progress, work, vol, sk)
                registered += 1
                continue
            ok, reason = can_register_volume(work, vol, progress)
            if not ok:
                skipped += 1
                continue
            ensure_volume(progress, work, vol, sk)
            registered += 1
            print(f"   + 登记卷 {vol} ({reason})")
        if skipped and not repair_mode():
            print(
                f"⏭  跳过 {skipped} 卷（硬门：仅按序登记下一卷；全量扫描请 HIST_REPAIR=1）"
            )
        if registered == 0 and not progress.get("volumes"):
            print(f"⚠️ 未登记任何卷。首卷 skeleton 须存在，或 HIST_REPAIR=1 全量 init --scan")
            return 1
    elif not progress.get("volumes"):
        print(f"⚠️ 进度为空。请加 --scan 扫描已有 skeleton，或先标注 Step1 落盘。")
        return 1
    fp = save_progress(work, progress)
    print(f"✅ 已初始化/更新进度: {fp}")
    print(f"   卷数: {len(progress.get('volumes', {}))}")
    return 0


def cmd_status(work: str) -> int:
    progress = load_progress(work)
    volumes = progress.get("volumes", {})
    if not volumes:
        print(f"⚠️ 无进度记录。运行: init --work {work} --scan")
        return 1
    done = sum(1 for v in volumes.values() if v.get("overall") == "done")
    print(f"\n📋 {work} 标注进度 ({done}/{len(volumes)} 卷完成)")
    print(f"   文件: {progress_path(work)}")
    for vol in sorted(volumes.keys()):
        v = volumes[vol]
        name = v.get("volume_name") or v.get("skeleton_file") or "?"
        steps = v.get("steps", {})
        icons = "".join("✓" if steps.get(s, {}).get("status") == "done" else "·" for s in STEPS)
        print(f"   {vol} {name:12s} [{icons}] {v.get('overall', '?')}")
    return 0


def cmd_next(work: str) -> int:
    progress = load_progress(work)
    volumes = progress.get("volumes", {})
    if not volumes:
        print(f"⚠️ 先 init --scan。若无 skeleton，从 Step1 标注第一卷。")
        return 1
    for vol in sorted(volumes.keys()):
        v = volumes[vol]
        if v.get("overall") == "done":
            continue
        steps = v.get("steps", {})
        for s in STEPS:
            if steps.get(s, {}).get("status") != "done":
                name = v.get("volume_name") or "?"
                print(f"\n▶ 下一任务: {work} 卷 {vol} ({name})")
                print(f"   当前步: Step{s} — {STEP_LABELS[s]}")
                sk = skeleton_for(work, vol)
                if sk:
                    print(f"   skeleton: {sk}")
                if s == "1":
                    print("   → 激活 historiography-annotate，完成 Step1 落盘")
                elif s == "3":
                    print("   → 跑 verify --step 2 通过后，激活 historiography-audit")
                elif s == "4":
                    print("   → fill_fields.py + LLM 补全 + verify --step 4")
                else:
                    print(f"   → python3 run_volume_pipeline.py verify --work {work} --vol {vol} --step {s}")
                return 0
    print(f"✅ {work} 全部卷已完成 Step1-4")
    return 0


def cmd_verify(work: str, vol: str, step: Optional[str], force_order: bool) -> int:
    progress = load_progress(work)
    vol = vol.zfill(3)
    try:
        enforce_pipeline(work, vol, progress, force_order=force_order)
    except GateError as e:
        gate_fail(str(e))
    skeleton = skeleton_for(work, vol)
    ensure_volume(progress, work, vol, skeleton)
    steps_to_run = [step] if step else list(STEPS)
    exit_code = 0
    for s in steps_to_run:
        if s not in STEPS:
            print(f"❌ 非法 step: {s}")
            return 1
        ok, msg = verify_step(work, vol, s)
        sym = "✅" if ok else "❌"
        print(f"{sym} Step{s} ({STEP_LABELS[s]}): {msg.split(chr(10))[0]}")
        if not ok and len(msg) > 80:
            print(f"   … {msg[-500:]}")
        update_step(progress, vol, s, ok, msg)
        if not ok:
            exit_code = 1
            if step is None:
                break
    save_progress(work, progress)
    return exit_code


def cmd_run(work: str, vol: str, through: int, force_order: bool) -> int:
    """自动跑脚本可验证的步骤（不替代 LLM Step1/3语义）。"""
    progress = load_progress(work)
    vol = vol.zfill(3)
    try:
        enforce_pipeline(work, vol, progress, force_order=force_order)
    except GateError as e:
        gate_fail(str(e))
    ensure_volume(progress, work, vol, skeleton_for(work, vol))
    exit_code = 0
    for s in STEPS:
        if int(s) > through:
            break
        if s in ("1",):
            ok, msg = verify_step(work, vol, s)
            if not ok:
                print(f"⏸ Step1 需 LLM: {msg}")
                exit_code = 1
                break
        else:
            ok, msg = verify_step(work, vol, s)
            sym = "✅" if ok else "❌"
            print(f"{sym} Step{s}: {msg.split(chr(10))[0]}")
            update_step(progress, vol, s, ok, msg)
            if not ok:
                if s == "3":
                    print("   → Step3 需 historiography-audit 语义审计并落盘审计 MD")
                elif s == "4":
                    print("   → Step4 需 fill_fields + LLM 补全字段")
                exit_code = 1
                break
    save_progress(work, progress)
    return exit_code


def cmd_mark(
    work: str, vol: str, step: str, status: str, note: str, force: bool, force_order: bool
) -> int:
    if step not in STEPS:
        print(f"❌ step 必须是 {STEPS[0]}-{STEPS[-1]}")
        return 1
    if status not in ("done", "pending", "failed"):
        print("❌ status 必须是 done|pending|failed")
        return 1
    progress = load_progress(work)
    vol = vol.zfill(3)
    if status == "done" and force and not repair_mode():
        allow_force = paths()["allow_force"].exists()
        if not allow_force:
            gate_fail(
                "mark --force 已禁用。创建 data/05工作流中间产物/编排/allow_force 或改用 verify 通过。"
            )
    if status in ("done", "failed"):
        try:
            enforce_pipeline(work, vol, progress, force_order=force_order)
        except GateError as e:
            gate_fail(str(e))
    ensure_volume(progress, work, vol, skeleton_for(work, vol))
    if status == "done" and not force:
        ok, msg = verify_step(work, vol, step)
        if not ok:
            print(f"❌ 验证未通过，不能 mark done（加 --force 强制）:\n{msg}")
            return 1
    rec = progress["volumes"][vol.zfill(3)]["steps"][step]
    rec["status"] = status
    rec["at"] = utc_now() if status != "pending" else None
    if note:
        rec["note"] = note
    progress["volumes"][vol.zfill(3)]["overall"] = overall_status(
        progress["volumes"][vol.zfill(3)]["steps"]
    )
    save_progress(work, progress)
    print(f"✅ 已标记 {work} 卷{vol.zfill(3)} Step{step} = {status}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="史料标注单卷流水线（白名单）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="查看著作进度")
    p_status.add_argument("--work", required=True, help="著作前缀，如 01史记")

    p_init = sub.add_parser("init", help="初始化进度文件")
    p_init.add_argument("--work", required=True)
    p_init.add_argument("--scan", action="store_true", help="扫描已有 skeleton 建卷列表")

    p_next = sub.add_parser("next", help="下一待办卷与步骤")
    p_next.add_argument("--work", required=True)

    p_verify = sub.add_parser("verify", help="验证并更新某步状态")
    p_verify.add_argument("--work", required=True)
    p_verify.add_argument("--vol", required=True, help="卷号，如 001")
    p_verify.add_argument("--step", choices=list(STEPS), help="仅验证指定步")
    p_verify.add_argument(
        "--force-order",
        action="store_true",
        help="跳过卷序检查（仍须租约；修复请优先 HIST_REPAIR=1）",
    )

    p_run = sub.add_parser("run", help="自动跑到指定步（脚本门）")
    p_run.add_argument("--work", required=True)
    p_run.add_argument("--vol", required=True)
    p_run.add_argument("--through", type=int, default=2, choices=[1, 2, 3, 4, 5])
    p_run.add_argument("--force-order", action="store_true")

    p_mark = sub.add_parser("mark", help="手动标记步骤（默认需 verify 通过）")
    p_mark.add_argument("--work", required=True)
    p_mark.add_argument("--vol", required=True)
    p_mark.add_argument("--step", required=True, choices=list(STEPS))
    p_mark.add_argument("--status", required=True, choices=["done", "pending", "failed"])
    p_mark.add_argument("--note", default="")
    p_mark.add_argument("--force", action="store_true")
    p_mark.add_argument("--force-order", action="store_true")

    args = parser.parse_args()
    if args.command == "status":
        return cmd_status(args.work)
    if args.command == "init":
        return cmd_init(args.work, args.scan)
    if args.command == "next":
        return cmd_next(args.work)
    if args.command == "verify":
        return cmd_verify(args.work, args.vol, args.step, args.force_order)
    if args.command == "run":
        return cmd_run(args.work, args.vol, args.through, args.force_order)
    if args.command == "mark":
        return cmd_mark(
            args.work,
            args.vol,
            args.step,
            args.status,
            args.note,
            args.force,
            args.force_order,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
