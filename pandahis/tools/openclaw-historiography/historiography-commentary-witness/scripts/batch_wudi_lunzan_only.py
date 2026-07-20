#!/usr/bin/env python3
"""五帝评述：只补 1 条二十四史论赞（论赞必收；不占「再补5条」额度，合计≤6）。"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import cw_lib as cw  # noqa: E402
from verify_cw import verify_file  # noqa: E402

DYNASTY = "五帝"


def _lunzan_prompt(entry: dict, existing: list[dict]) -> str:
    rules = cw.read_rule("commentary")
    eid = str(entry.get("史略ID", "")).strip()
    name = str(entry.get("史略名称", "")).strip()
    dynasty = str(entry.get("二级朝代坐标") or "").strip()
    cat = str(entry.get("史略分类") or "").strip()
    existing_titles = [
        f"- {r.get('评述标题')}｜{r.get('评述人')}｜{r.get('评述著作')}"
        for r in existing
    ]
    n_other = len(existing)
    strategy_note = (
        f"当前已有 {n_other} 条其他评述。"
        f"条数规则：论赞必收 1 条 + 最多再保留 {cw.MAX_OTHER_COMMENTARY} 条其他"
        f"（合计 ≤{cw.MAX_COMMENTARY_WITH_LUNZAN}）。"
        "请只产出 1 条论赞；脚本会插入为 P01，**不删除**已有其他评述。"
    )
    return (
        f"{rules}\n\n---\n\n## 本条任务（只补论赞）\n\n"
        f"- 史略ID：{eid}\n"
        f"- 史略名称：{name}\n"
        f"- 朝代：{dynasty}\n"
        f"- 分类：{cat}\n\n"
        f"{strategy_note}\n\n"
        "### 已有评述（勿重复角度/著作）\n"
        + ("\n".join(existing_titles) if existing_titles else "- （无）")
        + "\n\n"
        "### 硬性要求\n"
        "1. **只输出 0 或 1 条**正史史家论赞（太史公曰/赞曰/评曰/史臣曰/论曰/呜呼+史臣曰）。\n"
        "2. 五帝人物/事略优先查《史记》相关篇「太史公曰」；无对应论赞则输出 `[]`，禁止硬凑。\n"
        "3. 内容必须含论赞套语原文并嵌入议论；禁止本纪叙事冒充；禁止「原文/白话」翻译体。\n"
        "4. 论赞可引用《史记》等正史，即使详情参考著作已列该书。\n"
        "5. 字段完整：评述标题（含·）、评述人、评述著作、评述内容（50–200汉字）、"
        "评述简介（≤20汉字）、评述年代。\n\n"
        "只输出一个 JSON 数组（可用 ```json 围栏）。不要输出信封或其他说明。"
    )


def _pick_lunzan_row(raw_items: list) -> dict | None:
    for row in raw_items:
        if isinstance(row, dict) and cw.is_zhengshi_lunzan(row):
            return row
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        work = str(row.get("评述著作") or "")
        if any(k in work for k in ("太史公曰", "赞曰", "评曰", "史臣曰", "论曰")):
            return row
    return None


def supplement_one(entry: dict, *, dry_run: bool = False) -> dict:
    paths = cw.histograph_paths()
    out = cw.output_path("commentary", entry, paths)
    if not out.exists():
        return {"id": entry.get("史略ID"), "status": "missing_file", "path": str(out)}

    doc = json.loads(out.read_text(encoding="utf-8"))
    existing = list(doc.get("entries") or [])
    eid = str(entry.get("史略ID") or "")
    name = str(entry.get("史略名称") or "")

    if cw.commentary_has_lunzan(existing):
        return {
            "id": eid,
            "name": name,
            "status": "skip_has_lunzan",
            "entry_count": len(existing),
            "action": "skip_has_lunzan",
            "prev_count": len(existing),
        }

    prompt = _lunzan_prompt(entry, existing)
    if dry_run:
        return {
            "id": eid,
            "name": name,
            "status": "dry_run",
            "strategy": "append_keep_others",
            "entry_count": len(existing),
            "prev_count": len(existing),
            "prompt_chars": len(prompt),
        }

    raw_text = cw.call_llm(prompt, session_prefix="cw-lunzan-")
    raw_items = cw.extract_json_array(raw_text)
    lunzan = _pick_lunzan_row(raw_items)
    if lunzan is None:
        return {
            "id": eid,
            "name": name,
            "status": "no_lunzan",
            "entry_count": len(existing),
            "action": "none",
            "prev_count": len(existing),
            "raw_n": len(raw_items),
        }

    lunzan_n = cw.normalize_commentary_entries([lunzan], entry=entry)[0]
    if not cw.is_zhengshi_lunzan(lunzan_n):
        work = str(lunzan_n.get("评述著作") or "")
        for marker in ("太史公曰", "赞曰", "评曰", "史臣曰", "论曰", "呜呼"):
            if marker in work:
                body = str(lunzan_n.get("评述内容") or "")
                if marker not in body:
                    lunzan_n["评述内容"] = f"{marker}：{body}"
                break

    merged, action = cw.merge_lunzan_into_commentary(
        existing, lunzan_n, entry=entry
    )
    new_doc = cw.build_envelope("commentary", entry, merged)
    new_doc["model"] = f"{doc.get('model') or 'unknown'}+lunzan"
    new_doc["lunzan_patch"] = {
        "action": action,
        "strategy": "append_keep_others",
        "prev_count": len(existing),
    }
    cw.write_json(out, new_doc)

    issues = verify_file(out, mode="commentary", strict=True)
    critical = [i for i in issues if i["level"] == "CRITICAL"]
    if critical:
        fix_prompt = (
            "下列论赞条目未通过校验。请只输出修正后的 **1 条论赞** JSON 数组。\n"
            f"错误：{json.dumps(critical, ensure_ascii=False)}\n"
            "要求：标题「名·角度」角度词不得与已有评述重复；内容 50–200 汉字且含论赞套语；"
            "简介≤20汉字；禁止翻译体。\n"
            f"已有标题角度：{[str(r.get('评述标题') or '').split('·',1)[-1] for r in existing]}\n"
            f"当前论赞：{json.dumps(lunzan_n, ensure_ascii=False)}\n"
        )
        raw2 = cw.call_llm(fix_prompt, session_prefix="cw-lunzan-rev-")
        raw2_items = cw.extract_json_array(raw2)
        lunzan2 = _pick_lunzan_row(raw2_items) or (
            raw2_items[0] if raw2_items and isinstance(raw2_items[0], dict) else None
        )
        if lunzan2:
            lunzan_n = cw.normalize_commentary_entries([lunzan2], entry=entry)[0]
            merged, action = cw.merge_lunzan_into_commentary(
                existing, lunzan_n, entry=entry
            )
            new_doc = cw.build_envelope("commentary", entry, merged)
            new_doc["model"] = f"{doc.get('model') or 'unknown'}+lunzan"
            new_doc["lunzan_patch"] = {
                "action": action,
                "strategy": "append_keep_others",
                "prev_count": len(existing),
                "revised": True,
            }
            cw.write_json(out, new_doc)
            issues = verify_file(out, mode="commentary", strict=True)
            critical = [i for i in issues if i["level"] == "CRITICAL"]

    if critical:
        cw.write_json(out, doc)
        return {
            "id": eid,
            "name": name,
            "status": "verify_fail",
            "error": "; ".join(i["msg"] for i in critical[:6]),
            "action": action,
            "prev_count": len(existing),
        }

    cw.update_manifest("commentary", entry, new_doc, out, paths=paths)
    return {
        "id": eid,
        "name": name,
        "status": "ok",
        "action": action,
        "strategy": "append_keep_others",
        "entry_count": new_doc["entry_count"],
        "prev_count": len(existing),
        "path": str(out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="五帝评述只补论赞")
    parser.add_argument("--max", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--id", action="append", default=[], help="只处理指定史略ID")
    args = parser.parse_args()

    cw.validate_histograph_root()
    paths = cw.histograph_paths()
    mid = paths["commentary"].parent / "05工作流中间产物" / "评述见证补全"
    mid.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = mid / "五帝_lunzan_only.log"
    summary_path = mid / f"五帝_lunzan_only_{stamp}.json"

    entries = cw.list_entries_by_dynasty(DYNASTY)
    if args.id:
        want = set(args.id)
        entries = [e for e in entries if str(e.get("史略ID")) in want]
    if args.max > 0:
        entries = entries[: args.max]

    print(
        f"只补论赞 dyn={DYNASTY} n={len(entries)} dry={args.dry_run} "
        f"rule=1论赞+≤{cw.MAX_OTHER_COMMENTARY}其他",
        flush=True,
    )
    results: list[dict] = []

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n==== {stamp} n={len(entries)} ====\n")
        for i, e in enumerate(entries, 1):
            eid = str(e.get("史略ID") or "")
            name = str(e.get("史略名称") or "")
            print(f"[{i}/{len(entries)}] {eid} {name} …", flush=True)
            try:
                r = supplement_one(e, dry_run=args.dry_run)
                results.append(r)
                st = r.get("status")
                mark = (
                    "✅"
                    if st in ("ok", "skip_has_lunzan", "no_lunzan", "dry_run")
                    else "❌"
                )
                msg = (
                    f"    {mark} {st} action={r.get('action')} "
                    f"n={r.get('prev_count')}→{r.get('entry_count')}"
                )
                if r.get("error"):
                    msg += f" err={r['error'][:120]}"
                print(msg, flush=True)
                log.write(msg + "\n")
            except Exception as ex:
                print(f"    ❌ {eid}: {ex}", flush=True)
                traceback.print_exc()
                results.append(
                    {"id": eid, "name": name, "status": "error", "error": str(ex)}
                )
                log.write(f"    ❌ {eid}: {ex}\n")

    by: dict[str, int] = {}
    for r in results:
        by[r.get("status") or "?"] = by.get(r.get("status") or "?", 0) + 1
    print(f"\n=== DONE {by} ===", flush=True)
    summary_path.write_text(
        json.dumps(
            {"stamp": stamp, "dynasty": DYNASTY, "by_status": by, "results": results},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"summary → {summary_path}", flush=True)
    err_n = sum(1 for r in results if r.get("status") in ("error", "verify_fail"))
    return 1 if err_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
