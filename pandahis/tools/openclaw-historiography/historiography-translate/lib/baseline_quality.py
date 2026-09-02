"""相对旧优稿的回归门禁：禁止新跑无故大幅变薄或丢掉关键收束。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ENTRY_CLOSING_ANCHORS: Dict[str, Tuple[str, ...]] = {
    "GLBL_00084": ("轮台", "罪己", "征和"),
    "GLBL_00085": ("大风", "安刘", "长陵"),
}

_ENTRY_CONTENT_ANCHORS: Dict[str, Tuple[str, ...]] = {
    "GLBL_00084": ("卫青", "霍去病", "巫蛊", "轮台", "罪己", "征和"),
    "GLBL_00085": ("张良", "韩信", "白登", "安刘", "长陵"),
}

_PREFERRED_BASELINE_VERSION: Dict[str, int] = {
    "GLBL_00084": 6,
}


def _plain(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def baseline_min_length_ratio() -> float:
    raw = os.environ.get("TRANSLATE_BASELINE_MIN_RATIO", "0.85").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.85


def versions_dir_for_entry(out_dir: Path, entry_id: str, entry_name: str) -> Path:
    stem = f"{entry_id}_{entry_name}" if entry_name else entry_id
    return out_dir / "_versions" / stem


def _parse_version_num(path: Path) -> Tuple[int, str]:
    m = re.search(r"\.v(\d+)\.json$", path.name, re.I)
    if m:
        return int(m.group(1)), path.name
    return -1, path.name


def closing_anchors_for_entry(entry_id: str) -> Tuple[str, ...]:
    raw = os.environ.get("TRANSLATE_BASELINE_CLOSING_ANCHORS", "").strip()
    if raw:
        parts = tuple(p.strip() for p in re.split(r"[,，;；]", raw) if p.strip())
        if parts:
            return parts
    return _ENTRY_CLOSING_ANCHORS.get(entry_id, ())


def load_best_baseline_detail(
    out_dir: Path,
    entry_id: str,
    entry_name: str,
    exclude_version: str = "",
) -> Optional[Dict[str, Any]]:
    vdir = versions_dir_for_entry(out_dir, entry_id, entry_name)
    if not vdir.is_dir():
        return None

    excl = str(exclude_version or "").strip().lower().lstrip("v")
    preferred_raw = os.environ.get("TRANSLATE_BASELINE_PREFERRED", "").strip()
    preferred_n: Optional[int] = None

    if preferred_raw:
        if ":" in preferred_raw or ";" in preferred_raw:
            for part in preferred_raw.split(";"):
                part = part.strip()
                if not part or ":" not in part:
                    continue
                eid, ver = part.split(":", 1)
                if eid.strip() == entry_id and ver.strip().lstrip("v").isdigit():
                    preferred_n = int(ver.strip().lstrip("v"))
                    break
        elif preferred_raw.lstrip("v").isdigit():
            preferred_n = int(preferred_raw.lstrip("v"))

    if preferred_n is None:
        preferred_n = _PREFERRED_BASELINE_VERSION.get(entry_id)

    cands: List[Dict[str, Any]] = []
    for path in sorted(vdir.glob("*.json")):
        if path.name.endswith("-thin.json"):
            continue
        ver_n, _ = _parse_version_num(path)
        if excl.isdigit() and ver_n == int(excl):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        detail = str(data.get("翻译详情") or "")
        n = len(_plain(detail))
        if n < 500:
            continue
        version = str(data.get("翻译版本") or f"v{ver_n}" if ver_n >= 0 else path.name)
        cands.append(
            {
                "path": str(path),
                "version": version,
                "ver_n": ver_n,
                "翻译详情": detail,
                "chars": n,
            }
        )

    if not cands:
        return None

    if preferred_n is not None:
        for c in cands:
            if c["ver_n"] == preferred_n:
                return c

    anchors = closing_anchors_for_entry(entry_id)
    if anchors:
        with_a = [c for c in cands if any(a in c["翻译详情"] for a in anchors)]
        if with_a:
            return max(with_a, key=lambda x: (x["chars"], x["ver_n"]))

    return max(cands, key=lambda x: (x["ver_n"], x["chars"]))


def detect_baseline_regression(
    entry_id: str,
    detail: str,
    *,
    out_dir: Path,
    entry_name: str,
    exclude_version: str = "",
    mother: str = "",
) -> List[str]:
    """相对旧优稿回退 → 硬失败列表。"""
    flag = os.environ.get("TRANSLATE_BASELINE_REGRESSION", "1").strip().lower()
    if flag in {"off", "no", "false", "0"}:
        return []

    base = load_best_baseline_detail(
        out_dir,
        entry_id,
        entry_name,
        exclude_version=exclude_version,
    )
    if not base:
        return []

    errs: List[str] = []
    new_n = len(_plain(detail))
    base_n = int(base["chars"])
    ratio = baseline_min_length_ratio()

    if base_n >= 2000 and new_n < int(base_n * ratio):
        print(
            f"   ⚠️ 成稿相对旧优稿变薄（{new_n} < {base['version']}×{ratio:.0%}="
            f"{int(base_n * ratio)}）；仅作警告，继续检查内容锚点",
            flush=True,
        )

    content_anchors = _ENTRY_CONTENT_ANCHORS.get(entry_id, ())
    if content_anchors:
        base_text = str(base["翻译详情"])
        base_hits = [a for a in content_anchors if a in base_text]
        mother_plain = mother or ""
        enforceable = [a for a in base_hits if not mother_plain or a in mother_plain]
        missing = [a for a in enforceable if a not in detail]
        if missing:
            errs.append(
                "成稿丢失旧优稿核心内容锚点（"
                + "、".join(missing)
                + f"）；基线 {base['version']} 有而新稿全无"
            )

    anchors = closing_anchors_for_entry(entry_id)
    if anchors:
        base_text = str(base["翻译详情"])
        base_hits = [a for a in anchors if a in base_text]
        mother_plain = mother or ""
        enforceable = [a for a in base_hits if a in mother_plain]
        if not mother_plain:
            enforceable = base_hits
        if enforceable and not any(a in detail for a in enforceable):
            errs.append(
                "成稿丢失旧优稿已有的关键收束锚点（"
                + "、".join(enforceable)
                + f"）；基线 {base['version']} 有而新稿全无，须补回收科"
            )
        elif base_hits and not enforceable and any(a in detail for a in base_hits):
            print(
                f"   ⚠️ 旧优稿收束锚点（{'、'.join(base_hits)}）不在母本覆盖内，跳过硬拦",
                flush=True,
            )

    return errs
