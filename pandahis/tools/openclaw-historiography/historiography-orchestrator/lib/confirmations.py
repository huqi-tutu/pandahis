"""著作级人工确认关口（金标 / 封板 / 用户暂停恢复）。"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from lib import db
from lib.config import get_work_config, paths
from lib.decisions import stdin_is_interactive

# 终端 bracketed-paste / ANSI 残留
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _gold_volumes(work: str) -> list[str]:
    cfg = get_work_config(work)
    return [str(g).zfill(3) for g in cfg.get("gold_volumes", [])]


def _vol_steps_done(work: str, vol: str) -> bool:
    active_steps = ("1", "2", "3", "4")
    placeholders = ",".join("?" * len(active_steps))
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT status FROM jobs WHERE work_id=? AND vol=? AND step IN ({placeholders})",
            (work, vol, *active_steps),
        ).fetchall()
    return bool(rows) and all(r["status"] == "done" for r in rows)


def status_after_user_pause(work: str) -> str:
    """用户暂停后恢复时应回到的状态。"""
    cfg = get_work_config(work)
    w = db.get_work(work)
    if not w or w.get("gold_approved"):
        return "running"
    gold_vols = _gold_volumes(work)
    if gold_vols and all(_vol_steps_done(work, gv) for gv in gold_vols):
        return "gold_review"
    if gold_vols and w.get("status") == "gold_review":
        return "gold_review"
    return "running"


def format_gold_checkpoint_summary(work: str) -> str:
    cfg = get_work_config(work)
    w = db.get_work(work) or {}
    gold_vols = _gold_volumes(work)
    audit = paths()["audit"] / f"{work}_标注审计.md"
    lines = [
        "━" * 52,
        f"⏸ 金标卷待确认 — {work}（{cfg.get('title', work)}）",
        "━" * 52,
        f"金标卷：{', '.join(gold_vols) or '（未配置）'}",
    ]
    for gv in gold_vols:
        sk = paths()["annotations"].glob(f"{work}_{gv}_*_skeleton.json")
        sk_list = sorted(sk)
        if sk_list:
            lines.append(f"  · 卷{gv} skeleton: {sk_list[0].name}")
    if audit.exists():
        lines.append(f"审计：{audit}")
    done = db.count_jobs(work, "done")
    total = db.count_jobs(work)
    lines.append(f"进度：jobs done {done}/{total}")
    lines.append("━" * 52)
    return "\n".join(lines)


def format_work_review_summary(work: str) -> str:
    cfg = get_work_config(work)
    done = db.count_jobs(work, "done")
    total = db.count_jobs(work)
    lines = [
        "━" * 52,
        f"⏸ 全书待封板 — {work}（{cfg.get('title', work)}）",
        "━" * 52,
        f"全部卷步已完成：jobs {done}/{total}",
        f"封板后将执行 merge_volumes",
        "━" * 52,
    ]
    return "\n".join(lines)


def _clean_stdin_line(raw: str) -> str:
    """去掉 BOM、零宽字符、bracketed-paste 与 ANSI 转义。"""
    s = unicodedata.normalize("NFKC", raw or "")
    for ch in ("\ufeff", "\u200b", "\u00a0", "\r"):
        s = s.replace(ch, "")
    s = _ANSI_RE.sub("", s)
    s = s.replace("\x1b]200~", "").replace("\x1b[201~", "")
    return s.strip()


def _normalize_choice_token(raw: str) -> str:
    """取首行首词，兼容全角数字与同义词。"""
    line = _clean_stdin_line(raw).splitlines()[0].strip().lower()
    if not line:
        return ""
    token = line.split()[0]
    trans = str.maketrans("１２３ｑ", "123q")
    token = token.translate(trans)
    if token in ("y", "yes", "ok", "是", "确认", "通过", "封板", "继续"):
        return "1"
    if token in ("n", "no", "否", "暂停", "停", "取消"):
        return "q"
    if token and token[0] in ("1", "q"):
        return token[0]
    return token


def _looks_like_shell_paste(raw: str) -> bool:
    s = raw or ""
    return any(
        k in s
        for k in ("export ", "python3", "hist.py", "run-work", "HISTOGRAPH_ROOT")
    )


def _read_choice(prompt: str, valid: dict[str, str], default: str) -> Optional[str]:
    """valid: raw_input -> slug; default slug when empty."""
    hint_keys = sorted({k for k in valid if len(k) <= 2})
    attempts = 0
    while True:
        attempts += 1
        try:
            raw = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\n已退出确认（可另开终端继续其他著作）。", flush=True)
            return None
        cleaned = _clean_stdin_line(raw)
        if not cleaned:
            return default
        if _looks_like_shell_paste(raw):
            print(
                "⚠️ 此处只选 1 或 q，不要粘贴 shell 命令。"
                " 换著作请 Ctrl+C 退出本进程后另开终端。",
                flush=True,
            )
            continue
        token = _normalize_choice_token(raw)
        if token in valid:
            return valid[token]
        # 行内任意位置单独出现 1 / q（部分终端粘贴会粘连）
        for ch in ("1", "q"):
            if ch in valid and re.search(rf"(?<!\w){re.escape(ch)}(?!\w)", cleaned):
                return valid[ch]
        print(
            f"无效输入。只输入 1 或 q（回车={default}）。"
            f" 卡住请 Ctrl+C 退出。",
            flush=True,
        )
        if attempts >= 8:
            print(f"⚠️ 多次无效输入，按默认「{default}」继续。", flush=True)
            return default


def prompt_gold_checkpoint(work: str) -> Optional[str]:
    """
    返回 approve | pause；非交互返回 None。
    """
    if not stdin_is_interactive():
        return None

    print(format_gold_checkpoint_summary(work), flush=True)
    print("请选择：", flush=True)
    print("  1) 通过金标，继续标剩余卷", flush=True)
    print("  q) 暂停，稍后确认", flush=True)
    print(flush=True)

    return _read_choice(
        "请输入选项 [1/q]（回车=1）: ",
        {"1": "approve", "q": "pause", "quit": "pause", "n": "pause"},
        "approve",
    )


def prompt_work_review_checkpoint(work: str) -> Optional[str]:
    if not stdin_is_interactive():
        return None

    print(format_work_review_summary(work), flush=True)
    print("请选择：", flush=True)
    print("  1) 封板并完成 merge", flush=True)
    print("  q) 暂停，稍后确认", flush=True)
    print(flush=True)

    return _read_choice(
        "请输入选项 [1/q]（回车=1）: ",
        {"1": "approve", "q": "pause", "quit": "pause", "n": "pause"},
        "approve",
    )


def prompt_user_pause_resume(work: str, reason: str) -> Optional[str]:
    if not stdin_is_interactive():
        return None

    print("━" * 52, flush=True)
    print(f"⏸ {work} 已暂停", flush=True)
    if reason:
        print(f"原因：{reason}", flush=True)
    print("━" * 52, flush=True)
    print("请选择：", flush=True)
    print("  1) 继续跑批", flush=True)
    print("  q) 保持暂停", flush=True)
    print(flush=True)

    return _read_choice(
        "请输入选项 [1/q]（回车=1）: ",
        {"1": "resume", "q": "pause", "quit": "pause", "n": "pause"},
        "resume",
    )


def interactive_gold_checkpoint(work: str) -> bool:
    """
    金标卷跑完后交互确认。
    返回 True 表示已通过金标，调用方应继续 run_work。
    """
    choice = prompt_gold_checkpoint(work)
    if choice is None:
        print(f"⏸ 等待金标确认: hist approve-gold --work {work}", flush=True)
        print(f"   或在交互终端 hist run-work --work {work} 将弹出选项", flush=True)
        return False
    if choice == "approve":
        print(f"✅ 金标已通过，继续标剩余卷…", flush=True)
        return True
    print(f"⏸ 已暂停金标确认。稍后 hist run-work --work {work} 可再次选择。", flush=True)
    return False


def interactive_work_review_checkpoint(work: str) -> bool:
    choice = prompt_work_review_checkpoint(work)
    if choice is None:
        print(f"📋 {work} 全部卷步完成，进入 work_review", flush=True)
        print(f"   确认封板: hist approve-work --work {work}", flush=True)
        return False
    if choice == "approve":
        print(f"✅ 开始封板…", flush=True)
        return True
    print(f"⏸ 已暂停封板确认。稍后 hist run-work --work {work} 可再次选择。", flush=True)
    return False


def interactive_resume_from_user_pause(work: str) -> bool:
    w = db.get_work(work)
    if not w or w["status"] != "paused":
        return False
    reason = w.get("blocked_reason") or ""
    choice = prompt_user_pause_resume(work, reason)
    if choice is None:
        print(f"⏸ {work} 处于 paused: {reason}", flush=True)
        print(f"   修复后: hist resume --work {work}", flush=True)
        return False
    if choice == "resume":
        next_status = status_after_user_pause(work)
        db.set_work_status(work, next_status, blocked_reason=None)
        print(f"▶ {work} 已恢复（状态 → {next_status}）", flush=True)
        return True
    print(f"⏸ 保持暂停。", flush=True)
    return False
