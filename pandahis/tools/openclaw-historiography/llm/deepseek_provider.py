"""DeepSeek Chat Completions provider。"""

from __future__ import annotations

import gzip
import http.client
import json
import os
import socket
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_RETRYABLE_NET_ERRORS = (
    urllib.error.URLError,
    urllib.error.HTTPError,
    RuntimeError,
    TimeoutError,
    socket.timeout,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    http.client.RemoteDisconnected,
    http.client.IncompleteRead,
)

from llm.artifacts import persist_artifacts
from llm.config import DEFAULT_MAX_TOKENS, chat_completions_url, deepseek_settings


def _decode_api_body(raw: bytes) -> dict:
    """解析 Chat Completions 响应；部分网关返回 gzip 但未设 Content-Encoding。"""
    if not raw:
        raise RuntimeError("DeepSeek API 返回空响应体")
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        if raw[:2] == b"\x1f\x8b":
            try:
                return json.loads(gzip.decompress(raw).decode("utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise RuntimeError(
                    "DeepSeek API 响应 gzip 解压/解析失败"
                ) from exc
        preview = raw[:120].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"DeepSeek API 响应非 JSON（len={len(raw)} head={preview!r}）"
        )


def _is_glm53(model: str) -> bool:
    return str(model or "").strip().lower().startswith("glm-5.3")


def run_deepseek_turn(
    message: str,
    *,
    session_id: Optional[str],
    timeout_sec: int,
    artifact_paths: Optional[Dict[str, Path]] = None,
    max_attempts: int = 3,
    temperature: Optional[float] = None,
    response_format: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    settings = deepseek_settings()
    api_key = str(settings["api_key"])
    if not api_key:
        raise RuntimeError("DeepSeek provider 需要设置环境变量 DEEPSEEK_API_KEY")

    model = str(settings["model"])
    sid = session_id or f"ds-{uuid.uuid4().hex[:12]}"
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "temperature": settings["temperature"] if temperature is None else temperature,
        # 网关默认流式返回 SSE；非流式才返回标准 JSON，供 json.loads 解析
        "stream": False,
    }
    max_tokens = int(os.environ.get("DEEPSEEK_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
    if max_tokens > 0:
        # 智谱 glm-5.3 示例上限 65536；DeepSeek V4 硬顶 384K
        hard_cap = 65_536 if _is_glm53(model) else 384_000
        payload["max_tokens"] = min(max_tokens, hard_cap)
    # thinking：DeepSeek V4 可关；glm-5.3 仅支持 enabled（强制思考）
    thinking = os.environ.get("DEEPSEEK_THINKING", "disabled").strip().lower()
    if _is_glm53(model):
        payload["thinking"] = {"type": "enabled"}
        effort = os.environ.get("DEEPSEEK_REASONING_EFFORT", "low").strip().lower()
        if effort in ("low", "high", "max"):
            payload["reasoning_effort"] = effort
    elif thinking in ("0", "false", "no", "off", "disabled", "none"):
        payload["thinking"] = {"type": "disabled"}
    elif thinking in ("1", "true", "yes", "on", "enabled"):
        payload["thinking"] = {"type": "enabled"}
    # 其余取值：不显式下发，沿用 API 默认
    if response_format is not None:
        payload["response_format"] = response_format
    last_err: Optional[Exception] = None
    data: Optional[dict] = None
    endpoint = chat_completions_url(str(settings["base_url"]))
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "pandahis-historiography/1.0",
                "Accept-Encoding": "identity",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = _decode_api_body(resp.read())
            break
        except _RETRYABLE_NET_ERRORS as exc:
            last_err = exc
            if attempt >= max_attempts:
                if isinstance(exc, urllib.error.HTTPError):
                    body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"DeepSeek API 失败 (HTTP {exc.code}).\n{body[-2000:]}"
                    ) from exc
                raise RuntimeError(f"DeepSeek API 失败（已重试 {max_attempts} 次）: {exc}") from exc
            # 指数退避：避免对抖动中的网关连续空耗 timeout，也留出恢复窗口
            backoff_base = float(os.environ.get("DEEPSEEK_RETRY_BACKOFF_SEC", "3"))
            time.sleep(backoff_base * (2 ** (attempt - 1)))
            continue
    if data is None:
        raise RuntimeError(f"DeepSeek API 失败: {last_err}")

    content = ""
    finish_reason = ""
    choices = data.get("choices") or []
    if choices:
        choice0 = choices[0] or {}
        finish_reason = str(choice0.get("finish_reason") or "")
        content = str((choice0.get("message") or {}).get("content") or "")
    if finish_reason == "length":
        preview = content[-200:] if content else ""
        raise RuntimeError(
            "DeepSeek 输出被 max_tokens 截断（finish_reason=length）。"
            f" 请缩小单次任务或提高 DEEPSEEK_MAX_TOKENS。尾段: {preview!r}"
        )

    written = persist_artifacts(message, content, artifact_paths=artifact_paths)
    result: Dict[str, Any] = {
        "result": content,
        "session_id": sid,
        "provider": "deepseek",
        "model": settings["model"],
    }
    if written:
        result["written_artifacts"] = written
    return result
