#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线上史略索引：逐条 LLM 重判优先级（仅改 优先级 / 优先级判定理由）。

用法：
  python3 scripts/rejudge_online_priorities.py --limit 3          # 试跑 3 条
  python3 scripts/rejudge_online_priorities.py                    # 全量 897 条（断点续跑）
  python3 scripts/rejudge_online_priorities.py --sync-db          # 完成后同步 MySQL
  python3 scripts/rejudge_online_priorities.py --force            # 忽略 checkpoint 重跑
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "openclaw-historiography"
ANNOTATE = TOOLS / "historiography-annotate"
DEFAULT_JSON = ROOT / "data" / "12线上史略索引" / "史略索引_online.json"
CHECKPOINT_DIR = ROOT / "data" / "05工作流中间产物" / "优先级重判"
CHECKPOINT_FILE = CHECKPOINT_DIR / "online_priority_rejudge_checkpoint.json"
RULES_FILE = ANNOTATE / "reference" / "朝代优先级规则.md"
LOG_FILE = CHECKPOINT_DIR / "online_priority_rejudge.log"

PRI = "优先级"
PRI_REASON = "优先级判定理由"
VALID_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
MAX_RETRIES = 2
SAVE_EVERY = 10

for _p in (str(TOOLS), str(ANNOTATE)):
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


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_entries(path: Path) -> List[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"期望顶层 JSON 数组: {path}")
    return data


def normalize_category(raw: str) -> str:
    from category_v3 import normalize_entry_category  # noqa: WPS433

    return normalize_entry_category(raw or "")


def build_target_payload(entry: dict) -> dict:
    name = (entry.get("史略名称") or "").strip()
    payload = {
        "史略ID": entry.get("史略ID"),
        "判定主题": name,
        "史略分类": normalize_category(entry.get("史略分类", "")),
        "史略简介": entry.get("史略简介"),
        "史略开始年": entry.get("史略开始年"),
        "史略结束年": entry.get("史略结束年"),
        "峰值年": entry.get("峰值年"),
        "峰值原因": (entry.get("峰值原因") or "")[:120],
        "主要史料出处": entry.get("主要史料出处"),
        "人物标签": entry.get("人物标签"),
    }
    return {k: v for k, v in payload.items() if v not in (None, "")}


def build_roster_line(entry: dict) -> str:
    name = (entry.get("史略名称") or "").strip()
    cat = normalize_category(entry.get("史略分类", ""))
    brief = (entry.get("史略简介") or "")[:48].replace("\n", " ")
    rid = entry.get("史略ID", "")
    return f"{rid}|{name}|{cat}|{brief}"


def dynasty_display_name(entries: List[dict]) -> str:
    for e in entries:
        name = (e.get("二级朝代坐标") or "").strip()
        if name:
            return name
    return entries[0].get("朝代ID", "未知朝代") if entries else "未知朝代"


def group_by_dynasty(entries: List[dict]) -> Dict[str, List[dict]]:
    groups: Dict[str, List[dict]] = {}
    for e in entries:
        did = (e.get("朝代ID") or "").strip() or "UNKNOWN"
        groups.setdefault(did, []).append(e)
    return groups


def load_rules_text() -> str:
    if RULES_FILE.is_file():
        return RULES_FILE.read_text(encoding="utf-8").strip()
    return (
        "在同一朝代内按史略主题的历史/政治/军事/文化影响力横向比较定 P0–P3。"
        "P0=朝代核心；P1=重要配角；P2=有传但非主流；P3=边缘。"
        "君王不自动 P0；有独立叙事块不等于 P0；理由须点名判定主题。"
    )


