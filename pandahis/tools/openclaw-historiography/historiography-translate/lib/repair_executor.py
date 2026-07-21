"""根据 repair_ticket 执行定向修复（非盲重跑）。"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any, List, Tuple

from shared.qa_repair import RepairPlan, classify_translate_failure  # noqa: E402

from lib.attribution import apply_attribution_fixes  # noqa: E402
from lib.plan_postprocess import finalize_plan  # noqa: E402
from lib.recall import recall_entry  # noqa: E402
from lib.refine import refine_entry  # noqa: E402
from lib.repair_ticket import load_repair_ticket, save_repair_ticket  # noqa: E402
from lib.verify import load_output, verify_output  # noqa: E402
from lib.work_artifacts import plan_path  # noqa: E402


def _plan_from_dict(data: dict[str, Any]) -> RepairPlan:
    allowed = {f.name for f in fields(RepairPlan)}
    kwargs = {k: v for k, v in data.items() if k in allowed}
    if "invalidate" in kwargs and isinstance(kwargs["invalidate"], list):
        kwargs["invalidate"] = tuple(kwargs["invalidate"])
    return RepairPlan(**kwargs)


def execute_repair(
    entry_id: str,
    *,
    work_dir: Path,
    out_dir: Path,
    index_path: Path | None = None,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """读取工单并执行 disposition。返回 (成功与否, 说明)。"""
    ticket = load_repair_ticket(work_dir, entry_id)
    if not ticket:
        return False, f"无修复工单：{work_dir}/{entry_id}.repair.json（请先 run-one 失败或 verify）"

    plan = _plan_from_dict(ticket.get("plan") or {})
    errors = list(ticket.get("errors") or [])
    stage = str(ticket.get("stage") or "")
    fail_count = int(ticket.get("fail_count") or 0)

    if dry_run:
        return True, (
            f"dry-run repair {entry_id}: {plan.root_cause} → {plan.disposition} / {plan.action}\n"
            f"{plan.structured_prompt[:500]}"
        )

    if plan.disposition == "route_pipeline":
        return True, (
            f"↪ 已归类为转线（{plan.root_cause}）→ {plan.route_to or 'dynasty_supplement'}\n"
            f"建议：{plan.next_command or '朝代知识补全 candidates-renwu → fill-renwu → compose-detail'}"
        )

    if plan.disposition == "needs_human":
        return False, f"需人工：{plan.structured_prompt}"

    recalled = recall_entry(entry_id, index_path=index_path)
    entry_name = str(recalled.get("史略名称") or ticket.get("entry_name") or "")

    if plan.disposition == "script_fix" and plan.refine_scope == "attribution":
        ok, data, errs = load_output(entry_id, out_dir, entry_name)
        if not ok:
            return False, "; ".join(errs)
        pf = plan_path(entry_id, entry_name, work_dir)
        plan_data = {}
        if pf.is_file():
            import json

            plan_data = finalize_plan(json.loads(pf.read_text(encoding="utf-8")), recalled)
        detail = str(data.get("翻译详情") or "")
        fixed, changes = apply_attribution_fixes(detail, recalled, plan_data)
        if not changes:
            return False, "归因脚本未产生变更"
        data["翻译详情"] = fixed
        from lib.verify import resolve_output_path

        target = resolve_output_path(entry_id, out_dir, entry_name)
        target.write_text(
            __import__("json").dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        v_ok, v_errs = verify_output(entry_id, recalled, out_dir, plan=plan_data)
        if v_ok:
            return True, f"归因修复完成：{changes}"
        save_repair_ticket(
            work_dir,
            entry_id=entry_id,
            entry_name=entry_name,
            stage="verify",
            errors=v_errs,
            plan=classify_translate_failure(v_errs, stage="verify", fail_count=fail_count + 1),
            fail_count=fail_count + 1,
        )
        return False, f"归因后仍失败：{'; '.join(v_errs[:3])}"

    if plan.disposition == "refine_scope" and plan.refine_scope:
        scope = plan.refine_scope
        if scope not in ("intro", "mother", "tail", "full", "attribution"):
            scope = "full"
        ok, msg = refine_entry(
            entry_id,
            scope=scope,
            instructions=plan.structured_prompt,
            index_path=index_path,
            output_dir=out_dir,
        )
        return ok, msg

    if plan.disposition == "retry_llm":
        from lib import runner
        import os

        feedback = str(ticket.get("feedback") or "").strip()
        if feedback:
            os.environ["TRANSLATE_REPAIR_FEEDBACK"] = feedback[:3500]
        try:
            if plan.invalidate and "plan" in plan.invalidate:
                pf = plan_path(entry_id, entry_name, work_dir)
                if pf.is_file():
                    pf.unlink()
            from_phase = "phase2" if stage.startswith("phase2") or "enrich" in stage else None
            rc = runner.run_one(
                entry_id,
                index_path=index_path,
                use_llm=True,
                from_phase=from_phase,
            )
        finally:
            os.environ.pop("TRANSLATE_REPAIR_FEEDBACK", None)
        if rc == 0:
            return True, "带修复上下文重跑完成"
        if rc == 2:
            return True, "已转线至朝代知识补全（见 repair_ticket）"
        ticket2 = load_repair_ticket(work_dir, entry_id)
        err_hint = ""
        if ticket2:
            err_hint = "; ".join((ticket2.get("errors") or [])[:2])
        return False, f"重跑仍失败：{err_hint}"

    return False, f"未支持的 disposition：{plan.disposition}"


def print_repair_status(work_dir: Path, entry_id: str) -> int:
    ticket = load_repair_ticket(work_dir, entry_id)
    if not ticket:
        print(f"无工单 {entry_id}")
        return 1
    plan = ticket.get("plan") or {}
    print(f"史略ID: {entry_id}")
    print(f"阶段: {ticket.get('stage')}")
    print(f"根因: {plan.get('root_cause')}")
    print(f"处置: {plan.get('disposition')} / {plan.get('action')}")
    if plan.get("next_command"):
        print(f"建议命令: {plan.get('next_command')}")
    print("\n--- 结构化反馈 ---\n")
    print(ticket.get("feedback") or "")
    return 0
