"""LLM provider 配置（环境变量）。"""

from __future__ import annotations

import os
from pathlib import Path

PROVIDER_OPENCLAW = "openclaw"
PROVIDER_DEEPSEEK = "deepseek"
VALID_PROVIDERS = frozenset({PROVIDER_OPENCLAW, PROVIDER_DEEPSEEK})

# 按流水线写死模型（覆盖 DEEPSEEK_MODEL 环境变量）
MODEL_FLASH = "deepseek-v4-flash"
MODEL_ANNOTATE = MODEL_FLASH
MODEL_PRO = MODEL_FLASH  # 翻译·见证·详情·关系等主流水线
DEFAULT_DEEPSEEK_MODEL = MODEL_FLASH


def _load_env_file() -> None:
    """加载 openclaw-historiography/.env（setdefault，不覆盖已 export 的变量）。"""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


_load_env_file()


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
        model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
        return f"DeepSeek ({model})"
    return "OpenClaw agent"


def deepseek_settings() -> dict[str, str | float]:
    return {
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
        "temperature": float(os.environ.get("DEEPSEEK_TEMPERATURE", "0.2")),
    }


def pin_deepseek_model(required_model: str) -> str:
    """强制 DeepSeek 通道与模型（标注 / 翻译·补全·见证·关系等）。"""
    os.environ["HIST_LLM_PROVIDER"] = PROVIDER_DEEPSEEK
    os.environ["DEEPSEEK_MODEL"] = required_model
    actual = deepseek_settings()["model"]
    if str(actual) != required_model:
        raise RuntimeError(f"模型必须为 {required_model!r}，当前为 {actual!r}")
    return provider_label()


def ensure_annotate_model() -> str:
    """史料标注（v1/v2 Step1/3/4、峰值年、人物标签等）。"""
    return pin_deepseek_model(MODEL_ANNOTATE)


def ensure_deepseek_v4_pro() -> str:
    """翻译、朝代知识补全、人物关系、评述见证等（deepseek-v4-flash）。"""
    return pin_deepseek_model(MODEL_PRO)


def review_settings() -> dict[str, str | float]:
    """详情质检/审校 LLM（OpenAI 兼容，默认 DeepSeek Flash）。"""
    ds = deepseek_settings()
    base = os.environ.get("REVIEW_BASE_URL") or str(ds["base_url"])
    base = base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    api_key = os.environ.get("REVIEW_API_KEY") or str(ds["api_key"])
    return {
        "api_key": api_key,
        "base_url": base.rstrip("/"),
        "model": os.environ.get("REVIEW_MODEL", MODEL_FLASH),
        "temperature": float(os.environ.get("REVIEW_TEMPERATURE", "0.2")),
        "timeout_sec": int(os.environ.get("REVIEW_TIMEOUT_SEC", "900")),
    }
