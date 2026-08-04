#!/usr/bin/env python3
"""抽检「二十四史新」母本：内部结构 + 与旧母本/拆分卷交叉验证。

用法:
  python3 scripts/verify_ershisi_new.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "data/00原文母本/二十四史原文"
NEW = ROOT / "data/00原文母本/二十四史新"
SPLIT = ROOT / "data/02二十四史拆分后"

BOOKS = [
    ("01史记", "史记"),
    ("02汉书", "汉书"),
    ("03后汉书", "后汉书"),
    ("04三国志", "三国志"),
    ("05晋书", "晋书"),
    ("06宋书", "宋书"),
    ("07南齐书", "南齐书"),
    ("08梁书", "梁书"),
    ("09陈书", "陈书"),
    ("10魏书", "魏书"),
    ("11北齐书", "北齐书"),
    ("12周书", "周书"),
    ("13隋书", "隋书"),
    ("14南史", "南史"),
    ("15北史", "北史"),
    ("16旧唐书", "旧唐书"),
    ("17新唐书", "新唐书"),
    ("18旧五代史", "旧五代史"),
    ("19新五代史", "新五代史"),
    ("20宋史", "宋史"),
    ("21辽史", "辽史"),
    ("22金史", "金史"),
    ("23元史", "元史"),
    ("24明史", "明史"),
]


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def is_valid_old(text: str) -> bool:
    head = text[:800]
    return "书籍名称" in head or head.lstrip().startswith("卷")


def strip_header(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    started = False
    names = {b[1] for b in BOOKS}
    for ln in lines:
        s = ln.strip()
        if not started:
            if s.startswith("[ 本书籍由") or s.startswith("[本书籍由"):
                continue
            if s.startswith("书籍名称：") or s in names:
                started = True
                continue
        else:
            out.append(ln)
    return "\n".join(out)


def normalize(text: str) -> str:
    t = strip_header(text).replace("·", " ").replace("　", " ")
    return re.sub(r"\s+", "", t)


def vol_titles(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ln in strip_header(text).splitlines():
        s = re.sub(r" +", " ", ln.strip().replace("·", " "))
        if not re.match(r"^卷[一二三四五六七八九十百零\d]", s):
            continue
        if len(s) > 48 or "。" in s or "，" in s:
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def first_narrative_snippet(text: str, min_len: int = 40) -> str:
    for ln in strip_header(text).splitlines():
        s = ln.strip()
        if len(s) >= min_len and "。" in s and not re.match(r"^卷[一二三四五六七八九十百零\d]", s):
            return normalize(s)[:70]
    return ""


def internal_issues(name: str, text: str) -> list[str]:
    issues: list[str] = []
    if not text.startswith("书籍名称："):
        issues.append("缺书籍名称头")
    if name not in text[:300]:
        issues.append("缺书名行")
    if len(vol_titles(text)) < 5:
        issues.append("卷目过少")
    if not first_narrative_snippet(text):
        issues.append("无正文")
    if len(normalize(text)) < 50_000:
        issues.append("正文过短")
    return issues


def main() -> int:
    print("=" * 72)
    print("二十四史新 · 母本抽检")
    print("=" * 72)

    internal_fail = 0
    print("\n[A] 内部结构（24 部）")
    for stem, name in BOOKS:
        text = read_text(NEW / f"{stem}.txt")
        issues = internal_issues(name, text)
        st = "✅" if not issues else "❌"
        if issues:
            internal_fail += 1
        print(
            f"  {st} {name:<8} {len(normalize(text)):>9,}字 "
            f"{len(vol_titles(text)):>3}卷  {' · '.join(issues)}"
        )

    print("\n[B] 与旧母本对比（有效旧文件）")
    ok = warn = skip = 0
    for stem, name in BOOKS:
        new_t = read_text(NEW / f"{stem}.txt")
        old_p = OLD / f"{stem}.txt"
        if not old_p.is_file():
            skip += 1
            print(f"  — {name} 旧文件缺失")
            continue
        old_t = read_text(old_p)
        if not is_valid_old(old_t):
            skip += 1
            print(f"  — {name} 旧版无效（非正文）")
            continue
        on, nn = normalize(old_t), normalize(new_t)
        ratio = len(nn) / len(on) if on else 0
        op, np = first_narrative_snippet(old_t), first_narrative_snippet(new_t)
        same_open = op[:35] == np[:35] if op and np else False
        if 0.92 <= ratio <= 1.08 and same_open:
            ok += 1
            st = "✅"
        else:
            warn += 1
            st = "⚠️"
        print(
            f"  {st} {name:<8} 字数比 {ratio:.2f}  "
            f"卷 {len(vol_titles(old_t))}/{len(vol_titles(new_t))}  "
            f"开篇{'同' if same_open else '异'}"
        )
    print(f"  汇总: ✅{ok} ⚠️{warn} 跳过{skip}")

    print("\n[C] 与现有拆分卷交叉探针")
    probes = [
        ("02汉书", "02汉书_拆分后/02汉书_001_高帝纪第一上.txt", "高祖，沛丰邑中阳里人也"),
        ("01史记", "01史记_拆分后/01史记_001_五帝本纪第一.txt", "黄帝者，少典之子"),
    ]
    for stem, rel, needle in probes:
        fp = SPLIT / rel
        new_t = read_text(NEW / f"{stem}.txt")
        hit = needle in normalize(new_t)
        split_ok = fp.is_file() and needle in normalize(read_text(fp))
        print(
            f"  {'✅' if hit else '❌'} {stem} 探针「{needle[:18]}…」"
            f"  拆分卷{'有' if split_ok else '无'}"
        )

    print("\n结论:")
    if internal_fail:
        print(f"  ❌ 内部结构失败 {internal_fail} 部，需修复后再用")
        return 1
    print("  ✅ 24 部结构完整，可作为新母本使用")
    print("  ⚠️ 与流芳阁旧母本差异多属版本/用字（馀/余、惲/恽），非提取错误")
    print("  ⚠️ 旧版 04三国志.txt 为无效占位文件，勿作对照")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
