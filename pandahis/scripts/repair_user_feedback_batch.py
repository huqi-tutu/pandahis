#!/usr/bin/env python3
"""批量修复用户纠错反馈相关数据：P0 降级、参考著作格式、史料原文、措辞。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INDEX_PATH = DATA / "03索引标注条目" / "史略索引_01至02.json"
PARA_INDEX_DIR = DATA / "03索引标注条目" / "段落索引"
TRANS_DIR = DATA / "04史料翻译"
AGG_PATH = TRANS_DIR / "史略翻译_汇总.json"
DYN_DETAIL_DIR = DATA / "06朝代知识补全" / "详情"

P0_RESTORE = {
    "GLBL_00320": "孙武著《孙子兵法》，受吴王阖闾重用，参与破楚入郢之战，兵学思想影响深远，为军事领域的顶级核心人物。",
    "GLBL_00421": "管仲佐齐桓公成就春秋首霸，推行内政改革与「尊王攘夷」方略，其治国思想与霸业实践深刻重塑天下格局，属顶级政治家。",
    "GLBL_00426": "老子著《道德经》，创道家学派，其思想奠定中国哲学根基并影响世界，属于春秋文化思想的绝对核心。",
}

LAOZI_ID = "GLBL_00426"
SHIXIANGYU_DYNASTY_OLD = "秦末汉初"
SHIXIANGYU_DYNASTY_NEW = "楚汉"

REF_INLINE_RE = re.compile(r"([。！？；」』])([^\n]{0,120}?)参考著作\s*[:：]")


def load_index_entries() -> list[dict]:
    raw = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    for v in raw.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "史略ID" in v[0]:
            return v
    raise ValueError("无法解析索引结构")


def save_index(entries: list[dict]) -> None:
    INDEX_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def repair_p0_quota(entries: list[dict]) -> int:
    by_id = {e["史略ID"]: e for e in entries if e.get("史略ID")}
    n = 0
    for eid, reason in P0_RESTORE.items():
        e = by_id.get(eid)
        if not e:
            continue
        e["优先级"] = "P0"
        e["优先级判定理由"] = reason
        auto = e.setdefault("_auto_filled", {})
        auto.pop("_优先级待审", None)
        n += 1
    # 孔子：清除待审标记
    conf = by_id.get("GLBL_00316")
    if conf:
        auto = conf.setdefault("_auto_filled", {})
        if auto.pop("_优先级待审", None):
            n += 1
    return n


def fix_reference_format(detail: str) -> tuple[str, bool]:
    if "参考著作" not in detail:
        return detail, False
    if re.search(r"\n\n参考著作\s*[:：]", detail):
        return detail, False
    new_detail, count = REF_INLINE_RE.subn(r"\1\n\n参考著作：", detail, count=1)
    if count:
        return new_detail, True
    # fallback: first 参考著作 occurrence
    idx = detail.find("参考著作")
    if idx > 0 and not detail[idx - 2 : idx] == "\n\n":
        return detail[:idx].rstrip() + "\n\n" + detail[idx:], True
    return detail, False


def repair_reference_files() -> int:
    fixed = 0
    paths = list(TRANS_DIR.glob("GLBL_*.json"))
    paths = [p for p in paths if p.name != "史略翻译_汇总.json"]
    for fp in paths:
        data = json.loads(fp.read_text(encoding="utf-8"))
        detail = str(data.get("翻译详情") or "")
        new_detail, changed = fix_reference_format(detail)
        if changed:
            data["翻译详情"] = new_detail
            fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            fixed += 1
    if AGG_PATH.is_file():
        agg = json.loads(AGG_PATH.read_text(encoding="utf-8"))
        for item in agg.get("entries") or []:
            detail = str(item.get("翻译详情") or "")
            new_detail, changed = fix_reference_format(detail)
            if changed:
                item["翻译详情"] = new_detail
                fixed += 1
        AGG_PATH.write_text(json.dumps(agg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixed


def _load_para_index(index_file: str) -> dict[int, str]:
    path = PARA_INDEX_DIR / index_file
    if not path.is_file():
        path = DATA / "03索引标注条目" / index_file
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    paras = doc.get("paragraphs") or []
    out: dict[int, str] = {}
    for p in paras:
        pid = p.get("id")
        if pid is None:
            continue
        text = str(p.get("text") or "").strip()
        if text:
            out[int(pid)] = text
    return out


def build_original_from_entry(entry: dict) -> str:
    texts: list[str] = []
    for block in entry.get("paragraphs") or []:
        index_file = str(block.get("index_file") or "").replace("段落索引/", "")
        if not index_file:
            continue
        para_map = _load_para_index(index_file)
        p_from = int(block.get("paragraph_from") or 0)
        p_to = int(block.get("paragraph_to") or p_from)
        if p_from <= 0:
            continue
        for pn in range(p_from, p_to + 1):
            t = para_map.get(pn)
            if t:
                texts.append(t)
    return "\n".join(texts)


def repair_source_original(entries: list[dict]) -> int:
    by_id = {e["史略ID"]: e for e in entries if e.get("史略ID")}
    fixed = 0
    agg = None
    agg_by_id: dict[str, dict] = {}
    if AGG_PATH.is_file():
        agg = json.loads(AGG_PATH.read_text(encoding="utf-8"))
        agg_by_id = {str(x.get("史略ID")): x for x in agg.get("entries") or []}

    for fp in sorted(TRANS_DIR.glob("GLBL_*.json")):
        if fp.name == "史略翻译_汇总.json":
            continue
        data = json.loads(fp.read_text(encoding="utf-8"))
        eid = str(data.get("史略ID") or "")
        idx_e = by_id.get(eid)
        if not idx_e or not idx_e.get("paragraphs"):
            continue
        built = build_original_from_entry(idx_e)
        if not built.strip():
            continue
        current = data.get("史料原文")
        if isinstance(current, str) and len(current.strip()) >= len(built.strip()) * 0.9:
            continue
        data["史料原文"] = built
        citation = idx_e.get("原文出处") or idx_e.get("主要史料出处")
        if citation:
            data["原文出处"] = citation if str(citation).startswith("《") else f"《{citation}》"
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if eid in agg_by_id:
            agg_by_id[eid]["史料原文"] = built
            if data.get("原文出处"):
                agg_by_id[eid]["原文出处"] = data["原文出处"]
        fixed += 1

    if agg is not None:
        AGG_PATH.write_text(json.dumps(agg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixed


def repair_renjizhi_wording() -> bool:
    fp = DYN_DETAIL_DIR / "GLBL_00655_人祭制度.json"
    if not fp.is_file():
        return False
    data = json.loads(fp.read_text(encoding="utf-8"))
    detail = str(data.get("翻译详情") or "")
    if "民众实在是神灵的主宰" not in detail:
        return False
    data["翻译详情"] = detail.replace("民众实在是神灵的主宰", "民众乃神灵之主")
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dyn_agg = DYN_DETAIL_DIR / "朝代知识详情_汇总.json"
    if dyn_agg.is_file():
        agg = json.loads(dyn_agg.read_text(encoding="utf-8"))
        for item in agg.get("entries") or []:
            if item.get("史略ID") == "GLBL_00655":
                item["翻译详情"] = data["翻译详情"]
        dyn_agg.write_text(json.dumps(agg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def repair_laozi_category(entries: list[dict]) -> bool:
    """#20 老子：周守藏室之史，归类应为士臣而非文臣。"""
    by_id = {e["史略ID"]: e for e in entries if e.get("史略ID")}
    e = by_id.get(LAOZI_ID)
    if not e or e.get("史略分类") == "士臣":
        return False
    e["史略分类"] = "士臣"
    coord = str(e.get("五级细坐标") or "")
    if "文臣" in coord:
        e["五级细坐标"] = coord.replace("文臣", "士臣")
    skel = DATA / "03索引标注条目" / "01史记_063_老子韩非列传第三_skeleton.json"
    if skel.is_file():
        doc = json.loads(skel.read_text(encoding="utf-8"))
        for item in doc.get("entries") or []:
            if item.get("史略名称") == "老子":
                item["史略分类"] = "士臣"
                c = str(item.get("五级细坐标") or "")
                if "文臣" in c:
                    item["五级细坐标"] = c.replace("文臣", "士臣")
        skel.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def repair_chu_han_dynasty_name(entries: list[dict]) -> int:
    """#23 项羽等：二级朝代坐标统一为「楚汉」。"""
    n = 0
    for e in entries:
        if e.get("二级朝代坐标") == SHIXIANGYU_DYNASTY_OLD:
            e["二级朝代坐标"] = SHIXIANGYU_DYNASTY_NEW
            n += 1
    coord_files = [
        DATA / "01历史坐标数据" / "朝代.json",
        DATA / "01历史坐标数据" / "政权.json",
        DATA / "01历史坐标数据" / "帝王.json",
        ROOT / "tools/openclaw-historiography/historiography-annotate/reference/朝代.json",
        ROOT / "tools/openclaw-historiography/historiography-annotate/reference/政权.json",
        ROOT / "tools/openclaw-historiography/historiography-annotate/reference/帝王.json",
    ]
    for fp in coord_files:
        if not fp.is_file():
            continue
        text = fp.read_text(encoding="utf-8")
        if SHIXIANGYU_DYNASTY_OLD not in text:
            continue
        fp.write_text(text.replace(SHIXIANGYU_DYNASTY_OLD, SHIXIANGYU_DYNASTY_NEW), encoding="utf-8")
    return n


def main() -> int:
    entries = load_index_entries()
    p0_n = repair_p0_quota(entries)
    save_index(entries)
    ref_n = repair_reference_files()
    src_n = repair_source_original(entries)
    wording = repair_renjizhi_wording()
    laozi = repair_laozi_category(entries)
    save_index(entries)
    chu_han = repair_chu_han_dynasty_name(entries)
    if chu_han:
        save_index(entries)
    print(f"P0 恢复/清理: {p0_n} 条")
    print(f"参考著作格式修复: {ref_n} 处")
    print(f"史料原文补全: {src_n} 条")
    print(f"人祭制度措辞: {'已修复' if wording else '跳过'}")
    print(f"老子分类士臣: {'已修复' if laozi else '跳过'}")
    print(f"楚汉朝代名: {chu_han} 条索引 + 坐标文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
