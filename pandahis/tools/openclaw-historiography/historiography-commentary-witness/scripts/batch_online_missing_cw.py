#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按线上索引补全缺失的评述/见证（默认战国及以前；可用 --dynasties 指定秦等）。

硬约束：
  1. 仅处理「无评述文件」或「无见证文件」的条目；已有 done/已处理·无可用 不重跑。
  2. 同名/别名已有完整评述+见证时，克隆并改写 ID，不二次 LLM。
  3. 索引仅用 data/12线上史略索引；禁止读取 03/04 V1。

用法：
  python3 batch_online_missing_cw.py --dry-run
  python3 batch_online_missing_cw.py                 # 生成 + 入库
  python3 batch_online_missing_cw.py --dynasties 秦
  python3 batch_online_missing_cw.py --no-import
  python3 batch_online_missing_cw.py --ids GLBL_00993
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PKG_ROOT = SCRIPT_DIR.parent.parent  # tools/openclaw-historiography
# .../pandahis/pandahis
HIST_ROOT = PKG_ROOT.parent.parent

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PKG_ROOT))

# 强制 HISTOGRAPH_ROOT，避免落到 Desktop/历史图谱
os.environ["HISTOGRAPH_ROOT"] = str(HIST_ROOT)

import cw_lib as cw  # noqa: E402
from verify_cw import verify_file  # noqa: E402

ONLINE_INDEX = HIST_ROOT / "data" / "12线上史略索引" / "史略索引_online.json"
MID = HIST_ROOT / "data" / "05工作流中间产物" / "评述见证补全"
DEFAULT_DYNASTIES = ("五帝", "夏", "商", "西周", "春秋", "战国")
FORBIDDEN = ("03索引标注条目", "04史料翻译", "史略索引_01至02")

# 缺口名 → 已有完整 CW 的名称
NAME_ALIASES: dict[str, str] = {
    "魏公子无忌": "魏无忌",
    "项籍": "项羽",
    "秦始皇": "嬴政",
    "秦二世": "胡亥",
}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _assert_no_v1(index_path: Path) -> None:
    s = str(index_path)
    for bad in FORBIDDEN:
        if bad in s:
            raise SystemExit(f"禁止使用 V1 索引: {index_path}")


def _existing_output(mode: str, entry: dict, paths: dict) -> Path | None:
    """按标准路径或同 ID 通配查找已有产出（兼容改名）。"""
    out = cw.output_path(mode, entry, paths)  # type: ignore[arg-type]
    if out.is_file():
        return out
    eid = str(entry.get("史略ID") or "").strip()
    if not eid:
        return None
    folder = paths["commentary"] if mode == "commentary" else paths["witness"]
    suffix = "评述" if mode == "commentary" else "见证"
    hits = sorted(folder.glob(f"{eid}_*_{suffix}.json"))
    return hits[0] if hits else None


def _already_done(mode: str, entry: dict, paths: dict) -> bool:
    """有产出文件且 status 合法即视为已处理（不因 strict 告警重跑）。"""
    out = _existing_output(mode, entry, paths)
    if not out:
        return False
    try:
        doc = json.loads(out.read_text(encoding="utf-8"))
        return doc.get("status") in ("done", "已处理·无可用")
    except Exception:
        return False


def _find_source_file(mode: str, src_id: str, paths: dict) -> Path | None:
    folder = paths["commentary"] if mode == "commentary" else paths["witness"]
    suffix = "评述" if mode == "commentary" else "见证"
    hits = list(folder.glob(f"{src_id}_*_{suffix}.json"))
    return hits[0] if hits else None


def _clone_from_sibling(
    mode: str,
    target: dict,
    source_id: str,
    paths: dict,
) -> dict[str, Any] | None:
    src_path = _find_source_file(mode, source_id, paths)
    if not src_path or not src_path.is_file():
        return None
    doc = json.loads(src_path.read_text(encoding="utf-8"))
    old_id = str(doc.get("史略ID") or source_id)
    new_id = str(target["史略ID"])
    new_name = str(target.get("史略名称") or "")
    old_name = str(doc.get("史略名称") or "")

    out = deepcopy(doc)
    out["史略ID"] = new_id
    out["史略名称"] = new_name
    out["史略分类"] = target.get("史略分类") or out.get("史略分类")
    out["二级朝代坐标"] = target.get("二级朝代坐标") or out.get("二级朝代坐标")
    out["processed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["_cloned_from"] = old_id
    out["_clone_note"] = "同实体已有完整组件，对齐避免重复补全"

    id_key = "评述ID" if mode == "commentary" else "文物ID"
    for ent in out.get("entries") or []:
        if not isinstance(ent, dict):
            continue
        ent["史略ID"] = new_id
        ent["史略名称"] = new_name
        rid = str(ent.get(id_key) or "")
        if rid.startswith(old_id):
            ent[id_key] = new_id + rid[len(old_id) :]
        # 标题里旧名替换（轻量）
        for tk in ("评述标题", "文物标题"):
            if tk in ent and old_name and old_name in str(ent.get(tk) or ""):
                ent[tk] = str(ent[tk]).replace(old_name, new_name)

    dest = cw.output_path(mode, target, paths)  # type: ignore[arg-type]
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(dest), "entry_count": out.get("entry_count"), "status": out.get("status")}


