#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复三国/东汉一期人物：误挂帝王 + 帝王在位年冒充生卒 + 错误峰值年。

成因：
  1. 大量人物误挂「吴乌程侯」等，person_year_fallback 用帝王在位年当生卒；
  2. peak_year LLM 被锁在错误合法区间（如 264–280 → peak≈272）。

流程：
  检测毒条目 → 强制重挂四级帝王 → 清空毒年/毒峰值 → LLM 生卒 → LLM 峰值
  → 回写 online + V2(03至04) → 可选 sync-db

用法：
  python3 scripts/repair_sanguo_donghan_poisoned_years.py --dry-run
  python3 scripts/repair_sanguo_donghan_poisoned_years.py --limit 10
  python3 scripts/repair_sanguo_donghan_poisoned_years.py --sync-db
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ONLINE = DATA / "12线上史略索引" / "史略索引_online.json"
V2_INDEX = DATA / "10新标注条目" / "史略索引_03至04.json"
EMPEROR_JSON = DATA / "01历史坐标数据" / "帝王.json"
REPORT_DIR = DATA / "05工作流中间产物" / "三国东汉补全"

TOOLS = ROOT / "tools" / "openclaw-historiography"
ANNOTATE = TOOLS / "historiography-annotate"

for _p in (str(TOOLS), str(ANNOTATE), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_env = TOOLS / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())

TARGET_DYNASTIES = frozenset({"三国", "东汉"})
PERSON_CATS = frozenset({"文臣", "武将", "宗戚", "宦官", "庶众", "蕃祚"})

# 极少作为「批量人物挂靠」正确值：出现在毒模式时一律重推
POISON_PATRONS_SANGUO = frozenset({"吴乌程侯"})
POISON_YEAR_PAIRS = frozenset({
    (264, 280),  # 吴乌程侯在位
    (220, 220),  # 曹操单点占位
    (25, 25),    # 东汉朝代起始年
})

PEAK_KEYS = ("峰值年", "峰值原因", "峰值类型", "峰值置信度")
YEAR_KEYS = ("史略开始年", "史略结束年")
PEAK_AUTO_KEYS = (
    "_峰值指纹",
    "_峰值兜底级别",
    "_峰值LLM依据",
    "_峰值待审",
    "_峰值人工锁定",
    "_峰值对齐来源",
    "_峰值对齐说明",
)
YEAR_AUTO_KEYS = (
    "_年兜底级别",
    "_年兜底依据",
    "_年LLM依据",
    "_年待LLM",
    "_死亡年锚定",
    "_短跨度合理",
)

