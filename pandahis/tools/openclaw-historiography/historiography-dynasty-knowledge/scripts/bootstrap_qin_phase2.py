#!/usr/bin/env python3
"""Bootstrap 秦朝二期候选清单、人审批准，并导入 16 条一期史略索引行。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

HISTOGRAPH_ROOT = Path(
    __import__("os").environ.get(
        "HISTOGRAPH_ROOT",
        str(Path(__file__).resolve().parents[4]),
    )
)
WORK_DIR = HISTOGRAPH_ROOT / "data/05工作流中间产物/朝代知识补全"
ENTRIES_DIR = HISTOGRAPH_ROOT / "data/06朝代知识补全/索引条目"
GLOBAL_INDEX = HISTOGRAPH_ROOT / "data/03索引标注条目/史略索引_01至02.json"

DYNASTY_ID = "CD_HX_QIN"
DYNASTY_NAME = "秦"

# 一期卷级标注已有、需 compose-detail 的 16 条
PHASE1_GLBL = [
    "GLBL_00097",  # 秦二世
    "GLBL_00103",  # 秦始皇
    "GLBL_00221",  # 优旃
    "GLBL_00230",  # 卓氏
    "GLBL_00233",  # 宛孔氏
    "GLBL_00235",  # 巴寡妇清
    "GLBL_00238",  # 曹邴氏
    "GLBL_00244",  # 程郑
    "GLBL_00249",  # 陈涉
    "GLBL_00297",  # 吕不韦
    "GLBL_00368",  # 李斯
    "GLBL_00479",  # 韩非
    "GLBL_00522",  # 王翦
    "GLBL_00524",  # 田儋
    "GLBL_00532",  # 蒙恬
    "GLBL_00544",  # 项籍
]


def _c(
    name: str,
    *,
    year: int,
    attach: str,
    source: str = "《史记》",
    note: str = "",
    **extra: object,
) -> dict:
    row: dict = {
        "名称": name,
        "建议年份": year,
        "建议挂靠帝王": attach,
        "主要史料出处": source,
        "边界备注": note,
        "审核状态": "approved",
    }
    row.update(extra)
    return row


def build_candidates() -> dict[str, list[dict]]:
    shilue = [
        _c(
            "秦灭六国统一",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
            note="pick year 灭齐之年；与战国末兼并区分",
        ),
        _c(
            "北击匈奴",
            year=-215,
            attach="秦始皇",
            source="《史记·秦始皇本纪》《史记·蒙恬列传》",
        ),
        _c(
            "南征百越",
            year=-214,
            attach="秦始皇",
            source="《史记·秦始皇本纪》《史记·南越列传》",
        ),
        _c(
            "灵渠开凿",
            year=-214,
            attach="秦始皇",
            source="《史记·河渠书》",
        ),
        _c(
            "焚书坑儒",
            year=-213,
            attach="秦始皇",
            source="《史记·秦始皇本纪》《史记·儒林列传》",
        ),
        _c(
            "骊山陵与阿房宫",
            year=-212,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
            note="工程事略；与一期人物条分工",
        ),
        _c(
            "沙丘之变",
            year=-210,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
        ),
        _c(
            "陈涉起义",
            year=-209,
            attach="秦二世",
            source="《史记·陈涉世家》",
            note="事件条；与一期陈涉人物条分工",
        ),
        _c(
            "指鹿为马",
            year=-207,
            attach="秦二世",
            source="《史记·秦始皇本纪》",
        ),
        _c(
            "徐福东渡",
            year=-219,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
            note="方士求仙事略",
        ),
    ]

    dianzhi = [
        _c(
            "皇帝制度",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
            note="本朝创制；与战国郡县等区分",
        ),
        _c(
            "三公九卿制",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》《汉书·百官公卿表》",
        ),
        _c(
            "统一度量衡",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
        ),
        _c(
            "书同文",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
        ),
        _c(
            "统一货币",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
        ),
        _c(
            "统一车轨",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
        ),
        _c(
            "秦律",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》《睡虎地秦简》",
            note="统一后成体系；与李悝法经/战国成文法典区分",
        ),
        _c(
            "郡县制全国推行",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》",
            note="本朝聚焦统一后全国推行；战国条目保留商鞅变法萌芽",
        ),
        _c(
            "徭役征发制",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》《汉书·刑法志》",
        ),
        _c(
            "重农抑商",
            year=-221,
            attach="秦始皇",
            source="《史记·秦始皇本纪》《商君书》",
            note="秦制强化版；与战国按亩征租区分",
        ),
    ]

    lunzhu: list[dict] = []

    renwu: dict[str, list[dict]] = {
        "君王": [],
        "宗戚": [
            _c("扶苏", year=-210, attach="秦始皇", source="《史记·秦始皇本纪》"),
            _c("公子高", year=-210, attach="秦始皇", source="《史记·秦始皇本纪》"),
        ],
        "宦官": [
            _c("赵高", year=-210, attach="秦始皇", source="《史记·秦始皇本纪》"),
        ],
        "文臣": [
            _c("冯去疾", year=-221, attach="秦始皇", source="《史记·秦始皇本纪》"),
            _c("尉缭", year=-221, attach="秦始皇", source="《史记·秦始皇本纪》"),
            _c("卢生", year=-215, attach="秦始皇", source="《史记·秦始皇本纪》"),
        ],
        "武将": [
            _c("王贲", year=-221, attach="秦始皇", source="《史记·白起列传》"),
            _c("章邯", year=-207, attach="秦二世", source="《史记·项羽本纪》《史记·秦始皇本纪》"),
        ],
        "蕃祚": [
            _c("百越", year=-214, attach="秦始皇", source="《史记·南越列传》"),
            _c("匈奴", year=-215, attach="秦始皇", source="《史记·匈奴列传》"),
        ],
        "庶众": [
            _c("高渐离", year=-215, attach="秦始皇", source="《史记·刺客列传》"),
            _c("徐福", year=-219, attach="秦始皇", source="《史记·秦始皇本纪》"),
        ],
    }

    return {
        "事略": shilue,
        "典制": dianzhi,
        "论著": lunzhu,
        **renwu,
    }


def write_candidates() -> Path:
    candidates = build_candidates()
    total = sum(len(v) for v in candidates.values())
    doc = {
        "schema_version": 1,
        "朝代ID": DYNASTY_ID,
        "朝代名称": DYNASTY_NAME,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "用户批准二期候选（A类新条 + 16条B类一期史略compose）",
        "candidates": candidates,
    }
    path = WORK_DIR / "秦_候选清单.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 候选清单 → {path}（{total} 条）")
    return path


def write_approval(*, phase: str = "candidates") -> Path:
    candidates = build_candidates()
    items: dict[str, list[str]] = {}
    for cat, rows in candidates.items():
        names = [str(r["名称"]).strip() for r in rows]
        if names:
            items[cat] = names

    if phase == "entries":
        phase1_names = _phase1_entry_names()
        for row in phase1_names:
            cat = str(row.get("史略分类", "")).strip()
            name = str(row.get("史略名称", "")).strip()
            if cat and name:
                items.setdefault(cat, [])
                if name not in items[cat]:
                    items[cat].append(name)

    doc = {
        "schema_version": 1,
        "朝代ID": DYNASTY_ID,
        "朝代名称": DYNASTY_NAME,
        "phase": phase,
        "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "approved_by": "user",
        "note": "用户口头批准开始秦朝知识补全",
        "items": items,
    }
    path = WORK_DIR / "秦_人审批准.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 人审批准 phase={phase} → {path}")
    return path


def _phase1_entry_names() -> list[dict]:
    idx = json.loads(GLOBAL_INDEX.read_text(encoding="utf-8"))
    by_id = {str(e.get("史略ID", "")): e for e in idx.get("entries") or []}
    return [by_id[g] for g in PHASE1_GLBL if g in by_id]


def import_phase1_entries() -> Path:
    """将 16 条一期史略从全局索引复制到 06/秦_人物.json（保留原 GLBL）。"""
    ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
    path = ENTRIES_DIR / "秦_人物.json"
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {
            "schema_version": 1,
            "著作": "朝代知识补全",
            "朝代ID": DYNASTY_ID,
            "朝代名称": DYNASTY_NAME,
            "source_phase": "dynasty_supplement_v1",
            "entries": [],
        }

    existing_ids = {str(e.get("史略ID", "")) for e in doc.get("entries") or []}
    added = 0
    for row in _phase1_entry_names():
        eid = str(row.get("史略ID", ""))
        if not eid or eid in existing_ids:
            continue
        copy = dict(row)
        copy["史略来源"] = copy.get("史略来源") or "一期卷级标注"
        copy["补全来源"] = "一期待compose"
        doc["entries"].append(copy)
        existing_ids.add(eid)
        added += 1

    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 一期史略导入 → {path}（新增 {added} 条）")
    return path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=[
            "candidates",
            "approval-candidates",
            "approval-entries",
            "import-phase1",
            "all-bootstrap",
        ],
        default="all-bootstrap",
    )
    args = parser.parse_args()

    if args.action in ("candidates", "all-bootstrap"):
        write_candidates()
    if args.action in ("approval-candidates", "all-bootstrap"):
        write_approval(phase="candidates")
    if args.action == "approval-entries":
        write_approval(phase="entries")
    if args.action in ("import-phase1",):
        import_phase1_entries()
    if args.action == "all-bootstrap":
        total = sum(len(v) for v in build_candidates().values())
        print(f"📋 A 类候选 {total} 条；B 类一期史略 {len(PHASE1_GLBL)} 条待 import-phase1")


if __name__ == "__main__":
    main()