def _sibling_id(target: dict, by_name: dict[str, list[dict]], paths: dict) -> str | None:
    name = str(target.get("史略名称") or "")
    eid = str(target.get("史略ID") or "")
    candidates: list[str] = []
    for n in (name, NAME_ALIASES.get(name, "")):
        if not n:
            continue
        for other in by_name.get(n, []):
            oid = str(other.get("史略ID") or "")
            if oid == eid:
                continue
            if _already_done("commentary", other, paths) and _already_done("witness", other, paths):
                candidates.append(oid)
    return candidates[0] if candidates else None


def _collect_missing(
    online: list[dict],
    paths: dict,
    *,
    dynasties: tuple[str, ...] | list[str],
) -> list[dict]:
    allow = set(dynasties)
    miss = []
    for e in online:
        if e.get("二级朝代坐标") not in allow:
            continue
        need_c = not _already_done("commentary", e, paths)
        need_w = not _already_done("witness", e, paths)
        if need_c or need_w:
            miss.append({"entry": e, "need_c": need_c, "need_w": need_w})
    return miss


def _update_manifest(dynasty: str, mode: str, entry: dict, doc: dict, paths: dict) -> None:
    folder = paths["commentary"] if mode == "commentary" else paths["witness"]
    suffix = "评述" if mode == "commentary" else "见证"
    man_path = folder / f"{dynasty}_{suffix}_manifest.json"
    if man_path.is_file():
        man = json.loads(man_path.read_text(encoding="utf-8"))
    else:
        man = {"dynasty": dynasty, "mode": "commentary" if mode == "commentary" else "witness", "completed": []}
    completed = list(man.get("completed") or [])
    eid = str(entry.get("史略ID"))
    completed = [c for c in completed if c.get("glbl") != eid]
    out = cw.output_path(mode, entry, paths)  # type: ignore[arg-type]
    completed.append(
        {
            "glbl": eid,
            "name": entry.get("史略名称"),
            "file": out.name,
            "status": doc.get("status"),
            "entry_count": doc.get("entry_count") or 0,
            "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    man["completed"] = completed
    man["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _import_ids(ids: list[str], index_path: Path) -> int:
    import import_cw_lib as icw  # noqa: WPS433

    paths = cw.histograph_paths()
    all_stmts: list[str] = []
    imported = 0
    for eid in ids:
        entry = cw.find_entry(entry_id=eid, index_path=index_path)
        for mode in ("commentary", "witness"):
            fp = cw.output_path(mode, entry, paths)  # type: ignore[arg-type]
            if not fp.is_file():
                continue
            doc = icw.load_json(fp)
            stmts = (
                icw.build_critique_sql(doc)
                if mode == "commentary"
                else icw.build_relic_sql(doc)
            )
            if len(stmts) > 1:
                imported += 1
            all_stmts.extend(stmts)
    if all_stmts:
        icw.execute_mysql(all_stmts, **icw.default_mysql_kwargs())  # type: ignore[arg-type]
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="线上索引缺失评述/见证补全")
    parser.add_argument("--index", type=Path, default=ONLINE_INDEX)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-import", action="store_true")
    parser.add_argument("--ids", nargs="*", default=None, help="只处理这些 ID")
    parser.add_argument(
        "--dynasties",
        nargs="+",
        default=None,
        help="朝代过滤，默认五帝…战国；例：--dynasties 秦",
    )
    parser.add_argument("--limit", type=int, default=0, help="最多新生成条数（0=不限，按史略计）")
    args = parser.parse_args()

    dynasties: tuple[str, ...] = (
        tuple(args.dynasties) if args.dynasties else DEFAULT_DYNASTIES
    )

    _assert_no_v1(args.index)
    if not args.index.is_file():
        raise SystemExit(f"缺少线上索引: {args.index}")

    cw.validate_histograph_root()
    cw.ensure_deepseek_v4_pro()
    paths = cw.histograph_paths()
    MID.mkdir(parents=True, exist_ok=True)

    online_doc = json.loads(args.index.read_text(encoding="utf-8"))
    online = online_doc if isinstance(online_doc, list) else online_doc.get("entries") or []
    by_name: dict[str, list[dict]] = {}
    for e in online:
        by_name.setdefault(str(e.get("史略名称") or ""), []).append(e)

    missing = _collect_missing(online, paths, dynasties=dynasties)
    if args.ids:
        allow = set(args.ids)
        missing = [m for m in missing if m["entry"]["史略ID"] in allow]

    _log(f"缺失条目: {len(missing)}（索引={args.index.name}；朝代={','.join(dynasties)}）")
    for dyn in dynasties:
        n = sum(1 for m in missing if m["entry"].get("二级朝代坐标") == dyn)
        if n:
            _log(f"  {dyn}: {n}")

    results: list[dict] = []
    done_ids: list[str] = []
    generated = 0

    for m in missing:
        e = m["entry"]
        eid = str(e["史略ID"])
        name = str(e.get("史略名称") or "")
        dyn = str(e.get("二级朝代坐标") or "")
        sib = _sibling_id(e, by_name, paths)

        row: dict[str, Any] = {"id": eid, "name": name, "dynasty": dyn, "sibling": sib, "actions": {}}

        if args.dry_run:
            row["actions"] = {
                "commentary": "clone" if (m["need_c"] and sib) else ("llm" if m["need_c"] else "skip"),
                "witness": "clone" if (m["need_w"] and sib) else ("llm" if m["need_w"] else "skip"),
            }
            results.append(row)
            continue

        # clone first
        if sib:
            for mode, need in (("commentary", m["need_c"]), ("witness", m["need_w"])):
                if not need:
                    continue
                info = _clone_from_sibling(mode, e, sib, paths)
                if info:
                    row["actions"][mode] = {"via": "clone", **info}
                    doc = json.loads(Path(info["path"]).read_text(encoding="utf-8"))
                    _update_manifest(dyn, mode, e, doc, paths)
                    _log(f"  ↪ clone {mode} {eid} ← {sib}")

        # refresh needs after clone
        need_c = not _already_done("commentary", e, paths)
        need_w = not _already_done("witness", e, paths)

        if (need_c or need_w) and args.limit and generated >= args.limit:
            row["actions"]["llm"] = "limit_reached"
            results.append(row)
            continue

        for mode, need in (("commentary", need_c), ("witness", need_w)):
            if not need:
                continue
            label = "评述" if mode == "commentary" else "见证"
            _log(f"  → LLM {label} {eid} {name} …")
            last_err = ""
            success = False
            for attempt in range(1, 4):
                extra = (
                    "禁止教材级争议框架（如禅让真假/层累疑古）占据第1条评述；"
                    "见证：实物条目优先级须互不相同（P0–P4 各至多一条）；"
                    "附加文学见证最多 1 条且须标「附加文学见证: true」、优先级 P4、"
                    "现藏地点以「传世文本」开头；体裁限诗词歌赋与文章"
                    "（如《阿房宫赋》《过秦论》）；"
                    "禁止《史记》本纪/世家/列传、《汉书》《左传》《资治通鉴》等史书纪传，"
                    "禁止杂剧/演义冒充文学见证；其余条勿标附加文学。"
                )
                if attempt > 1 and last_err:
                    extra = (
                        f"上一次输出未通过校验，必须修正后重写 entries。\n"
                        f"校验错误：{last_err}\n"
                        + extra
                    )
                try:
                    r = cw.compose_one(
                        mode,  # type: ignore[arg-type]
                        entry_id=eid,
                        index_path=args.index,
                        revise=True,
                        extra_prompt=extra,
                    )
                    row["actions"][mode] = {
                        "via": "llm",
                        "attempt": attempt,
                        "status": r.get("status"),
                        "entry_count": r.get("entry_count"),
                    }
                    out = cw.output_path(mode, e, paths)  # type: ignore[arg-type]
                    if out.is_file():
                        doc = json.loads(out.read_text(encoding="utf-8"))
                        _update_manifest(dyn, mode, e, doc, paths)
                    _log(
                        f"    ✅ {label} status={r.get('status')} n={r.get('entry_count')} "
                        f"(try {attempt})"
                    )
                    success = True
                    break
                except Exception as ex:
                    last_err = str(ex)
                    _log(f"    ⚠️ {label} try {attempt}/3: {ex}")
                    # 删除半成品，避免 status=done 阻断重试
                    out = _existing_output(mode, e, paths)
                    if out and out.is_file():
                        out.unlink()
            if not success:
                traceback.print_exc()
                row["actions"][mode] = {"via": "llm", "error": last_err}

        if need_c or need_w:
            generated += 1
        done_ids.append(eid)
        results.append(row)

        # checkpoint summary
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        (MID / "online_missing_cw_checkpoint.json").write_text(
            json.dumps({"updated_at": stamp, "results": results}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    if args.dry_run:
        out = MID / f"online_missing_cw_dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps({"missing": len(missing), "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _log(f"dry-run → {out}")
        return 0

    if not args.no_import and done_ids:
        try:
            n = _import_ids(sorted(set(done_ids)), args.index)
            _log(f"☁️ MySQL 导入完成（{n} 个有数据行的 mode×条目）")
        except Exception as ex:
            _log(f"⚠️ MySQL 导入失败: {ex}")
            traceback.print_exc()

    summary_path = MID / f"online_missing_cw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary_path.write_text(
        json.dumps(
            {
                "index": str(args.index),
                "missing_before": len(missing),
                "processed": len(done_ids),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _log(f"summary → {summary_path}")

    # final residual
    residual = _collect_missing(online, paths, dynasties=dynasties)
    _log(f"完成后仍缺文件: {len(residual)}")
    for m in residual[:20]:
        _log(f"  {m['entry']['史略ID']} {m['entry'].get('史略名称')} c={m['need_c']} w={m['need_w']}")
    return 0 if not residual else 0


if __name__ == "__main__":
    raise SystemExit(main())
