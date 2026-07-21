"""信息点卫生与覆盖验收单元分组。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from lib.citation_mode import detect_citation_mode


def info_point_is_classical(info: str, orig: str) -> bool:
    """信息点若仍是文言摘句副本，则不宜做字面关键词验收。"""
    a = re.sub(r"\s+", "", str(info or ""))
    b = re.sub(r"\s+", "", str(orig or ""))
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 4 and shorter in longer:
        return len(shorter) / len(longer) >= 0.72
    return False


def sanitize_info_point(info: str, orig: str) -> str:
    """落盘时禁止把原文摘句当作信息点。"""
    text = str(info or "").strip()
    if not text or info_point_is_classical(text, orig):
        return ""
    return text


def body_without_intro_zone(detail: str) -> str:
    """剔除前置引入区（规则：引入不计入母本覆盖）。"""
    body = detail.split("*参考著作*")[0].split("参考著作")[0]
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paras:
        return body.strip()
    zone_end = 0
    for i, para in enumerate(paras[:3]):
        zone_end = i + 1
        if re.search(r"让我们|下面|来看一看|按下.*顺序|如何记载", para):
            break
    if zone_end < len(paras):
        return "\n\n".join(paras[zone_end:]).strip()
    return body.strip()


@dataclass(frozen=True)
class CoverageUnit:
    kind: str  # item | group
    items: tuple[Dict[str, Any], ...]
    label: str

    @property
    def primary(self) -> Dict[str, Any]:
        return self.items[0]


def build_coverage_units(checklist: Sequence[Dict[str, Any]]) -> List[CoverageUnit]:
    """并列句群（同段）合并为组：组内任一命中即计该组通过。"""
    units: List[CoverageUnit] = []
    buf: List[Dict[str, Any]] = []

    def _flush() -> None:
        nonlocal buf
        if not buf:
            return
        if len(buf) > 1 and all(
            str(x.get("引用粒度") or detect_citation_mode(str(x.get("原文摘句") or "")))
            == "parallel_cluster"
            and str(x.get("段落") or "") == str(buf[0].get("段落") or "")
            for x in buf
        ):
            sid = str(buf[0].get("编号") or "")
            elid = str(buf[-1].get("编号") or "")
            label = f"{sid}–{elid}" if elid != sid else sid
            units.append(CoverageUnit(kind="group", items=tuple(buf), label=label))
        else:
            for row in buf:
                units.append(
                    CoverageUnit(
                        kind="item",
                        items=(row,),
                        label=str(row.get("编号") or ""),
                    )
                )
        buf = []

    for row in checklist:
        if not isinstance(row, dict):
            continue
        orig = str(row.get("原文摘句") or row.get("text") or "").strip()
        if not orig and not str(row.get("信息点") or "").strip():
            continue
        mode = str(row.get("引用粒度") or detect_citation_mode(orig))
        para = str(row.get("段落") or "")
        if (
            buf
            and mode == "parallel_cluster"
            and str(buf[-1].get("引用粒度") or detect_citation_mode(str(buf[-1].get("原文摘句") or "")))
            == "parallel_cluster"
            and str(buf[-1].get("段落") or "") == para
        ):
            buf.append(row)
        else:
            _flush()
            buf = [row]
    _flush()
    return units
