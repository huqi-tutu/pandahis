#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将用户指定的 A/B 级 V1 史料提取条目迁入 V2 索引，并把 04 翻译复制到 11新标注条目翻译。

规则：
  - 周共王、周昭王、季历：以 06 模型补全（已在 V2）为准，不覆盖详情
  - 已有 V2 同名条目（06 春秋人物包）：沿用 V2 ID，04 翻译写入 11 且 史略ID 对齐
  - 其余：从 V1 索引追加，复用 V1 GLBL 编号，04 → 11

产出：
  - data/10新标注条目/史略索引_史记汉书.json
  - data/11新标注条目翻译/GLBL_*.json
  - data/05工作流中间产物/migrate_v1_ab_to_v2_report.json
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
V1_INDEX = DATA / "03索引标注条目" / "史略索引_01至02.json"
TRANS_V1 = DATA / "04史料翻译"
TRANS_V11 = DATA / "11新标注条目翻译"
OUT_REPORT = DATA / "05工作流中间产物" / "migrate_v1_ab_to_v2_report.json"

USE_06_STANDARD: dict[str, str] = {
    "周共王": "GLBL_00817",
    "周昭王": "GLBL_00816",
    "季历": "GLBL_00818",
}

NAMES_A = [
    "太甲", "古公亶父", "后稷", "周宣王", "周康王", "宋微子", "燕召公",
    "周定王", "周平王", "周庄王", "周惠王", "周敬王", "周景王", "周桓王",
    "周灵王", "周襄王", "周釐王",
    "卫文公", "卫懿公", "晋武公", "晋襄公", "晋景公", "楚成王", "秦襄公",
    "秦文公", "郑武公", "郑文公", "鲁隐公", "鲁昭公", "鲁庄公", "陶朱公",
    "周赧王", "秦惠文王", "秦献公", "赵幽缪王", "赵烈侯", "齐王建", "魏无忌",
]
NAMES_B = [
    "太戊", "小乙", "周共王", "周昭王", "季历",
    "卫宣公", "卫成公", "卫庄公蒯聩", "卫出公", "宋宣公", "宋殇公", "宋湣公",
    "晋厉公", "晋灵公", "晋平公", "楚昭王", "楚惠王",
    "秦武公", "秦德公", "秦康公", "秦桓公", "秦景公", "秦哀公", "秦宣公", "秦成公",
    "郑成公", "郑襄公", "陈灵公", "陈湣公",
    "鲁桓公", "鲁釐公", "齐顷公", "齐简公", "齐孝公", "齐灵公", "齐庄公",
    "齐悼公", "齐惠公", "齐懿公", "齐釐公", "有若", "原宪", "樊须", "巫马施",
    "宋君偃", "晋出公", "楚顷襄王", "燕哙", "燕惠王", "王无彊", "秦武王", "齐襄王",
]
TIER_BY_NAME = {n: "A" for n in NAMES_A} | {n: "B" for n in NAMES_B}

TOOLS = ROOT / "tools" / "openclaw-historiography"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from category_normalize import normalize_entries  # noqa: E402
from entry_source import normalize_entry_source  # noqa: E402


def glbl_num(eid: str) -> int:
    m = re.match(r"GLBL_(\d+)", eid or "")
    return int(m.group(1)) if m else 999999


