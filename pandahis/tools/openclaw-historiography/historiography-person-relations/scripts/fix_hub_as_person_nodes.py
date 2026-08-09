#!/usr/bin/env python3
"""清除「枢纽名误落人物层」的伪节点，并修复子女错挂在枢纽名下的链。

问题形态（魏惠王等）：
- 已有 `节点类型=二级分类` 的「父母/臣子/外敌」枢纽
- 同时又有 `关系层级=二级`、标题同为「父母/臣子/外敌」的叶子（非分类）

另：子女 `所属二级关系` 误填「配偶/正妻」时，改挂「不详」并补配偶占位节点。
"""

from __future__ import annotations

import argparse
import json
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

HUB_TITLES = frozenset(
    {
        "父母",
        "配偶",
        "兄弟姐妹",
        "君王",
        "同僚",
        "臣子",
        "内敌",
        "外敌",
        "老师",
        "学生",
        "好友",
        "正妻",  # 旧枢纽残留
    }
)


def _is_hub(rec: dict[str, Any]) -> bool:
    return str(rec.get("节点类型") or "").strip() == "二级分类"


def _title(rec: dict[str, Any]) -> str:
    return str(rec.get("关系节点标题") or "").strip()


def _ensure_unknown_spouse(rows: list[dict[str, Any]], subject: str) -> list[dict[str, Any]]:
    has_unknown = any(
        (not _is_hub(r))
        and _title(r) == "不详"
        and str(r.get("所属一级关系") or "") == "配偶"
        and str(r.get("关系层级") or "") == "二级"
        for r in rows
    )
    if has_unknown:
        return rows
    has_spouse_hub = any(
        _is_hub(r) and _title(r) == "配偶" and str(r.get("关系类别") or "") == "家庭"
        for r in rows
    )
    out = list(rows)
    if not has_spouse_hub:
        out.append(
            {
                "关联史略名称": subject,
                "关系ID": f"HD-FAM-HUB-配偶-{uuid.uuid4().hex[:6]}",
                "关系类别": "家庭",
                "关系层级": "一级",
                "关系节点标题": "配偶",
                "上级连接线标题": "",
                "节点类型": "二级分类",
                "关系简述": f"{subject}之配偶支。",
                "record_id": f"rec{uuid.uuid4().hex[:12]}",
            }
        )
    out.append(
        {
            "关联史略名称": subject,
            "关系ID": f"HD-FAM-UNK-{uuid.uuid4().hex[:6]}",
            "关系类别": "家庭",
            "关系层级": "二级",
            "关系节点标题": "不详",
            "上级连接线标题": "妻",
            "所属一级关系": "配偶",
            "关系简述": "生母不详，子女暂挂于此。",
            "record_id": f"rec{uuid.uuid4().hex[:12]}",
        }
    )
    return out


def fix_file(path: Path) -> dict[str, Any]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        return {"changed": False, "removed": 0, "remapped": 0}
    subject = path.name.replace("关系表.json", "")

    removed: list[str] = []
    kept: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if (not _is_hub(r)) and _title(r) in HUB_TITLES:
            removed.append(_title(r))
            continue
        kept.append(r)

    remapped = 0
    need_unknown = False
    fixed: list[dict[str, Any]] = []
    for r in kept:
        nr = dict(r)
        for key in ("所属二级关系", "所属三级关系"):
            v = str(nr.get(key) or "").strip()
            if v in HUB_TITLES:
                # 子女/孙辈误挂枢纽名 → 改挂「不详」
                if key == "所属二级关系" and v in {"配偶", "正妻"}:
                    nr[key] = "不详"
                    if str(nr.get("所属一级关系") or "").strip() != "配偶":
                        nr["所属一级关系"] = "配偶"
                    need_unknown = True
                    remapped += 1
                elif key == "所属三级关系" and v in {"配偶", "正妻"}:
                    # 极少见：三级链误写枢纽，改为不详并降为挂在不详下的四级需人工；此处改不详
                    nr["所属二级关系"] = "不详"
                    nr.pop("所属三级关系", None)
                    nr["关系层级"] = "三级"
                    nr["所属一级关系"] = "配偶"
                    need_unknown = True
                    remapped += 1
                else:
                    # 其他枢纽名作二级父：无法作为人物父，改挂不详（家庭）或删除链字段
                    if str(nr.get("关系类别") or "") == "家庭":
                        nr["所属一级关系"] = "配偶"
                        nr["所属二级关系"] = "不详"
                        nr.pop("所属三级关系", None)
                        if str(nr.get("关系层级") or "") not in ("三级", "四级"):
                            nr["关系层级"] = "三级"
                        need_unknown = True
                        remapped += 1
        fixed.append(nr)

    if need_unknown:
        fixed = _ensure_unknown_spouse(fixed, subject)

    if not removed and remapped == 0:
        return {"changed": False, "removed": 0, "remapped": 0, "removedTitles": []}

    path.write_text(
        json.dumps(fixed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "changed": True,
        "removed": len(removed),
        "remapped": remapped,
        "removedTitles": removed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="默认 HISTOGRAPH_ROOT/data/07人物关系",
    )
    args = parser.parse_args()

    import os
    import sys

    openclaw = Path(__file__).resolve().parents[2]
    if str(openclaw) not in sys.path:
        sys.path.insert(0, str(openclaw))
    from paths_config import histograph_paths, validate_histograph_root

    validate_histograph_root()
    paths = histograph_paths()
    rel_dir = args.dir or (paths["root"] / "data" / "07人物关系")
    out_dir = paths["root"] / "data" / "05工作流中间产物" / "人物关系补全"
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {"files": {}, "totalRemoved": 0, "totalRemapped": 0}
    for path in sorted(rel_dir.glob("*关系表.json")):
        if not args.apply:
            # dry: only count
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                continue
            phantoms = [
                _title(r)
                for r in rows
                if isinstance(r, dict) and (not _is_hub(r)) and _title(r) in HUB_TITLES
            ]
            bad_parent = 0
            for r in rows:
                if not isinstance(r, dict) or _is_hub(r):
                    continue
                for key in ("所属二级关系", "所属三级关系"):
                    if str(r.get(key) or "").strip() in HUB_TITLES:
                        bad_parent += 1
            if phantoms or bad_parent:
                report["files"][path.name] = {
                    "phantoms": phantoms,
                    "badParentRefs": bad_parent,
                }
                report["totalRemoved"] += len(phantoms)
                report["totalRemapped"] += bad_parent
        else:
            res = fix_file(path)
            if res.get("changed"):
                report["files"][path.name] = res
                report["totalRemoved"] += int(res["removed"])
                report["totalRemapped"] += int(res["remapped"])

    report["touchedFiles"] = len(report["files"])
    report["mode"] = "apply" if args.apply else "dry-run"
    out = out_dir / "hub_as_person_fix_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"{report['mode']}: files={report['touchedFiles']} "
        f"phantomRows={report['totalRemoved']} badParentRefs={report['totalRemapped']}"
    )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
