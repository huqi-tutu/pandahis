#!/usr/bin/env python3
"""Bootstrap 战国二期候选清单、人审批准，并导入 12 条薄标注索引行。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import dynasty_supplement_lib as dkl  # noqa: E402

HISTOGRAPH_ROOT = Path(
    __import__("os").environ.get(
        "HISTOGRAPH_ROOT",
        str(Path(__file__).resolve().parents[4]),
    )
)
WORK_DIR = HISTOGRAPH_ROOT / "data/05工作流中间产物/朝代知识补全"
ENTRIES_DIR = HISTOGRAPH_ROOT / "data/06朝代知识补全/索引条目"
GLOBAL_INDEX = HISTOGRAPH_ROOT / "data/03索引标注条目/史略索引_01至02.json"

DYNASTY_ID = "CD_HX_ZHANGUO"
DYNASTY_NAME = "战国"

THIN_GLBL = [
    "GLBL_00014",  # 周元王
    "GLBL_00018",  # 周威烈王
    "GLBL_00019",  # 周安王
    "GLBL_00027",  # 周慎靓王
    "GLBL_00032",  # 周显王
    "GLBL_00037",  # 周烈王
    "GLBL_00040",  # 周贞定王
    "GLBL_00105",  # 秦孝文王
    "GLBL_00142",  # 韩王安
    "GLBL_00242",  # 猗顿
    "GLBL_00695",  # 卫君角
    "GLBL_00724",  # 田齐太公和
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
        _c("三家分晋", year=-403, attach="周威烈王", source="《史记·晋世家》《资治通鉴》"),
        _c("田氏代齐", year=-386, attach="周显王", source="《史记·田敬仲完世家》"),
        _c("李悝变法", year=-420, attach="魏文侯", source="《史记·魏世家》《汉书·食货志》"),
        _c("商鞅变法", year=-356, attach="秦惠文王", source="《史记·商君列传》"),
        _c("桂陵之战", year=-354, attach="魏惠王", source="《史记·孙子吴起列传》"),
        _c("马陵之战", year=-341, attach="魏惠王", source="《史记·孙子吴起列传》"),
        _c("徐州相王", year=-334, attach="魏惠王", source="《史记·魏世家》《史记·田敬仲完世家》"),
        _c("秦灭巴蜀", year=-316, attach="秦惠文王", source="《史记·秦本纪》《华阳国志》"),
        _c("伊阙之战", year=-293, attach="秦惠文王", source="《史记·白起列传》"),
        _c("鄢郢之战", year=-278, attach="秦惠文王", source="《史记·白起列传》《史记·楚世家》"),
        _c(
            "五国合纵攻秦",
            year=-318,
            attach="秦惠文王",
            source="《史记·苏秦列传》《史记·张仪列传》",
        ),
        _c("五国伐齐", year=-284, attach="燕昭王", source="《史记·乐毅列传》《史记·田敬仲完世家》"),
        _c("田单火牛复齐", year=-279, attach="齐湣王", source="《史记·田敬仲完世家》"),
        _c(
            "赵武灵王胡服骑射",
            year=-307,
            attach="赵武灵王",
            source="《史记·赵世家》",
            note="事件条；与一期赵武灵王人物条分工",
        ),
        _c("长平之战", year=-260, attach="赵孝成王", source="《史记·白起列传》《史记·赵世家》"),
        _c(
            "邯郸保卫战",
            year=-257,
            attach="赵孝成王",
            source="《史记·魏公子列传》《史记·赵世家》",
        ),
        _c(
            "远交近攻",
            year=-270,
            attach="秦惠文王",
            source="《史记·范睢蔡泽列传》",
            note="范雎之策；与一期范睢人物条分工",
        ),
        _c("郑国渠", year=-246, attach="秦惠文王", source="《史记·河渠书》《史记·韩世家》"),
    ]

    dianzhi = [
        _c("成文法典（李悝法经）", year=-420, attach="魏文侯", source="《汉书·刑法志》《晋书·刑法志》"),
        _c("军功爵制", year=-350, attach="秦惠文王", source="《商君书》《汉书·百官公卿表》"),
        _c("什伍连坐制", year=-350, attach="秦惠文王", source="《商君书·赏刑》《史记·商君列传》"),
        _c("上计制", year=-400, attach="魏文侯", source="《汉书·百官公卿表》"),
        _c("虎符调兵制", year=-300, attach="秦惠文王", source="《史记·春申君列传》"),
        _c("郡县制", year=-350, attach="秦惠文王", source="《史记·秦始皇本纪》《史记·商君列传》"),
        _c("平籴法", year=-420, attach="魏文侯", source="《汉书·食货志》"),
        _c("封君食邑制", year=-350, attach="秦惠文王", source="《史记·商君列传》"),
        _c("按亩征租", year=-350, attach="秦惠文王", source="《商君书·垦令》《汉书·食货志》"),
    ]

    lunzhu = [
        _c("《孙子兵法》", year=-500, attach="齐威王", source="《史记·孙子吴起列传》", 子类="典籍", 论著标签="兵家"),
        _c("《孙膑兵法》", year=-340, attach="齐威王", source="《史记·孙子吴起列传》", 子类="典籍", 论著标签="兵家"),
        _c("《墨子》", year=-400, attach="周显王", source="《史记·孟子荀卿列传》", 子类="典籍", 论著标签="兼爱"),
        _c("《孟子》", year=-320, attach="周显王", source="《史记·孟子荀卿列传》", 子类="典籍", 论著标签="仁政"),
        _c("《庄子》", year=-300, attach="周显王", source="《史记·老子韩非列传》", 子类="典籍", 论著标签="逍遥"),
        _c("《荀子》", year=-250, attach="周显王", source="《史记·孟子荀卿列传》", 子类="典籍", 论著标签="性恶"),
        _c("《韩非子》", year=-233, attach="秦昭襄王", source="《史记·老子韩非列传》", 子类="典籍", 论著标签="法术势"),
        _c("《国语》", year=-300, attach="周显王", source="《史记·太史公自序》", 子类="典籍", 论著标签="国别史"),
        _c("《吕氏春秋》", year=-239, attach="秦昭襄王", source="《史记·吕不韦列传》", 子类="典籍", 论著标签="杂家"),
        _c("《离骚》", year=-278, attach="楚怀王", source="《史记·屈原贾生列传》", 子类="名篇", 论著标签="楚辞"),
        _c("《劝学》", year=-250, attach="周显王", source="《荀子·劝学》", 子类="名篇", 论著标签="劝学"),
    ]

    renwu: dict[str, list[dict]] = {
        "诸侯": [
            _c("楚考烈王", year=-262, attach="楚考烈王", source="《史记·楚世家》"),
            _c("赵惠文王", year=-298, attach="赵惠文王", source="《史记·赵世家》"),
        ],
        "宗戚": [
            _c("赵长安君", year=-260, attach="赵孝成王", source="《史记·赵世家》"),
            _c("秦华阳夫人", year=-250, attach="秦昭襄王", source="《史记·吕不韦列传》"),
            _c("秦宣太后", year=-306, attach="秦惠文王", source="《史记·秦本纪》"),
            _c("魏公子卬", year=-330, attach="魏惠王", source="《史记·商君列传》"),
            _c("秦泾阳君", year=-250, attach="秦昭襄王", source="《史记·吕不韦列传》"),
            _c("秦高陵君", year=-250, attach="秦昭襄王", source="《史记·吕不韦列传》"),
            _c("楚公子兰", year=-278, attach="楚考烈王", source="《史记·楚世家》"),
            _c("赵公子章", year=-295, attach="赵武灵王", source="《史记·赵世家》"),
            _c("秦成蟜", year=-239, attach="秦昭襄王", source="《史记·秦始皇本纪》"),
        ],
        "宦官": [
            _c("景监", year=-360, attach="秦孝公", source="《史记·商君列传》"),
            _c("缪贤", year=-279, attach="燕昭王", source="《史记·刺客列传》"),
            _c("靳尚", year=-313, attach="楚怀王", source="《史记·屈原贾生列传》"),
        ],
        "文臣": [
            _c("李悝", year=-420, attach="魏文侯", source="《史记·魏世家》"),
            _c("申不害", year=-337, attach="韩哀侯", source="《史记·老子韩非列传》"),
            _c("邹忌", year=-355, attach="齐威王", source="《史记·田敬仲完世家》"),
            _c("公孙衍", year=-318, attach="魏惠王", source="《史记·苏秦列传》"),
            _c("司马错", year=-316, attach="秦惠文王", source="《史记·张仪列传》"),
            _c("张孟谈", year=-453, attach="赵献侯", source="《史记·赵世家》"),
            _c("冯亭", year=-260, attach="赵孝成王", source="《史记·白起列传》"),
            _c("公仲连", year=-350, attach="韩哀侯", source="《史记·韩世家》"),
            _c("顿弱", year=-240, attach="秦昭襄王", source="《战国策·齐策》"),
            _c("剧辛", year=-242, attach="燕王喜", source="《史记·燕世家》"),
            _c("景翠", year=-278, attach="楚考烈王", source="《史记·楚世家》"),
            _c("触龙", year=-262, attach="赵孝成王", source="《战国策·赵策》"),
            _c("甘罗", year=-239, attach="秦昭襄王", source="《史记·甘茂列传》"),
            _c("邹衍", year=-240, attach="燕昭王", source="《史记·孟子荀卿列传》"),
        ],
        "武将": [
            _c("李牧", year=-233, attach="赵悼襄王", source="《史记·廉颇蔺相如列传》"),
            _c("赵奢", year=-260, attach="赵孝成王", source="《史记·廉颇蔺相如列传》"),
            _c("蒙骜", year=-240, attach="秦昭襄王", source="《史记·蒙恬列传》"),
            _c("王龁", year=-260, attach="秦昭襄王", source="《史记·白起列传》"),
            _c("庞煖", year=-251, attach="赵悼襄王", source="《史记·春申君列传》"),
            _c("项燕", year=-223, attach="楚考烈王", source="《史记·项羽本纪》"),
            _c("李信", year=-226, attach="秦昭襄王", source="《史记·白起列传》"),
            _c("田忌", year=-341, attach="齐威王", source="《史记·孙子吴起列传》"),
            _c("秦开", year=-300, attach="燕昭王", source="《史记·燕世家》"),
            _c("暴鸢", year=-293, attach="秦昭襄王", source="《史记·白起列传》"),
            _c("公孙喜", year=-293, attach="韩釐王", source="《史记·白起列传》"),
            _c("王陵", year=-260, attach="秦昭襄王", source="《史记·白起列传》"),
            _c("乐羊", year=-408, attach="魏文侯", source="《史记·乐毅列传》"),
        ],
        "蕃祚": [
            _c("义渠", year=-330, attach="秦惠文王", source="《史记·秦本纪》"),
            _c("中山国", year=-296, attach="赵武灵王", source="《史记·赵世家》"),
            _c("巴国", year=-316, attach="秦惠文王", source="《华阳国志·巴志》"),
            _c("蜀国", year=-316, attach="秦惠文王", source="《华阳国志·蜀志》"),
            _c("滇国", year=-300, attach="楚怀王", source="《史记·西南夷列传》"),
            _c("东胡", year=-300, attach="赵武灵王", source="《史记·匈奴列传》"),
            _c("林胡", year=-300, attach="赵武灵王", source="《史记·赵世家》"),
            _c("楼烦", year=-300, attach="赵武灵王", source="《史记·赵世家》"),
        ],
        "庶众": [
            _c("侯嬴", year=-257, attach="魏安釐王", source="《史记·魏公子列传》"),
            _c("朱亥", year=-257, attach="魏安釐王", source="《史记·魏公子列传》"),
            _c("毛遂", year=-257, attach="赵孝成王", source="《史记·平原君虞卿列传》"),
            _c("寡妇清", year=-220, attach="秦昭襄王", source="《史记·货殖列传》"),
            _c("冯谖", year=-279, attach="齐湣王", source="《史记·孟尝君列传》"),
            _c("郭纵", year=-220, attach="秦昭襄王", source="《史记·货殖列传》"),
        ],
        "君王": [],
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
        "note": "用户批准二期候选（97条A类 + 12条B类薄标注compose）",
        "candidates": candidates,
    }
    path = WORK_DIR / "战国_候选清单.json"
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
        thin_names = _thin_entry_names()
        for row in thin_names:
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
        "note": "用户口头批准开始补全详情",
        "items": items,
    }
    path = WORK_DIR / "战国_人审批准.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 人审批准 phase={phase} → {path}")
    return path


def _thin_entry_names() -> list[dict]:
    idx = json.loads(GLOBAL_INDEX.read_text(encoding="utf-8"))
    by_id = {str(e.get("史略ID", "")): e for e in idx.get("entries") or []}
    return [by_id[g] for g in THIN_GLBL if g in by_id]


def import_thin_entries() -> Path:
    """将 12 条薄标注从全局索引复制到 06/战国_人物.json（保留原 GLBL）。"""
    ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
    path = ENTRIES_DIR / "战国_人物.json"
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
    for row in _thin_entry_names():
        eid = str(row.get("史略ID", ""))
        if not eid or eid in existing_ids:
            continue
        copy = dict(row)
        copy["史略来源"] = copy.get("史略来源") or "一期薄标注"
        copy["补全来源"] = "薄标注待补"
        doc["entries"].append(copy)
        existing_ids.add(eid)
        added += 1

    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 薄标注导入 → {path}（新增 {added} 条）")
    return path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=["candidates", "approval-candidates", "approval-entries", "import-thin", "all-bootstrap"],
        default="all-bootstrap",
    )
    args = parser.parse_args()

    if args.action in ("candidates", "all-bootstrap"):
        write_candidates()
    if args.action in ("approval-candidates", "all-bootstrap"):
        write_approval(phase="candidates")
    if args.action == "approval-entries":
        write_approval(phase="entries")
    if args.action in ("import-thin",):
        import_thin_entries()
    if args.action == "all-bootstrap":
        total = sum(len(v) for v in build_candidates().values())
        print(f"📋 A 类候选 {total} 条；B 类薄标注 {len(THIN_GLBL)} 条待 import-thin")


if __name__ == "__main__":
    main()
