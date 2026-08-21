"""DeepSeek Chat Completions provider。"""

from __future__ import annotations

import gzip
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from llm.artifacts import persist_artifacts
from llm.config import deepseek_settings


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

    sid = session_id or f"ds-{uuid.uuid4().hex[:12]}"
    payload: Dict[str, Any] = {
        "model": settings["model"],
        "messages": [{"role": "user", "content": message}],
        "temperature": settings["temperature"] if temperature is None else temperature,
    }
    max_tokens = int(os.environ.get("DEEPSEEK_MAX_TOKENS", "50000"))
    if max_tokens > 0:
        payload["max_tokens"] = max_tokens
    if response_format is not None:
        payload["response_format"] = response_format
    # V4 默认开启 thinking：推理 token 计入 max_tokens，易耗尽导致 content 空。
    # 标注默认关闭；需要推理时设 DEEPSEEK_THINKING=enabled。
    thinking_mode = (os.environ.get("DEEPSEEK_THINKING") or "disabled").strip().lower()
    if thinking_mode in ("enabled", "disabled"):
        payload["thinking"] = {"type": thinking_mode}
    last_err: Optional[Exception] = None
    data: Optional[dict] = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            f"{settings['base_url']}/v1/chat/completions",
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
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            last_err = exc
            if attempt >= max_attempts:
                if isinstance(exc, urllib.error.HTTPError):
                    body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"DeepSeek API 失败 (HTTP {exc.code}).\n{body[-2000:]}"
                    ) from exc
                raise
    if data is None:
        raise RuntimeError(f"DeepSeek API 失败: {last_err}")

    content = ""
    choices = data.get("choices") or []
    if choices:
        content = str((choices[0].get("message") or {}).get("content") or "")

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
