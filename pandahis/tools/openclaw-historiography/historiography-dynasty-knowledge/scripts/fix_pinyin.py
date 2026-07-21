#!/usr/bin/env python3
"""批量清除对客正文与中间产物中的拼音括注。

规则 SSOT：dynasty_supplement_lib.clean_over_pinyin（删除一切拼音括注，保留纯「今…」地名）

用法：
  python3 fix_pinyin.py --scope details --apply     # 06/详情/
  python3 fix_pinyin.py --scope translate --apply   # 04史料翻译/ 单条 JSON
  python3 fix_pinyin.py --scope plans --apply       # 05工作流中间产物/翻译/*.plan.json
  python3 fix_pinyin.py --scope all --apply         # 以上全部
  python3 fix_pinyin.py --id-range 561 585 --apply  # 限定 GLBL ID 范围（details）
  python3 fix_pinyin.py --file path/to/GLBL_xxx.json --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
OPENCLAW_ROOT = SCRIPTS_DIR.parent.parent
sys.path.insert(0, str(OPENCLAW_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from paths_config import (  # noqa: E402
    DIR_DYNASTY_KNOWLEDGE,
    DIR_INTERMEDIATE,
    DIR_TRANSLATIONS,
    SUBDIR_DYNASTY_KNOWLEDGE_DETAILS,
    SUBDIR_INTERMEDIATE_TRANSLATE,
    get_histograph_root,
)

import dynasty_supplement_lib as dkl  # noqa: E402

ROOT = get_histograph_root()
DETAILS_DIR = ROOT / "data" / DIR_DYNASTY_KNOWLEDGE / SUBDIR_DYNASTY_KNOWLEDGE_DETAILS
TRANSLATE_DIR = ROOT / "data" / DIR_TRANSLATIONS
PLANS_DIR = ROOT / "data" / DIR_INTERMEDIATE / SUBDIR_INTERMEDIATE_TRANSLATE
MOTHERS_GLOB = "*.mother*.json"
AGGREGATE_PATH = TRANSLATE_DIR / "史略翻译_汇总.json"
DYNASTY_AGGREGATE_PATH = DETAILS_DIR.parent / "朝代知识详情_汇总.json"

# plan 提示语中需剔除的注音指令片段
_HINT_STRIP_PATTERNS = [
    re.compile(r"[；;，,、]?\s*[^；;，,、]*注音[^；;，,、]*"),
    re.compile(r"[；;，,、]?\s*[^；;，,、]*生僻字[^；;，,、]*"),
    re.compile(r"[；;，,、]?\s*[^；;，,、]*需标注[^；;，,、]*"),
    re.compile(r"[「\"“][^」\"”]+[」\"”][（(][^）)]+[）)]\s*等?生僻字[^。；;]*[。；;]?"),
    re.compile(r"[；;，,、]?\s*[^；;，,、]*拼音[^；;，,、]*"),
    re.compile(r"只标生僻字[^；;，,、]*"),
    re.compile(r"严格遵守注音规则[^；;，,、]*"),
    re.compile(r"[（(][a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü][^）)]*[）)]"),
]


def glbl_num(path: Path) -> int | None:
    m = re.search(r"GLBL_(\d+)", path.name)
    return int(m.group(1)) if m else None


def clean_hint_text(text: str) -> tuple[str, bool]:
    """清洗 plan 提示字段中的注音指令。"""
    original = text
    cleaned, pinyin_changes = dkl.clean_over_pinyin(text)
    for pat in _HINT_STRIP_PATTERNS:
        cleaned = pat.sub("", cleaned)
    cleaned = re.sub(r"[；;]{2,}", "；", cleaned)
    cleaned = re.sub(r"^[；;，,、\s]+|[；;，,、\s]+$", "", cleaned)
    return cleaned, cleaned != original or bool(pinyin_changes)


def _walk_json_strings(obj: Any) -> tuple[Any, list[str]]:
    """递归清洗 JSON 中所有字符串值。"""
    changes: list[str] = []
    if isinstance(obj, str):
        cleaned, changed = clean_hint_text(obj)
        if changed:
            if cleaned != obj:
                changes.append(f"…{obj[:40]}… → …{cleaned[:40]}…")
            else:
                changes.append("hint stripped")
        return cleaned, changes
    if isinstance(obj, list):
        out: list[Any] = []
        for item in obj:
            new_item, sub = _walk_json_strings(item)
            out.append(new_item)
            changes.extend(sub)
        return out, changes
    if isinstance(obj, dict):
        out_dict: dict[str, Any] = {}
        for k, v in obj.items():
            new_v, sub = _walk_json_strings(v)
            out_dict[k] = new_v
            changes.extend(sub)
        return out_dict, changes
    return obj, changes


def process_json_text_fields(path: Path, fields: tuple[str, ...], *, apply: bool) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    changes: list[str] = []
    updated = False

    def clean_field(obj: dict[str, Any], key: str) -> None:
        nonlocal updated
        if key not in obj:
            return
        raw = str(obj.get(key, ""))
        cleaned, sub = dkl.clean_over_pinyin(raw)
        if sub:
            changes.extend([f"{path.name}/{key}: {c}" for c in sub[:5]])
            obj[key] = cleaned
            updated = True

    if isinstance(doc, dict):
        for key in fields:
            clean_field(doc, key)
    if updated and apply:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changes


def process_detail_file(path: Path, *, apply: bool) -> list[str]:
    return process_json_text_fields(path, ("翻译详情",), apply=apply)


def process_mother_file(path: Path, *, apply: bool) -> list[str]:
    return process_json_text_fields(
        path, ("母本顺译", "翻译详情", "draft", "正文"), apply=apply
    )


def process_plan_file(path: Path, *, apply: bool) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    new_doc, hint_changes = _walk_json_strings(doc)
    if not hint_changes:
        return []
    if apply:
        path.write_text(json.dumps(new_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [f"{path.name}: {len(hint_changes)} 处提示/注音已清洗"]


def process_aggregate(path: Path, *, apply: bool) -> list[str]:
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    entries = doc if isinstance(doc, list) else doc.get("entries") or doc.get("史略") or []
    if not isinstance(entries, list):
        return []
    all_changes: list[str] = []
    touched = 0
    for item in entries:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("翻译详情", ""))
        cleaned, changes = dkl.clean_over_pinyin(raw)
        if not changes:
            continue
        touched += 1
        item["翻译详情"] = cleaned
        all_changes.extend(changes[:3])
    if touched and apply:
        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if touched:
        return [f"{path.name}: {touched} 条，示例 {all_changes[:5]}"]
    return []


def collect_paths(
    scope: str,
    *,
    id_range: tuple[int, int] | None,
    extra_files: list[Path],
) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {"details": [], "translate": [], "plans": [], "mothers": []}

    if scope in ("details", "all"):
        for p in sorted(DETAILS_DIR.glob("GLBL_*.json")):
            if id_range:
                n = glbl_num(p)
                if n is None or not (id_range[0] <= n <= id_range[1]):
                    continue
            out["details"].append(p)

    if scope in ("translate", "all"):
        for p in sorted(TRANSLATE_DIR.glob("GLBL_*.json")):
            if id_range:
                n = glbl_num(p)
                if n is None or not (id_range[0] <= n <= id_range[1]):
                    continue
            out["translate"].append(p)

    if scope in ("plans", "all"):
        out["plans"] = sorted(PLANS_DIR.glob("*.plan.json"))

    if scope in ("mothers", "all"):
        out["mothers"] = sorted(PLANS_DIR.glob(MOTHERS_GLOB))

    for f in extra_files:
        if f.suffix == ".json":
            if "plan" in f.name:
                out["plans"].append(f)
            elif f.parent == DETAILS_DIR or "详情" in str(f):
                out["details"].append(f)
            else:
                out["translate"].append(f)

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="清除正文与 plan 提示中的拼音括注")
    parser.add_argument(
        "--scope",
        choices=("details", "translate", "plans", "mothers", "all"),
        default="details",
        help="清洗范围（默认 details）",
    )
    parser.add_argument("--id-range", nargs=2, type=int, metavar=("FROM", "TO"))
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="写回文件（默认仅预览）")
    args = parser.parse_args()

    id_range = tuple(args.id_range) if args.id_range else None
    groups = collect_paths(args.scope, id_range=id_range, extra_files=args.file)

    if not any(groups.values()) and args.scope != "translate":
        print("未找到待处理文件", file=sys.stderr)
        return 1

    total_changes = 0
    touched = 0

    for path in sorted(set(groups["details"])):
        if not path.is_file():
            continue
        changes = process_detail_file(path, apply=args.apply)
        if changes:
            touched += 1
            total_changes += len(changes)
            for line in changes[:5]:
                print(line)
            if len(changes) > 5:
                print(f"  …共 {len(changes)} 处")

    for path in sorted(set(groups["translate"])):
        if not path.is_file():
            continue
        changes = process_detail_file(path, apply=args.apply)
        if changes:
            touched += 1
            total_changes += len(changes)
            for line in changes[:5]:
                print(line)
            if len(changes) > 5:
                print(f"  …共 {len(changes)} 处")

    if args.scope in ("translate", "all"):
        for line in process_aggregate(AGGREGATE_PATH, apply=args.apply):
            print(line)
            touched += 1

    if args.scope in ("details", "all"):
        for line in process_aggregate(DYNASTY_AGGREGATE_PATH, apply=args.apply):
            print(line)
            touched += 1

    for path in sorted(set(groups["plans"])):
        if not path.is_file():
            continue
        changes = process_plan_file(path, apply=args.apply)
        if changes:
            touched += 1
            total_changes += len(changes)
            for line in changes:
                print(line)

    for path in sorted(set(groups["mothers"])):
        if not path.is_file():
            continue
        changes = process_mother_file(path, apply=args.apply)
        if changes:
            touched += 1
            total_changes += len(changes)
            print(f"{path.name}: {len(changes)} 处")

    mode = "已写回" if args.apply else "预览"
    print(f"\n{mode}：{touched} 个文件/批次，约 {total_changes} 处变更")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
