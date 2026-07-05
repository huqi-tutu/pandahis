"""Step4 坐标冲突人工决策（awaiting_decision 状态）。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from lib.config import ANNOTATE_DIR, paths

sys.path.insert(0, str(ANNOTATE_DIR))

from fill_fields import apply_coord_decision, collect_coord_decisions  # noqa: E402

INTERACTIVE_CHOICES = (
    ("1", "emperor-ssot", "采用帝王表坐标（推荐）"),
    ("2", "keep-current", "保留当前 skeleton 坐标"),
)


class DecisionRequired(Exception):
    """校验失败须人工决策；不消耗重试次数。"""

    def __init__(
        self,
        work: str,
        vol: str,
        decision_path: Path,
        summary: str,
        *,
        interactive: bool = False,
        kind: str = "coord_mismatch",
    ):
        self.work = work
        self.vol = vol
        self.decision_path = decision_path
        self.summary = summary
        self.interactive = interactive
        self.kind = kind
        super().__init__(summary)


class DurationHardFail(Exception):
    """Step1/3 LLM 用时低于硬门槛。"""

    def __init__(
        self,
        step: str,
        elapsed: float,
        hard_floor: int,
        detail: str = "",
    ):
        self.step = step
        self.elapsed = elapsed
        self.hard_floor = hard_floor
        self.detail = detail
        super().__init__(
            f"Step{step} 用时 {elapsed:.1f}s < 硬门槛 {hard_floor}s"
            f"（疑似未真正执行 LLM 或秒回空完成；主门控仍为 verify）"
        )


def decisions_dir() -> Path:
    d = paths()["decisions"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def decision_path(work: str, vol: str, step: str = "4") -> Path:
    return decisions_dir() / f"{work}_{vol.zfill(3)}_step{step}.json"


def duration_decision_path(work: str, vol: str, step: str) -> Path:
    return decisions_dir() / f"{work}_{vol.zfill(3)}_step{step}_duration.json"


def is_duration_hard_fail_msg(msg: str) -> bool:
    return "硬门槛" in msg and "用时" in msg


def parse_elapsed_from_duration_msg(msg: str) -> Optional[float]:
    import re

    m = re.search(r"用时\s*([\d.]+)s", msg or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def format_duration_bypass_summary(
    work: str, vol: str, step: str, elapsed: float, hard_floor: int
) -> str:
    return (
        f"\n{'━' * 52}\n"
        f"⏸ Step{step} 用时过短 — {work} 卷{vol.zfill(3)}\n"
        f"{'━' * 52}\n"
        f"LLM 仅 {elapsed:.1f}s（硬门槛 {hard_floor}s），已连续失败 2 次。\n"
        f"worker 可能秒回未完成；也可能确实很快写完（需你人工质检）。\n"
        f"{'━' * 52}"
    )


def prompt_duration_bypass_interactive(
    work: str, vol: str, step: str, elapsed: float, hard_floor: int
) -> Optional[str]:
    """
    返回 bypass | retry | pause；非交互或选 q 返回 pause。
    """
    if not stdin_is_interactive():
        return "pause"

    print(format_duration_bypass_summary(work, vol, step, elapsed, hard_floor), flush=True)
    print("请选择：", flush=True)
    print("  1) 放行：跳过用时门槛，继续跑 verify（你自行质检）", flush=True)
    print("  2) 重试：再跑一次 LLM", flush=True)
    print("  q) 暂停跑批", flush=True)
    print(flush=True)

    while True:
        try:
            raw = input("请输入选项 [1/2/q]（回车=1）: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已暂停。", flush=True)
            return "pause"
        if raw in ("", "1"):
            return "bypass"
        if raw == "2":
            return "retry"
        if raw in ("q", "quit", "n"):
            return "pause"
        print("无效输入，请输入 1、2 或 q。", flush=True)


def save_duration_decision_file(
    work: str,
    vol: str,
    step: str,
    *,
    elapsed: float,
    hard_floor: int,
) -> Path:
    p = duration_decision_path(work, vol, step)
    doc = {
        "kind": "duration_bypass",
        "work": work,
        "vol": vol.zfill(3),
        "step": step,
        "elapsed_sec": round(elapsed, 1),
        "hard_floor_sec": hard_floor,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return p


def load_duration_decision_file(work: str, vol: str, step: str) -> Optional[dict]:
    p = duration_decision_path(work, vol, step)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def handle_duration_hard_fail(
    work: str,
    vol: str,
    step: str,
    job_id: int,
    job: dict,
    err: DurationHardFail,
) -> str:
    """
    处理 Step1/3 用时硬失败。
    返回: retry | bypass | pause
    """
    from lib import db, events, gates

    max_retries = gates.max_retries_per_step(work, step)
    fail_count = int(job.get("fail_count") or 0) + 1
    msg = str(err)

    db.update_job(
        job_id,
        status="failed",
        finished_at=db.utc_now(),
        fail_count=fail_count,
        detail=msg[:2000],
    )
    events.log(
        "job_failed",
        work=work,
        vol=vol,
        step=step,
        error=msg[:500],
        fail_count=fail_count,
        reason="duration_hard_fail",
    )

    if fail_count < max_retries:
        db.update_job(
            job_id,
            status="pending",
            finished_at=None,
            started_at=None,
            session_id=None,
        )
        events.log(
            "job_retry_scheduled",
            work=work,
            vol=vol,
            step=step,
            attempt=fail_count,
            max_retries=max_retries,
            reason="duration_hard_fail",
        )
        print(
            f"⚠️ 卷{vol} Step{step} 用时过短 ({fail_count}/{max_retries})，将自动重试",
            flush=True,
        )
        return "retry"

    dp = save_duration_decision_file(
        work, vol, step, elapsed=err.elapsed, hard_floor=err.hard_floor
    )
    choice = prompt_duration_bypass_interactive(
        work, vol, step, err.elapsed, err.hard_floor
    )

    if choice == "bypass":
        if dp.exists():
            dp.unlink()
        db.update_job(
            job_id,
            status="running",
            fail_count=0,
            detail="duration_bypass:verify_only",
            finished_at=None,
        )
        events.log(
            "duration_bypass_accepted",
            work=work,
            vol=vol,
            step=step,
            elapsed_sec=err.elapsed,
        )
        print(
            f"✅ 已放行 Step{step} 用时门槛，继续 verify（请自行质检本卷）",
            flush=True,
        )
        return "bypass"

    if choice == "retry":
        db.update_job(
            job_id,
            status="pending",
            fail_count=0,
            finished_at=None,
            started_at=None,
            session_id=None,
        )
        events.log("duration_bypass_retry", work=work, vol=vol, step=step)
        print(f"▶ 将重新跑 Step{step} LLM", flush=True)
        return "retry"

    summary = (
        format_duration_bypass_summary(work, vol, step, err.elapsed, err.hard_floor)
        + "\n已暂停。在终端 hist run-work 将弹出选项。"
    )
    db.update_job(
        job_id,
        status="pending",
        finished_at=None,
        started_at=None,
        session_id=None,
        detail=summary[:2000],
    )
    db.set_work_status(work, "awaiting_decision", blocked_reason=msg[:500])
    events.log(
        "awaiting_decision",
        work=work,
        vol=vol,
        step=step,
        decision_file=str(dp),
        kind="duration_bypass",
    )
    print(summary, flush=True)
    return "pause"


def try_resume_duration_decision(work: str) -> bool:
    """paused/awaiting_decision 且为用时门槛时，终端弹出放行选项。"""
    from lib import db, events

    w = db.get_work(work)
    if not w:
        return True

    vol = (w.get("current_vol") or "").zfill(3)
    step = str(w.get("current_step") or "")
    blocked = w.get("blocked_reason") or ""

    if w["status"] not in ("paused", "awaiting_decision"):
        return False

    doc = load_duration_decision_file(work, vol, step) if vol and step else None
    if not doc and not is_duration_hard_fail_msg(blocked):
        return False

    if not vol or not step:
        return False

    parsed = parse_elapsed_from_duration_msg(blocked)
    elapsed = float(
        (doc or {}).get("elapsed_sec")
        or parsed
        or 3.8
    )
    hard_floor = int((doc or {}).get("hard_floor_sec") or 5)

    if not stdin_is_interactive():
        print(
            format_duration_bypass_summary(work, vol, step, elapsed, hard_floor),
            flush=True,
        )
        print(
            f"   在终端执行: hist run-work --work {work}  或 hist resume --work {work}",
            flush=True,
        )
        print("   将弹出选项：放行继续 verify / 重试 LLM / 暂停", flush=True)
        return False

    if is_duration_hard_fail_msg(blocked) and not doc:
        save_duration_decision_file(work, vol, step, elapsed=elapsed, hard_floor=hard_floor)

    choice = prompt_duration_bypass_interactive(work, vol, step, elapsed, hard_floor)

    job = db.get_job(work, vol, step)
    if not job:
        return False

    if choice == "bypass":
        p = duration_decision_path(work, vol, step)
        if p.exists():
            p.unlink()
        db.update_job(
            job["id"],
            status="pending",
            fail_count=0,
            detail="duration_bypass:verify_only",
            finished_at=None,
            started_at=None,
            session_id=None,
        )
        db.set_work_status(
            work, "running", blocked_reason=None, current_vol=vol, current_step=step
        )
        events.log("duration_bypass_accepted", work=work, vol=vol, step=step, resumed=True)
        print(f"✅ 已放行，继续跑 Step{step} verify…", flush=True)
        return True

    if choice == "retry":
        p = duration_decision_path(work, vol, step)
        if p.exists():
            p.unlink()
        db.update_job(
            job["id"],
            status="pending",
            fail_count=0,
            finished_at=None,
            started_at=None,
            session_id=None,
        )
        db.set_work_status(work, "running", blocked_reason=None)
        return True

    return False


def save_decision_file(
    work: str,
    vol: str,
    payload: dict,
    *,
    step: str = "4",
    verify_msg: str = "",
) -> Path:
    p = decision_path(work, vol, step)
    doc = {
        "work": work,
        "vol": vol.zfill(3),
        "step": step,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verify_excerpt": (verify_msg or "")[-1500:],
        **payload,
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return p


def load_decision_file(work: str, vol: str, step: str = "4") -> Optional[dict]:
    p = decision_path(work, vol, step)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def format_decision_summary(doc: dict) -> str:
    """终端展示冲突摘要（不含 hist decide 命令）。"""
    work = doc.get("work", "")
    vol = doc.get("vol", "")
    lines = [
        "",
        "━" * 52,
        f"⏸ Step4 坐标冲突 — {work} 卷{vol}",
        "━" * 52,
        "以下条目的坐标链与帝王表不一致：",
    ]
    items = doc.get("items") or []
    for it in items[:10]:
        cur = it.get("current", {})
        exp = it.get("expected", {})
        fields = it.get("mismatched_fields") or []
        detail = "、".join(
            f"{f.replace('坐标', '')} {cur.get(f, '')}→{exp.get(f, '')}"
            for f in fields[:2]
        )
        lines.append(f"  · [{it.get('entry_id')}] {it.get('name')}  {detail}")
    if len(items) > 10:
        lines.append(f"  … 共 {len(items)} 条")
    lines.append("━" * 52)
    return "\n".join(lines)


def format_decision_prompt(doc: dict) -> str:
    """非交互环境：提示下次在终端跑批时会弹出选项。"""
    return (
        format_decision_summary(doc)
        + "\n后台/非交互模式已暂停；请在终端执行 hist run-work 将弹出选项。"
    )


def stdin_is_interactive() -> bool:
    """是否可在当前终端直接读用户输入。"""
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


def prompt_interactive_choice(doc: dict) -> Optional[str]:
    """
    终端交互选择。返回 emperor-ssot / keep-current；用户选稍后或 EOF 返回 None。
    """
    if not stdin_is_interactive():
        return None

    print(format_decision_summary(doc), flush=True)
    print("请选择：", flush=True)
    for key, _slug, label in INTERACTIVE_CHOICES:
        print(f"  {key}) {label}", flush=True)
    print("  q) 稍后决定，暂停跑批", flush=True)
    print(flush=True)

    key_to_slug = {k: slug for k, slug, _ in INTERACTIVE_CHOICES}
    while True:
        try:
            raw = input("请输入选项 [1/2/q]（回车=1）: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消，跑批暂停。", flush=True)
            return None
        if raw in ("", "1"):
            return key_to_slug["1"]
        if raw == "2":
            return key_to_slug["2"]
        if raw in ("q", "quit", "n"):
            print("已暂停，稍后可 hist run-work 继续选择。", flush=True)
            return None
        print("无效输入，请输入 1、2 或 q。", flush=True)


def choice_label(choice: str) -> str:
    for _k, slug, label in INTERACTIVE_CHOICES:
        if choice == slug:
            return label
    return choice


def build_decisions_from_skeleton(skeleton: Path) -> dict:
    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)
    return collect_coord_decisions(data)


def apply_decision(
    work: str,
    vol: str,
    choice: str,
    *,
    skeleton: Path,
    step: str = "4",
) -> Tuple[int, List[str]]:
    with open(skeleton, encoding="utf-8") as f:
        data = json.load(f)
    n, logs = apply_coord_decision(data, choice)
    with open(skeleton, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    p = decision_path(work, vol, step)
    if p.exists():
        p.unlink()
    return n, logs


def raise_coord_decision_required(
    work: str,
    vol: str,
    payload: dict,
    *,
    verify_msg: str = "",
    skeleton=None,
    restore_scratch=None,
) -> None:
    """保存决策文件；非交互则 restore scratch 并抛出 DecisionRequired。"""
    dp = save_decision_file(work, vol, payload, verify_msg=verify_msg)
    doc = {**payload, "work": work, "vol": vol.zfill(3)}
    if restore_scratch and skeleton is not None:
        restore_scratch(skeleton)
    raise DecisionRequired(
        work,
        vol,
        dp,
        format_decision_prompt(doc),
        interactive=False,
    )


def resolve_coord_conflict_interactive(
    work: str,
    vol: str,
    skeleton: Path,
    payload: dict,
    *,
    verify_fn,
    reconcile_fn,
) -> bool:
    """
    终端交互解决坐标冲突。
    成功返回 True；用户选稍后或无法交互时 restore + 抛 DecisionRequired。
    """
    from lib import gates

    vol_z = vol.zfill(3)
    doc = {**payload, "work": work, "vol": vol_z}
    save_decision_file(work, vol, payload)

    choice = prompt_interactive_choice(doc)
    if not choice:
        gates.step4_restore_scratch(skeleton)
        dp = decision_path(work, vol)
        raise DecisionRequired(
            work,
            vol,
            dp,
            format_decision_prompt(doc),
            interactive=False,
        )

    n, logs = apply_decision(work, vol, choice, skeleton=skeleton)
    print(f"\n✅ 已应用：{choice_label(choice)}（{n} 条）", flush=True)
    for line in logs[:8]:
        print(f"  · {line}", flush=True)

    ok, _ = reconcile_fn(skeleton)
    if ok:
        print("✅ Step4 reconcile（帝王表坐标链对齐）", flush=True)
    ok, msg = verify_fn(skeleton, require_clean=False)
    if not ok:
        payload2 = gates.step4_collect_decisions(skeleton)
        if payload2.get("items") and choice == "keep-current":
            gates.step4_restore_scratch(skeleton)
            doc = {**payload2, "work": work, "vol": vol_z}
            save_decision_file(work, vol, payload2)
            raise DecisionRequired(
                work,
                vol,
                decision_path(work, vol),
                format_decision_summary(doc)
                + "\n保留当前坐标仍无法通过校验，请修改帝王表/政权表后 hist run-work。",
                interactive=False,
            )
        if payload2.get("items"):
            return resolve_coord_conflict_interactive(
                work,
                vol,
                skeleton,
                payload2,
                verify_fn=verify_fn,
                reconcile_fn=reconcile_fn,
            )
        gates.step4_restore_scratch(skeleton)
        raise RuntimeError(f"决策后 Step4 仍校验失败:\n{msg}")
    print("✅ 决策后 Step4 字段校验通过", flush=True)
    return True


def try_auto_coord_decision(work: str, vol: str, choice: str = "emperor-ssot") -> bool:
    """无人值守：自动应用坐标决策并恢复 Step4 job。"""
    from lib import db, gates

    vol = vol.zfill(3)
    sk = gates.skeleton_path(work, vol)
    if not sk:
        return False
    payload = gates.step4_collect_decisions(sk)
    if not payload.get("items"):
        doc = load_decision_file(work, vol)
        if doc:
            payload = doc
    if not payload.get("items"):
        return False

    n, logs = apply_decision(work, vol, choice, skeleton=sk)
    print(f"  自动决策 {n} 条", flush=True)
    for line in logs[:4]:
        print(f"    · {line}", flush=True)

    ok, _ = gates.step4_reconcile(sk)
    ok, msg = gates.step4_verify_fields(sk, require_clean=False)
    if not ok:
        gates.step4_restore_scratch(sk)
        print(f"  ⚠️ 自动决策后仍校验失败: {msg[:200]}", flush=True)
        return False

    db.set_work_status(work, "running", blocked_reason=None, current_vol=vol, current_step="4")
    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE jobs SET status='pending', fail_count=0, detail=NULL,
                   session_id=NULL, started_at=NULL, finished_at=NULL
            WHERE work_id=? AND vol=? AND step='4'
            """,
            (work, vol),
        )
    dp = decision_path(work, vol)
    if dp.exists():
        dp.unlink()
    return True


