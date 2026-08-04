#!/usr/bin/env python3
"""将 EPUB 转为纯文本 TXT（标准库实现，无需额外依赖）。

用法:
  python3 scripts/epub_to_txt.py book.epub
  python3 scripts/epub_to_txt.py book.epub -o book.txt
  python3 scripts/epub_to_txt.py --input-dir ./epubs --output-dir ./txt

说明:
  - 按 spine 顺序读取章节，保留段落换行
  - 仅输出正文，跳过 CSS/图片等资源
  - 不修改 EPUB 原文件
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

BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "br",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "tr",
        "section",
        "article",
        "blockquote",
    }
)
SKIP_TAGS = frozenset({"script", "style", "head", "title", "meta", "link"})

NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_child(parent: ET.Element, local_name: str) -> ET.Element | None:
    for child in parent:
        if _local(child.tag) == local_name:
            return child
    return None


def _find_children(parent: ET.Element, local_name: str) -> list[ET.Element]:
    return [c for c in parent if _local(c.tag) == local_name]


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
        if self._skip_depth:
            return
        self._parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self._parts))
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        raw = re.sub(r"[ \t\f\v]+", " ", raw)
        raw = re.sub(r"\n[ \t]+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(content: bytes) -> str:
    for enc in ("utf-8", "gb18030", "gbk", "latin-1"):
        try:
            html_text = content.decode(enc)
            break
        except UnicodeDecodeError:
            html_text = None
    if html_text is None:
        html_text = content.decode("utf-8", errors="replace")

    parser = _HTMLTextExtractor()
    parser.feed(html_text)
    parser.close()
    return parser.text()


def _read_zip_text(zf: zipfile.ZipFile, inner_path: str) -> bytes:
    # EPUB 内路径大小写敏感；先精确匹配，再忽略大小写
    names = zf.namelist()
    if inner_path in names:
        return zf.read(inner_path)
    norm = inner_path.replace("\\", "/").lstrip("/")
    for name in names:
        if name.replace("\\", "/") == norm:
            return zf.read(name)
    lower_map = {n.replace("\\", "/").lower(): n for n in names}
    hit = lower_map.get(norm.lower())
    if hit:
        return zf.read(hit)
    raise KeyError(inner_path)


def _resolve_href(base_dir: str, href: str) -> str:
    href = href.split("#", 1)[0].strip()
    if not href:
        return base_dir
    base_parts = [p for p in base_dir.replace("\\", "/").split("/") if p and p != "."]
    for part in href.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if base_parts:
                base_parts.pop()
        else:
            base_parts.append(part)
    return "/".join(base_parts)


def _find_opf_path(zf: zipfile.ZipFile) -> str:
    container_xml = _read_zip_text(zf, "META-INF/container.xml")
    root = ET.fromstring(container_xml)
    rootfiles = root.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfiles")
    if rootfiles is None:
        rootfiles = _find_child(root, "rootfiles")
    if rootfiles is None:
        raise ValueError("无效的 EPUB：缺少 container.xml rootfiles")

    for rf in _find_children(rootfiles, "rootfile"):
        if rf.attrib.get("media-type") == "application/oebps-package+xml":
            return rf.attrib["full-path"]
    first = _find_children(rootfiles, "rootfile")[0]
    return first.attrib["full-path"]


def _load_opf(zf: zipfile.ZipFile, opf_path: str) -> ET.Element:
    opf_bytes = _read_zip_text(zf, opf_path)
    return ET.fromstring(opf_bytes)


def _manifest_map(opf_root: ET.Element) -> dict[str, str]:
    manifest = _find_child(opf_root, "manifest")
    if manifest is None:
        raise ValueError("无效的 EPUB：OPF 缺少 manifest")
    out: dict[str, str] = {}
    for item in _find_children(manifest, "item"):
        item_id = item.attrib.get("id")
        href = item.attrib.get("href")
        if item_id and href:
            out[item_id] = href
    return out


def _spine_ids(opf_root: ET.Element) -> list[str]:
    spine = _find_child(opf_root, "spine")
    if spine is None:
        raise ValueError("无效的 EPUB：OPF 缺少 spine")
    ids: list[str] = []
    for itemref in _find_children(spine, "itemref"):
        ref = itemref.attrib.get("idref")
        if ref:
            ids.append(ref)
    return ids


def _fallback_document_hrefs(zf: zipfile.ZipFile, manifest: dict[str, str]) -> list[str]:
    """无 spine 或 spine 为空时，按 manifest 中 xhtml/html 顺序读取。"""
    html_items = []
    for _id, href in manifest.items():
        low = href.lower()
        if low.endswith((".xhtml", ".html", ".htm")):
            html_items.append(href)
    if html_items:
        return sorted(html_items)
    # 最后兜底：扫描 zip 内所有 html
    return sorted(
        n
        for n in zf.namelist()
        if n.lower().endswith((".xhtml", ".html", ".htm"))
        and not n.startswith("META-INF/")
    )


def convert_epub_to_text(epub_path: Path) -> str:
    epub_path = epub_path.resolve()
    if not epub_path.is_file():
        raise FileNotFoundError(epub_path)

    with zipfile.ZipFile(epub_path) as zf:
        opf_path = _find_opf_path(zf)
        opf_root = _load_opf(zf, opf_path)
        manifest = _manifest_map(opf_root)
        spine_ids = _spine_ids(opf_root)
        opf_dir = str(Path(opf_path).parent).replace("\\", "/")
        if opf_dir == ".":
            opf_dir = ""

        hrefs: list[str] = []
        if spine_ids:
            for item_id in spine_ids:
                href = manifest.get(item_id)
                if href:
                    hrefs.append(href)
        if not hrefs:
            hrefs = _fallback_document_hrefs(zf, manifest)
        if not hrefs:
            raise ValueError(f"未找到可读章节: {epub_path.name}")

        chapters: list[str] = []
        for href in hrefs:
            inner = _resolve_href(opf_dir, href)
            try:
                raw = _read_zip_text(zf, inner)
            except KeyError:
                continue
            text = _html_to_text(raw)
            if text:
                chapters.append(text)

    if not chapters:
        raise ValueError(f"未能从 EPUB 提取正文: {epub_path.name}")

    return "\n\n".join(chapters).strip() + "\n"


def convert_file(epub_path: Path, output_path: Path | None = None) -> Path:
    out = output_path or epub_path.with_suffix(".txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    text = convert_epub_to_text(epub_path)
    out.write_text(text, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="EPUB → TXT（标准库）")
    parser.add_argument("epub", nargs="*", help="EPUB 文件路径")
    parser.add_argument("-o", "--output", help="输出 TXT 路径（单文件模式）")
    parser.add_argument("--input-dir", type=Path, help="批量：输入目录")
    parser.add_argument("--output-dir", type=Path, help="批量：输出目录（默认同目录）")
    parser.add_argument("--suffix", default=".txt", help="输出后缀，默认 .txt")
    args = parser.parse_args()

    jobs: list[tuple[Path, Path | None]] = []

    if args.input_dir:
        if not args.input_dir.is_dir():
            print(f"❌ 目录不存在: {args.input_dir}", file=sys.stderr)
            return 1
        out_dir = args.output_dir or args.input_dir
        for fp in sorted(args.input_dir.glob("*.epub")):
            out = out_dir / (fp.stem + args.suffix)
            jobs.append((fp, out))
    elif args.epub:
        first = Path(args.epub[0])
        out = Path(args.output) if args.output else None
        jobs.append((first, out))
        for extra in args.epub[1:]:
            ep = Path(extra)
            jobs.append((ep, ep.with_suffix(args.suffix)))
    else:
        parser.print_help()
        return 1

    if not jobs:
        print("❌ 未找到 EPUB 文件", file=sys.stderr)
        return 1

    ok, fail = 0, 0
    for epub_path, out_path in jobs:
        try:
            saved = convert_file(epub_path, out_path)
            chars = saved.read_text(encoding="utf-8")
            print(f"✅ {epub_path.name} → {saved}（{len(chars)} 字符）")
            ok += 1
        except Exception as exc:
            print(f"❌ {epub_path.name}: {exc}", file=sys.stderr)
            fail += 1

    if fail:
        print(f"\n完成: 成功 {ok} · 失败 {fail}", file=sys.stderr)
        return 1
    print(f"\n完成: 成功 {ok} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
