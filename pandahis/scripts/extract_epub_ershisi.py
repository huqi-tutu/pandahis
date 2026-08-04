#!/usr/bin/env python3
"""从「二十四史：完本精校大全集.epub」按史书拆分为独立 TXT。

输出至 data/00原文母本/二十四史新/，文件名与「二十四史原文」目录一致。
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

# spine 上「目录」段索引 → (文件名前缀, 显示名)
BOOK_BOUNDARIES: list[tuple[int, str, str]] = [
    (3, "01史记", "史记"),
    (134, "02汉书", "汉书"),
    (256, "03后汉书", "后汉书"),
    (388, "04三国志", "三国志"),
    (456, "05晋书", "晋书"),
    (588, "06宋书", "宋书"),
    (690, "07南齐书", "南齐书"),
    (752, "08梁书", "梁书"),
    (811, "09陈书", "陈书"),
    (850, "10魏书", "魏书"),
    (983, "11北齐书", "北齐书"),
    (1035, "12周书", "周书"),
    (1088, "13隋书", "隋书"),
    (1176, "14南史", "南史"),
    (1258, "15北史", "北史"),
    (1360, "16旧唐书", "旧唐书"),
    (1577, "17新唐书", "新唐书"),
    (1828, "18旧五代史", "旧五代史"),
    (1981, "19新五代史", "新五代史"),
    (2058, "20宋史", "宋史"),
    (2556, "21辽史", "辽史"),
    (2675, "22金史", "金史"),
    (2814, "23元史", "元史"),
    (3028, "24明史", "明史"),
]

BLOCK_TAGS = frozenset(
    {"p", "div", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "li", "section", "article"}
)
SKIP_TAGS = frozenset({"script", "style", "head", "title", "meta", "link"})


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        t = tag.lower()
        if t in SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if t in BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if t in BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self._parts))
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        raw = re.sub(r"[ \t\f\v]+", " ", raw)
        raw = re.sub(r"\n[ \t]+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read_zip(zf: zipfile.ZipFile, inner_path: str) -> bytes:
    if inner_path in zf.namelist():
        return zf.read(inner_path)
    norm = inner_path.replace("\\", "/").lstrip("/")
    for name in zf.namelist():
        if name.replace("\\", "/") == norm:
            return zf.read(name)
    raise KeyError(inner_path)


def _load_spine(zf: zipfile.ZipFile) -> tuple[list[str], str, dict[str, str]]:
    container = ET.fromstring(_read_zip(zf, "META-INF/container.xml"))
    opf_path = next(
        rf.attrib["full-path"]
        for rf in container.iter()
        if rf.tag.endswith("rootfile")
    )
    opf = ET.fromstring(_read_zip(zf, opf_path))
    manifest: dict[str, str] = {}
    for el in opf.iter():
        if _local(el.tag) == "item" and el.attrib.get("id") and el.attrib.get("href"):
            manifest[el.attrib["id"]] = el.attrib["href"]
    spine = [
        el.attrib["idref"]
        for el in opf.iter()
        if _local(el.tag) == "itemref" and el.attrib.get("idref")
    ]
    opf_dir = str(Path(opf_path).parent).replace("\\", "/")
    return spine, opf_dir, manifest


def _html_to_text(raw: bytes) -> str:
    for enc in ("utf-8", "gb18030", "gbk", "latin-1"):
        try:
            html_text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            html_text = None
    if html_text is None:
        html_text = raw.decode("utf-8", errors="replace")
    parser = _HTMLTextExtractor()
    parser.feed(html_text)
    parser.close()
    return parser.text()


def _normalize_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    # 与旧版拆分 txt 对齐：卷一·五帝 → 卷一 五帝
    line = line.replace("·", " ")
    line = re.sub(r" +", " ", line)
    return line


def _normalize_text(text: str) -> str:
    lines = [_normalize_line(ln) for ln in text.split("\n")]
    out: list[str] = []
    prev_blank = False
    for ln in lines:
        if not ln:
            if not prev_blank and out:
                out.append("")
                prev_blank = True
            continue
        out.append(ln)
        prev_blank = False
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def _extract_part_text(zf: zipfile.ZipFile, opf_dir: str, href: str) -> str:
    path = f"{opf_dir}/{href}".replace("\\", "/")
    try:
        raw = _read_zip(zf, path)
    except KeyError:
        return ""
    return _normalize_text(_html_to_text(raw))


def _build_book_texts(
    zf: zipfile.ZipFile,
    spine: list[str],
    opf_dir: str,
    manifest: dict[str, str],
) -> dict[str, str]:
    spine_hrefs = [manifest[sid] for sid in spine if sid in manifest]
    part_texts = [_extract_part_text(zf, opf_dir, href) for href in spine_hrefs]

    bounds = BOOK_BOUNDARIES + [(len(spine_hrefs), "", "")]
    out: dict[str, str] = {}

    for idx, (toc_i, file_stem, display_name) in enumerate(BOOK_BOUNDARIES):
        next_toc_i = bounds[idx + 1][0]
        toc_text = part_texts[toc_i] if toc_i < len(part_texts) else ""
        body_parts = [
            t
            for t in part_texts[toc_i + 1 : next_toc_i]
            if t and t != "目录"
        ]
        sections: list[str] = [
            f"书籍名称：《{display_name}》",
            "",
            display_name,
            "",
        ]
        if toc_text:
            # 去掉首行「目录」，保留卷目列表
            toc_lines = toc_text.split("\n")
            if toc_lines and toc_lines[0].strip() == "目录":
                toc_lines = toc_lines[1:]
            toc_clean = _normalize_text("\n".join(toc_lines))
            if toc_clean:
                sections.append(toc_clean)
                sections.append("")
        if body_parts:
            sections.append("\n\n".join(body_parts))
        out[f"{file_stem}.txt"] = "\n".join(sections).strip() + "\n"
    return out


def extract_epub(epub_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    print(f"📖 解析 EPUB: {epub_path.name}", flush=True)
    with zipfile.ZipFile(epub_path) as zf:
        spine, opf_dir, manifest = _load_spine(zf)
        print(f"   spine {len(spine)} 章 · 开始提取…", flush=True)
        books = _build_book_texts(zf, spine, opf_dir, manifest)
    for name, text in books.items():
        fp = output_dir / name
        fp.write_text(text, encoding="utf-8")
        written.append(fp)
        chars = len(text)
        vols = text.count("\n卷")
        print(f"   ✅ {name} · {chars:,} 字 · 约 {vols} 处卷标", flush=True)
    return written


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="二十四史 EPUB → 按书拆分 TXT")
    parser.add_argument(
        "--epub",
        type=Path,
        default=root / "data/00原文母本/二十四史：完本精校大全集.epub",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "data/00原文母本/二十四史新",
    )
    args = parser.parse_args()
    if not args.epub.is_file():
        print(f"❌ EPUB 不存在: {args.epub}", file=sys.stderr)
        return 1
    files = extract_epub(args.epub.resolve(), args.output_dir.resolve())
    print(f"\n✅ 共导出 {len(files)} 部 → {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
