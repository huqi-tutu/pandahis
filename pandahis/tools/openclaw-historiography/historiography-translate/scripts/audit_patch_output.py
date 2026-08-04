#!/usr/bin/env python3
"""审计 _patch_output 相对 V1 基稿是否丢失母本信息。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.config import paths  # noqa: E402
from lib.patch_paragraphs import (  # noqa: E402
    DEFAULT_BASE_DIR,
    DEFAULT_MANIFEST,
    DEFAULT_PATCH_OUTPUT_DIR,
    _body_paragraphs,
    _load_v2_index,
    _para_map,
    audit_append_redundancy,
    audit_v1_mother_preservation,
    spec_from_manifest,
)


def main() -> int:
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    v2_index = _load_v2_index(None)
    rows = []

    for entry in manifest.get("entries") or []:
        eid = entry["id"]
        base_fp = DEFAULT_BASE_DIR / entry["file"]
        out_fp = DEFAULT_PATCH_OUTPUT_DIR / entry["file"]
        if not base_fp.is_file() or not out_fp.is_file():
            rows.append({"id": eid, "name": entry["name"], "status": "missing_file"})
            continue
        v1 = json.loads(base_fp.read_text(encoding="utf-8"))
        out = json.loads(out_fp.read_text(encoding="utf-8"))
        meta = out.get("_patch_meta") or {}
        if meta.get("patch_source") == "source_only":
            rows.append({"id": eid, "name": entry["name"], "status": "source_only"})
            continue
        spec = spec_from_manifest(eid, manifest, v2_index)
        pm = _para_map(spec.work, spec.vol)
        audit = audit_v1_mother_preservation(
            v1.get("翻译详情") or "",
            out.get("翻译详情") or "",
            spec,
            pm,
        )
        lost = audit.get("lost_clauses") or []
        status = "ok" if not lost else "mother_lost"
        enrich_lost = []
        v1_detail = v1.get("翻译详情") or ""
        out_detail = out.get("翻译详情") or ""
        for m in (
            "穆天子传", "西王母", "八骏", "至此", "最高处", "侯嬴", "信陵君大惭",
            "武丁", "殷道复兴", "稳定的都城", "政治遗产", "侧面反映", "活成了传奇",
        ):
            if m in v1_detail and m not in out_detail:
                enrich_lost.append(m)
        if enrich_lost and status == "ok":
            status = "enrich_lost"
        append_redundant: list[str] = []
        if meta.get("append_mode") and entry.get("side") == "末尾":
            v1_paras = _body_paragraphs(v1_detail)
            out_paras = _body_paragraphs(out_detail)
            if len(v1_paras) >= 1 and len(out_paras) >= len(v1_paras) + 1:
                preceding = v1_paras[-1]
                append = out_paras[len(v1_paras)]
                append_redundant = audit_append_redundancy(preceding, append)
                if append_redundant and status == "ok":
                    status = "append_redundant"
        rows.append({
            "id": eid,
            "name": entry["name"],
            "side": entry["side"],
            "missing": entry["missing_paras"],
            "v1_range": entry.get("v1_range"),
            "status": status,
            "lost_count": len(lost),
            "lost_samples": lost[:8],
            "enrich_lost": enrich_lost,
            "append_redundant": append_redundant,
            "patch_mode_old": meta.get("patch_mode"),
            "append_mode_old": meta.get("append_mode"),
        })

    lost_rows = [r for r in rows if r.get("status") in ("mother_lost", "enrich_lost", "append_redundant")]
    lost_rows.sort(key=lambda x: -(x.get("lost_count", 0) + len(x.get("enrich_lost") or [])))

    print(f"审计 {len(rows)} 条：{len(lost_rows)} 条有问题\n")
    for r in lost_rows:
        tag = "母本" if r.get("lost_count") else ("append重复" if r.get("append_redundant") else "enrich")
        print(f"⚠️  {r['id']} {r['name']} ({r['side']}, missing P{r['missing']}) [{tag}]")
        if r.get("lost_samples"):
            print(f"    母本丢失: {', '.join(r['lost_samples'][:5])}")
        if r.get("enrich_lost"):
            print(f"    enrich丢失: {', '.join(r['enrich_lost'][:5])}")
        if r.get("append_redundant"):
            print(f"    末段重复: {'; '.join(r['append_redundant'][:3])}")
    print("\n✅ 无母本丢失:")
    for r in rows:
        if r.get("status") == "ok":
            print(f"   {r['id']} {r['name']}")

    out_path = DEFAULT_PATCH_OUTPUT_DIR / "mother_preservation_audit.json"
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n报告 → {out_path}")
    return 1 if lost_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
