"""Step4 主轴说明专写 LLM（小 prompt，避免整卷 skeleton JSON 被截断）。"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from llm.artifacts import extract_json_objects
from llm.config import ensure_annotate_model, get_provider_name, PROVIDER_DEEPSEEK
from llm.provider import run_agent_turn

from lib import events

FORBIDDEN_TEMPLATE = ("主要功业/仕宦事", "本卷以", "为最著")


def spindle_only_missing(entries: list) -> bool:
    """是否仅缺 _坐标主轴说明（其余正式字段已齐，且人物年份已有考订依据）。"""
    if not entries:
        return False
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "historiography-annotate"))
    from hanshu_step4_hardening import any_entry_missing_year_basis  # noqa: E402

    if any_entry_missing_year_basis(entries):
        return False
    for entry in entries:
        needs = entry.get("_needs_llm") or []
        if not needs:
            continue
        if needs != ["_坐标主轴说明"]:
            return False
        formal = (
            "优先级",
            "优先级判定理由",
            "史略开始年",
            "史略结束年",
            "四级帝王坐标",
        )
        for field in formal:
            val = entry.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                return False
    return any(entry.get("_needs_llm") for entry in entries)


def build_spindle_prompt(volume_name: str, entries: list) -> str:
    lines = [
        "你是《汉书》人物坐标考订员。",
        f"本卷《{volume_name}》条目四级帝王坐标已定，",
        "现仅需补写跨时期人物的 `_坐标主轴说明`。",
        "",
        "任务：为下列人物各写 1～2 句 `_坐标主轴说明`（≥30 字史实句），",
        "说明为何四级帝王取所选帝王（据本传主政/仕宦/封侯/军功等史实）。",
        "禁止模板句「本卷以…主要功业/仕宦事…为最著」。",
        "",
        "输出**单个** ```json 数组```，每项仅含：",
        '- `"史略ID"`（必须与下表完全一致）',
        '- `"_坐标主轴说明"`',
        "",
        "人物清单：",
    ]
    for entry in entries:
        needs = entry.get("_needs_llm") or []
        if "_坐标主轴说明" not in needs:
            continue
        af = entry.get("_auto_filled") or {}
        hint = (af.get("_坐标主轴待说明") or "").strip()
        lines.append(
            f"- {entry.get('史略ID')} {entry.get('史略名称')} | "
            f"四级={entry.get('四级帝王坐标')} | "
            f"原文首句={str(entry.get('原文字句') or '')[:40]}…"
        )
        if hint:
            lines.append(f"  提示：{hint[:120]}")
    lines.append("")
    lines.append("禁止输出完整 skeleton；只输出上述 JSON 数组。")
    return "\n".join(lines)


def parse_spindle_array(content: str, expected_ids: Set[str]) -> Dict[str, str]:
    objects = extract_json_objects(content)
    items: Optional[List[dict]] = None
    for obj in objects:
        if isinstance(obj, list) and obj:
            items = obj
            break
        if isinstance(obj, dict) and isinstance(obj.get("items"), list):
            items = obj["items"]
            break
    if not items:
        raise ValueError("LLM 未返回 JSON 数组（须含 史略ID + _坐标主轴说明）")

    out: Dict[str, str] = {}
    for row in items:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("史略ID") or "").strip()
        text = str(row.get("_坐标主轴说明") or "").strip()
        if eid and text:
            out[eid] = text

    missing = expected_ids - set(out)
    if missing:
        raise ValueError(f"主轴说明缺条目: {sorted(missing)}")
    for eid, text in out.items():
        if len(text) < 8:
            raise ValueError(f"{eid} 主轴说明过短")
        if any(m in text for m in FORBIDDEN_TEMPLATE):
            raise ValueError(f"{eid} 含禁止模板句")
    return out


def merge_spindle_rationales(sk_path: Path, rationales: Dict[str, str]) -> None:
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    new_entries = []
    for entry in data.get("entries") or []:
        eid = entry.get("史略ID")
        if eid not in rationales:
            new_entries.append(entry)
            continue
        af = dict(entry.get("_auto_filled") or {})
        af = {**af, "_坐标主轴说明": rationales[eid]}
        needs = [n for n in (entry.get("_needs_llm") or []) if n != "_坐标主轴说明"]
        new_entry = {**entry, "_auto_filled": af}
        if needs:
            new_entry["_needs_llm"] = needs
        else:
            new_entry.pop("_needs_llm", None)
        new_entries.append(new_entry)
    data = {**data, "entries": new_entries}
    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_spindle_llm_supplement(
    work: str,
    vol: str,
    sk_path: Path,
    *,
    session_id: str,
    timeout_sec: int = 300,
    max_attempts: int = 3,
) -> Dict[str, str]:
    """专写主轴说明并合并到 skeleton；返回 rationales。"""
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    need_entries = [
        e for e in entries if "_坐标主轴说明" in (e.get("_needs_llm") or [])
    ]
    if not need_entries:
        raise ValueError("无待补 _坐标主轴说明 条目")

    expected_ids = {e.get("史略ID") for e in need_entries}
    volume_name = (data.get("volume") or "").strip() or f"卷{vol}"
    prompt = build_spindle_prompt(volume_name, need_entries)

    last_err = ""
    for attempt in range(1, max_attempts + 1):
        if get_provider_name() == PROVIDER_DEEPSEEK:
            ensure_annotate_model()
        events.log(
            "llm_start",
            work=work,
            vol=vol,
            step="4",
            session_id=f"{session_id}-spindle-a{attempt}",
            mode="spindle_only",
        )
        t0 = time.time()
        result = run_agent_turn(
            prompt,
            session_id=f"{session_id}-spindle-a{attempt}",
            timeout_sec=timeout_sec,
        )
        elapsed = time.time() - t0
        content = str(result.get("result") or "")
        events.log(
            "llm_end",
            work=work,
            vol=vol,
            step="4",
            elapsed_sec=round(elapsed, 1),
            mode="spindle_only",
            attempt=attempt,
        )
        try:
            rationales = parse_spindle_array(content, expected_ids)
            merge_spindle_rationales(sk_path, rationales)
            events.log(
                "step4_spindle_written",
                work=work,
                vol=vol,
                count=len(rationales),
                attempt=attempt,
            )
            return rationales
        except ValueError as exc:
            last_err = str(exc)

    raise RuntimeError(f"主轴说明 LLM 未通过（{max_attempts} 次）: {last_err}")
