#!/usr/bin/env python3
"""批量跑 v2 单卷标注；identity_gate 失败时从 v1 skeleton 同步 category 后 --skip-1a 重试。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUN = ROOT / "tools/openclaw-historiography/historiography-annotate-v2/scripts/run_v2_volume_llm.py"
V1 = ROOT / "data/03索引标注条目"
WORK = ROOT / "data/05工作流中间产物/标注-v2"
OUT = ROOT / "data/10新标注条目"


def v1_categories(vol: str) -> dict[str, str]:
    vol = vol.zfill(3)
    files = list(V1.glob(f"01史记_{vol}_*_skeleton.json"))
    if not files:
        return {}
    sk = json.loads(files[0].read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for e in sk.get("entries") or sk.get("标注条目") or []:
        name = (e.get("史略名称") or e.get("name") or "").strip()
        cat = (e.get("史略分类") or e.get("category") or "").strip()
        if name and cat:
            out[name] = cat
            # 别名：滕公（夏侯婴）→ 夏侯婴
            m = re.match(r"^(.+?)（(.+?)）$", name)
            if m:
                out[m.group(2)] = cat
                out[m.group(1)] = cat
    return out


def fix_protagonists_from_v1(work: str, vol: str) -> bool:
    pp = WORK / f"{work}_{vol.zfill(3)}_protagonists.json"
    if not pp.is_file():
        return False
    cats = v1_categories(vol)
    if not cats:
        return False
    data = json.loads(pp.read_text(encoding="utf-8"))
    changed = False
    for p in data.get("protagonists") or []:
        name = (p.get("name") or "").strip()
        old = (p.get("category") or "").strip()
        new = cats.get(name)
        if not new:
            for k, v in cats.items():
                if k in name or name in k:
                    new = v
                    break
        if new and new != old:
            p["category"] = new
            changed = True
            print(f"  修正 {name}: {old} → {new}", flush=True)
    if changed:
        pp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def skeleton_exists(vol: str) -> bool:
    return bool(list(OUT.glob(f"01史记_{vol.zfill(3)}_*_skeleton.json")))


def run_vol(vol: str) -> bool:
    vol = vol.zfill(3)
    if skeleton_exists(vol):
        print(f"⏭ 091.. 跳过 {vol}（已有 skeleton）", flush=True)
        return True

    env = {**dict(__import__("os").environ)}
    cmd = [sys.executable, str(RUN), "--work", "01史记", "--vol", vol]

    print(f"\n{'='*60}\n▶ 01史记 {vol}\n{'='*60}", flush=True)
    r = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    print(r.stdout, end="", flush=True)
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr, flush=True)

    if r.returncode == 0:
        print(f"✅ {vol} 完成", flush=True)
        return True

    if "identity_gate" in (r.stdout + r.stderr):
        print(f"⚠ {vol} identity_gate 失败，尝试 v1 分类修正…", flush=True)
        if fix_protagonists_from_v1("01史记", vol):
            cmd2 = cmd + ["--skip-1a"]
            r2 = subprocess.run(cmd2, cwd=str(ROOT), env=env, capture_output=True, text=True)
            print(r2.stdout, end="", flush=True)
            if r2.stderr:
                print(r2.stderr, end="", file=sys.stderr, flush=True)
            if r2.returncode == 0:
                print(f"✅ {vol} 修正后完成", flush=True)
                return True
        print(f"❌ {vol} 仍失败", flush=True)
        return False

    print(f"❌ {vol} 失败 (code {r.returncode})", flush=True)
    return False


def main() -> int:
    vols = [f"{v:03d}" for v in range(int(sys.argv[1]), int(sys.argv[2]) + 1)] if len(sys.argv) >= 3 else [
        f"{v:03d}" for v in range(92, 106)
    ]
    ok, fail = [], []
    for vol in vols:
        if run_vol(vol):
            ok.append(vol)
        else:
            fail.append(vol)
    print(f"\n汇总: 成功 {len(ok)} · 失败 {len(fail)}", flush=True)
    if fail:
        print("失败卷:", ", ".join(fail), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
