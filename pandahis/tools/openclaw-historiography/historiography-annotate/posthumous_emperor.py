#!/usr/bin/env python3
"""
追尊帝王：补录帝王.json + skeleton 君纪/士臣双条目。

规则：
- 君纪：即位=退位=开国年；政权/朝代同开国君主
- 士臣：与君纪同名、同段落、同原文；年份按士臣叙事逻辑
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from coordinate_index import COORD_FIELDS, coords_from_emperor, emperor_row_name, migrate_entry_fields
from emperor_resolve import build_emperor_info_index, ensure_emperor_coord_chain

SKILL_DIR = Path(__file__).resolve().parent
CONFIG_JSON = SKILL_DIR / "reference" / "帝王追尊.json"
EMPEROR_JSON = SKILL_DIR / "reference" / "帝王.json"
ALIAS_JSON = SKILL_DIR / "reference" / "帝王别名.json"


def _slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE).strip("_").lower()
    return s or "unknown"


def load_config() -> dict:
    with open(CONFIG_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_emperor_rows() -> List[dict]:
    with open(EMPEROR_JSON, encoding="utf-8-sig") as f:
        rows = json.load(f)
    return [{k.lstrip("\ufeff"): v for k, v in r.items()} for r in rows]


def build_posthumous_row(group: dict, member: dict) -> dict:
    fy = group["founding_year"]
    emperor = member["帝王"]
    row = {
        "帝王名称": emperor,
        "政权": group["政权"],
        "朝代": group["朝代"],
        "文明": group["文明"],
        "帝王原名": member.get("帝王名字", member.get("帝王原名", emperor)),
        "庙号": member.get("庙号", ""),
        "年号": "-",
        "即位时间": str(fy),
        "退位时间": str(fy),
        "在位时长": "0",
        "重要性评级": member.get("重要性评级", "4"),
        "标签": member.get("标签", "追尊"),
    }
    ensure_emperor_coord_chain(row)
    return row


def merge_posthumous_into_emperor_json(*, dry_run: bool = False) -> Tuple[int, List[str]]:
    cfg = load_config()
    rows = load_emperor_rows()
    by_name = {emperor_row_name(r): i for i, r in enumerate(rows)}
    logs: List[str] = []
    changed = 0

    for group in cfg.get("groups", {}).values():
        fy = group["founding_year"]
        for member in group.get("members", []):
            emperor = member["帝王"]
            rename_from = member.get("rename_from")
            if rename_from and rename_from in by_name:
                idx = by_name.pop(rename_from)
                row = rows[idx]
                row["帝王名称"] = emperor
                row["帝王原名"] = member.get("帝王名字", member.get("帝王原名", emperor))
                row["庙号"] = member.get("庙号", row.get("庙号", ""))
                row["政权"] = group["政权"]
                row["朝代"] = group["朝代"]
                row["文明"] = group["文明"]
                row["即位时间"] = str(fy)
                row["退位时间"] = str(fy)
                row["在位时长"] = "0"
                tag = member.get("标签", "追尊")
                row["标签"] = tag
                by_name[emperor] = idx
                logs.append(f"更名「{rename_from}」→「{emperor}」（追尊年 {fy}）")
                changed += 1
                continue

            if emperor in by_name:
                idx = by_name[emperor]
                row = rows[idx]
                row["即位时间"] = str(fy)
                row["退位时间"] = str(fy)
                row["政权"] = group["政权"]
                row["朝代"] = group["朝代"]
                row["标签"] = member.get("标签", row.get("标签", "追尊"))
                logs.append(f"更新「{emperor}」追尊年 → {fy}")
                changed += 1
                continue

            row = build_posthumous_row(group, member)
            rows.append(row)
            by_name[emperor] = len(rows) - 1
            logs.append(f"补录「{emperor}」")
            changed += 1

    if changed and not dry_run:
        with open(EMPEROR_JSON, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")
        _sync_aliases(cfg)

    return changed, logs


def _sync_aliases(cfg: dict) -> None:
    alias_data = {"global": {}, "strip_prefixes": [], "by_work": {}}
    if ALIAS_JSON.exists():
        with open(ALIAS_JSON, encoding="utf-8") as f:
            alias_data = json.load(f)
    g = alias_data.setdefault("global", {})
    for group in cfg.get("groups", {}).values():
        for member in group.get("members", []):
            canonical = member["帝王"]
            g[canonical] = canonical
            for a in member.get("别名", []):
                g[a] = canonical
            if member.get("rename_from"):
                g[member["rename_from"]] = canonical
    with open(ALIAS_JSON, "w", encoding="utf-8") as f:
        json.dump(alias_data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _next_entry_id(entries: list, prefix: str) -> str:
    nums = []
    for e in entries:
        m = re.match(rf"^{re.escape(prefix)}_(\d+)$", e.get("史略ID", ""))
        if m:
            nums.append(int(m.group(1)))
    n = max(nums, default=0) + 1
    return f"{prefix}_{n:02d}"


def _coords_for_emperor(name: str) -> dict:
    eidx = build_emperor_info_index()
    info = eidx.get(name)
    if not info:
        return {}
    return coords_from_emperor(info)


def _clone_entry(
    src: dict,
    *,
    new_id: str,
    category: str,
    year_start: int,
    year_end: int,
    emperor_coord: Optional[str] = None,
) -> dict:
    e = copy.deepcopy(src)
    e["史略ID"] = new_id
    e["史略分类"] = category
    e["史略开始年"] = year_start
    e["史略结束年"] = year_end
    migrate_entry_fields(e)
    for old in ("三级帝王归属", "二级王朝归属", "一级文明归属"):
        e.pop(old, None)
    emp = emperor_coord or (e.get("史略名称") or "").strip()
    if category == "君纪":
        coords = _coords_for_emperor(emp)
        for k, v in coords.items():
            e[k] = v
        e["四级帝王坐标"] = emp
    return e


def _add_owner(attribution: list, paragraph: int, name: str, category: str) -> None:
    for row in attribution:
        if row.get("paragraph") != paragraph:
            continue
        owners = row.setdefault("owners", [])
        key = (name, category)
        if any((o.get("name"), o.get("category")) == key for o in owners):
            return
        owners.append({"name": name, "category": category})
        return


def _rename_owners(attribution: list, old: str, new: str, category: str) -> None:
    for row in attribution:
        for o in row.get("owners", []):
            if o.get("category") == category and o.get("name") == old:
                o["name"] = new


def patch_shiji_003(data: dict) -> List[str]:
    logs: List[str] = []
    entries = data["entries"]
    qi = next(e for e in entries if e.get("史略名称") == "契" and e.get("史略分类") == "士臣")
    if not any(e.get("史略名称") == "契" and e.get("史略分类") == "君纪" for e in entries):
        jid = _next_entry_id(entries, "SHIJI_003")
        junji = _clone_entry(qi, new_id=jid, category="君纪", year_start=-1600, year_end=-1600)
        entries.insert(0, junji)
        _add_owner(data["segment_attribution"], 1, "契", "君纪")
        logs.append(f"003 新增君纪「契」{jid}（与士臣同段）")
    return logs


def patch_shiji_004(data: dict) -> List[str]:
    logs: List[str] = []
    entries = data["entries"]
    attr = data["segment_attribution"]
    eidx = build_emperor_info_index()
    fy = -1046

    # 古公亶父：君纪改年 + 士臣双条
    gugong = next(
        (e for e in entries if e.get("史略名称") == "古公亶父" and e.get("史略分类") == "君纪"),
        None,
    )
    if gugong:
        hs, he = gugong.get("史略开始年", -1200), gugong.get("史略结束年", -1180)
        if not isinstance(hs, int):
            hs, he = -1200, -1180
        gugong["史略开始年"] = fy
        gugong["史略结束年"] = fy
        for k, v in _coords_for_emperor("古公亶父").items():
            gugong[k] = v
        if not any(
            e.get("史略名称") == "古公亶父" and e.get("史略分类") == "士臣" for e in entries
        ):
            jid = _next_entry_id(entries, "SHIJI_004")
            shichen = _clone_entry(
                gugong, new_id=jid, category="士臣", year_start=hs, year_end=he,
                emperor_coord="古公亶父",
            )
            entries.append(shichen)
            for p in range(4, 8):
                _add_owner(attr, p, "古公亶父", "士臣")
            logs.append(f"004 古公亶父 君纪追尊年 + 士臣双条 {jid}")

    # 季历：君纪+士臣 段7
    if not any(e.get("史略名称") == "季历" for e in entries):
        text = (
            "古公卒，季历立，是为公季。公季脩古公遗道，笃於行义，诸侯顺之。"
        )
        base = {
            "史略名称": "季历",
            "史略简介": "公季修古公遗道笃行义诸侯顺之",
            "主要史料出处": "《史记·周本纪》",
            "paragraphs": [{"volume": "周本纪", "paragraph_from": 7, "paragraph_to": 7}],
            "原文字句": text,
            "优先级": "P2",
            "优先级判定理由": "周先公季历修古公之道诸侯顺之",
        }
        jid = _next_entry_id(entries, "SHIJI_004")
        junji = {**base, "史略ID": jid, "史略分类": "君纪",
                 "史略开始年": fy, "史略结束年": fy}
        for k, v in _coords_for_emperor("季历").items():
            junji[k] = v
        junji["四级帝王坐标"] = "季历"
        sid = _next_entry_id(entries + [junji], "SHIJI_004")
        shichen = {**base, "史略ID": sid, "史略分类": "士臣",
                   "史略开始年": -1190, "史略结束年": -1185}
        for k, v in _coords_for_emperor("季历").items():
            shichen[k] = v
        shichen["四级帝王坐标"] = "季历"
        entries.extend([junji, shichen])
        _add_owner(attr, 7, "季历", "君纪")
        _add_owner(attr, 7, "季历", "士臣")
        logs.append(f"004 新增季历 君纪{jid}+士臣{sid}")

    # 姬昌：周文王 → 姬昌
    jichang = next(
        (e for e in entries if e.get("史略名称") in ("周文王", "姬昌") and e.get("史略分类") == "君纪"),
        None,
    )
    if jichang:
        hs, he = jichang.get("史略开始年", -1099), jichang.get("史略结束年", -1050)
        if not isinstance(hs, int):
            hs, he = -1099, -1050
        old_name = jichang.get("史略名称")
        jichang["史略名称"] = "姬昌"
        jichang["史略开始年"] = fy
        jichang["史略结束年"] = fy
        for k, v in _coords_for_emperor("姬昌").items():
            jichang[k] = v
        jichang["四级帝王坐标"] = "姬昌"
        if old_name != "姬昌":
            _rename_owners(attr, old_name, "姬昌", "君纪")
            logs.append(f"004 君纪「{old_name}」→「姬昌」")
        if not any(
            e.get("史略名称") == "姬昌" and e.get("史略分类") == "士臣" for e in entries
        ):
            jid = _next_entry_id(entries, "SHIJI_004")
            shichen = _clone_entry(
                jichang, new_id=jid, category="士臣", year_start=hs, year_end=he,
                emperor_coord="姬昌",
            )
            entries.append(shichen)
            for p in range(8, 14):
                _add_owner(attr, p, "姬昌", "士臣")
            logs.append(f"004 姬昌 士臣双条 {jid}")

    return logs


def patch_skeleton(path: Path) -> List[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = path.name
    if "003_" in name:
        logs = patch_shiji_003(data)
    elif "004_" in name:
        logs = patch_shiji_004(data)
    else:
        return []
    if logs:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return logs


def main() -> int:
    parser = argparse.ArgumentParser(description="追尊帝王补录与 skeleton 双条")
    parser.add_argument("--merge-json", action="store_true", help="写入帝王.json")
    parser.add_argument("--patch-skeleton", nargs="*", help="skeleton 路径")
    parser.add_argument("--work", help="如 01史记，仅补 003/004")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.merge_json:
        n, logs = merge_posthumous_into_emperor_json(dry_run=args.dry_run)
        print(f"帝王.json 变更 {n} 条")
        for line in logs:
            print(f"  {line}")

    paths: List[Path] = []
    if args.work == "01史记":
        from lib_config import paths as hp

        ann = hp()["annotations"]
        paths.extend([ann / "01史记_003_殷本纪第三_skeleton.json",
                      ann / "01史记_004_周本纪第四_skeleton.json"])
    for p in args.patch_skeleton or []:
        paths.append(Path(p))

    for fp in paths:
        if fp.exists():
            for line in patch_skeleton(fp):
                print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
