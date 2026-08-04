"""卷级 manifest：narrative_mode 与机械划块策略。"""

from __future__ import annotations

import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from lib.config import ANNOTATE_DIR

if str(ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(ANNOTATE_DIR))

from paragraph_utils import classify_paragraph_header  # noqa: E402
from category_v3 import VALID_CATS  # noqa: E402

VALID_NARRATIVE_MODES = frozenset({"skip", "single", "hezhuan", "fanzuo"})
VALID_VOLUME_TYPES = frozenset(
    {"本纪", "世家", "列传", "合传", "表", "书", "志", "志书数据", "志书叙事"}
)

# 合传段落内异名（传记段首常见）
HEZHUAN_BIO_ALIASES: Dict[str, Tuple[str, ...]] = {
    "英布": ("黥布",),
    "朱建": ("硃建",),
    "刘敬": ("娄敬",),
    "石奋": ("万石君",),
    "疏受": ("受", "广兄子受"),
    "彭宣": ("鼓宣",),
    "梁孝王": ("梁孝王武",),
    "刘参": ("代孝王",),
    "刘揖": ("梁怀王",),
}

# 评述段首关键词（机械 exclude）
COMMENTARY_MARKERS = (
    "太史公曰",
    "赞曰",
    "班固曰",
    "司马贞",
    "索隐",
    "论曰",
    "论赞",
    "臣光曰",
    "臣朔曰",
)


def infer_narrative_mode(manifest: dict) -> str:
    """据 manifest 字段推断 narrative_mode（LLM 未写时兜底）。"""
    mode = (manifest.get("narrative_mode") or "").strip()
    if mode in VALID_NARRATIVE_MODES:
        return mode
    if manifest.get("skip_reason"):
        return "skip"
    protagonists = manifest.get("protagonists") or []
    if not protagonists:
        vtype = (manifest.get("volume_type_guess") or "").strip()
        if vtype in ("表", "书", "志", "志书数据"):
            return "skip"
        return "skip"
    if len(protagonists) == 1:
        cat = (protagonists[0].get("category") or "").strip()
        if cat == "蕃祚":
            return "fanzuo"
        return "single"
    if all((p.get("category") or "").strip() == "蕃祚" for p in protagonists):
        return "hezhuan" if len(protagonists) > 1 else "fanzuo"
    return "hezhuan"


def normalize_manifest(manifest: dict, *, volume_name: str = "") -> Tuple[dict, List[str]]:
    """补全 narrative_mode / volume_name；返回 (manifest, 变更日志)。"""
    logs: List[str] = []
    out = dict(manifest)
    if volume_name and not (out.get("volume_name") or "").strip():
        out["volume_name"] = volume_name
        logs.append(f"补 volume_name={volume_name}")
    mode = infer_narrative_mode(out)
    if out.get("narrative_mode") != mode:
        out["narrative_mode"] = mode
        logs.append(f"narrative_mode → {mode}")
    return out, logs


def manifest_payload_errors(obj: Any, *, work: str = "", vol: str = "") -> List[str]:
    if not isinstance(obj, dict):
        return ["须为 JSON 对象"]
    errors: List[str] = []
    if work and (obj.get("work") or "").strip() not in ("", work):
        errors.append(f"work 应为 {work!r}")
    vol_z = vol.zfill(3) if vol else ""
    raw_vol = str(obj.get("vol") or "").strip()
    if vol_z and raw_vol and raw_vol.zfill(3) != vol_z:
        errors.append(f"vol 应为 {vol_z!r}")
    mode = infer_narrative_mode(obj)
    if mode not in VALID_NARRATIVE_MODES:
        errors.append(f"narrative_mode 非法: {mode!r}")
    protagonists = obj.get("protagonists")
    if not isinstance(protagonists, list):
        errors.append("protagonists 须为数组")
    elif mode == "skip":
        if protagonists:
            errors.append("skip 卷 protagonists 须为空")
        if not (obj.get("skip_reason") or "").strip():
            errors.append("skip 卷须填写 skip_reason")
    elif not protagonists:
        errors.append("叙事卷 protagonists 须为非空数组")
    else:
        for i, item in enumerate(protagonists[:8], start=1):
            if not isinstance(item, dict):
                errors.append(f"protagonists[{i}] 须为对象")
                break
            for key in ("name", "category", "rationale"):
                if not (item.get(key) or "").strip():
                    errors.append(f"protagonists[{i}] 缺少 {key}")
                    break
            cat = (item.get("category") or "").strip()
            if cat and cat not in VALID_CATS:
                errors.append(f"protagonists[{i}] category 非法: {cat!r}")
    if "blocks" in obj or "entries" in obj:
        errors.append("protagonists 草稿禁止含 blocks/entries")
    return errors


