"""《汉书》结构脚本修复：卷首标题 / 篇内小标题（非 LLM 知识字段）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

from lib import db, gates
from lib.config import ANNOTATE_DIR


def _row_has_owner(row: dict | None, name: str, category: str) -> bool:
    if not row:
        return False
    owners = row.get("owners") or []
    for owner in owners:
        if owner.get("name") == name and owner.get("category") == category:
            return True
    return False


def _trim_entry_paragraph_ranges(entries: list[dict], attr_map: dict[int, dict]) -> list[str]:
    fixes: list[str] = []
    for entry in entries:
        name = (entry.get("史略名称") or "").strip()
        category = (entry.get("史略分类") or "").strip()
        if not name or not category:
            continue
        for rng in entry.get("paragraphs") or []:
            start = rng.get("paragraph_from")
            end = rng.get("paragraph_to")
            if not isinstance(start, int) or not isinstance(end, int) or start > end:
                continue
            new_start = start
            new_end = end
            while new_start <= end and not _row_has_owner(
                attr_map.get(new_start), name, category
            ):
                new_start += 1
            while new_end >= new_start and not _row_has_owner(
                attr_map.get(new_end), name, category
            ):
                new_end -= 1
            if new_start <= new_end and (new_start != start or new_end != end):
                rng["paragraph_from"] = new_start
                rng["paragraph_to"] = new_end
                fixes.append(f"{name} P{start}-P{end}→P{new_start}-P{new_end}")
    return fixes


def repair_skeleton_headers(work: str, vol: str) -> Tuple[bool, str]:
    """按原文 classify_paragraph_header 修正 segment_attribution 头段 exclude。"""
    if not str(work).startswith("02汉书"):
        return False, ""
    vol = vol.zfill(3)
    sk = gates.skeleton_path(work, vol)
    if sk is None or not sk.exists():
        return False, "无 skeleton"

    sys.path.insert(0, str(ANNOTATE_DIR))
    from check_format import resolve_source_file, work_from_skeleton_path  # noqa: E402
    from paragraph_utils import (  # noqa: E402
        classify_paragraph_header,
        split_mode_for_work,
        split_paragraphs,
    )

    data = json.loads(sk.read_text(encoding="utf-8"))
    source = resolve_source_file(data, sk)
    if source is None or not source.is_file():
        return False, "无法加载原文"
    work_id = work_from_skeleton_path(sk)
    text = source.read_text(encoding="utf-8")
    paras = split_paragraphs(text, split_mode_for_work(work_id, text))
    attr = data.get("segment_attribution") or []
    entries = data.get("entries") or []
    attr_map = {row["paragraph"]: row for row in attr if isinstance(row.get("paragraph"), int)}
    fixes: List[str] = []

    for i, text in enumerate(paras, 1):
        header = classify_paragraph_header(text)
        if not header:
            # 汉书论赞段误标太史公曰 → 赞曰/论赞
            row = attr_map.get(i)
            if row and not row.get("owners"):
                t = (text or "").strip()
                reason = (row.get("exclude_reason") or "").strip()
                if reason == "太史公曰" and t.startswith("赞曰"):
                    attr_map[i] = {"paragraph": i, "owners": [], "exclude_reason": "赞曰"}
                    fixes.append(f"P{i} exclude→赞曰")
                elif reason == "太史公曰" and t.startswith("论曰"):
                    attr_map[i] = {"paragraph": i, "owners": [], "exclude_reason": "论赞"}
                    fixes.append(f"P{i} exclude→论赞")
            continue
        row = attr_map.get(i)
        if not row:
            continue
        if row.get("owners"):
            attr_map[i] = {"paragraph": i, "owners": [], "exclude_reason": header}
            fixes.append(f"P{i}→{header}")
        elif row.get("exclude_reason") != header:
            attr_map[i] = {"paragraph": i, "owners": [], "exclude_reason": header}
            fixes.append(f"P{i} exclude→{header}")

    if not fixes:
        return False, "头段 exclude 无需修复"

    ordered: List[dict] = []
    for row in attr:
        p = row.get("paragraph")
        if isinstance(p, int) and p in attr_map:
            ordered.append(attr_map[p])
        else:
            ordered.append(row)
    entry_fixes = _trim_entry_paragraph_ranges(entries, attr_map)
    if entry_fixes:
        fixes.extend(f"条目范围 {item}" for item in entry_fixes[:8])

    new_data = {**data, "segment_attribution": ordered, "entries": entries}
    sk.write_text(json.dumps(new_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, "头段修复: " + "; ".join(fixes[:8])


def repair_step4_lvtaihou_gongjuan(sk_path: Path) -> Tuple[bool, str]:
    """高后纪/吕太后宗戚：四级帝王挂汉高祖，年轴临朝称制（帝王表+史记009同卷）。"""
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    if len(entries) != 1:
        return False, "非单条主轴卷"
    e = entries[0]
    name = (e.get("史略名称") or "").strip()
    cat = (e.get("史略分类") or "").strip()
    vol = (data.get("volume") or "").strip()
    if cat != "宗戚" or name not in ("吕太后", "吕后") or "高后" not in vol:
        return False, "非吕太后宗戚高后纪"
    if name == "吕后":
        e["史略名称"] = "吕太后"
        e["史略简介"] = "吕太后"
    formal = {
        "史略开始年": -195,
        "史略结束年": -180,
        "优先级": "P0",
        "优先级判定理由": "本纪主轴叙事，临朝太后（宗戚）",
        "四级帝王坐标": "汉高祖",
        "三级政权坐标": "西汉",
        "二级朝代坐标": "西汉",
        "一级文明坐标": "华夏",
        "文明ID": "HX",
        "朝代ID": "CD_HX_XIHAN",
        "政权ID": "ZQ_HX_XIHAN_XIHAN",
        "帝王ID": "DW_HX_XIHAN_XIHAN_HANGAOZU",
    }
    for k, v in formal.items():
        e[k] = v
    e.pop("_needs_llm", None)
    auto = dict(e.get("_auto_filled") or {})
    auto.update(
        {
            "match_confidence": "exact",
            "_主轴参考": "宗戚册封之君：汉高祖（与史记吕太后本纪、帝王表一致）",
            "_坐标主轴说明": "宗戚以册封之君为准：吕雉为汉高祖皇后；惠帝朝临朝称制见共段事略。",
            "帝王开始年": -202,
            "帝王结束年": -195,
        }
    )
    e["_auto_filled"] = auto
    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, "吕太后宗戚 Step4 坐标/年份已按帝王表+史记009对齐"


def try_recover_hanshu_step4(work: str, vol: str) -> Tuple[bool, str]:
    """Step4 熔断前：汉书特例修复 + finalize + final 校验。"""
    if not str(work).startswith("02汉书"):
        return False, ""
    vol = vol.zfill(3)
    sk = gates.skeleton_path(work, vol)
    if sk is None:
        return False, "无 skeleton"
    repaired, msg = repair_step4_lvtaihou_gongjuan(sk)
    if not repaired:
        return False, msg or "无可用修复"
    ok, fin_msg = gates.step4_finalize(sk)
    if not ok:
        return False, f"finalize 失败: {fin_msg[:200]}"
    ok, ver_msg = gates.verify_step4_final(sk)
    if not ok:
        gates.step4_restore_scratch(sk)
        return False, ver_msg[:400]
    return True, msg


def repair_and_requeue_verify(work: str, vol: str) -> Tuple[bool, str]:
    """修复头段/合传机械划块后：保留 Step1 done，Step2–4 重置 pending 以便重跑 verify。"""
    repaired, msg = repair_skeleton_headers(work, vol)
    if not repaired and str(work).startswith("02汉书"):
        try:
            from lib import gates as _gates
            from lib.hanshu_hezhuan_autofix import try_repair_hanshu_hezhuan_step1

            idx = _gates.load_paragraph_index(work, vol)
            rep_ok, rep_msg = try_repair_hanshu_hezhuan_step1(work, vol, idx)
            if rep_ok:
                repaired, msg = True, rep_msg
        except FileNotFoundError:
            pass
    if not repaired:
        return False, msg
    vol = vol.zfill(3)
    j1 = db.get_job(work, vol, "1")
    if j1 and j1["status"] != "done":
        db.mark_volume_steps_done(work, vol, "1")
    for step in ("2", "3", "4"):
        db.reset_volume_step(work, vol, step)
    return True, msg + "；已重置 Step2–4"