def try_resume_awaiting_decision(work: str) -> bool:
    """若著作 awaiting_decision，在交互终端弹出选项；成功则恢复 running。"""
    from lib import db, gates

    w = db.get_work(work)
    if not w or w["status"] != "awaiting_decision":
        return True

    vol = (w.get("current_vol") or "").zfill(3)
    if not vol:
        return False

    doc = load_decision_file(work, vol)
    sk = gates.skeleton_path(work, vol)
    if not doc or not sk:
        print(f"⏸ {work} 等待决策，但缺少决策文件或 skeleton。", flush=True)
        return False

    if not stdin_is_interactive():
        print(format_decision_prompt({**doc, "work": work, "vol": vol}), flush=True)
        return False

    try:
        resolve_coord_conflict_interactive(
            work,
            vol,
            sk,
            doc,
            verify_fn=gates.step4_verify_fields,
            reconcile_fn=gates.step4_reconcile,
        )
    except DecisionRequired:
        return False

    db.set_work_status(work, "running", blocked_reason=None, current_vol=vol, current_step="4")
    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE jobs SET status='pending', fail_count=0, detail=NULL,
                   session_id=NULL, started_at=NULL, finished_at=NULL
            WHERE work_id=? AND vol=? AND step='4'
            """,
            (work, vol),
        )
    print(f"▶ {work} 卷{vol} 决策完成，继续跑批…", flush=True)
    return True