def uses_mechanical_blocks(manifest: dict) -> bool:
    return infer_narrative_mode(manifest) in ("single", "fanzuo", "hezhuan")


def _is_commentary_paragraph(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    head = t[:24]
    return any(m in head for m in COMMENTARY_MARKERS)


def _commentary_exclude_reason(text: str) -> str:
    t = (text or "").strip()[:16]
    if "太史公" in t:
        return "太史公曰"
    if t.startswith("赞曰"):
        return "赞曰"
    if "班固曰" in t:
        return "其他"
    return "其他"


def _detect_commentary_paragraphs(para_text: Dict[int, str], total: int) -> List[int]:
    out: List[int] = []
    for pid in range(1, total + 1):
        if _is_commentary_paragraph(para_text.get(pid, "")):
            out.append(pid)
    return out


def _detect_structural_header_paragraphs(
    para_text: Dict[int, str], total: int
) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for pid in range(1, total + 1):
        kind = classify_paragraph_header(para_text.get(pid, ""))
        if kind in ("篇内小标题", "纯纪年"):
            out.append((pid, kind))
    return out


def _bio_names_for_protagonist(name: str) -> Tuple[str, ...]:
    aliases = HEZHUAN_BIO_ALIASES.get(name, ())
    return (name,) + aliases


def _paragraph_starts_bio(text: str, names: Tuple[str, ...]) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    for n in names:
        if t.startswith(n):
            return True
        if re.match(rf"^{re.escape(n)}[，、字]", t):
            return True
    return False


def _paragraph_contains_bio_handoff(text: str, names: Tuple[str, ...]) -> bool:
    t = text or ""
    for n in names:
        if re.search(rf"[。；\s]{re.escape(n)}(?:[，、字者]|为)", t):
            return True
    return False


def _find_bio_start_pid(
    para_text: Dict[int, str],
    total: int,
    names: Tuple[str, ...],
    min_pid: int,
) -> Optional[int]:
    found = _find_bio_start_pid_with_kind(para_text, total, names, min_pid)
    return found[0] if found else None


def _find_bio_start_pid_with_kind(
    para_text: Dict[int, str],
    total: int,
    names: Tuple[str, ...],
    min_pid: int,
) -> Optional[Tuple[int, str]]:
    """返回 (段落号, 'start'|'handoff')。"""
    for pid in range(min_pid, total + 1):
        if _paragraph_starts_bio(para_text.get(pid, ""), names):
            return pid, "start"
    for pid in range(min_pid, total + 1):
        if _paragraph_contains_bio_handoff(para_text.get(pid, ""), names):
            return pid, "handoff"
    return None


def build_mechanical_hezhuan_blocks(
    manifest: dict,
    *,
    total_paragraphs: int,
    para_text: Optional[Dict[int, str]] = None,
    bio_aliases: Optional[Dict[str, Tuple[str, ...]]] = None,
) -> dict:
    """
    hezhuan：按传主传记段首机械划块（卷首/评述排除），避免 LLM 漏人。
    """
    mode = infer_narrative_mode(manifest)
    if mode != "hezhuan":
        raise ValueError(f"合传机械划块仅适用于 hezhuan，当前 {mode}")
    protagonists = manifest.get("protagonists") or []
    if len(protagonists) < 2:
        raise ValueError("hezhuan 须至少 2 名主人公")

    total = int(total_paragraphs)
    para_text = para_text or {}
    excludes: List[dict] = []
    excluded_pids: set[int] = set()

    if total >= 1:
        excludes.append(
            {"paragraph_from": 1, "paragraph_to": 1, "exclude_reason": "卷首标题"}
        )
        excluded_pids.add(1)

    for pid, reason in _detect_structural_header_paragraphs(para_text, total):
        if pid in excluded_pids:
            continue
        excludes.append(
            {
                "paragraph_from": pid,
                "paragraph_to": pid,
                "exclude_reason": reason,
            }
        )
        excluded_pids.add(pid)

    for pid in _detect_commentary_paragraphs(para_text, total):
        if pid in excluded_pids:
            continue
        excludes.append(
            {
                "paragraph_from": pid,
                "paragraph_to": pid,
                "exclude_reason": _commentary_exclude_reason(para_text.get(pid, "")),
            }
        )
        excluded_pids.add(pid)

    narrative_pids = [p for p in range(1, total + 1) if p not in excluded_pids]
    if not narrative_pids:
        raise ValueError("排除卷首/评述后无叙事段")
    last_narrative = narrative_pids[-1]

    alias_map = dict(HEZHUAN_BIO_ALIASES)
    if bio_aliases:
        alias_map.update(bio_aliases)

    def _names_for(name: str) -> Tuple[str, ...]:
        aliases = alias_map.get(name, ())
        return (name,) + aliases

    starts: List[int] = []
    search_from = narrative_pids[0]
    for item in protagonists:
        name = (item.get("name") or "").strip()
        if not name:
            raise ValueError("protagonist name 为空")
        found = _find_bio_start_pid_with_kind(
            para_text, total, _names_for(name), search_from
        )
        if found is None:
            raise ValueError(f"未找到 {name!r} 传记段首（自 P{search_from} 起）")
        pid, _kind = found
        # 同段接力：前一位已占本段时，从下一段起划块（避免 P 重复归属）
        if starts and pid <= starts[-1]:
            pid = pid + 1
            if pid > last_narrative:
                raise ValueError(
                    f"{name!r} 传记段首与前位同段且无法后移（自 P{search_from} 起）"
                )
        starts.append(pid)
        search_from = pid

    blocks: List[dict] = []
    for i, item in enumerate(protagonists):
        name = (item.get("name") or "").strip()
        cat = (item.get("category") or "").strip()
        pf = starts[i]
        if i + 1 < len(starts):
            pt = starts[i + 1] - 1
            if pt < pf:
                pt = pf
        else:
            pt = last_narrative
        blocks.append(
            {
                "name": name,
                "category": cat,
                "paragraph_from": pf,
                "paragraph_to": pt,
            }
        )

    return {
        "work": manifest.get("work"),
        "vol": manifest.get("vol"),
        "volume_name": manifest.get("volume_name"),
        "narrative_mode": mode,
        "total_paragraphs": total,
        "excludes": excludes,
        "blocks": blocks,
        "_mechanical": True,
        "_mechanical_hezhuan": True,
    }


def build_mechanical_blocks(
    manifest: dict,
    *,
    total_paragraphs: int,
    para_text: Optional[Dict[int, str]] = None,
) -> dict:
    mode = infer_narrative_mode(manifest)
    if mode == "hezhuan":
        return build_mechanical_hezhuan_blocks(
            manifest,
            total_paragraphs=total_paragraphs,
            para_text=para_text,
        )
    if mode not in ("single", "fanzuo"):
        raise ValueError(f"机械划块仅适用于 single/fanzuo/hezhuan，当前 {mode}")
    protagonists = manifest.get("protagonists") or []
    if not protagonists:
        raise ValueError("缺少 protagonists")
    total = int(total_paragraphs)
    if total <= 0:
        raise ValueError("total_paragraphs 须为正整数")

    para_text = para_text or {}
    excludes: List[dict] = []
    excluded_pids: set[int] = set()

    # 卷首标题：P1
    if total >= 1:
        excludes.append(
            {
                "paragraph_from": 1,
                "paragraph_to": 1,
                "exclude_reason": "卷首标题",
            }
        )
        excluded_pids.add(1)

    for pid, reason in _detect_structural_header_paragraphs(para_text, total):
        if pid in excluded_pids:
            continue
        excludes.append(
            {
                "paragraph_from": pid,
                "paragraph_to": pid,
                "exclude_reason": reason,
            }
        )
        excluded_pids.add(pid)

    # 评述段
    for pid in _detect_commentary_paragraphs(para_text, total):
        if pid in excluded_pids:
            continue
        excludes.append(
            {
                "paragraph_from": pid,
                "paragraph_to": pid,
                "exclude_reason": _commentary_exclude_reason(para_text.get(pid, "")),
            }
        )
        excluded_pids.add(pid)

    narrative_pids = [p for p in range(1, total + 1) if p not in excluded_pids]
    if not narrative_pids:
        raise ValueError("排除卷首/评述后无叙事段")

    pf, pt = narrative_pids[0], narrative_pids[-1]
    blocks: List[dict] = []
    for item in protagonists:
        name = (item.get("name") or "").strip()
        cat = (item.get("category") or "").strip()
        if not name or not cat:
            continue
        blocks.append(
            {
                "name": name,
                "category": cat,
                "paragraph_from": pf,
                "paragraph_to": pt,
            }
        )

    return {
        "work": manifest.get("work"),
        "vol": manifest.get("vol"),
        "volume_name": manifest.get("volume_name"),
        "narrative_mode": mode,
        "total_paragraphs": total,
        "excludes": excludes,
        "blocks": blocks,
        "_mechanical": True,
    }


def skip_reason_from_volume_name(volume_name: str) -> Optional[str]:
    """表/书/志卷机械 skip 原因（含分卷：王子侯表第三上、律历志第一上等）。"""
    name = (volume_name or "").strip()
    if name.endswith("表") or "表第" in name or any(
        k in name for k in ("侯表", "公卿表", "功臣表", "恩泽侯表", "诸侯王表", "人表", "异姓诸侯王表")
    ):
        return f"表卷「{name}」无叙事主人公"
    if name.endswith("书"):
        return f"书卷「{name}」无叙事主人公"
    if name.endswith("志") or "志第" in name:
        return f"志卷「{name}」无叙事主人公"
    return None
