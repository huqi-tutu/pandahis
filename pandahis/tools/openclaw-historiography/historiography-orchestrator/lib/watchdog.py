"""编排层 watchdog：识别长期无进展与同一阻塞反复出现。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from lib.config import get_work_config

MECHANICAL_BLOCK_KEYWORDS = (
    "卷首标题",
    "篇内小标题",
    "不得设 owners",
    "须 exclude_reason=",
)


def is_mechanical_blocked_reason(reason: str) -> bool:
    text = (reason or "").strip()
    return any(keyword in text for keyword in MECHANICAL_BLOCK_KEYWORDS)


def blocked_signature(state: str, vol: str, step: str, blocked: str) -> str:
    if state not in ("paused", "awaiting_decision"):
        return ""
    norm = re.sub(r"\s+", " ", (blocked or "").strip())
    if not norm:
        return ""
    return f"{state}|{(vol or '').zfill(3)}|{step}|{norm[:120]}"


@dataclass(frozen=True)
class WatchdogThresholds:
    idle_rounds: int = 8
    blocked_rounds: int = 3


def thresholds_for_work(work: str) -> WatchdogThresholds:
    cfg = get_work_config(work)
    idle = int(
        os.environ.get(
            "HIST_WATCHDOG_IDLE_ROUNDS",
            cfg.get("watchdog_idle_rounds", 8),
        )
    )
    blocked = int(
        os.environ.get(
            "HIST_WATCHDOG_BLOCKED_ROUNDS",
            cfg.get("watchdog_blocked_rounds", 3),
        )
    )
    return WatchdogThresholds(
        idle_rounds=max(idle, 1),
        blocked_rounds=max(blocked, 1),
    )


@dataclass(frozen=True)
class WorkSnapshot:
    done: int
    failed: int
    state: str
    vol: str = ""
    step: str = ""
    blocked: str = ""

    @property
    def signature(self) -> str:
        return blocked_signature(self.state, self.vol, self.step, self.blocked)


@dataclass(frozen=True)
class WatchdogObservation:
    idle_rounds: int
    same_blocked_rounds: int
    blocked_signature: str
    progress_changed: bool
    fingerprint_changed: bool
    should_probe: bool
    should_escalate_block: bool


class WorkWatchdog:
    def __init__(self, thresholds: WatchdogThresholds | None = None) -> None:
        self.thresholds = thresholds or WatchdogThresholds()
        self._last_done: int | None = None
        self._last_failed: int | None = None
        self._last_fingerprint: tuple[str, str, str, str] | None = None
        self._last_blocked_signature = ""
        self._idle_rounds = 0
        self._same_blocked_rounds = 0

    def observe(self, snapshot: WorkSnapshot) -> WatchdogObservation:
        progress_changed = (
            self._last_done is None
            or self._last_failed is None
            or snapshot.done != self._last_done
            or snapshot.failed != self._last_failed
        )
        fingerprint = (
            snapshot.state,
            (snapshot.vol or "").zfill(3),
            snapshot.step or "",
            snapshot.signature,
        )
        fingerprint_changed = (
            self._last_fingerprint is None or fingerprint != self._last_fingerprint
        )
        if progress_changed or fingerprint_changed:
            self._idle_rounds = 0
        else:
            self._idle_rounds += 1

        sig = snapshot.signature
        if sig and sig == self._last_blocked_signature:
            self._same_blocked_rounds += 1
        elif sig:
            self._same_blocked_rounds = 1
        else:
            self._same_blocked_rounds = 0

        self._last_done = snapshot.done
        self._last_failed = snapshot.failed
        self._last_fingerprint = fingerprint
        self._last_blocked_signature = sig

        return WatchdogObservation(
            idle_rounds=self._idle_rounds,
            same_blocked_rounds=self._same_blocked_rounds,
            blocked_signature=sig,
            progress_changed=progress_changed,
            fingerprint_changed=fingerprint_changed,
            should_probe=self._idle_rounds >= self.thresholds.idle_rounds,
            should_escalate_block=bool(sig)
            and self._same_blocked_rounds >= self.thresholds.blocked_rounds,
        )
