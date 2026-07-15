"""独立质检/审校 LLM provider（OpenAI Chat Completions 兼容，默认 Moonshot Kimi）。"""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Optional

from llm.config import review_settings


def _decode_api_body(raw: bytes) -> dict:
    if not raw:
        raise RuntimeError("Review LLM API 返回空响应体")
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        if raw[:2] == b"\x1f\x8b":
            try:
                return json.loads(gzip.decompress(raw).decode("utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise RuntimeError("Review LLM API 响应 gzip 解压/解析失败") from exc
        preview = raw[:120].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Review LLM API 响应非 JSON（len={len(raw)} head={preview!r}）"
        )


def run_review_turn(
    message: str,
    *,
    session_id: Optional[str] = None,
    timeout_sec: Optional[int] = None,
    max_attempts: int = 3,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """调用审校模型（Kimi）；与撰写 DeepSeek 通道隔离。"""
    settings = review_settings()
    api_key = str(settings["api_key"])
    if not api_key:
        raise RuntimeError(
            "Review LLM 需要设置环境变量 REVIEW_API_KEY（见 .env.example）"
        )

    effective_timeout = (
        int(settings["timeout_sec"]) if timeout_sec is None else timeout_sec
    )

    sid = session_id or f"rv-{uuid.uuid4().hex[:12]}"
    payload = {
        "model": settings["model"],
        "messages": [{"role": "user", "content": message}],
        "temperature": settings["temperature"] if temperature is None else temperature,
    }
    url = f"{settings['base_url']}/chat/completions"
    last_err: Optional[Exception] = None
    data: Optional[dict] = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url,
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
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = _decode_api_body(resp.read())
            break
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            last_err = exc
            if attempt >= max_attempts:
                if isinstance(exc, urllib.error.HTTPError):
                    body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"Review LLM API 失败 (HTTP {exc.code}).\n{body[-2000:]}"
                    ) from exc
                raise
    if data is None:
        raise RuntimeError(f"Review LLM API 失败: {last_err}")

    content = ""
    choices = data.get("choices") or []
    if choices:
        content = str((choices[0].get("message") or {}).get("content") or "")

    return {
        "result": content,
        "session_id": sid,
        "provider": "review_openai_compat",
        "model": settings["model"],
        "base_url": settings["base_url"],
    }


def test_review_connectivity() -> Dict[str, Any]:
    """连通性探测：要求模型回复 OK。"""
    out = run_review_turn(
        "连通性测试：请只回复一个大写单词 OK，不要其它内容。",
        timeout_sec=60,
    )
    text = str(out.get("result", "")).strip().upper()
    if "OK" not in text:
        raise RuntimeError(f"Review LLM 连通性异常，回复: {text[:200]!r}")
    return out
