"""统一 LLM 调用入口。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from llm.config import PROVIDER_DEEPSEEK, get_provider_name
from llm.deepseek_provider import run_deepseek_turn
from llm.openclaw_provider import resolve_agent_id, run_openclaw_turn


def ensure_package_root() -> Path:
    """确保 openclaw-historiography 根目录在 sys.path 中。"""
    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


ensure_package_root()


def run_agent_turn(
    message: str,
    *,
    agent_id: str = "hist-worker",
    session_id: Optional[str] = None,
    timeout_sec: int = 900,
    artifact_paths: Optional[Dict[str, Path]] = None,
    temperature: Optional[float] = None,
    openclaw_env_key: str = "HIST_OPENCLAW_AGENT",
    openclaw_local_env_key: str = "HIST_OPENCLAW_LOCAL",
    forbid_main_message: str = (
        "禁止回调 main agent。请设置 HIST_OPENCLAW_AGENT=hist-worker，"
        "或改用 HIST_LLM_PROVIDER=deepseek。"
    ),
) -> Dict[str, Any]:
    provider = get_provider_name()
    if provider == PROVIDER_DEEPSEEK:
        return run_deepseek_turn(
            message,
            session_id=session_id,
            timeout_sec=timeout_sec,
            artifact_paths=artifact_paths,
            temperature=temperature,
        )

    resolved_agent = resolve_agent_id(
        agent_id,
        env_key=openclaw_env_key,
        forbid_main_message=forbid_main_message,
    )
    return run_openclaw_turn(
        message,
        agent_id=resolved_agent,
        session_id=session_id,
        timeout_sec=timeout_sec,
        local_env_key=openclaw_local_env_key,
    )