def build_prompt(
    target: dict,
    dynasty_name: str,
    dynasty_id: str,
    dynasty_entries: List[dict],
    rules_text: str,
) -> str:
    roster = [build_roster_line(e) for e in dynasty_entries]
    target_json = json.dumps(build_target_payload(target), ensure_ascii=False)
    lines = [
        "你是历史图谱编辑。请为下列**单条**史略主题判定**朝代全局优先级** P0–P3。",
        "",
        "【判定规则】",
        rules_text,
        "",
        "【硬性要求】",
        "1. 必须在同一朝代内与同朝全部条目横向比较后定级，不是卷内主轴权重。",
        "2. 「有独立叙事块/专传/段落多」≠ 自动 P0；边缘诸侯、世系链、工具性人物多为 P2/P3。",
        "3. 君王不自动 P0；仅开国、盛世、重大转折君主或顶级将相/event 可为 P0。",
        "4. 不设 P0 数量上限，完全按历史影响力定性。",
        "5. 优先级判定理由须点名「判定主题」（=史略名称）。",
        "",
        f"【朝代】{dynasty_name}（{dynasty_id}），共 {len(dynasty_entries)} 条",
        "",
        "【同朝条目清单（横向比较参照，格式：史略ID|名称|分类|简介摘要）】",
        *roster,
        "",
        "【待判定条目（只判这一条）】",
        target_json,
        "",
        "只输出一个 JSON 对象，不要 markdown，不要数组：",
        '{"史略ID":"...","优先级":"P0|P1|P2|P3","优先级判定理由":"须点名判定主题"}',
    ]
    return "\n".join(lines)


def _extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("{"), text.rfind("}")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def call_llm_once(
    prompt: str,
    *,
    entry_id: str,
    timeout_sec: int = 120,
) -> Tuple[Optional[str], Optional[str], str]:
    from llm.config import ensure_annotate_model, get_provider_name, PROVIDER_DEEPSEEK  # noqa: WPS433
    from llm.provider import run_agent_turn  # noqa: WPS433

    if get_provider_name() == PROVIDER_DEEPSEEK:
        ensure_annotate_model()

    sid = "opri-" + hashlib.sha1(f"{entry_id}:{prompt[:200]}".encode()).hexdigest()[:12]
    res = run_agent_turn(prompt, session_id=sid, timeout_sec=timeout_sec, temperature=0)
    raw = str(res.get("result", "") or "")
    row = _extract_json_object(raw)
    if not row:
        return None, None, f"无法解析 JSON: {raw[:200]}"
    pri = (str(row.get(PRI, "")).strip().upper())
    reason = str(row.get(PRI_REASON, "")).strip()
    if pri not in VALID_PRIORITIES:
        return None, None, f"非法优先级 {pri!r}"
    if not reason:
        return None, None, "缺少优先级判定理由"
    return pri, reason, ""


def judge_entry(
    entry: dict,
    dynasty_name: str,
    dynasty_id: str,
    dynasty_entries: List[dict],
    rules_text: str,
    *,
    timeout_sec: int,
) -> Tuple[bool, Optional[str], Optional[str], str]:
    prompt = build_prompt(entry, dynasty_name, dynasty_id, dynasty_entries, rules_text)
    entry_id = str(entry.get("史略ID", "")).strip()
    last_err = ""
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            pri, reason, err = call_llm_once(prompt, entry_id=entry_id, timeout_sec=timeout_sec)
            if pri and reason:
                return True, pri, reason, ""
            last_err = err or "未知错误"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
        if attempt <= MAX_RETRIES:
            _log(f"  ↻ 重试 {entry_id} 第 {attempt}/{MAX_RETRIES}: {last_err}")
            time.sleep(2 * attempt)
    return False, None, None, last_err


def load_checkpoint() -> dict:
    if not CHECKPOINT_FILE.is_file():
        return {"completed": {}, "failed": []}
    return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))


def save_checkpoint(state: dict) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(CHECKPOINT_FILE, state)


def apply_priority(entry: dict, pri: str, reason: str) -> None:
    entry[PRI] = pri
    entry[PRI_REASON] = reason


