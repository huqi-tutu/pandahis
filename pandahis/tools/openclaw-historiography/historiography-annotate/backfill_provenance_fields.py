#!/usr/bin/env python3
"""批量补全 _auto_filled._年LLM依据 与 _坐标主轴说明（不覆盖已有值）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from shiji_person_fallback import SPINDLE_RATIONALES, _spindle_rationale_text
from shiji_scholarly_lifespans import lookup_scholarly_lifespan

# 史略ID → 主轴说明（人工精修，优先于模板）
AXIS_BY_EID: Dict[str, str] = {
    "SHIJI_045_01": "本世家开篇叙韩厥保赵氏孤、位列晋卿，主轴挂韩昭侯（韩氏世系坐标）；事晋景公诸段见共段事略。",
    "SHIJI_048_01": "本世家以大泽乡起兵、称王张楚至败亡为主线，主轴挂秦二世；起事前佣耕见共段事略。",
    "SHIJI_051_02": "本卷以刘贾从高祖定三秦、击项羽至封荆王为主线，主轴挂汉高祖；吕后朝刘泽事见共段事略。",
    "SHIJI_054_01": "本世家以从高祖征战、封侯及任丞相清静无为为主线，主轴挂汉高祖；惠帝朝为相见共段事略。",
    "SHIJI_059_02": "外戚以册立之君为准：本卷以唐姬幸景帝、生长沙王为主线，主轴挂汉景帝。",
    "SHIJI_059_03": "外戚以册立之君为准：本卷以栗姬为景帝妃、三子封王及太子废立为主线，主轴挂汉景帝。",
    "SHIJI_065_02": "本列传以孙武见吴王阖闾、练兵破楚为主线，主轴挂吴王阖闾；后载孙膑吴起见共段事略。",
    "SHIJI_083_02": "本卷以鲁仲连邯郸义不帝秦、却魏围赵为主线，主轴挂齐湣王；后载邹阳见共段事略。",
    "SHIJI_086_01": "本卷以专诸匕首献鱼刺杀王僚为主线，主轴挂吴王僚；后世刺客见共段事略。",
    "SHIJI_086_02": "本卷以曹沫执匕首劫齐桓公复鲁地为主线，主轴挂鲁庄公；后世刺客见共段事略。",
    "SHIJI_086_03": "本卷以聂政刺韩傀为主线，主轴挂韩桓惠王；豫让、荆轲见共段事略。",
    "SHIJI_086_04": "本卷以荆轲刺秦王为主线，主轴挂燕王喜；易水送别及秦宫事见本传。",
    "SHIJI_093_02": "本卷以韩王信封韩王、徙太原守边至叛入匈奴为主线，主轴挂汉高祖；卢绾传见共段事略。",
}

ANCIENT_DYNASTIES = frozenset(
    {"五帝", "夏", "商", "殷", "周", "秦"}
)


def _abs_year(y: int) -> str:
    return f"前{abs(y)}" if y < 0 else str(y)


def _year_span_note(s: int, e: int) -> str:
    if s == e:
        return _abs_year(s)
    return f"{_abs_year(s)}–{_abs_year(e)}"


def infer_year_basis(entry: dict, volume_name: str) -> Optional[str]:
    af = entry.get("_auto_filled") or {}
    if af.get("_年LLM依据"):
        return None
    span = lookup_scholarly_lifespan(entry)
    if span is not None:
        return span[2]
    name = (entry.get("史略名称") or "").strip()
    cat = (entry.get("史略分类") or "").strip()
    s, e = entry.get("史略开始年"), entry.get("史略结束年")
    if not isinstance(s, int) or not isinstance(e, int):
        return None
    dynasty = (entry.get("二级朝代坐标") or "").strip()
    ancient = dynasty in ANCIENT_DYNASTIES or "本纪" in volume_name and s < -500
    span_txt = _year_span_note(s, e)
    if cat == "君王":
        if s == e:
            if ancient:
                return f"{name}在位/传说年代约{span_txt}（上古多推测）"
            return f"{name}在位约{span_txt}"
        if ancient:
            return f"{name}即位{_abs_year(s)}，崩{_abs_year(e)}（上古年代多推测）"
        return f"{name}即位{_abs_year(s)}，崩{_abs_year(e)}"
    if cat == "宗戚":
        if s == e:
            return f"{name}约{span_txt}（生年不详）"
        return f"{name}约{span_txt}（生年推测）"
    # 士臣 / 庶众
    if s == e:
        return f"{name}卒{_abs_year(e)}确定，生年不详"
    return f"{name}生卒约{span_txt}（生年推测）"


def infer_axis(entry: dict, volume_name: str) -> Optional[str]:
    af = entry.get("_auto_filled") or {}
    if af.get("_坐标主轴说明"):
        return None
    eid = (entry.get("史略ID") or "").strip()
    if eid in AXIS_BY_EID:
        return AXIS_BY_EID[eid]
    if eid in SPINDLE_RATIONALES:
        return SPINDLE_RATIONALES[eid]
    name = (entry.get("史略名称") or "").strip()
    patron = (entry.get("四级帝王坐标") or "").strip()
    cat = (entry.get("史略分类") or "").strip()
    if cat == "君王":
        if "本纪" in volume_name:
            return f"本纪以{name}即位治国为主线，主轴即{name}本身"
        if "世家" in volume_name:
            return f"本世家以{name}传世袭国为主线，主轴即{name}本身"
        if "书" in volume_name:
            return f"本卷述典章制度沿革，以{name}朝相关段落为坐标锚点，主轴挂{name}"
        return f"本卷以{name}为主轴君王"
    if cat == "宗戚" and patron:
        return (
            f"外戚以册立之君为准：本卷以{name}侍{patron}、册立诸子为主线，"
            f"主轴挂{patron}"
        )
    if patron:
        return _spindle_rationale_text(entry, patron)
    return None


def backfill_file(path: Path, *, dry_run: bool = False) -> Tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    vol_name = (data.get("volume") or "").strip()
    year_n = axis_n = 0
    for entry in data.get("entries") or []:
        af = dict(entry.get("_auto_filled") or {})
        yb = infer_year_basis(entry, vol_name)
        ax = infer_axis(entry, vol_name)
        if yb:
            af["_年LLM依据"] = yb
            year_n += 1
        if ax:
            af["_坐标主轴说明"] = ax
            axis_n += 1
        if yb or ax:
            entry["_auto_filled"] = af
    if (year_n or axis_n) and not dry_run:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return year_n, axis_n


def parse_vol(stem: str) -> int:
    m = re.search(r"01史记_(\d+)_", stem)
    return int(m.group(1)) if m else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="补全考订溯源字段")
    ap.add_argument("paths", nargs="*", help="skeleton.json；缺省则扫 03索引标注条目")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--vols", help="逗号分隔卷号，如 001,045,086")
    args = ap.parse_args()
    if args.paths:
        files = [Path(p) for p in args.paths]
    else:
        base = Path(__file__).resolve().parents[3] / "data" / "03索引标注条目"
        files = sorted(base.glob("01史记_*_skeleton.json"), key=lambda p: parse_vol(p.stem))
    if args.vols:
        want = {int(x.strip()) for x in args.vols.split(",") if x.strip()}
        files = [f for f in files if parse_vol(f.stem) in want]
    total_y = total_a = 0
    touched = 0
    for f in files:
        y, a = backfill_file(f, dry_run=args.dry_run)
        if y or a:
            touched += 1
            print(f"{f.name}: +年依据{y} +主轴{a}")
            total_y += y
            total_a += a
    mode = "（dry-run）" if args.dry_run else ""
    print(f"完成{mode}: {touched} 文件, 补年依据 {total_y} 条, 补主轴 {total_a} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
