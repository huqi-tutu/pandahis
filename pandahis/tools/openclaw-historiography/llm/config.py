"""LLM provider 配置（环境变量）。"""

from __future__ import annotations

import os

PROVIDER_OPENCLAW = "openclaw"
PROVIDER_DEEPSEEK = "deepseek"
VALID_PROVIDERS = frozenset({PROVIDER_OPENCLAW, PROVIDER_DEEPSEEK})


def get_provider_name() -> str:
    raw = (os.environ.get("HIST_LLM_PROVIDER") or PROVIDER_DEEPSEEK).strip().lower()
    if raw not in VALID_PROVIDERS:
        raise RuntimeError(
            f"未知 HIST_LLM_PROVIDER={raw!r}，可选: {', '.join(sorted(VALID_PROVIDERS))}"
        )
    return raw


def provider_label(name: str | None = None) -> str:
    provider = name or get_provider_name()
    if provider == PROVIDER_DEEPSEEK:
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        return f"DeepSeek ({model})"
    return "OpenClaw agent"


def deepseek_settings() -> dict[str, str | float]:
    return {
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "temperature": float(os.environ.get("DEEPSEEK_TEMPERATURE", "0.2")),
    }
