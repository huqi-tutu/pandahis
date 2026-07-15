#!/usr/bin/env python3
"""朝代知识补全 · 内容展现测试（模拟小程序 box-detail 分段 + 可选 API 探测）。"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import dynasty_supplement_lib as dkl


def _dropcap_char(paragraph: str) -> str:
    text = paragraph.lstrip()
    text = re.sub(r'^[\s，。！？、；：""''（）【】《》…—\-]+', "", text)
    return text[0] if text else ""


def simulate_miniapp_paragraphs(md: str) -> list[dict[str, Any]]:
    """对齐 miniapp/pages/box-detail splitDetailParagraphs 行为。"""
    parts = dkl.split_detail_paragraphs(md)
    out: list[dict[str, Any]] = []
    for i, para in enumerate(parts):
        item: dict[str, Any] = {
            "index": i,
            "char_count": len(para),
            "sentence_count": len([p for p in re.split(r"[。！？!?]", para) if p.strip()]),
        }
        if i == 0:
            item["dropcap"] = _dropcap_char(para)
        out.append(item)
    return out


def _fetch_json(url: str, timeout: int = 5) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def probe_api(box_id: str, base_url: str = "http://localhost:8080/api/v1") -> dict[str, Any]:
    header = _fetch_json(f"{base_url}/boxes/{box_id}")
    detail = _fetch_json(f"{base_url}/boxes/{box_id}/detail")
    return {
        "api_reachable": header is not None,
        "header_ok": bool(header and header.get("data")),
        "detail_ok": bool(detail and detail.get("data", {}).get("detailMd")),
        "detail_chars": len(str((detail or {}).get("data", {}).get("detailMd") or "")),
    }


def run_display_tests(
    details_dir: Path,
    *,
    entry_id: str | None = None,
    api_base: str = "http://localhost:8080/api/v1",
) -> int:
    files = sorted(details_dir.glob("GLBL_*.json"))
    if entry_id:
        files = [p for p in files if p.name.startswith(f"{entry_id}_")]
    if not files:
        print("❌ 未找到详情 JSON", file=sys.stderr)
        return 1

    failures = 0
    print(f"📱 test-display · {len(files)} 条 · 目录 {details_dir}")
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        eid = str(doc.get("史略ID") or path.stem.split("_", 1)[0])
        md = str(doc.get("翻译详情") or "")
        paras = simulate_miniapp_paragraphs(md)
        issues: list[str] = []
        if not paras:
            issues.append("正文切段为空")
        if paras and not paras[0].get("dropcap"):
            issues.append("首段 dropcap 为空")
        if len(paras) < 3:
            issues.append(f"段落过少（{len(paras)}）")
        body = dkl.strip_detail_body(md)
        if len(body) < 100:
            issues.append(f"正文过短（{len(body)} 字）")

        api = probe_api(eid, api_base)
        status = "✅" if not issues else "❌"
        if issues:
            failures += 1
        print(
            f"{status} {eid} · {path.name} · {len(paras)} 段 · "
            f"dropcap={paras[0].get('dropcap') if paras else '-'} · "
            f"api={'OK' if api['detail_ok'] else 'offline/missing'}"
        )
        for issue in issues:
            print(f"    · {issue}")
        if api["api_reachable"] and not api["detail_ok"]:
            print("    · API 可达但该 box 无 detailMd（可能未 import）")

    if failures:
        print(f"\n❌ test-display 失败 {failures}/{len(files)}")
        return 1
    print(f"\n✅ test-display 全部通过（{len(files)} 条）")
    return 0


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[4]
    details = root / "data" / "06朝代知识补全" / "详情"
    eid = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(run_display_tests(details, entry_id=eid))
