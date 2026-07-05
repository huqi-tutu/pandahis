#!/usr/bin/env python3
"""批量将「汉高帝」统一为「汉高祖」，删除帝王表重复项，并重跑坐标对齐。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANNOTATE = ORCH.parent / "historiography-annotate"
DATA_DIR = ORCH.parents[2] / "data"
SKELETON_DIR = DATA_DIR / "03索引标注条目"

sys.path.insert(0, str(ANNOTATE))

FORBIDDEN_ID = "DW_HX_XIHAN_XIHAN_HANGAODI"
CANONICAL_ID = "DW_HX_XIHAN_XIHAN_HANGAOZU"

SPINDLE_042 = {
    "HANSHU_042_01": (
        "张耳本传从秦末反秦、巨鹿之战至归汉受封赵王，其最高爵位与政治终局在汉高祖朝确立；"
        "虽曾从项楚，但列传结论与功业归位于汉初诸侯体系，故四级帝王取汉高祖。"
    ),
    "HANSHU_042_02": (
        "陈馀与张耳合传，事迹贯穿秦末赵将合纵、楚汉战争至败亡于汉；自立代王后与汉高祖对峙，"
        "本卷叙事终归于汉初天下格局，故四级帝王取汉高祖。"
    ),
}


def remove_hangaodi_from_emperor_json(path: Path) -> bool:
    if not path.is_file():
        return False
    rows = json.loads(path.read_text(encoding="utf-8"))
    new_rows = [r for r in rows if (r.get("帝王ID") or "").strip() != FORBIDDEN_ID]
    if len(new_rows) == len(rows):
        return False
    path.write_text(json.dumps(new_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def fix_text(s: str) -> str:
    if not s:
        return s
    s = s.replace("汉高帝刘邦", "汉高祖刘邦")
    s = s.replace("汉高帝朝", "汉高祖朝")
    s = s.replace("汉高帝时期", "汉高祖时期")
    s = s.replace("汉高帝", "汉高祖")
    s = s.replace(FORBIDDEN_ID, CANONICAL_ID)
    return s


def fix_skeleton(path: Path, *, is_042: bool) -> list[str]:
    logs: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for entry in data.get("entries") or []:
        eid = entry.get("史略ID", "?")
        emp = (entry.get("四级帝王坐标") or "").strip()
        if emp in ("汉高帝", "项羽") and is_042:
            entry["四级帝王坐标"] = "汉高祖"
            changed = True
            logs.append(f"  [{eid}] 四级帝王 → 汉高祖")
        elif emp == "汉高帝":
            entry["四级帝王坐标"] = "汉高祖"
            changed = True
            logs.append(f"  [{eid}] 四级帝王 汉高帝 → 汉高祖")

        if (entry.get("帝王ID") or "").strip() == FORBIDDEN_ID:
            entry["帝王ID"] = CANONICAL_ID
            changed = True

        auto = entry.get("_auto_filled")
        if isinstance(auto, dict) and auto.get("_坐标主轴说明"):
            old = auto["_坐标主轴说明"]
            new = fix_text(old)
            if is_042 and eid in SPINDLE_042:
                new = SPINDLE_042[eid]
            if new != old:
                auto["_坐标主轴说明"] = new
                changed = True
                logs.append(f"  [{eid}] 主轴说明已更新")

        for key, val in list(entry.items()):
            if isinstance(val, str) and ("汉高帝" in val or FORBIDDEN_ID in val):
                fixed = fix_text(val)
                if fixed != val:
                    entry[key] = fixed
                    changed = True

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logs.insert(0, f"已写回 {path.name}")
    return logs


def run_fill(skeleton: Path, *args: str) -> tuple[int, str]:
    cmd = [sys.executable, str(ANNOTATE / "fill_fields.py"), str(skeleton), *args]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ANNOTATE))
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def main() -> int:
    emperor_paths = [
        ANNOTATE / "reference" / "帝王.json",
        DATA_DIR / "01历史坐标数据" / "帝王.json",
    ]
    for p in emperor_paths:
        if remove_hangaodi_from_emperor_json(p):
            print(f"✓ 已删除 {p} 中的汉高帝条目")
        else:
            print(f"· {p} 无需删除或不存在")

    skeletons = sorted(SKELETON_DIR.glob("02汉书*_skeleton.json"))
    affected: list[Path] = []
    for sk in skeletons:
        text = sk.read_text(encoding="utf-8")
        is_042 = "042" in sk.name
        if not (re.search(r"汉高帝|HANGAODI", text) or (is_042 and "项羽" in text)):
            continue
        logs = fix_skeleton(sk, is_042=is_042)
        for line in logs:
            print(line)
        affected.append(sk)

    print(f"\n共 {len(affected)} 个 skeleton 需 reconcile")
    failed = []
    for sk in affected:
        code, out = run_fill(sk, "--merge-auto")
        if code != 0:
            failed.append((sk.name, out[-500:]))
            print(f"✗ merge-auto 失败: {sk.name}")
            continue
        code, out = run_fill(sk, "--verify", "--require-clean")
        if code != 0:
            code2, out2 = run_fill(sk, "--finalize")
            code, out = run_fill(sk, "--verify", "--require-clean")
            if code != 0:
                failed.append((sk.name, out[-500:]))
                print(f"✗ verify 失败: {sk.name}")
                continue
        print(f"✓ {sk.name} reconcile + verify 通过")

    if failed:
        print("\n失败卷:")
        for name, tail in failed:
            print(f"  {name}: {tail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
