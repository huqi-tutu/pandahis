#!/usr/bin/env python3
"""朝代全局优先级标注：按朝代ID分批 LLM 横向定级 P0–P3，覆盖 优先级/优先级判定理由。

用法：
  python3 dynasty_priority.py <index.json> --llm --dry-run
  python3 dynasty_priority.py <index.json> --llm --dynasty-id CD_HX_XIHAN
  python3 dynasty_priority.py <index.json> --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent
PKG_ROOT = SKILL_DIR.parent
for _p in (str(SKILL_DIR), str(PKG_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib_config import VALID_PRIORITIES, coerce_year  # noqa: E402
from category_v3 import normalize_entry_category  # noqa: E402

PRI = "优先级"
PRI_REASON = "优先级判定理由"
META_FP = "_优先级指纹"
META_LOCK = "_优先级人工锁定"
META_GLOBAL = "_优先级朝代全局"
META_REVIEW = "_优先级待审"

CATEGORY_ORDER = {
    "君王": 0,
    "武将": 1,
    "文臣": 2,
    "宗戚": 3,
    "宦官": 4,
    "蕃祚": 5,
    "庶众": 6,
    "士臣": 2,
}

RULES_BRIEF = (
    "在同一朝代内按史略主题的历史/政治/军事/文化影响力横向比较定 P0–P3。"
    "P0=朝代核心（开国君、盛世之主、顶级将相、改变格局的政权/事件）；"
    "P1=重要配角/名将名臣二级；P2=有传但非主流；P3=边缘一笔带过。"
    "君王不自动 P0；蕃祚按政权分量；理由须点名判定主题。"
)


def _log(msg: str) -> None:
    print(msg, flush=True)


def _auto(entry: dict) -> dict:
    auto = entry.get("_auto_filled")
    if not isinstance(auto, dict):
        auto = {}
        entry["_auto_filled"] = auto
    return auto


def entry_fingerprint(entry: dict) -> str:
    basis = "|".join(
        str(entry.get(k, ""))
        for k in (
            "史略ID",
            "史略名称",
            "史略分类",
            "史略简介",
            "史略开始年",
            "史略结束年",
            "峰值年",
            "朝代ID",
        )
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def is_locked(entry: dict) -> bool:
    return bool((entry.get("_auto_filled") or {}).get(META_LOCK))


def is_fresh(entry: dict) -> bool:
    auto = entry.get("_auto_filled") or {}
    pri = (entry.get(PRI) or "").strip()
    return (
        pri in VALID_PRIORITIES
        and auto.get(META_GLOBAL) is True
        and auto.get(META_FP) == entry_fingerprint(entry)
    )


def dynasty_p0_cap(total: int) -> int:
    if total <= 6:
        return max(1, (total + 1) // 3)
    if total <= 25:
        return max(2, total // 5)
    return max(8, min(30, round(total * 0.09)))


def _name_in_text(name: str, text: str) -> bool:
    name = (name or "").strip()
    text = (text or "").strip()
    if not name or not text:
        return False
    if name in text:
        return True
    return len(name) >= 2 and name[-2:] in text and len(name) <= 4


def write_priority(entry: dict, pri: str, reason: str) -> None:
    if is_locked(entry):
        return
    pri = (pri or "").strip().upper()
    if pri not in VALID_PRIORITIES:
        return
    entry[PRI] = pri
    entry[PRI_REASON] = (reason or "").strip() or "（待补理由）"
    auto = _auto(entry)
    auto[META_GLOBAL] = True
    auto[META_FP] = entry_fingerprint(entry)
    auto.pop(META_REVIEW, None)


def apply_post_checks(entry: dict) -> List[str]:
    notes: List[str] = []
    name = (entry.get("史略名称") or "").strip()
    reason = (entry.get(PRI_REASON) or "").strip()
    if name and reason and not _name_in_text(name, reason):
        notes.append(f"优先级理由未点名({name})")
        auto = _auto(entry)
        prev = (auto.get(META_REVIEW) or "").strip()
        auto[META_REVIEW] = "；".join(x for x in [prev, notes[-1]] if x)
    return notes


def enforce_p0_cap(entries: List[dict], cap: int) -> int:
    """超出 P0 配额时，按文臣/庶众优先降级（保留君王武将）。"""
    p0s = [e for e in entries if (e.get(PRI) or "") == "P0"]
    if len(p0s) <= cap:
        return 0
    demote_rank = {"庶众": 0, "文臣": 1, "士臣": 1, "宗戚": 2, "宦官": 3, "蕃祚": 4, "武将": 5, "君王": 6}

    def sort_key(e: dict) -> Tuple[int, str]:
        cat = normalize_entry_category(e.get("史略分类", ""))
        return (demote_rank.get(cat, 3), e.get("史略名称", ""))

    overflow = sorted(p0s, key=sort_key)
    n_demote = len(p0s) - cap
    for e in overflow[:n_demote]:
        if is_locked(e):
            continue
        e[PRI] = "P1"
        e[PRI_REASON] = (e.get(PRI_REASON) or "") + "（P0超配额降为P1）"
        auto = _auto(e)
        auto[META_REVIEW] = "P0超朝代配额"
    return n_demote


def build_llm_input(entry: dict) -> dict:
    name = (entry.get("史略名称") or "").strip()
    payload = {
        "史略ID": entry.get("史略ID"),
        "判定主题": name,
        "史略分类": normalize_entry_category(entry.get("史略分类", "")),
        "史略简介": entry.get("史略简介"),
        "史略开始年": entry.get("史略开始年"),
        "史略结束年": entry.get("史略结束年"),
        "峰值年": entry.get("峰值年"),
        "峰值原因": (entry.get("峰值原因") or "")[:80],
        "主要史料出处": entry.get("主要史料出处"),
    }
    return {k: v for k, v in payload.items() if v not in (None, "")}


def build_prompt(
    dynasty_name: str,
    dynasty_id: str,
    batch: List[dict],
    *,
    p0_cap: int,
    p0_assigned: List[dict],
    batch_index: int,
    total_batches: int,
) -> str:
    p0_names = [e.get("史略名称") for e in p0_assigned[:40]]
    lines = [
        f"你是历史图谱编辑。为「{dynasty_name}」（{dynasty_id}）内下列史略主题判定**朝代全局优先级** P0–P3。",
        "【主体锁定】每条只判「判定主题」（=史略名称）本人或该政权/事件本身，勿与卷内他人混淆。",
        RULES_BRIEF,
        f"本朝共 {len(p0_assigned) + len(batch)} 条量级；按影响力独立定级，不受 P0 名额限制。",
        f"已标 P0 示例：{', '.join(p0_names) if p0_names else '（尚无）'}",
        f"本批为第 {batch_index}/{total_batches} 批；须与已标 P0 保持尺度一致。",
        "",
        "只输出 JSON 数组，元素："
        '{"史略ID":"...","优先级":"P0|P1|P2|P3","优先级判定理由":"须点名判定主题"}',
        "",
        "待判定：",
    ]
    for e in batch:
        lines.append(json.dumps(build_llm_input(e), ensure_ascii=False))
    return "\n".join(lines)


def _extract_json_array(text: str) -> List[dict]:
    if not text:
        return []
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("["), text.rfind("]")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _sort_dynasty_entries(entries: List[dict]) -> List[dict]:
    def key(e: dict) -> Tuple[int, int, str]:
        cat = normalize_entry_category(e.get("史略分类", ""))
        py = coerce_year(e.get("峰值年"))
        year_key = py if py is not None else 0
        return (CATEGORY_ORDER.get(cat, 9), year_key, e.get("史略名称", ""))

    return sorted(entries, key=key)


def _chunk(items: List[dict], size: int) -> List[List[dict]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def run_dynasty_llm(
    dynasty_name: str,
    dynasty_id: str,
    entries: List[dict],
    *,
    batch_size: int = 20,
    timeout_sec: int = 180,
    on_batch_done: Optional[Callable[[], None]] = None,
) -> Dict[str, int]:
    from llm.config import ensure_annotate_model, get_provider_name, PROVIDER_DEEPSEEK  # noqa: E402
    from llm.provider import run_agent_turn  # noqa: E402

    if get_provider_name() == PROVIDER_DEEPSEEK:
        ensure_annotate_model()
    stats = {"llm": 0, "fallback": 0, "flagged": 0}
    ordered = _sort_dynasty_entries(entries)
    batches = _chunk(ordered, batch_size if len(ordered) > 35 else len(ordered))
    p0_assigned: List[dict] = []

    for bi, batch in enumerate(batches, start=1):
        prompt = build_prompt(
            dynasty_name,
            dynasty_id,
            batch,
            p0_cap=0,
            p0_assigned=p0_assigned,
            batch_index=bi,
            total_batches=len(batches),
        )
        sid = "dpri-" + hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
        _log(f"  🤖 [{dynasty_name}] 第 {bi}/{len(batches)} 批 ({len(batch)} 条) P0={len(p0_assigned)}")
        try:
            res = run_agent_turn(prompt, session_id=sid, timeout_sec=timeout_sec, temperature=0)
            rows = _extract_json_array(str(res.get("result", "")))
        except Exception as exc:  # noqa: BLE001
            _log(f"     ⚠️ LLM 失败，本批改 P2: {exc}")
            rows = []

        by_id = {str(r.get("史略ID", "")).strip(): r for r in rows if r.get("史略ID")}
        for e in batch:
            rid = str(e.get("史略ID", "")).strip()
            row = by_id.get(rid)
            pri = (str(row.get(PRI, "")).strip().upper() if row else "") or "P2"
            reason = str(row.get(PRI_REASON, "")) if row else f"{e.get('史略名称')}在{dynasty_name}属一般记载，暂列P2"
            if pri not in VALID_PRIORITIES:
                pri = "P2"
                stats["fallback"] += 1
            else:
                stats["llm"] += 1
            write_priority(e, pri, reason)
            if apply_post_checks(e):
                stats["flagged"] += 1
            if pri == "P0":
                p0_assigned.append(e)
        if on_batch_done:
            on_batch_done()

    return stats


def group_by_dynasty(entries: List[dict]) -> Dict[str, List[dict]]:
    groups: Dict[str, List[dict]] = {}
    for e in entries:
        did = (e.get("朝代ID") or "").strip() or "UNKNOWN"
        groups.setdefault(did, []).append(e)
    return groups


def dynasty_display_name(entries: List[dict]) -> str:
    for e in entries:
        name = (e.get("二级朝代坐标") or "").strip()
        if name:
            return name
    return entries[0].get("朝代ID", "未知朝代") if entries else "未知朝代"


def annotate(
    entries: List[dict],
    *,
    use_llm: bool = False,
    force: bool = False,
    dynasty_id: Optional[str] = None,
    batch_size: int = 20,
    on_batch_done: Optional[Callable[[], None]] = None,
) -> Dict[str, int]:
    groups = group_by_dynasty(entries)
    if dynasty_id:
        groups = {k: v for k, v in groups.items() if k == dynasty_id}

    stats = {
        "dynasties": 0,
        "entries": 0,
        "skipped_fresh": 0,
        "skipped_locked": 0,
        "llm": 0,
        "fallback": 0,
        "flagged": 0,
    }

    for did in sorted(groups.keys()):
        group = groups[did]
        work: List[dict] = []
        for e in group:
            if is_locked(e):
                stats["skipped_locked"] += 1
                continue
            if not force and is_fresh(e):
                stats["skipped_fresh"] += 1
                continue
            work.append(e)
        if not work:
            continue
        stats["dynasties"] += 1
        stats["entries"] += len(work)
        dname = dynasty_display_name(work)
        if use_llm:
            ds = run_dynasty_llm(
                dname,
                did,
                work,
                batch_size=batch_size,
                on_batch_done=on_batch_done,
            )
            stats["llm"] += ds["llm"]
            stats["fallback"] += ds["fallback"]
            stats["flagged"] += ds["flagged"]
        else:
            for e in work:
                write_priority(e, "P2", f"{e.get('史略名称')}在{dname}属一般记载（未启用LLM）")

    return stats


def verify_entries(entries: List[dict]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    for e in entries:
        eid = e.get("史略ID", "?")
        name = e.get("史略名称", "?")
        pri = (e.get(PRI) or "").strip()
        if pri not in VALID_PRIORITIES:
            issues.append(f"[{eid}] {name} 非法优先级: {pri}")
        if not (e.get(PRI_REASON) or "").strip():
            issues.append(f"[{eid}] {name} 缺少优先级判定理由")
    return len(issues) == 0, issues


def _load(path: Path) -> Tuple[dict, List[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise SystemExit("JSON 顶层须含 entries 数组")
    return data, entries


def main() -> int:
    ap = argparse.ArgumentParser(description="朝代全局优先级 P0–P3")
    ap.add_argument("json_path", type=Path)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dynasty-id", default=None)
    ap.add_argument("--batch-size", type=int, default=20)
    args = ap.parse_args()

    if not args.json_path.is_file():
        _log(f"❌ 文件不存在: {args.json_path}")
        return 1

    data, all_entries = _load(args.json_path)

    if args.verify:
        ok, issues = verify_entries(all_entries)
        if not ok:
            _log(f"❌ 校验失败（{len(issues)} 项）")
            for line in issues[:30]:
                _log(f"  - {line}")
            return 1
        _log(f"✅ 优先级校验通过（{len(all_entries)} 条）")
        return 0

    work_groups = group_by_dynasty(all_entries)
    if args.dynasty_id:
        work_groups = {k: v for k, v in work_groups.items() if k == args.dynasty_id}
        _log(f"  朝代过滤 {args.dynasty_id}: {sum(len(v) for v in work_groups.values())} 条")

    def checkpoint() -> None:
        data["entries"] = all_entries
        args.json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    stats = annotate(
        all_entries,
        use_llm=args.llm,
        force=args.force,
        dynasty_id=args.dynasty_id,
        batch_size=args.batch_size,
        on_batch_done=checkpoint if args.llm else None,
    )
    _log("📊 朝代优先级: " + " ".join(f"{k}={v}" for k, v in stats.items()))

    if args.dry_run:
        _log("（dry-run：未写回）")
        return 0

    checkpoint()
    _log(f"✅ 已写回: {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
