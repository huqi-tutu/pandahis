"""评述 / 见证 JSON verify 门禁。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from cw_lib import STATUS_DONE, STATUS_EMPTY, count_han  # noqa: E402

Mode = Literal["commentary", "witness"]

ID_P = re.compile(r"^GLBL_\d{5}_P\d{2}$")
ID_W = re.compile(r"^GLBL_\d{5}_W\d{2}$")
# 兼容非 GLBL 前缀史略（若有）
ID_P_FLEX = re.compile(r"^.+_P\d{2}$")
ID_W_FLEX = re.compile(r"^.+_W\d{2}$")
PRI_OK = frozenset({"P0", "P1", "P2", "P3", "P4"})


def _issue(level: str, msg: str) -> dict[str, str]:
    return {"level": level, "msg": msg}


def verify_envelope(doc: dict[str, Any], mode: Mode) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if doc.get("schema_version") != 1:
        issues.append(_issue("CRITICAL", f"schema_version 须为 1，当前 {doc.get('schema_version')!r}"))
    if doc.get("mode") != mode:
        issues.append(_issue("CRITICAL", f"mode 须为 {mode!r}，当前 {doc.get('mode')!r}"))
    status = doc.get("status")
    if status not in (STATUS_DONE, STATUS_EMPTY):
        issues.append(_issue("CRITICAL", f"非法 status: {status!r}"))
    entries = doc.get("entries")
    if not isinstance(entries, list):
        issues.append(_issue("CRITICAL", "entries 须为数组"))
        return issues
    if doc.get("entry_count") != len(entries):
        issues.append(
            _issue(
                "CRITICAL",
                f"entry_count={doc.get('entry_count')} 与 entries 长度 {len(entries)} 不一致",
            )
        )
    if status == STATUS_EMPTY and len(entries) != 0:
        issues.append(_issue("CRITICAL", "status=已处理·无可用 时 entries 须为空"))
    if status == STATUS_DONE and len(entries) == 0:
        issues.append(_issue("CRITICAL", "status=done 时 entries 不可为空（应标 已处理·无可用）"))
    for key in ("史略ID", "史略名称"):
        if not str(doc.get(key) or "").strip():
            issues.append(_issue("CRITICAL", f"信封缺少 {key}"))
    return issues


def verify_commentary_entries(doc: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    eid = str(doc.get("史略ID") or "").strip()
    name = str(doc.get("史略名称") or "").strip()
    seen: set[str] = set()
    for i, row in enumerate(doc.get("entries") or [], start=1):
        prefix = f"[{i}]"
        if not isinstance(row, dict):
            issues.append(_issue("CRITICAL", f"{prefix} 条目非对象"))
            continue
        rid = str(row.get("评述ID") or "").strip()
        if not ID_P_FLEX.match(rid) or not rid.startswith(f"{eid}_P"):
            issues.append(_issue("CRITICAL", f"{prefix} 评述ID 非法: {rid!r}"))
        expect = f"{eid}_P{i:02d}"
        if rid != expect:
            issues.append(_issue("CRITICAL", f"{prefix} 评述ID 应为 {expect}，当前 {rid}"))
        if rid in seen:
            issues.append(_issue("CRITICAL", f"{prefix} 评述ID 重复: {rid}"))
        seen.add(rid)
        if str(row.get("史略ID") or "").strip() != eid:
            issues.append(_issue("CRITICAL", f"{prefix} 史略ID 与信封不一致"))
        if str(row.get("史略名称") or "").strip() != name:
            issues.append(_issue("CRITICAL", f"{prefix} 史略名称 与信封不一致"))
        title = str(row.get("评述标题") or "").strip()
        if "·" not in title:
            issues.append(_issue("CRITICAL", f"{prefix} 评述标题须含「·」: {title!r}"))
        for k in ("评述人", "评述著作", "评述内容", "评述简介", "评述年代"):
            if not str(row.get(k) or "").strip():
                issues.append(_issue("CRITICAL", f"{prefix} 缺少 {k}"))
        brief = str(row.get("评述简介") or "")
        if count_han(brief) > 20:
            issues.append(
                _issue("CRITICAL", f"{prefix} 评述简介汉字数 {count_han(brief)} > 20")
            )
        body = str(row.get("评述内容") or "")
        hc = count_han(body)
        if hc < 50 or hc > 200:
            issues.append(_issue("CRITICAL", f"{prefix} 评述内容汉字数 {hc} 不在 50–200"))
        if "《" not in str(row.get("评述著作") or ""):
            issues.append(_issue("WARN", f"{prefix} 评述著作建议含书名号"))
    n = len(doc.get("entries") or [])
    if doc.get("status") == STATUS_DONE and (n < 1 or n > 5):
        issues.append(_issue("WARN", f"评述条数 {n} 超出建议 1–5"))
    return issues


def verify_witness_entries(doc: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    eid = str(doc.get("史略ID") or "").strip()
    name = str(doc.get("史略名称") or "").strip()
    seen_id: set[str] = set()
    seen_pri: set[str] = set()
    for i, row in enumerate(doc.get("entries") or [], start=1):
        prefix = f"[{i}]"
        if not isinstance(row, dict):
            issues.append(_issue("CRITICAL", f"{prefix} 条目非对象"))
            continue
        rid = str(row.get("文物ID") or "").strip()
        expect = f"{eid}_W{i:02d}"
        if rid != expect:
            issues.append(_issue("CRITICAL", f"{prefix} 文物ID 应为 {expect}，当前 {rid}"))
        if rid in seen_id:
            issues.append(_issue("CRITICAL", f"{prefix} 文物ID 重复"))
        seen_id.add(rid)
        if str(row.get("史略ID") or "").strip() != eid:
            issues.append(_issue("CRITICAL", f"{prefix} 史略ID 与信封不一致"))
        if str(row.get("史略名称") or "").strip() != name:
            issues.append(_issue("CRITICAL", f"{prefix} 史略名称 与信封不一致"))
        for k in ("文物标题", "现藏地点", "文物介绍", "文物优先级", "优先级判定理由"):
            if not str(row.get(k) or "").strip():
                issues.append(_issue("CRITICAL", f"{prefix} 缺少 {k}"))
        img = row.get("文物图片")
        if img not in ("", None):
            issues.append(_issue("CRITICAL", f"{prefix} 文物图片须为空字符串，当前 {img!r}"))
        pri = str(row.get("文物优先级") or "").strip().upper()
        if pri not in PRI_OK:
            issues.append(_issue("CRITICAL", f"{prefix} 非法优先级: {pri!r}"))
        elif pri in seen_pri:
            issues.append(_issue("CRITICAL", f"{prefix} 优先级重复: {pri}"))
        seen_pri.add(pri)
        intro = str(row.get("文物介绍") or "")
        hc = count_han(intro)
        if hc < 100 or hc > 200:
            issues.append(_issue("CRITICAL", f"{prefix} 文物介绍汉字数 {hc} 不在 100–200"))
        reason = str(row.get("优先级判定理由") or "")
        rc = count_han(reason)
        if rc < 20 or rc > 80:
            issues.append(_issue("WARN", f"{prefix} 优先级判定理由汉字数 {rc} 建议 20–80"))
        loc = str(row.get("现藏地点") or "")
        if "·" not in loc:
            issues.append(_issue("WARN", f"{prefix} 现藏地点建议「国家·机构」格式"))
    n = len(doc.get("entries") or [])
    if doc.get("status") == STATUS_DONE and (n < 1 or n > 5):
        issues.append(_issue("WARN", f"文物件数 {n} 超出建议 1–5"))
    return issues


def verify_file(path: Path, *, mode: Mode, strict: bool = True) -> list[dict[str, str]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    issues = verify_envelope(doc, mode)
    if mode == "commentary":
        issues.extend(verify_commentary_entries(doc))
    else:
        issues.extend(verify_witness_entries(doc))
    if strict:
        # WARN 不阻断；仅 CRITICAL 由调用方判断
        pass
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="校验评述/见证 JSON")
    parser.add_argument("file", type=Path)
    parser.add_argument("--mode", choices=["commentary", "witness"], required=True)
    parser.add_argument("--strict", action="store_true", default=True)
    parser.add_argument("--no-strict", action="store_true")
    args = parser.parse_args()
    strict = not args.no_strict
    issues = verify_file(args.file, mode=args.mode, strict=strict)
    for it in issues:
        print(f"{it['level']}: {it['msg']}")
    critical = [i for i in issues if i["level"] == "CRITICAL"]
    if critical:
        print(f"\n⛔ {len(critical)} CRITICAL")
        return 1
    print(f"\n✅ verify OK（{len(issues)} issues，0 CRITICAL）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
