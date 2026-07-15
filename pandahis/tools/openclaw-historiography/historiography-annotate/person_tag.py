#!/usr/bin/env python3
"""史略人物标签标注：全局 enrichment 专用，卷级 Step4 不写入。

字段：人物标签 / 人物标签判定理由 / 人物标签置信度
规则 SSOT：reference/人物标签规则.md

用法：
  python3 person_tag.py <史略索引.json> --llm
  python3 person_tag.py <史略索引.json> --verify
  python3 person_tag.py <史略索引.json> --dry-run
  python3 person_tag.py <史略索引.json> --llm --dynasty-id CD_HX_XIHAN
  python3 person_tag.py <史略索引.json> --llm --no-empty  # 二期补全：禁止留空
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

from category_v3 import VALID_CATS, normalize_entry_category  # noqa: E402
from lib_config import coerce_year  # noqa: E402
from peak_year import (  # noqa: E402
    MOTHER_QUOTE_MAX,
    _extract_json_array,
    _kaoding,
    is_high_risk_entry,
    mother_paragraph_ref,
    mother_work_label,
)

TAG = "人物标签"
TAG_REASON = "人物标签判定理由"
TAG_CONF = "人物标签置信度"

META_FP = "_人物标签指纹"
META_LOCK = "_人物标签人工锁定"
META_REVIEW = "_人物标签待审"
META_LLM = "_人物标签LLM依据"
META_EMPTY = "_人物标签留空"

TAG_ELIGIBLE = frozenset(VALID_CATS)
TAG_RE = re.compile(r"^[\u4e00-\u9fff]{2,5}$")
REVIEW_CONF_THRESHOLD = 0.4
BATCH_SIZE = 15

# 泳道分类词 + 空泛褒义（笼统角色词如「名将」允许作兜底）
BANNED_SUBSTRINGS = (
    "文臣", "武将", "宦官", "庶众", "宗戚", "君王", "蕃祚", "伟人",
)

# 描述「史书没记载/无事迹」的元标签 → 应留空
ABSENCE_META_RE = re.compile(
    r"寡闻|无闻|无迹|无事迹|事迹不详|事迹阙载|史载|载籍|记载少|记载寡|"
    r"无突出|无显著|边缘君主|边缘诸侯|一笔带过|难辨识|附传级|一般记载|"
    r"六年无事|四年无迹|两年遽亡|长期无功|附庸之嗣|一年即崩|事迹泯然|缺乏记忆"
)

# 标签锚定在他人身上（XX之子/之父 等）
ABOUT_OTHER_RE = re.compile(
    r"^(.+?)(之子|之女|之孙|之父|之母|之妻|之夫|弟子|门人|后裔|后人|嗣王|嗣位)$"
)

SUBJECT_LOCK = (
    "你只给字段「判定对象」打标签；标签须描述该人本人。"
    "不得以他人姓名/封号为主体（如「破羌之子」应改为描述辛庆忌本人，或留空）。"
)

RULES_BRIEF = (
    "人物标签=后世提及该主体时最具辨识度的记忆锚点（2～5汉字）。"
    "优先：通行典故>标志性事件>传世标识>历史角色>笼统角色词（名将/名臣等兜底）。"
    "若无任何合适锚点，人物标签留空（输出空字符串），不要硬凑。"
    "禁止：泳道分类词、元描述缺载标签（史载寡闻/事迹不详等）、姓名本字、朝代名。"
    "禁止以本名/表字/别号/谥号/庙号代替标签（标签须是后世记忆锚点，非人物称谓本身）。"
    "峰值年/峰值原因/优先级仅作参考，可与标签不一致。"
)

NO_EMPTY_RULES = (
    "人物标签=后世提及该主体时最具辨识度的记忆锚点（2～5汉字）。"
    "优先：通行典故>标志性事件>传世标识>历史角色>笼统角色词（名将/名臣等兜底）。"
    "补全条目均为重要历史人物，**每条都必须给出标签，不得留空**。"
    "若无通行典故，退而求其次：标志性事件简写 → 传世标识 → 历史角色（如「乐官始祖」「司法鼻祖」）。"
    "禁止：泳道分类词、元描述缺载标签、姓名本字、朝代名。"
    "禁止以本名/表字/别号/谥号/庙号代替标签（标签须是后世记忆锚点，非人物称谓本身）。"
    "峰值年/峰值原因/优先级仅作参考，可与标签不一致。"
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
            "原文字句",
            "峰值年",
            "峰值原因",
            "优先级",
        )
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def is_locked(entry: dict) -> bool:
    return bool((entry.get("_auto_filled") or {}).get(META_LOCK))


def is_eligible(entry: dict) -> bool:
    return normalize_entry_category(entry.get("史略分类", "")) in TAG_ELIGIBLE


def has_valid_tag(entry: dict) -> bool:
    tag = (entry.get(TAG) or "").strip()
    return bool(tag and TAG_RE.match(tag))


def is_tag_decided(entry: dict) -> bool:
    auto = entry.get("_auto_filled") or {}
    return has_valid_tag(entry) or bool(auto.get(META_EMPTY))


def is_fresh(entry: dict) -> bool:
    auto = entry.get("_auto_filled") or {}
    return is_tag_decided(entry) and auto.get(META_FP) == entry_fingerprint(entry)


def _tag_about_other(name: str, tag: str) -> Optional[str]:
    m = ABOUT_OTHER_RE.match(tag.strip())
    if not m:
        return None
    anchor = (m.group(1) or "").strip()
    if not anchor or anchor in name:
        return None
    return anchor


def build_llm_input(entry: dict) -> dict:
    name = (entry.get("史略名称") or "").strip()
    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))
    kaoding = _kaoding(entry)
    payload = {
        "史略ID": entry.get("史略ID"),
        "判定对象": name,
        "史略分类": normalize_entry_category(entry.get("史略分类", "")),
        "史略简介": entry.get("史略简介"),
        "史略开始年": start,
        "史略结束年": end,
        "二级朝代坐标": entry.get("二级朝代坐标"),
        "四级帝王坐标": entry.get("四级帝王坐标"),
        "坐标主轴": kaoding.get("坐标主轴") or "",
        "年考订": kaoding.get("年") or "",
        "母本段落": mother_paragraph_ref(entry),
        "母本原文字句": (entry.get("原文字句") or "")[:MOTHER_QUOTE_MAX],
        "峰值年": entry.get("峰值年"),
        "峰值原因": entry.get("峰值原因"),
        "峰值类型": entry.get("峰值类型"),
        "优先级": entry.get("优先级"),
        "优先级判定理由": entry.get("优先级判定理由"),
    }
    if is_high_risk_entry(entry):
        payload["注意"] = "合传/蕃祚等易混淆：标签必须描述判定对象本人/本政权"
    return {k: v for k, v in payload.items() if v not in (None, "")}


def validate_tag(entry: dict, *, strict: bool = True) -> List[str]:
    eid = entry.get("史略ID", "?")
    name = entry.get("史略名称", "?")
    prefix = f"[{eid}] {name}"
    issues: List[str] = []
    if not is_eligible(entry):
        return issues
    tag = (entry.get(TAG) or "").strip()
    if not tag:
        return issues
    if not TAG_RE.match(tag):
        issues.append(f"{prefix} 人物标签须为 2～5 个汉字: {tag!r}")
    if name and name in tag:
        issues.append(f"{prefix} 标签不得含姓名本字")
    for bad in BANNED_SUBSTRINGS:
        if bad in tag:
            issues.append(f"{prefix} 标签含禁用词「{bad}」")
    anchor = _tag_about_other(name, tag)
    if anchor:
        issues.append(f"{prefix} 标签主体为他人「{anchor}」")
    if ABSENCE_META_RE.search(tag):
        issues.append(f"{prefix} 元描述缺载标签应留空: {tag!r}")
    reason = (entry.get(TAG_REASON) or "").strip()
    if strict and tag and not reason:
        issues.append(f"{prefix} 缺少人物标签判定理由")
    conf = entry.get(TAG_CONF)
    if conf is not None and not isinstance(conf, (int, float)):
        issues.append(f"{prefix} 人物标签置信度须为数字")
    return issues


def qc_entry(entry: dict) -> List[str]:
    """质检：返回建议动作（留空/重标/待审）。"""
    if not is_eligible(entry):
        return []
    name = (entry.get("史略名称") or "").strip()
    tag = (entry.get(TAG) or "").strip()
    notes: List[str] = []
    if not tag:
        return notes
    notes.extend(validate_tag(entry, strict=False))
    conf = entry.get(TAG_CONF)
    if isinstance(conf, (int, float)) and conf < REVIEW_CONF_THRESHOLD:
        notes.append(f"置信度低({conf:.2f})")
    return notes


def clear_tag(entry: dict, reason: str = "") -> None:
    if is_locked(entry):
        return
    entry[TAG] = ""
    entry[TAG_REASON] = (reason or "").strip() or "无通行典故或标志性事件，留空"
    entry[TAG_CONF] = None
    auto = _auto(entry)
    auto[META_FP] = entry_fingerprint(entry)
    auto[META_EMPTY] = True
    auto.pop(META_LLM, None)
    auto.pop(META_REVIEW, None)


def write_tag(entry: dict, tag: str, reason: str, conf: float) -> None:
    if is_locked(entry):
        return
    tag = (tag or "").strip()
    if not tag:
        clear_tag(entry, reason)
        return
    reason = (reason or "").strip() or "（待补理由）"
    conf = round(max(0.0, min(1.0, float(conf))), 2)
    entry[TAG] = tag
    entry[TAG_REASON] = reason
    entry[TAG_CONF] = conf
    auto = _auto(entry)
    auto[META_FP] = entry_fingerprint(entry)
    auto[META_LLM] = reason
    auto.pop(META_EMPTY, None)
    gate_notes = validate_tag(entry, strict=False)
    if gate_notes or conf < REVIEW_CONF_THRESHOLD:
        notes = list(gate_notes)
        if conf < REVIEW_CONF_THRESHOLD:
            notes.append(f"置信度低({conf:.2f})")
        auto[META_REVIEW] = "；".join(notes)
    else:
        auto.pop(META_REVIEW, None)


def build_llm_prompt(batch: List[dict], *, no_empty: bool = False) -> str:
    rules = NO_EMPTY_RULES if no_empty else RULES_BRIEF
    lines = [
        "你是历史图谱编辑。为下列史略逐条判定「人物标签」（2～5汉字" + ("，不可留空" if no_empty else "，或留空") + "）。",
        SUBJECT_LOCK,
        "",
        rules,
        "",
        "只输出 JSON 数组，元素形如：",
        '{"史略ID":"...","人物标签":"2-5字","人物标签判定理由":"须点名判定对象",'
        '"人物标签置信度":0.xx}',
    ]
    if not no_empty:
        lines.append("无合适锚点时人物标签输出空字符串。")
    lines.append("")
    lines.append("待判定条目：")
    for e in batch:
        lines.append(json.dumps(build_llm_input(e), ensure_ascii=False))
    return "\n".join(lines)


def run_llm_batch(batch: List[dict], *, batch_index: int, no_empty: bool = False) -> Dict[str, dict]:
    from llm.provider import run_agent_turn  # noqa: WPS433

    prompt = build_llm_prompt(batch, no_empty=no_empty)
    sid = "ptag-" + hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
    _log(f"  🤖 LLM 人物标签 第 {batch_index} 批 ({len(batch)} 条)")
    out: Dict[str, dict] = {}
    try:
        res = run_agent_turn(prompt, session_id=sid, timeout_sec=180, temperature=0)
    except Exception as exc:  # noqa: BLE001
        _log(f"     ⚠️ LLM 失败: {exc}")
        return out
    for row in _extract_json_array(str(res.get("result", ""))):
        rid = str(row.get("史略ID", "")).strip()
        if rid:
            out[rid] = row
    return out


def annotate(
    entries: List[dict],
    *,
    use_llm: bool = True,
    force: bool = False,
    no_empty: bool = False,
    on_batch_done: Optional[Callable[[], None]] = None,
) -> Dict[str, int]:
    stats = {"total": 0, "skipped": 0, "locked": 0, "fresh": 0, "llm": 0, "empty": 0, "failed": 0}
    pending: List[dict] = []
    for entry in entries:
        if not is_eligible(entry):
            continue
        stats["total"] += 1
        if is_locked(entry):
            stats["locked"] += 1
            continue
        if not force and is_fresh(entry):
            stats["fresh"] += 1
            continue
        pending.append(entry)

    if not use_llm or not pending:
        stats["skipped"] = len(pending)
        return stats

    batch_no = 0
    by_id = {str(e.get("史略ID", "")): e for e in pending}
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        batch_no += 1
        rows = run_llm_batch(batch, batch_index=batch_no, no_empty=no_empty)
        for e in batch:
            eid = str(e.get("史略ID", ""))
            row = rows.get(eid)
            if not row:
                stats["failed"] += 1
                continue
            tag = str(row.get(TAG, "") or "").strip()
            reason = str(row.get(TAG_REASON, ""))
            conf = float(row.get(TAG_CONF, 0.65) or 0.65)
            if tag:
                write_tag(e, tag, reason, conf)
                stats["llm"] += 1
            elif no_empty:
                # 二期补全不允许留空：LLM 未产出标签 → 不清除已有标签，标记待审
                auto = _auto(e)
                auto[META_REVIEW] = "二期补全拒绝留空，LLM 未产出标签"
                stats["empty"] += 1
            else:
                clear_tag(e, reason)
                stats["empty"] += 1
        if on_batch_done:
            on_batch_done()
    return stats


def _load(path: Path) -> Tuple[dict, List[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    return data, entries


def filter_by_dynasty(entries: List[dict], dynasty_id: Optional[str]) -> List[dict]:
    if not dynasty_id:
        return entries
    return [e for e in entries if (e.get("朝代ID") or "").strip() == dynasty_id]


def annotate_index(
    index_path: Path,
    *,
    use_llm: bool = True,
    force: bool = False,
    dynasty_id: Optional[str] = None,
    no_empty: bool = False,
) -> Tuple[Dict[str, int], List[str]]:
    data, entries = _load(index_path)
    logs: List[str] = []
    if not entries:
        return {"total": 0}, ["无 entries"]

    work = filter_by_dynasty(entries, dynasty_id)
    if dynasty_id:
        logs.append(f"朝代过滤 {dynasty_id}: {len(work)} 条参与")

    def _checkpoint() -> None:
        data["entries"] = entries
        index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    stats = annotate(
        work,
        use_llm=use_llm,
        force=force,
        no_empty=no_empty,
        on_batch_done=_checkpoint if use_llm else None,
    )
    data["entries"] = entries
    index_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logs.append("人物标签 " + " ".join(f"{k}={v}" for k, v in stats.items()))
    review_n = sum(1 for e in entries if (_auto(e).get(META_REVIEW)))
    if review_n:
        logs.append(f"待人工审核 {review_n} 条（不阻断 enrichment）")
    return stats, logs


def mark_for_retag(entry: dict) -> None:
    if is_locked(entry):
        return
    auto = _auto(entry)
    auto.pop(META_FP, None)
    auto.pop(META_EMPTY, None)
    auto.pop(META_REVIEW, None)
    entry[TAG] = ""
    entry[TAG_REASON] = ""
    entry[TAG_CONF] = None


def should_remediate(entry: dict) -> bool:
    if not is_eligible(entry) or is_locked(entry):
        return False
    tag = (entry.get(TAG) or "").strip()
    if not tag:
        return False
    name = (entry.get("史略名称") or "").strip()
    if ABSENCE_META_RE.search(tag):
        return True
    if _tag_about_other(name, tag):
        return True
    return False


def remediate_index(
    index_path: Path,
    *,
    use_llm: bool = False,
) -> Tuple[Dict[str, int], List[str]]:
    data, entries = _load(index_path)
    logs: List[str] = []
    cleared = 0
    for entry in entries:
        if should_remediate(entry):
            mark_for_retag(entry)
            cleared += 1
    logs.append(f"已清除待重标标签 {cleared} 条")
    data["entries"] = entries
    index_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    stats = {"cleared": cleared, "llm": 0, "empty": 0, "failed": 0}
    if use_llm and cleared:
        llm_stats, llm_logs = annotate_index(index_path, use_llm=True, force=False)
        stats.update({k: llm_stats.get(k, 0) for k in ("llm", "empty", "failed", "total")})
        logs.extend(llm_logs)
    return stats, logs


def verify_all(entries: List[dict]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    for entry in entries:
        if not is_eligible(entry):
            continue
        issues.extend(validate_tag(entry))
    return len(issues) == 0, issues


def qc_report(entries: List[dict]) -> Dict[str, object]:
    flagged: List[dict] = []
    empty = 0
    tagged = 0
    for entry in entries:
        if not is_eligible(entry):
            continue
        tag = (entry.get(TAG) or "").strip()
        if tag:
            tagged += 1
        else:
            empty += 1
        notes = qc_entry(entry)
        if notes:
            flagged.append({
                "史略ID": entry.get("史略ID"),
                "史略名称": entry.get("史略名称"),
                "史略分类": entry.get("史略分类"),
                "人物标签": tag,
                "人物标签置信度": entry.get(TAG_CONF),
                "问题": notes,
            })
    by_kind: Dict[str, int] = {}
    for row in flagged:
        for note in row["问题"]:
            key = note.split("」")[0] if "」" in note else note[:24]
            by_kind[key] = by_kind.get(key, 0) + 1
    return {
        "eligible": tagged + empty,
        "tagged": tagged,
        "empty": empty,
        "flagged": len(flagged),
        "by_kind": by_kind,
        "items": flagged,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="史略人物标签（全局 enrichment）")
    ap.add_argument("index_path", type=Path)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--remediate", action="store_true", help="清除元描述/他人主体标签并重标")
    ap.add_argument("--qc", action="store_true", help="质检已标注标签，输出问题清单")
    ap.add_argument("--qc-out", type=Path, default=None, help="--qc 报告 JSON 路径")
    ap.add_argument("--dynasty-id", default=None)
    ap.add_argument("--no-empty", action="store_true", help="二期补全模式：所有条目都必须有标签，禁止留空")
    args = ap.parse_args()

    data, entries = _load(args.index_path)
    if args.remediate:
        stats, logs = remediate_index(args.index_path, use_llm=args.llm)
        for ln in logs:
            _log(ln)
        _log("📊 remediate " + " ".join(f"{k}={v}" for k, v in stats.items()))
        return

    if args.qc:
        report = qc_report(entries)
        _log(
            f"质检: 适用 {report['eligible']} 条 | 有标签 {report['tagged']} | "
            f"留空 {report['empty']} | 问题 {report['flagged']}"
        )
        for kind, cnt in sorted(report["by_kind"].items(), key=lambda x: -x[1]):
            _log(f"  · {kind}: {cnt}")
        for row in report["items"][:30]:
            _log(
                f"  [{row['史略ID']}] {row['史略名称']} → {row['人物标签']!r} | "
                + "；".join(row["问题"])
            )
        if len(report["items"]) > 30:
            _log(f"  ... 另有 {len(report['items']) - 30} 条")
        if args.qc_out:
            args.qc_out.parent.mkdir(parents=True, exist_ok=True)
            args.qc_out.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            _log(f"报告已写: {args.qc_out}")
        return

    if args.verify:
        ok, issues = verify_all(entries)
        if not ok:
            _log(f"❌ 人物标签校验失败（{len(issues)} 项）:")
            for line in issues[:40]:
                _log(f"  {line}")
            sys.exit(1)
        tagged = sum(1 for e in entries if is_eligible(e) and (e.get(TAG) or "").strip())
        empty = sum(1 for e in entries if is_eligible(e) and not (e.get(TAG) or "").strip())
        _log(f"✅ 人物标签校验通过（有标签 {tagged}，留空 {empty}）")
        return

    if args.dry_run:
        n = sum(1 for e in entries if is_eligible(e) and not is_fresh(e))
        _log(f"DRY-RUN: 待标注约 {n} 条（--llm 将调用模型）")
        return

    stats, logs = annotate_index(
        args.index_path,
        use_llm=args.llm,
        force=args.force,
        dynasty_id=args.dynasty_id,
        no_empty=args.no_empty,
    )
    for ln in logs:
        _log(ln)
    _log("📊 " + " ".join(f"{k}={v}" for k, v in stats.items()))


if __name__ == "__main__":
    main()