def sync_mysql(json_path: Path) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "import_box_index_json.py"),
        "--json",
        str(json_path),
        "--enrichment-only",
    ]
    _log(f"同步 MySQL: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="线上史略逐条 LLM 重判优先级")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 条（0=全部）")
    parser.add_argument("--force", action="store_true", help="忽略 checkpoint 全部重跑")
    parser.add_argument("--sync-db", action="store_true", help="完成后 import_box_index_json")
    parser.add_argument("--timeout", type=int, default=120, help="单次 LLM 超时秒数")
    args = parser.parse_args()

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    all_entries = load_entries(args.json)
    all_entries.sort(key=lambda e: str(e.get("史略ID", "")))

    work_entries = all_entries[: args.limit] if args.limit > 0 else all_entries
    if len(all_entries) < 800:
        _log(f"⚠️ 索引仅 {len(all_entries)} 条，若曾误 truncate 请先 build_online_index.py")

    groups = group_by_dynasty(all_entries)
    rules_text = load_rules_text()
    checkpoint = {"completed": {}, "failed": []} if args.force else load_checkpoint()
    completed: Dict[str, dict] = checkpoint.setdefault("completed", {})
    failed: List[dict] = checkpoint.setdefault("failed", [])

    total = len(work_entries)
    stats = {"ok": 0, "skipped": 0, "failed": 0, "llm_calls": 0}

    _log(f"开始重判 {total} 条 | checkpoint 已完成 {len(completed)} | force={args.force}")

    for idx, entry in enumerate(work_entries, start=1):
        entry_id = str(entry.get("史略ID", "")).strip()
        if not entry_id:
            continue

        if not args.force and entry_id in completed:
            row = completed[entry_id]
            apply_priority(entry, row[PRI], row[PRI_REASON])
            stats["skipped"] += 1
            if idx % 50 == 0 or idx == total:
                _log(f"  … 进度 {idx}/{total}（跳过已完成的 {entry_id}）")
            continue

        did = (entry.get("朝代ID") or "").strip() or "UNKNOWN"
        group = groups.get(did, [entry])
        dynasty_name = dynasty_display_name(group)

        name = entry.get("史略名称", entry_id)
        _log(f"[{idx}/{total}] 🤖 {entry_id} {name} ({dynasty_name})")

        ok, pri, reason, err = judge_entry(
            entry,
            dynasty_name,
            did,
            group,
            rules_text,
            timeout_sec=args.timeout,
        )
        stats["llm_calls"] += 1

        if ok and pri and reason:
            apply_priority(entry, pri, reason)
            completed[entry_id] = {PRI: pri, PRI_REASON: reason}
            stats["ok"] += 1
            _log(f"  ✓ {pri} | {reason[:80]}")
            failed = [f for f in failed if f.get("史略ID") != entry_id]
        else:
            stats["failed"] += 1
            failed = [f for f in failed if f.get("史略ID") != entry_id]
            failed.append({"史略ID": entry_id, "史略名称": name, "error": err})
            _log(f"  ✗ 保留原值 | {err}")

        if idx % SAVE_EVERY == 0 or idx == total:
            save_checkpoint(checkpoint)
            atomic_write_json(args.json, all_entries)
            _log(f"  💾 已落盘 ({idx}/{total}) ok={stats['ok']} skip={stats['skipped']} fail={stats['failed']}")

    save_checkpoint(checkpoint)
    atomic_write_json(args.json, all_entries)

    _log(
        f"完成 | LLM 调用 {stats['llm_calls']} | 成功 {stats['ok']} | "
        f"跳过 {stats['skipped']} | 失败 {stats['failed']}"
    )
    if failed:
        fail_path = CHECKPOINT_DIR / "online_priority_rejudge_failed.json"
        atomic_write_json(fail_path, failed)
        _log(f"失败清单: {fail_path}")

    if args.sync_db:
        if len(all_entries) < 800:
            raise SystemExit(f"拒绝 sync-db：索引仅 {len(all_entries)} 条，请先恢复全量索引")
        sync_mysql(args.json)


if __name__ == "__main__":
    main()
