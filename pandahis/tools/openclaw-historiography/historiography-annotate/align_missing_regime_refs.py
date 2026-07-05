#!/usr/bin/env python3
"""补全 政权.json / 朝代.json 中帝王.json 引用的缺失 ID，并修正明显错链。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from coordinate_index import (
    DYNASTY_JSON,
    EMPEROR_JSON,
    REGIME_JSON,
    parse_year_value,
    validate_emperor_records,
)

SKILL_DIR = Path(__file__).resolve().parent
SYNC = {
    EMPEROR_JSON: Path.home() / "Desktop/padanhis/pandahis/pandahis/data/帝王.json",
    REGIME_JSON: Path.home() / "Desktop/padanhis/pandahis/pandahis/data/政权.json",
    DYNASTY_JSON: Path.home() / "Desktop/padanhis/pandahis/pandahis/data/朝代.json",
}

# 十国分政权 + 南明（与帝王.json 已有 ID 对齐）
REGIME_ROWS = [
    {
        "政权": "十国·前蜀",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUOQIANSHU",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "907",
        "结束时间": "925",
    },
    {
        "政权": "十国·后蜀",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUOHOUSHU",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "934",
        "结束时间": "965",
    },
    {
        "政权": "十国·吴",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUOWU",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "902",
        "结束时间": "937",
    },
    {
        "政权": "十国·南唐",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUONANTANG",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "937",
        "结束时间": "975",
    },
    {
        "政权": "十国·吴越",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUOWUYUE",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "907",
        "结束时间": "978",
    },
    {
        "政权": "十国·南汉",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUONANHAN",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "917",
        "结束时间": "971",
    },
    {
        "政权": "十国·南平",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUONANPING",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "924",
        "结束时间": "963",
    },
    {
        "政权": "十国·闽",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUOMIN",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "909",
        "结束时间": "945",
    },
    {
        "政权": "十国·楚",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUOCHU",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "907",
        "结束时间": "951",
    },
    {
        "政权": "十国·北汉",
        "政权ID": "ZQ_HX_WUDAISHIGUO_SHIGUOBEIHAN",
        "朝代": "五代十国",
        "朝代ID": "CD_HX_WUDAISHIGUO",
        "开始时间": "951",
        "结束时间": "979",
    },
    {
        "政权": "南明",
        "政权ID": "ZQ_HX_NANMING_NANMING",
        "朝代": "南明",
        "朝代ID": "CD_HX_NANMING",
        "开始时间": "1644",
        "结束时间": "1662",
    },
]

DYNASTY_ROW = {
    "朝代": "南明",
    "朝代ID": "CD_HX_NANMING",
    "文明": "华夏",
    "文明ID": "HX",
    "开始时间": "1644",
    "结束时间": "1662",
}

# 帝王.json 中应指向已有政权行的修正
EMPEROR_FIXES = {
    "ZQ_HX_NANBEICHAO_NANCHAO": {
        "政权": "南朝·齐",
        "政权ID": "ZQ_HX_NANBEICHAO_NANCHAOQI",
    },
}


def _norm_row(raw: dict) -> dict:
    return {str(k).lstrip("\ufeff").strip(): v for k, v in raw.items()}


def _load(path: Path) -> list[dict]:
    return [_norm_row(r) for r in json.loads(path.read_text(encoding="utf-8-sig"))]


def _save(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _complete_regime_row(spec: dict) -> dict:
    return {
        "政权": spec["政权"],
        "政权ID": spec["政权ID"],
        "朝代": spec["朝代"],
        "朝代ID": spec["朝代ID"],
        "dynasty_zy": spec["朝代"],
        "文明": "华夏",
        "文明ID": "HX",
        "开始时间": spec["开始时间"],
        "结束时间": spec["结束时间"],
    }


def insert_regime_rows(regimes: list[dict], new_rows: list[dict]) -> int:
    existing = {(r.get("政权ID") or "").strip() for r in regimes}
    added = 0
    insert_at = next(
        (i for i, r in enumerate(regimes) if r.get("政权ID") == "ZQ_HX_WUDAISHIGUO_SHIGUO"),
        len(regimes),
    )
    batch: list[dict] = []
    for spec in new_rows:
        rid = spec["政权ID"]
        if rid in existing:
            continue
        batch.append(_complete_regime_row(spec))
        existing.add(rid)
        added += 1
    if batch:
        regimes[insert_at:insert_at] = batch
    return added


def insert_dynasty_row(dynasties: list[dict], row: dict) -> bool:
    existing = {(d.get("朝代ID") or "").strip() for d in dynasties}
    if row["朝代ID"] in existing:
        return False
    insert_at = next(
        (i for i, d in enumerate(dynasties) if d.get("朝代ID") == "CD_HX_NANSONG"),
        len(dynasties),
    )
    dynasties.insert(insert_at + 1, row)
    return True


def fix_emperor_refs(emperors: list[dict]) -> int:
    n = 0
    for row in emperors:
        old_rid = (row.get("政权ID") or "").strip()
        patch = EMPEROR_FIXES.get(old_rid)
        if not patch:
            continue
        for k, v in patch.items():
            if row.get(k) != v:
                row[k] = v
                n += 1
    return n


def sync_all(emperors, regimes, dynasties) -> None:
    payloads = {
        EMPEROR_JSON: emperors,
        REGIME_JSON: regimes,
        DYNASTY_JSON: dynasties,
    }
    for src, data in payloads.items():
        _save(src, data)
        dst = SYNC.get(src)
        if dst:
            dst.parent.mkdir(parents=True, exist_ok=True)
            _save(dst, data)


def main() -> int:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in (EMPEROR_JSON, REGIME_JSON, DYNASTY_JSON):
        shutil.copy2(path, path.with_name(f"_backup_{path.stem}_{ts}.json"))

    emperors = _load(EMPEROR_JSON)
    regimes = _load(REGIME_JSON)
    dynasties = _load(DYNASTY_JSON)

    regime_added = insert_regime_rows(regimes, REGIME_ROWS)
    dynasty_added = insert_dynasty_row(dynasties, DYNASTY_ROW)
    emperor_fixed = fix_emperor_refs(emperors)

    errs = validate_emperor_records(emperors, regimes=regimes, dynasties=dynasties)
    if errs:
        print("⛔ 校验失败，已中止写入：")
        for e in errs[:20]:
            print(f"  - {e}")
        return 1

    sync_all(emperors, regimes, dynasties)
    print(f"✅ 政权.json 新增 {regime_added} 条")
    print(f"✅ 朝代.json 新增 {1 if dynasty_added else 0} 条（南明）")
    print(f"✅ 帝王.json 修正 {emperor_fixed} 处（齐高帝 → 南朝·齐）")
    print("✅ 交叉引用校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
