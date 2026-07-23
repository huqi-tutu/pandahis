#!/usr/bin/env python3
"""对已有译稿应用规则化修复（归因/引入/句群/禁释）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.attribution import apply_attribution_fixes
from lib.gloss_rules import detect_forbidden_gloss
from lib.recall import recall_entry
from lib.config import default_index_path, paths
from lib.verify import resolve_output_path


def _fix_huangdi_intro(detail: str) -> str:
    """黄帝：收窄引入，避免与 M001 重复。"""
    old_intro = (
        "如果在中国历史上找一个共同的起点，绝大多数人会指向同一个名字——黄帝。"
        "他是华夏民族公认的人文始祖，《史记》五帝本纪的第一位，被后世尊为「土德之君」。"
        "在距今约五千年前，这位名叫轩辕的部落首领，通过一系列征战整合了黄河中下游的各大部族，"
        "奠定了早期华夏文明的版图。他的时代没有文字记录流传下来，但后人通过口耳相传和后世史书追记，"
        "依然为他勾勒出了一幅清晰的形象。\n\n"
        "那么，这位被历代帝王奉为祖先的传奇人物，究竟有着怎样的家世和早年经历？"
        "让我们来看一看《史记·五帝本纪》是如何描述黄帝的。"
    )
    new_intro = (
        "《史记·五帝本纪》从轩辕讲起，但叙事并非从一片空白开始——"
        "当时神农氏号令不行，诸侯混战，正文将从这一乱世背景切入，"
        "按司马迁的次序展开黄帝如何崛起、征战与立国。\n\n"
        "让我们来看一看《史记·五帝本纪》是如何描述黄帝的。"
    )
    if old_intro in detail:
        return detail.replace(old_intro, new_intro)
    return detail


def _fix_huangdi_cluster_quotes(detail: str) -> str:
    """黄帝：合并修德振兵等碎引号为句群。"""
    old = (
        "司马迁在这里列举了一大串战前准备：对内「修德振兵」，修明德行、提振军力；"
        "同时「治五气」，调和天地四时的运行；经济上「蓺五种」，推广黍稷稻麦菽五谷的种植；"
        "民生上「抚万民」，安抚四方百姓；规划上「度四方」，制定总体的空间布局。"
        "最特别的是，他「教熊罴貔貅貙虎」——不是真的去训练野兽上战场，"
        "而是把手下各部族按猛兽图腾编成突击力量，熊部、罴部、貔貅部、貙部、虎部，只听名字就带着一股凶悍气。"
    )
    new = (
        "司马迁在这里用一整串并列短语概括战前准备：《史记》原文作"
        "「修德振兵，治五气，蓺五种，抚万民，度四方，教熊罴貔貅貙虎」。"
        "白话来说，就是修明德行、提振军力，调和四时，推广五谷种植，安抚万民，规划四方版图；"
        "又把各部族按熊、罴、貔貅、貙、虎等猛兽图腾编成战阵——不是真驯兽上阵，"
        "而是以图腾名号组织突击力量，只听名字就带着一股凶悍气。"
    )
    if old in detail:
        detail = detail.replace(old, new)
    # 早期碎引号段
    old2 = (
        "在这样的乱世里，轩辕的做法很简单也很直接——他开始「习用干戈」，整顿兵器铠甲，"
        "拉起了一支能打仗的队伍。谁不来朝贡、表示服从，他就带兵去打，这就是「以征不享」。"
        "效果立竿见影，诸侯一个接一个跑来归附，「咸来宾从」。"
    )
    new2 = (
        "在这样的乱世里，轩辕的做法很简单也很直接——《史记》记他「习用干戈，以征不享」，"
        "整顿兵器、拉起队伍，谁不来朝贡就出兵征讨。效果立竿见影，诸侯纷纷来归附。"
    )
    if old2 in detail:
        detail = detail.replace(old2, new2)
    return detail


def _fix_zhuanxu_opening(detail: str) -> str:
    """颛顼：删前文黄帝崩展开。"""
    detail = re.sub(
        r"\n\n黄帝去世后，葬在桥山[^。]*。说到这儿，得插一段高阳即位前的经历。",
        "",
        detail,
    )
    detail = re.sub(
        r"《帝王世纪》记载，这孩子十岁的时候就开始辅佐少昊了。[^。]*。",
        "",
        detail,
    )
    return detail


def _strip_trivial_gloss(detail: str) -> str:
    """删除通识字冗余解释。"""
    detail = re.sub(r"也就是原文说的「崩」", "去世", detail)
    detail = re.sub(r"「崩」[^。]{0,12}(?:去世|逝世|死亡)", "去世", detail)
    return detail


def patch_entry(entry_id: str) -> list[str]:
    changes: list[str] = []
    recalled = recall_entry(entry_id, index_path=default_index_path())
    name = str(recalled.get("史略名称") or "")
    out_dir = paths()["translate_output"]
    path = resolve_output_path(entry_id, out_dir, name)
    data = json.loads(path.read_text(encoding="utf-8"))
    detail = str(data.get("翻译详情") or "")

    if entry_id == "GLBL_00149":
        nd = _fix_huangdi_intro(detail)
        if nd != detail:
            changes.append("黄帝引入收窄")
            detail = nd
        nd = _fix_huangdi_cluster_quotes(detail)
        if nd != detail:
            changes.append("黄帝句群引用")
            detail = nd

    if entry_id == "GLBL_00144":
        nd = _fix_zhuanxu_opening(detail)
        if nd != detail:
            changes.append("颛顼删黄帝崩前文")
            detail = nd

    nd = _strip_trivial_gloss(detail)
    if nd != detail:
        changes.append("禁释词清理")
        detail = nd

    detail, attr_changes = apply_attribution_fixes(detail, recalled)
    changes.extend(attr_changes)

    gloss = detect_forbidden_gloss(detail)
    if gloss:
        changes.append(f"仍有禁释警告: {len(gloss)}")

    data["翻译详情"] = detail
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changes


def main() -> int:
    ids = sys.argv[1:] or ["GLBL_00149", "GLBL_00144"]
    for eid in ids:
        ch = patch_entry(eid)
        print(f"{eid}: {ch or '无变化'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
