"""OpenClaw agent provider。"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


def default_state_dir() -> str:
    return os.environ.get(
        "OPENCLAW_STATE_DIR",
        str(Path.home() / ".openclaw-autoclaw"),
    )


def resolve_agent_id(
    preferred: str,
    *,
    env_key: str = "HIST_OPENCLAW_AGENT",
    forbid_main_message: str,
) -> str:
    agent = os.environ.get(env_key, preferred)
    if agent == "main" and os.environ.get("HISTOGRAPH_ALLOW_MAIN_AGENT") != "1":
        raise RuntimeError(forbid_main_message)
    return agent


def _parse_agent_json(stdout: str) -> Dict[str, Any]:
    idx = stdout.find("{")
    if idx < 0:
        raise json.JSONDecodeError("no JSON object in stdout", stdout, 0)
    data = json.loads(stdout[idx:])
    payloads = data.get("payloads") or []
    texts = [p.get("text", "") for p in payloads if isinstance(p, dict) and p.get("text")]
    if texts and not data.get("result"):
        data["result"] = "\n".join(texts)
    return data


def run_openclaw_turn(
    message: str,
    *,
    agent_id: str,
    session_id: Optional[str],
    timeout_sec: int,
    local_env_key: str,
) -> Dict[str, Any]:
    sid = session_id or f"hist-{uuid.uuid4().hex[:12]}"
    env = os.environ.copy()
    state = default_state_dir()
    env["OPENCLAW_STATE_DIR"] = state
    config = Path(state) / "openclaw.json"
    if config.exists():
        env["OPENCLAW_CONFIG_PATH"] = str(config)

    use_local = os.environ.get(local_env_key, "1") != "0"
    cmd = ["openclaw", "agent", "--agent", agent_id]
    if use_local:
        cmd.append("--local")
    cmd.extend(
        [
            "--message",
            message,
            "--session-id",
            sid,
            "--json",
            "--timeout",
            str(timeout_sec),
        ]
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    raw = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise RuntimeError(f"openclaw agent 失败 (exit {proc.returncode}).\n{raw[-2000:]}")
    try:
        data = _parse_agent_json(proc.stdout or "")
        data.setdefault("session_id", sid)
        data["provider"] = "openclaw"
        return data
    except json.JSONDecodeError:
        return {"raw": raw, "session_id": sid, "provider": "openclaw"}
