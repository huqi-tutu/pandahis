#!/usr/bin/env python3
"""增量补漏：向候选清单追加条目并写入人审批准（用户已点名清单）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HISTOGRAPH_ROOT = Path(__file__).resolve().parents[4]
WORK = HISTOGRAPH_ROOT / "data" / "05工作流中间产物" / "朝代知识补全"

WUDI_SUPPLEMENT = {
    "武将": [
        {
            "名称": "蚩尤",
            "史略分类": "武将",
            "分类判定理由": "九黎部落首领，涿鹿之战中与黄帝联盟对抗，军事主轴。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "黄帝",
            "主要史料出处": "《史记·五帝本纪》",
            "边界备注": "与事略「涿鹿之战」姊妹条，人物侧写为主",
            "去重自检": "一期与06均无蚩尤条",
            "审核状态": "approved",
        },
        {
            "名称": "共工",
            "史略分类": "武将",
            "分类判定理由": "上古神话人物，与颛顼争帝，触不周山；主语为人，归武将。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "颛顼",
            "主要史料出处": "《史记·五帝本纪》《淮南子·天文训》",
            "边界备注": "用户标注事略/武将，按人物实体归武将",
            "去重自检": "一期与06均无共工条",
            "审核状态": "approved",
        },
    ],
    "君王": [
        {
            "名称": "炎帝",
            "史略分类": "君王",
            "分类判定理由": "阪泉之战前与黄帝并列的部落联盟首领，炎黄始祖之一。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "炎帝",
            "主要史料出处": "《史记·五帝本纪》",
            "边界备注": "传说时代，与事略「阪泉之战」互补",
            "去重自检": "一期与06均无炎帝君王条",
            "审核状态": "approved",
        },
        {
            "名称": "少昊",
            "史略分类": "君王",
            "分类判定理由": "传说时代东方天帝/金天氏，常与黄帝—颛顼谱系并论。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "少昊",
            "主要史料出处": "《史记·五帝本纪》《左传·昭公十七年》",
            "边界备注": "年代与系谱多异说，正文须列异说",
            "去重自检": "一期与06均无少昊条",
            "审核状态": "approved",
        },
    ],
    "庶众": [
        {
            "名称": "彭祖",
            "史略分类": "庶众",
            "分类判定理由": "传说长寿者，与尧舜禹时代关联，非帝王非卿相。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "尧",
            "主要史料出处": "《庄子·大宗师》《史记·楚世家》",
            "边界备注": "与西汉同名「彭祖」文臣/宗戚条（GLBL_00166等）异人异朝，勿混淆",
            "去重自检": "五帝坐标下无彭祖条",
            "审核状态": "approved",
        },
    ],
    "论著": [
        {
            "名称": "《击壤歌》",
            "子类": "名篇",
            "主旨": "上古民谣，咏太平自足、无求于上",
            "作者或提出者": "不详，传说为帝尧时代民间歌谣",
            "成书或传播年": -2300,
            "建议年份": -2300,
            "建议挂靠帝王": "尧",
            "主要史料出处": "《帝王世纪》",
            "影响": "成为后世咏怀太平、批判奢政的经典意象",
            "边界备注": "用户增量补漏",
            "审核状态": "approved",
        },
        {
            "名称": "《卿云歌》",
            "子类": "名篇",
            "主旨": "舜禅位禹时的庆贺之歌，颂天命与德政",
            "作者或提出者": "传说为舜与群臣所作",
            "成书或传播年": -2200,
            "建议年份": -2200,
            "建议挂靠帝王": "舜",
            "主要史料出处": "《尚书大传》",
            "影响": "后世禅让叙事与祥瑞政治的重要文学符号",
            "边界备注": "用户增量补漏",
            "审核状态": "approved",
        },
        {
            "名称": "《南风歌》",
            "子类": "名篇",
            "主旨": "传说舜所制之歌，以南风解民愠",
            "作者或提出者": "传说为舜",
            "成书或传播年": -2250,
            "建议年份": -2250,
            "建议挂靠帝王": "舜",
            "主要史料出处": "《孔子家语·辩乐解》",
            "影响": "成为圣王德音、民本政治的象征",
            "边界备注": "用户增量补漏",
            "审核状态": "approved",
        },
    ],
}

XIA_SUPPLEMENT = {
    "文臣": [
        {
            "名称": "胤侯",
            "史略分类": "文臣",
            "分类判定理由": "夏朝诸侯，太康失国时与夏后氏同衰，《胤征》所涉。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "太康",
            "主要史料出处": "《竹书纪年》",
            "边界备注": "与论著《胤征》姊妹条",
            "去重自检": "一期与06均无胤侯条",
            "审核状态": "approved",
        },
    ],
    "武将": [
        {
            "名称": "女艾",
            "史略分类": "武将",
            "分类判定理由": "少康臣，收罗夏遗民、参与灭寒浞，军事主轴。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "少康",
            "主要史料出处": "《左传·襄公四年》",
            "边界备注": "",
            "去重自检": "一期与06均无女艾条",
            "审核状态": "approved",
        },
        {
            "名称": "寒浇",
            "史略分类": "武将",
            "分类判定理由": "寒浞之子，灭夏后相、追杀少康，军事主轴。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "相",
            "主要史料出处": "《左传·襄公四年》《竹书纪年》",
            "边界备注": "与寒豷为兄弟",
            "去重自检": "一期与06均无寒浇条",
            "审核状态": "approved",
        },
        {
            "名称": "寒豷",
            "史略分类": "武将",
            "分类判定理由": "寒浞之子，与寒浇并力攻夏，军事主轴。",
            "补全来源": "用户增量补漏",
            "建议挂靠帝王": "相",
            "主要史料出处": "《左传·襄公四年》",
            "边界备注": "与寒浇为兄弟",
            "去重自检": "一期与06均无寒豷条",
            "审核状态": "approved",
        },
    ],
    "论著": [
        {
            "名称": "《五子之歌》",
            "子类": "名篇",
            "主旨": "太康失国后五子述戒，咏怀明德与失国教训",
            "作者或提出者": "传说为夏太康五弟所作",
            "成书或传播年": -1900,
            "建议年份": -1900,
            "建议挂靠帝王": "太康",
            "主要史料出处": "《尚书·五子之歌》（今文佚篇）",
            "影响": "后世戒奢保国、追思祖训的重要文本",
            "边界备注": "用户增量补漏；今文多佚，正文须标注文献性质",
            "审核状态": "approved",
        },
        {
            "名称": "《胤征》",
            "子类": "典籍",
            "主旨": "记载胤侯与夏后氏同衰、征伐失道之事",
            "作者或提出者": "不详",
            "成书或传播年": -1900,
            "建议年份": -1900,
            "建议挂靠帝王": "太康",
            "主要史料出处": "《竹书纪年》",
            "影响": "夏朝中期政治危机的文献记忆",
            "边界备注": "与文臣胤侯姊妹条",
            "审核状态": "approved",
        },
    ],
}


def _existing_names(doc: dict, cat: str) -> set[str]:
    return {
        str(c.get("名称", "")).strip()
        for c in (doc.get("candidates") or {}).get(cat) or []
        if isinstance(c, dict)
    }


def append_candidates(path: Path, supplement: dict[str, list]) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    added: list[str] = []
    for cat, rows in supplement.items():
        doc.setdefault("candidates", {})
        doc["candidates"].setdefault(cat, [])
        exist = _existing_names(doc, cat)
        for row in rows:
            name = str(row.get("名称", "")).strip()
            if name in exist:
                continue
            doc["candidates"][cat].append(row)
            added.append(f"{cat}:{name}")
    doc["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def write_approval(path: Path, *, dynasty_id: str, dynasty_name: str, items: dict[str, list[str]]) -> None:
    doc = {
        "schema_version": 1,
        "朝代ID": dynasty_id,
        "朝代名称": dynasty_name,
        "phase": "candidates",
        "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "approved_by": "user",
        "note": "增量补漏批次（用户点名清单）",
        "items": items,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    wudi_cand = WORK / "五帝_候选清单.json"
    xia_cand = WORK / "夏_候选清单.json"
    wudi_added = append_candidates(wudi_cand, WUDI_SUPPLEMENT)
    xia_added = append_candidates(xia_cand, XIA_SUPPLEMENT)
    print("五帝候选追加:", wudi_added)
    print("夏候选追加:", xia_added)

    write_approval(
        WORK / "五帝_人审批准.json",
        dynasty_id="CD_HX_WUDI",
        dynasty_name="五帝",
        items={
            "论著": ["《击壤歌》", "《卿云歌》", "《南风歌》"],
            "武将": ["蚩尤", "共工"],
            "君王": ["炎帝", "少昊"],
            "庶众": ["彭祖"],
        },
    )
    write_approval(
        WORK / "夏_人审批准.json",
        dynasty_id="CD_HX_XIA",
        dynasty_name="夏",
        items={
            "论著": ["《五子之歌》", "《胤征》"],
            "文臣": ["胤侯"],
            "武将": ["女艾", "寒浇", "寒豷"],
        },
    )
    print("✅ 人审批准已写入（phase=candidates，仅含本批增量）")
    print()
    print("后续必跑（字段补全，不可省略 enrich-all）：")
    print("  fill-* / fill-renwu → compose-pending → enrich-all → gate → append/sync")
    print("  python3 dynasty_supplement.py --dynasty <朝> --step enrich-all")


if __name__ == "__main__":
    main()
