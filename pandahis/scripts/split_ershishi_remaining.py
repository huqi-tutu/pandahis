#!/usr/bin/env python3
"""拆分尚未按卷切开的二十四史原文（默认 05晋书–24明史）。

样式对齐《后汉书》《三国志》拆分：
- 输出目录：02二十四史拆分后/{书名}_拆分后/
- 文件名：{书名}_NNN_标题.txt
- 卷首行：卷号行 +（若有）短篇名，中间双空格
- 删除纯空白行，跳过「返回总目录」
- 不改动任何非空正文

正文起点：目录区后，同一卷首第二次出现处。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tools/openclaw-historiography"
sys.path.insert(0, str(SKILLS))

from paths_config import resolve_split_dir  # noqa: E402

SOURCE_DIR = ROOT / "data/00原文母本/二十四史原文"

# 按实际母本切出的文件数（含上/中/下分卷）
DEFAULT_EXPECT: dict[str, int] = {
    "05晋书": 130,
    "06宋书": 100,
    "07南齐书": 59,
    "08梁书": 56,
    "09陈书": 36,
    "10魏书": 122,
    "11北齐书": 50,
    "12周书": 50,
    "13隋书": 85,
    "14南史": 80,
    "15北史": 100,
    "16旧唐书": 214,
    "17新唐书": 248,
    "18旧五代史": 150,
    "19新五代史": 74,
    "20宋史": 496,
    "21辽史": 116,
    "22金史": 135,
    "23元史": 210,
    "24明史": 332,
}

# 卷首：卷一 帝纪第一 / 卷十七上 本纪第十七上 / 卷一（梁书） 太祖纪一
VOL_HEADER_RE = re.compile(
    r"^卷[一二三四五六七八九十百零\d上中下]+"
    r"(?:（[^）]+）)?"
    r"\s+"
    r".+$"
)
SKIP_LINE_RE = re.compile(r"^返回总目录\s*$")
HEADER_PARSE_RE = re.compile(
    r"^(卷[一二三四五六七八九十百零\d上中下]+(?:（[^）]+）)?)\s+(.+)$"
)


def normalize_title_key(title: str) -> str:
    return re.sub(r"\s+", "", title.strip())


def is_vol_header(line: str) -> bool:
    s = line.strip()
    if not s or SKIP_LINE_RE.match(s):
        return False
    if len(s) > 80:
        return False
    # 正文长句中偶含「卷×」字样
    if "。" in s and len(s) > 40:
        return False
    return bool(VOL_HEADER_RE.match(s))


def is_subtitle_line(line: str) -> bool:
    """卷首后短篇名行（非叙事句）。"""
    s = line.strip()
    if not s or SKIP_LINE_RE.match(s):
        return False
    if is_vol_header(s):
        return False
    if s.startswith("△"):
        return False
    if "。" in s:
        return False
    if len(s) > 60:
        return False
    return True


def find_body_start(lines: list[str]) -> int:
    seen: dict[str, int] = {}
    for i, ln in enumerate(lines):
        if not is_vol_header(ln):
            continue
        key = normalize_title_key(ln)
        if key in seen:
            return i
        seen[key] = i
    raise RuntimeError("未找到正文起始（目录区后第二次出现的卷首）")


def split_body_sections(
    lines: list[str], start: int
) -> list[tuple[str, str | None, list[str]]]:
    """返回 (卷首原行, 短篇名或 None, 正文行)。"""
    indices = [i for i in range(start, len(lines)) if is_vol_header(lines[i])]
    sections: list[tuple[str, str | None, list[str]]] = []
    for idx, pos in enumerate(indices):
        end = indices[idx + 1] if idx + 1 < len(indices) else len(lines)
        header = lines[pos].strip()
        body_raw: list[str] = []
        for ln in lines[pos + 1 : end]:
            if not ln.strip():
                continue
            if SKIP_LINE_RE.match(ln.strip()):
                continue
            if is_vol_header(ln):
                continue
            body_raw.append(ln.rstrip("\n"))

        subtitle: str | None = None
        body = body_raw
        if body_raw and is_subtitle_line(body_raw[0]):
            subtitle = body_raw[0].strip()
            # 篇名后还有正文则剥离；仅一行时既作篇名也保留正文（如「（表略）」）
            if len(body_raw) > 1:
                body = body_raw[1:]
        sections.append((header, subtitle, body))
    return sections


def parse_header(header: str) -> tuple[str, str]:
    h = re.sub(r"\s+", " ", header.strip())
    m = HEADER_PARSE_RE.match(h)
    if not m:
        return h, ""
    return m.group(1), m.group(2).strip()


def format_header_line(header: str, subtitle: str | None) -> str:
    vol, title = parse_header(header)
    if not title:
        base = re.sub(r"\s+", " ", header.strip())
        return f"{base}  {subtitle}" if subtitle else base
    if subtitle:
        return f"{vol}  {title}  {subtitle}"
    return f"{vol}  {title}"


def filename_title(header: str, subtitle: str | None) -> str:
    _, title = parse_header(header)
    title = title or re.sub(r"\s+", "", header.strip())
    if subtitle:
        return f"{title}_{subtitle}"
    return title


def safe_filename_title(title: str) -> str:
    t = title.strip()
    for ch in ("/", "\\", ":", "*", "?", '"', "<", ">", "|"):
        t = t.replace(ch, "＿")
    # 文件名不宜过长
    if len(t) > 80:
        t = t[:80]
    return t


def list_default_works() -> list[str]:
    return sorted(DEFAULT_EXPECT.keys())


def split_one(work: str, *, dry_run: bool, expect: int | None) -> int:
    source = SOURCE_DIR / f"{work}.txt"
    if not source.is_file():
        raise SystemExit(f"源文件不存在: {source}")

    expected = expect if expect is not None else DEFAULT_EXPECT.get(work)
    raw = source.read_text(encoding="utf-8")
    lines = raw.splitlines()
    body_start = find_body_start(lines)
    sections = split_body_sections(lines, body_start)

    print(f"\n=== {work} ===")
    print(f"源文件: {source}")
    print(f"正文起始: 第 {body_start + 1} 行")
    print(f"切分卷数: {len(sections)}")

    if expected is not None and len(sections) != expected:
        raise SystemExit(
            f"{work} 卷数不符：得到 {len(sections)}，期望 {expected}。"
            "请检查卷首识别规则。"
        )

    blank_check = sum(1 for _, _, body in sections for ln in body if not ln.strip())
    if blank_check:
        raise SystemExit(f"{work} 输出仍含 {blank_check} 行空白正文")

    empty_body = [i for i, (_, _, body) in enumerate(sections, 1) if not body]
    if empty_body:
        raise SystemExit(f"{work} 以下卷无正文: {empty_body[:20]}")

    assignments: list[tuple[str, str, list[str]]] = []
    used_names: set[str] = set()
    for i, (header, subtitle, body) in enumerate(sections, start=1):
        title = filename_title(header, subtitle)
        if not title:
            raise SystemExit(f"{work} 无法解析标题: {header}")
        vol = f"{i:03d}"
        out_name = f"{work}_{vol}_{safe_filename_title(title)}.txt"
        if out_name in used_names:
            raise SystemExit(f"{work} 文件名冲突: {out_name}")
        used_names.add(out_name)
        header_line = format_header_line(header, subtitle)
        assignments.append((out_name, header_line, body))

    if dry_run:
        for name, header_line, body in assignments[:5]:
            print(f"  {name}: header={header_line!r} body_lines={len(body)}")
        print("  …")
        for name, header_line, body in assignments[-3:]:
            print(f"  {name}: header={header_line!r} body_lines={len(body)}")
        return len(assignments)

    split_dir = resolve_split_dir(f"{work}_拆分后")
    split_dir.mkdir(parents=True, exist_ok=True)
    for old in split_dir.glob(f"{work}_*.txt"):
        old.unlink()

    written = 0
    for out_name, header_line, body in assignments:
        parts = [header_line, *body]
        text = "\n".join(parts) + "\n"
        (split_dir / out_name).write_text(text, encoding="utf-8")
        written += 1

    print(f"✅ 已写入 {written} 个文件 → {split_dir}")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="拆分剩余二十四史为按卷 txt")
    parser.add_argument(
        "--works",
        nargs="*",
        default=None,
        help="指定书名（如 05晋书）；默认处理全部未拆分正史",
    )
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    parser.add_argument(
        "--expect",
        type=int,
        default=None,
        help="单书期望卷数（仅当 --works 恰好一本时可用）",
    )
    args = parser.parse_args()

    works = args.works or list_default_works()
    if args.expect is not None and len(works) != 1:
        raise SystemExit("--expect 仅可与单本书同时使用")

    total = 0
    for work in works:
        exp = args.expect if args.expect is not None else None
        total += split_one(work, dry_run=args.dry_run, expect=exp)

    print(f"\n合计卷数: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