def load_v1_by_name() -> dict[str, list[dict]]:
    rows = json.loads(V1_INDEX.read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    for e in rows:
        name = str(e.get("史略名称") or "").strip()
        if name:
            out.setdefault(name, []).append(e)
    return out


def pick_v1_source(name: str, v1_by_name: dict[str, list[dict]]) -> dict | None:
    items = v1_by_name.get(name) or []
    if not items:
        return None
    extract = [e for e in items if e.get("史略来源") == "史料提取"]
    pool = extract or items
    return min(pool, key=lambda e: glbl_num(str(e.get("史略ID", ""))))


def resolve_canonical_id(name: str, v2_by_id: dict[str, dict], v1_by_name: dict[str, list[dict]]) -> str:
    if name in USE_06_STANDARD:
        return USE_06_STANDARD[name]
    v2_hits = [e for e in v2_by_id.values() if e.get("史略名称") == name]
    if v2_hits:
        v2_hits.sort(
            key=lambda e: (
                0 if e.get("史略来源") == "模型补全" else 1,
                glbl_num(str(e.get("史略ID", ""))),
            )
        )
        return str(v2_hits[0]["史略ID"])
    src = pick_v1_source(name, v1_by_name)
    if not src:
        raise KeyError(f"V1 无条目: {name}")
    return str(src["史略ID"])


def find_v1_trans_file(v1_id: str) -> Path | None:
    matches = sorted(TRANS_V1.glob(f"{v1_id}_*.json"))
    return matches[0] if matches else None


def copy_translation(v1_id: str, canonical_id: str, name: str) -> Path | None:
    src_fp = find_v1_trans_file(v1_id)
    if not src_fp:
        return None
    doc = json.loads(src_fp.read_text(encoding="utf-8"))
    detail = str(doc.get("翻译详情") or "").strip()
    if not detail:
        return None
    out = deepcopy(doc)
    out["史略ID"] = canonical_id
    out.setdefault("史略名称", name)
    out["_migrated_from"] = {
        "v1_id": v1_id,
        "source_file": str(src_fp.relative_to(ROOT)),
        "migrated_at": datetime.now(timezone.utc).isoformat(),
    }
    dest = TRANS_V11 / f"{canonical_id}_{name}.json"
    if dest.is_file():
        backup = dest.with_suffix(".json.pre_migrate_bak")
        if not backup.is_file():
            shutil.copy2(dest, backup)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def main() -> None:
    v1_by_name = load_v1_by_name()
    v2_list = json.loads(V2_INDEX.read_text(encoding="utf-8"))
    by_id: dict[str, dict] = {
        str(e["史略ID"]): normalize_entry_source(deepcopy(e)) for e in v2_list
    }

    report = {
        "schema": "migrate-v1-ab-to-v2/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_names": len(TIER_BY_NAME),
        "index_added": [],
        "index_skipped_existing": [],
        "detail_copied": [],
        "detail_skipped_06": [],
        "detail_missing": [],
        "errors": [],
    }

    all_names = sorted(TIER_BY_NAME, key=lambda n: (TIER_BY_NAME[n], n))

    for name in all_names:
        tier = TIER_BY_NAME[name]
        try:
            canonical_id = resolve_canonical_id(name, by_id, v1_by_name)
        except KeyError as exc:
            report["errors"].append({"name": name, "error": str(exc)})
            continue

        v1_src = pick_v1_source(name, v1_by_name)
        v1_id = str(v1_src["史略ID"]) if v1_src else ""

        if canonical_id in by_id:
            report["index_skipped_existing"].append(
                {"name": name, "tier": tier, "canonical_id": canonical_id, "v1_id": v1_id}
            )
        else:
            if not v1_src:
                report["errors"].append({"name": name, "error": "无 V1 源条目"})
                continue
            ent = normalize_entry_source(deepcopy(v1_src))
            ent["史略ID"] = canonical_id
            ent["史略来源"] = "史料提取"
            ent["_迁移批次"] = f"V1翻译迁入V2/{tier}级"
            by_id[canonical_id] = ent
            report["index_added"].append(
                {"name": name, "tier": tier, "canonical_id": canonical_id, "v1_id": v1_id}
            )

        if name in USE_06_STANDARD:
            report["detail_skipped_06"].append(
                {"name": name, "canonical_id": canonical_id, "reason": "以06模型补全为准"}
            )
            continue

        # V1 04 顺译不入 11（脏数据），含 remapped 到 06 V2 ID 的情形
        report.setdefault("detail_skipped_dirty_v1", []).append(
            {
                "name": name,
                "tier": tier,
                "canonical_id": canonical_id,
                "v1_id": v1_id,
                "reason": "V1顺译脏数据，不写入11",
            }
        )
        continue

    merged = sorted(by_id.values(), key=lambda e: glbl_num(str(e.get("史略ID", ""))))
    merged, cat_log = normalize_entries(merged)

    backup = V2_INDEX.with_suffix(".json.pre_ab_migrate_bak")
    if not backup.is_file():
        shutil.copy2(V2_INDEX, backup)
    V2_INDEX.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report["v2_before"] = len(v2_list)
    report["v2_after"] = len(merged)
    report["category_normalize"] = cat_log
    report["backup"] = str(backup)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"V2: {len(v2_list)} -> {len(merged)} "
        f"(+{len(report['index_added'])} index, "
        f"{len(report['detail_copied'])} detail, "
        f"{len(report['detail_skipped_06'])} skip-06)"
    )
    print(f"Report: {OUT_REPORT}")


if __name__ == "__main__":
    main()