# 高置信学界生卒（优先于 LLM，保证诸葛亮等关键人物正确）
SEED_LIFESPANS: dict[str, tuple[int, int, str]] = {
    "诸葛亮": (181, 234, "诸葛亮生卒学界主流约181–234（建兴十二年卒于五丈原）"),
    "关羽": (160, 220, "关羽卒建安二十四年（220），生年约160（推测）"),
    "张飞": (165, 221, "张飞章武元年（221）遇刺，生年约165（推测）"),
    "赵云": (168, 229, "赵云建兴七年（229）卒，生年约168（推测）"),
    "马超": (176, 222, "马超章武二年（222）卒，生年约176"),
    "黄忠": (148, 220, "黄忠建安末卒，生年约148（推测）"),
    "周瑜": (175, 210, "周瑜生卒175–210"),
    "鲁肃": (172, 217, "鲁肃生卒约172–217"),
    "吕蒙": (178, 220, "吕蒙建安二十四年卒，生年约178"),
    "陆逊": (183, 245, "陆逊生卒183–245"),
    "司马懿": (179, 251, "司马懿生卒179–251"),
    "曹操": (155, 220, "曹操生卒155–220"),
    "刘备": (161, 223, "刘备生卒161–223"),
    "孙权": (182, 252, "孙权生卒182–252"),
    "曹丕": (187, 226, "魏文帝曹丕生卒187–226"),
    "曹叡": (205, 239, "魏明帝曹叡生卒约205–239"),
    "刘禅": (207, 271, "蜀后主刘禅生卒207–271"),
    "邓艾": (197, 264, "邓艾生卒约197–264"),
    "钟会": (225, 264, "钟会生卒225–264"),
    "姜维": (202, 264, "姜维生卒约202–264"),
    "庞统": (179, 214, "庞统生卒约179–214"),
    "法正": (176, 220, "法正生卒176–220"),
    "徐庶": (170, 232, "徐庶生卒约170–232（推测）"),
    "邓禹": (2, 58, "邓禹生卒2–58"),
    "马援": (-14, 49, "马援生卒前14–49"),
    "班超": (32, 102, "班超生卒32–102"),
    "班固": (32, 92, "班固生卒32–92"),
    "张衡": (78, 139, "张衡生卒78–139"),
    "蔡伦": (62, 121, "蔡伦生卒约62–121"),
    "张仲景": (150, 219, "张仲景生卒约150–219（推测）"),
    "华佗": (145, 208, "华佗生卒约145–208（推测）"),
    "董卓": (139, 192, "董卓生卒约139–192"),
}


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_list_or_entries(path: Path) -> tuple[Any, list[dict], str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw, raw, "list"
    if isinstance(raw, dict) and isinstance(raw.get("entries"), list):
        return raw, raw["entries"], "entries"
    raise SystemExit(f"不支持的索引格式: {path}")


def save_list_or_entries(path: Path, container: Any, entries: list[dict], mode: str) -> None:
    if mode == "list":
        atomic_write_json(path, entries)
        return
    container["entries"] = entries
    atomic_write_json(path, container)


def _vol_num(entry: dict) -> int | None:
    for p in entry.get("paragraphs") or []:
        src = str(p.get("source_file") or "")
        m = re.search(r"_(\d{3})_", src)
        if m:
            return int(m.group(1))
        vol = str(p.get("vol") or "").strip()
        if vol.isdigit():
            return int(vol)
    return None


def _work_id(entry: dict) -> str:
    for p in entry.get("paragraphs") or []:
        if p.get("work"):
            return str(p["work"])
    mother = str(entry.get("母本著作") or "")
    src = str(entry.get("主要史料出处") or "")
    for hint in (mother, src):
        if "后汉书" in hint:
            return "03后汉书"
        if "三国志" in hint:
            return "04三国志"
    return ""


def years_match_emperor_reign(entry: dict, ei: dict) -> bool:
    """人物起止年与四级帝王在位年完全一致 → 帝王在位冒充生卒。"""
    patron = str(entry.get("四级帝王坐标") or "").strip()
    info = ei.get(patron)
    if not info:
        return False
    sy, ey = entry.get("史略开始年"), entry.get("史略结束年")
    es, ee = info.get("start_year"), info.get("end_year")
    if not isinstance(sy, int) or not isinstance(ey, int):
        return False
    if es is None or ee is None:
        return False
    return sy == int(es) and ey == int(ee)


def is_poisoned(entry: dict, ei: dict) -> bool:
    if entry.get("二级朝代坐标") not in TARGET_DYNASTIES:
        return False
    if entry.get("史略来源") != "史料提取":
        return False
    cat = str(entry.get("史略分类") or "")
    if cat not in PERSON_CATS:
        return False
    if cat == "君王":
        return False

    sy, ey = entry.get("史略开始年"), entry.get("史略结束年")
    pair = (sy, ey) if isinstance(sy, int) and isinstance(ey, int) else None
    patron = str(entry.get("四级帝王坐标") or "").strip()
    af = entry.get("_auto_filled") or {}
    level = str(af.get("_年兜底级别") or "")

    if level in ("活跃期帝王在位", "朝代起始年"):
        return True
    if pair in POISON_YEAR_PAIRS:
        return True
    if patron in POISON_PATRONS_SANGUO and pair == (264, 280):
        return True
    if years_match_emperor_reign(entry, ei):
        return True
    # 峰值落在毒区间中点附近且起止为毒对
    if pair == (264, 280) and entry.get("峰值年") in (272, 274, 271, 273):
        return True
    return False


def infer_sanguo_patron(entry: dict, ei: dict) -> str:
    """强制重推三国挂靠：不信任现有吴乌程侯。"""
    from backfill_incomplete_entries import (  # noqa: WPS433
        _infer_patron_from_rules,
        _resolve_patron_name,
        PATRON_CANONICAL,
    )
    from emperor_resolve import pick_emperor_from_text  # noqa: WPS433

    rule = _infer_patron_from_rules(entry)
    if rule:
        resolved = _resolve_patron_name(rule, ei) or PATRON_CANONICAL.get(rule, rule)
        if resolved in ei and str(ei[resolved].get("dynasty") or "") == "三国":
            return resolved

    name = str(entry.get("史略名称") or "").strip()
    if name.startswith("曹"):
        return "曹操" if "曹操" in ei else "魏武帝"
    if name.startswith("孙"):
        return "吴大帝"
    if name.startswith("刘") and (_vol_num(entry) or 0) in range(31, 46):
        return "蜀昭烈帝"

    text = f"{entry.get('史略简介', '')} {entry.get('原文字句', '')}"
    info, _ = pick_emperor_from_text(text, ei, work_id="04三国志", dynasty_hint="三国")
    if info:
        p = str(info.get("emperor") or info.get("帝王名称") or "").strip()
        p = _resolve_patron_name(p, ei) or PATRON_CANONICAL.get(p, p)
        if p in ei and str(ei[p].get("dynasty") or "") == "三国" and p not in POISON_PATRONS_SANGUO:
            return p

    vol = _vol_num(entry)
    if vol is not None:
        if 31 <= vol <= 45:
            return "蜀昭烈帝"
        if 46 <= vol <= 65:
            return "吴大帝"
        if 1 <= vol <= 30:
            return "曹操"
    return "曹操"


def infer_donghan_patron(entry: dict, ei: dict, era_patrons: list) -> str:
    from backfill_incomplete_entries import _infer_donghan_patron  # noqa: WPS433

    return _infer_donghan_patron(entry, ei=ei, era_patrons=era_patrons) or "汉光武帝"


def apply_coords(entry: dict, patron: str, ei: dict, ri: dict) -> None:
    from backfill_incomplete_entries import (  # noqa: WPS433
        _apply_coords_from_patron,
        _sync_full_coords_from_patron,
        _resolve_patron_name,
    )

    resolved = _resolve_patron_name(patron, ei) or patron
    if resolved not in ei:
        return
    _apply_coords_from_patron(entry, resolved, ei, ri)
    _sync_full_coords_from_patron(entry, ei=ei, ri=ri)


def clear_years_and_peak(entry: dict) -> None:
    for k in YEAR_KEYS + PEAK_KEYS:
        entry.pop(k, None)
    af = dict(entry.get("_auto_filled") or {})
    for k in YEAR_AUTO_KEYS + PEAK_AUTO_KEYS:
        af.pop(k, None)
    entry["_auto_filled"] = af


def write_years(entry: dict, start: int, end: int, note: str, *, level: str = "llm") -> None:
    entry["史略开始年"] = int(start)
    entry["史略结束年"] = int(end)
    af = dict(entry.get("_auto_filled") or {})
    af["_年LLM依据"] = note
    af["_年兜底级别"] = level
    af.pop("_年待LLM", None)
    af.pop("_死亡年锚定", None)
    entry["_auto_filled"] = af


def apply_seed_or_keep(entry: dict) -> bool:
    name = str(entry.get("史略名称") or "").strip()
    seed = SEED_LIFESPANS.get(name)
    if not seed:
        return False
    # 董卓条目特殊：修正笔误
    start, end, note = seed
    if name == "董卓" and start < 0:
        start, end, note = 139, 192, "董卓生卒约139–192"
    write_years(entry, start, end, note, level="学界生卒表")
    return True


def _extract_json_array(text: str) -> list[dict]:
    text = (text or "").strip()
    if not text:
        return []
    # fenced
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if m:
        text = m.group(1)
    else:
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def llm_fill_years(
    entries: list[dict],
    *,
    batch_size: int = 12,
    on_batch_done: Optional[Callable[[], None]] = None,
) -> dict[str, int]:
    from llm.config import ensure_annotate_model, get_provider_name, PROVIDER_DEEPSEEK
    from llm.provider import run_agent_turn

    if get_provider_name() == PROVIDER_DEEPSEEK:
        ensure_annotate_model()

    stats = {"llm": 0, "failed": 0, "seed_skip": 0}
    pending = [e for e in entries if e.get("史略开始年") is None]
    stats["seed_skip"] = len(entries) - len(pending)

    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        payload = []
        for e in batch:
            payload.append(
                {
                    "史略ID": e.get("史略ID"),
                    "判定对象": e.get("史略名称"),
                    "史略分类": e.get("史略分类"),
                    "史略简介": e.get("史略简介"),
                    "二级朝代坐标": e.get("二级朝代坐标"),
                    "四级帝王坐标": e.get("四级帝王坐标"),
                    "主要史料出处": e.get("主要史料出处"),
                    "母本原文字句": (e.get("原文字句") or "")[:800],
                }
            )
        prompt = (
            "你是历史考订助手。为下列人物史略填写生卒年。\n"
            "硬约束：\n"
            "1. 史略开始年=出生年，史略结束年=去世年（公元整数，公元前为负）。\n"
            "2. 取史学界主流观点；生年不详可合理推测，卒年优先用史载。\n"
            "3. 禁止用挂靠帝王的在位年冒充人物生卒。\n"
            "4. 开始年必须 ≤ 结束年；人物生卒跨度通常 20～90 年。\n"
            "5. 只输出 JSON 数组，元素形如："
            '{"史略ID":"...","史略开始年":整数,"史略结束年":整数,"依据":"简述（须点名判定对象）"}\n'
            "不要输出数组以外的文字。\n\n"
            f"待判定条目：\n{json.dumps(payload, ensure_ascii=False)}"
        )
        sid = "yrs-" + hashlib.sha1(prompt.encode()).hexdigest()[:12]
        _log(f"  🤖 LLM 生卒 第 {i // batch_size + 1} 批 ({len(batch)} 条)")
        try:
            res = run_agent_turn(prompt, session_id=sid, timeout_sec=180, temperature=0)
            rows = _extract_json_array(str(res.get("result", "")))
        except Exception as exc:  # noqa: BLE001
            _log(f"     ⚠️ 生卒批失败: {exc}")
            stats["failed"] += len(batch)
            continue
        by_id = {str(r.get("史略ID", "")).strip(): r for r in rows if isinstance(r, dict)}
        for e in batch:
            eid = str(e.get("史略ID") or "")
            row = by_id.get(eid)
            if not row:
                stats["failed"] += 1
                continue
            try:
                sy = int(row["史略开始年"])
                ey = int(row["史略结束年"])
            except (KeyError, TypeError, ValueError):
                stats["failed"] += 1
                continue
            if sy > ey or ey - sy > 120 or ey - sy < 0:
                stats["failed"] += 1
                continue
            note = str(row.get("依据") or f"{e.get('史略名称')}生卒约{sy}–{ey}")
            write_years(e, sy, ey, note, level="llm")
            stats["llm"] += 1
        if on_batch_done:
            on_batch_done()
    return stats


def patch_v2(updated_by_id: dict[str, dict]) -> int:
    if not V2_INDEX.is_file():
        return 0
    container, entries, mode = load_list_or_entries(V2_INDEX)
    n = 0
    field_keys = (
        "四级帝王坐标",
        "三级政权坐标",
        "二级朝代坐标",
        "一级文明坐标",
        "文明ID",
        "朝代ID",
        "政权ID",
        "帝王ID",
        *YEAR_KEYS,
        *PEAK_KEYS,
        "_auto_filled",
    )
    for i, e in enumerate(entries):
        eid = str(e.get("史略ID") or "")
        src = updated_by_id.get(eid)
        if not src:
            continue
        changed = False
        for k in field_keys:
            if k == "_auto_filled":
                continue
            if src.get(k) != e.get(k):
                e[k] = deepcopy(src.get(k))
                changed = True
        src_af = src.get("_auto_filled") or {}
        if isinstance(src_af, dict):
            af = dict(e.get("_auto_filled") or {})
            af.update(src_af)
            # 清理毒元数据键若 src 已删
            for k in YEAR_AUTO_KEYS + PEAK_AUTO_KEYS:
                if k not in src_af and k in af:
                    af.pop(k, None)
            e["_auto_filled"] = af
            changed = True
        if changed:
            entries[i] = e
            n += 1
    if n:
        save_list_or_entries(V2_INDEX, container, entries, mode)
    return n


def sync_mysql() -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "import_box_index_json.py"),
        "--json",
        str(ONLINE),
        "--enrichment-only",
    ]
    _log(f"同步 MySQL: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="修复三国/东汉毒化生卒与峰值年")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-llm", action="store_true", help="只修挂靠+种子生卒，不调 LLM")
    parser.add_argument("--skip-peak", action="store_true")
    parser.add_argument("--sync-db", action="store_true")
    parser.add_argument("--online", type=Path, default=ONLINE)
    args = parser.parse_args()

    from coordinate_index import build_regime_index  # noqa: WPS433
    from emperor_resolve import build_emperor_info_index  # noqa: WPS433
    from backfill_incomplete_entries import _build_donghan_era_patron  # noqa: WPS433
    from emperor_year_align import load_emperor_rows  # noqa: WPS433

    ei = build_emperor_info_index()
    ri = build_regime_index()
    em_rows = load_emperor_rows(EMPEROR_JSON)
    era_patrons = _build_donghan_era_patron(em_rows)

    online_container, online, online_mode = load_list_or_entries(args.online)
    poisoned = [e for e in online if is_poisoned(e, ei)]
    if args.limit > 0:
        poisoned = poisoned[: args.limit]

    _log(f"毒条目: {len(poisoned)}")
    sg_n = sum(1 for e in poisoned if e.get("二级朝代坐标") == "三国")
    dh_n = sum(1 for e in poisoned if e.get("二级朝代坐标") == "东汉")
    _log(f"  三国 {sg_n} / 东汉 {dh_n}")

    report: dict[str, Any] = {
        "schema": "sg-dh-poisoned-years-repair/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "poisoned_before": len(poisoned),
        "samples": [],
        "patron_changes": [],
        "year_stats": {},
        "peak_stats": {},
        "v2_patched": 0,
        "still_poisoned": [],
    }

    for e in poisoned[:8]:
        report["samples"].append(
            {
                "id": e.get("史略ID"),
                "name": e.get("史略名称"),
                "dynasty": e.get("二级朝代坐标"),
                "patron": e.get("四级帝王坐标"),
                "years": [e.get("史略开始年"), e.get("史略结束年")],
                "peak": e.get("峰值年"),
            }
        )

    if args.dry_run:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORT_DIR / f"repair_dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        atomic_write_json(out, report)
        _log(f"dry-run 报告: {out}")
        for s in report["samples"]:
            _log(f"  样例 {s}")
        return 0

    # 1) 重挂 + 清毒
    for e in poisoned:
        old_patron = str(e.get("四级帝王坐标") or "")
        old_years = [e.get("史略开始年"), e.get("史略结束年")]
        dynasty = e.get("二级朝代坐标")
        if dynasty == "三国":
            # 现有挂靠若为毒模式或等于帝王在位年，强制重推
            need_repatron = (
                old_patron in POISON_PATRONS_SANGUO
                or years_match_emperor_reign(e, ei)
                or (old_years[0], old_years[1]) in POISON_YEAR_PAIRS
            )
            new_patron = infer_sanguo_patron(e, ei) if need_repatron else old_patron
            if not new_patron or new_patron in POISON_PATRONS_SANGUO:
                new_patron = infer_sanguo_patron(e, ei)
        else:
            need_repatron = years_match_emperor_reign(e, ei) or (
                (old_years[0], old_years[1]) in POISON_YEAR_PAIRS
            )
            new_patron = (
                infer_donghan_patron(e, ei, era_patrons) if need_repatron else old_patron
            )

        clear_years_and_peak(e)
        apply_coords(e, new_patron, ei, ri)
        if str(e.get("四级帝王坐标") or "") != old_patron:
            report["patron_changes"].append(
                {
                    "id": e.get("史略ID"),
                    "name": e.get("史略名称"),
                    "from": old_patron,
                    "to": e.get("四级帝王坐标"),
                }
            )
        apply_seed_or_keep(e)

    def _ckpt() -> None:
        save_list_or_entries(args.online, online_container, online, online_mode)

    _ckpt()
    _log(f"挂靠变更: {len(report['patron_changes'])}；种子生卒已写")

    # 2) LLM 生卒
    if not args.no_llm:
        year_stats = llm_fill_years(poisoned, on_batch_done=_ckpt)
        report["year_stats"] = year_stats
        _log(f"生卒 stats: {year_stats}")
        _ckpt()
    else:
        report["year_stats"] = {"skipped": "no-llm"}

    # 仍无年的：不得再用帝王在位兜底；标待审
    still_no_year = []
    for e in poisoned:
        if e.get("史略开始年") is None or e.get("史略结束年") is None:
            still_no_year.append(e.get("史略ID"))
            af = dict(e.get("_auto_filled") or {})
            af["_年待LLM"] = "毒年已清，LLM/种子未产出生卒"
            e["_auto_filled"] = af
    if still_no_year:
        _log(f"⚠️ 仍无生卒: {len(still_no_year)}")
    report["still_no_year"] = still_no_year

    # 3) 重算峰值（仅有完整生卒者）
    peak_targets = [
        e
        for e in poisoned
        if isinstance(e.get("史略开始年"), int) and isinstance(e.get("史略结束年"), int)
    ]
    if not args.no_llm and not args.skip_peak and peak_targets:
        from peak_year import annotate as annotate_peak  # noqa: WPS433

        _log(f"🤖 峰值年 LLM（{len(peak_targets)} 条）…")
        peak_stats = annotate_peak(
            peak_targets,
            use_llm=True,
            force=True,
            batch_size=20,
            on_batch_done=_ckpt,
        )
        report["peak_stats"] = peak_stats
        _log(f"peak stats: {peak_stats}")
        _ckpt()
    else:
        report["peak_stats"] = {"skipped": True}

    # 4) 回写 V2
    updated = {str(e["史略ID"]): e for e in poisoned}
    n_v2 = patch_v2(updated)
    report["v2_patched"] = n_v2
    _log(f"回写 V2: {n_v2}")

    # 5) 验收
    still = [e for e in online if is_poisoned(e, ei)]
    report["still_poisoned"] = [
        {"id": e.get("史略ID"), "name": e.get("史略名称"), "years": [e.get("史略开始年"), e.get("史略结束年")], "patron": e.get("四级帝王坐标")}
        for e in still[:50]
    ]
    _log(f"修复后仍毒: {len(still)}")

    # 关键样例
    for name in ("诸葛亮", "关羽", "周瑜", "邓禹", "班超"):
        e = next((x for x in online if x.get("史略名称") == name and x.get("史略来源") == "史料提取"), None)
        if e:
            _log(
                f"  ✓ {name}: {e.get('四级帝王坐标')} "
                f"{e.get('史略开始年')}–{e.get('史略结束年')} peak={e.get('峰值年')}"
            )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"repair_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    atomic_write_json(out, report)
    _log(f"✅ 报告: {out}")

    if args.sync_db:
        sync_mysql()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
