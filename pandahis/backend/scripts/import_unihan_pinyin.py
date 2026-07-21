#!/usr/bin/env python3
"""Extract kMandarin readings from Unicode Unihan into a compact lookup bundle."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

UNIHAN_ZIP_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
READINGS_FILE = "Unihan_Readings.txt"
LINE_RE = re.compile(r"^(U\+[0-9A-F]{4,6})\tkMandarin\t(.+)$")


def codepoint_to_char(codepoint: str) -> str:
    return chr(int(codepoint[2:], 16))


def parse_readings(text: str) -> dict[str, str]:
    pinyin: dict[str, str] = {}
    for line in text.splitlines():
        match = LINE_RE.match(line)
        if not match:
            continue
        ch = codepoint_to_char(match.group(1))
        reading = match.group(2).strip()
        if not reading:
            continue
        # Keep the first kMandarin reading when duplicates appear.
        pinyin.setdefault(ch, reading)
    return pinyin


def load_readings_from_zip(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        try:
            return archive.read(READINGS_FILE).decode("utf-8")
        except KeyError as exc:
            raise FileNotFoundError(f"{READINGS_FILE} not found in {zip_path}") from exc


def download_unihan_zip(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {UNIHAN_ZIP_URL} ...", file=sys.stderr)
    urlretrieve(UNIHAN_ZIP_URL, dest)


def build_bundle(readings_text: str) -> dict:
    pinyin = parse_readings(readings_text)
    return {
        "version": 1,
        "source": "https://www.unicode.org/Public/UCD/latest/ucd/Unihan/",
        "license": "Unicode License V3",
        "field": "kMandarin",
        "entryCount": len(pinyin),
        "pinyin": pinyin,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Unihan kMandarin pinyin bundle.")
    parser.add_argument(
        "--zip",
        type=Path,
        default=Path(__file__).resolve().parent / ".cache" / "Unihan.zip",
        help="Path to Unihan.zip (downloaded if missing)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "src"
        / "main"
        / "resources"
        / "dictionary"
        / "unihan-pinyin.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Do not download Unihan.zip when missing",
    )
    args = parser.parse_args()

    if not args.zip.is_file():
        if args.no_download:
            print(f"Unihan zip not found: {args.zip}", file=sys.stderr)
            sys.exit(1)
        download_unihan_zip(args.zip)

    readings_text = load_readings_from_zip(args.zip)
    bundle = build_bundle(readings_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Wrote {bundle['entryCount']} pinyin entries to {args.output}")


if __name__ == "__main__":
    main()
