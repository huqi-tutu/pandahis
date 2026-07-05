"""扫描著作 skeleton，列出 Step4 正式字段缺失 / 疑似批量跳过终检的卷。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

from lib.config import ANNOTATE_DIR, PIPELINE_DIR, paths

sys.path.insert(0, str(ANNOTATE_DIR))
from fill_fields import STEP4_FORMAL_FIELDS, entry_missing_fields  # noqa: E402

sys.path.insert(0, str(PIPELINE_DIR))
from hist_gates import parse_skeleton_path  # noqa: E402


def list_skeletons(work: str) -> List[Path]:
    return sorted(paths()["annotations"].glob(f"{work}_*_skeleton.json"))


def audit_skeleton(sk: Path) -> Tuple[str, str, List[str]]:
    work, vol = parse_skeleton_path(sk)
    data = json.loads(sk.read_text(encoding="utf-8"))
    missing_all: List[str] = []
    for entry in data.get("entries", []):
        eid = entry.get("史略ID", "?")
        miss = entry_missing_fields(entry)
        if miss:
            missing_all.append(f"{eid}: {', '.join(miss)}")
    has_temp = any("_needs_llm" in e or "_auto_filled" in e for e in data.get("entries", []))
    issues = list(missing_all)
    if has_temp:
        issues.append("含未 finalize 的 _needs_llm/_auto_filled")
    return work, vol, issues


def run_audit(work: str, *, only_issues: bool = True) -> int:
    skeletons = list_skeletons(work)
    if not skeletons:
        print(f"⚠️ 未找到 {work} 的 skeleton")
        return 1

    bad = 0
    ok_count = 0
    print(f"\n🔍 {work} skeleton 审计（Step4 正式字段）共 {len(skeletons)} 卷\n")
    for sk in skeletons:
        try:
            _, vol, issues = audit_skeleton(sk)
        except Exception as e:
            print(f"  ❌ {sk.name}: 无法解析 ({e})")
            bad += 1
            continue
        if issues:
            bad += 1
            print(f"  ❌ 卷{vol} {sk.name}")
            for line in issues[:8]:
                print(f"      - {line}")
            if len(issues) > 8:
                print(f"      … 另有 {len(issues) - 8} 条")
        elif not only_issues:
            ok_count += 1
            print(f"  ✅ 卷{vol}")

    if only_issues and bad == 0:
        print("  ✅ 未发现 Step4 正式字段缺失")
    elif not only_issues:
        print(f"\n汇总: 问题 {bad} 卷，通过 {ok_count} 卷")
    else:
        print(f"\n汇总: {bad} 卷需修复（单卷: HIST_REPAIR=1 + fill_fields → verify → finalize）")
    return 1 if bad else 0
