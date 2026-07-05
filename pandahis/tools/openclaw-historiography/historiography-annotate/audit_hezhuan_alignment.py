#!/usr/bin/env python3
"""合传卷人物–段落错位扫描：对照 blocks / skeleton 与段落索引做启发式校验。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from paths_config import get_histograph_root  # noqa: E402

DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"
SKELETON_DIR = DATA / "03索引标注条目"
BLOCKS_DIR = DATA / "05工作流中间产物" / "标注"

# 传主别名 → 规范名（可扩展）
ALIASES: Dict[str, str] = {
    "子赣": "子贡",
    "朱公": "陶朱公",
    "范蠡": "陶朱公",
    "蜀卓氏": "卓氏",
    "韩王孙嫣": "韩嫣",
    "翁伯": "郭解",
}

TRANSITION_RE = re.compile(
    r"^(其后|是时|久之|居无何|而|及|至若|今天子|孝文|孝景|武帝|秦始皇|二世)"
)
BIO_START_RE = re.compile(r"([\u4e00-\u9fff]{2,6})(?:者|，)")


@dataclass
class Issue:
    vol: str
    kind: str
    severity: str
    message: str
    paragraph: Optional[int] = None
    protagonist: Optional[str] = None


@dataclass
class VolReport:
    vol: str
    volume_name: str
    protagonists: List[str] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity in ("error", "warn") for i in self.issues)


def _load_paragraphs(work: str, vol: str) -> Dict[int, str]:
    p = INDEX_DIR / f"{work}_{vol}.json"
    if not p.is_file():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {int(x["id"]): x.get("text", "") for x in data.get("paragraphs") or []}


def _load_blocks(work: str, vol: str) -> Optional[dict]:
    p = BLOCKS_DIR / f"{work}_{vol}_blocks.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _load_skeleton(work: str, vol: str) -> Optional[dict]:
    for pat in (f"{work}_{vol}_*_skeleton.json", f"{work}_{vol}_skeleton.json"):
        matches = list(SKELETON_DIR.glob(pat))
        if matches:
            return json.loads(matches[0].read_text(encoding="utf-8"))
    return None


def _canon(name: str) -> str:
    return ALIASES.get(name, name)


def _names_in_text(text: str, candidates: Set[str]) -> Set[str]:
    found: Set[str] = set()
    for c in candidates:
        if c in text:
            found.add(c)
        for alias, canon in ALIASES.items():
            if canon == c and alias in text:
                found.add(c)
    return found


def audit_volume(work: str, vol: str) -> VolReport:
    vol = vol.zfill(3)
    paras = _load_paragraphs(work, vol)
    blocks_data = _load_blocks(work, vol)
    sk = _load_skeleton(work, vol)
    vn = (sk or {}).get("volume", vol)
    report = VolReport(vol=vol, volume_name=vn)

    if not paras:
        report.issues.append(
            Issue(vol, "missing_index", "error", "缺少段落索引")
        )
        return report

    if not blocks_data:
        report.issues.append(
            Issue(vol, "missing_blocks", "error", "缺少 blocks.json")
        )
        return report

    blocks = blocks_data.get("blocks") or []
    protagonists = [_canon(b["name"]) for b in blocks]
    report.protagonists = list(dict.fromkeys(protagonists))
    canon_set = set(report.protagonists)

    # 1) 块界单调、无重叠
    covered: Dict[int, str] = {}
    for b in blocks:
        name = _canon(b["name"])
        pf, pt = int(b["paragraph_from"]), int(b["paragraph_to"])
        for p in range(pf, pt + 1):
            if p in covered:
                report.issues.append(
                    Issue(
                        vol,
                        "overlap",
                        "error",
                        f"P{p} 同时归属 {covered[p]} 与 {name}",
                        paragraph=p,
                        protagonist=name,
                    )
                )
            covered[p] = name

    # 2) 块首锚点：首段应含本传主或定语句
    for b in blocks:
        name = _canon(b["name"])
        pf = int(b["paragraph_from"])
        text = paras.get(pf, "")
        if not text:
            continue
        if name not in text and not any(
            alias in text and _canon(alias) == name for alias in ALIASES
        ):
            m = BIO_START_RE.match(text.strip())
            hinted = m.group(1) if m else ""
            if hinted and _canon(hinted) != name and hinted not in text.replace(name, ""):
                report.issues.append(
                    Issue(
                        vol,
                        "block_start_mismatch",
                        "warn",
                        f"{name} 块起 P{pf} 段首无姓名锚点（段首：{text[:24]}…）",
                        paragraph=pf,
                        protagonist=name,
                    )
                )

    # 3) 块首是否出现其他传主姓名（错位强信号）
    for b in blocks:
        name = _canon(b["name"])
        pf = int(b["paragraph_from"])
        text = paras.get(pf, "")
        others = _names_in_text(text, canon_set - {name})
        if others:
            report.issues.append(
                Issue(
                    vol,
                    "foreign_protagonist_at_start",
                    "warn",
                    f"{name} 块起 P{pf} 出现其他传主：{', '.join(sorted(others))}",
                    paragraph=pf,
                    protagonist=name,
                )
            )

    # 4) 过渡句单独成块
    for b in blocks:
        name = _canon(b["name"])
        pf, pt = int(b["paragraph_from"]), int(b["paragraph_to"])
        if pf == pt:
            text = paras.get(pf, "").strip()
            if TRANSITION_RE.match(text) and name not in text[:20]:
                report.issues.append(
                    Issue(
                        vol,
                        "transition_only_block",
                        "info",
                        f"{name} 仅 P{pf} 且似过渡句，宜 exclude 或并入前块",
                        paragraph=pf,
                        protagonist=name,
                    )
                )

    # 5) skeleton ↔ blocks 人名一致
    if sk:
        sk_names = [_canon(e.get("史略名称", "")) for e in sk.get("entries") or []]
        if set(sk_names) != set(report.protagonists):
            report.issues.append(
                Issue(
                    vol,
                    "skeleton_blocks_name_mismatch",
                    "error",
                    f"skeleton 条目 {sk_names} ≠ blocks 传主 {report.protagonists}",
                )
            )
        for entry in sk.get("entries") or []:
            ename = _canon(entry.get("史略名称", ""))
            paras_e = entry.get("paragraphs") or []
            if not paras_e:
                continue
            epf = int(paras_e[0]["paragraph_from"])
            excerpt = (entry.get("原文字句") or "").strip()
            idx_text = paras.get(epf, "")
            if excerpt and idx_text and not idx_text.startswith(excerpt[:12]):
                report.issues.append(
                    Issue(
                        vol,
                        "excerpt_drift",
                        "warn",
                        f"{ename} 原文字句与 P{epf} 段首不一致",
                        paragraph=epf,
                        protagonist=ename,
                    )
                )

    # 6) 太史公曰 / 褚先生 不应有 owner
    attr = (sk or {}).get("segment_attribution") or []
    for seg in attr:
        p = int(seg.get("paragraph", 0))
        text = paras.get(p, "")
        owners = seg.get("owners") or []
        if owners and (
            text.strip().startswith("太史公曰")
            or text.strip().startswith("褚先生曰")
        ):
            report.issues.append(
                Issue(
                    vol,
                    "commentary_owned",
                    "error",
                    f"P{p} 为评述/补笔却归属 {[o.get('name') for o in owners]}",
                    paragraph=p,
                )
            )

    return report


def audit_all_hezhuan(work: str = "01史记", vols: Optional[List[str]] = None) -> List[VolReport]:
    if vols:
        targets = [v.zfill(3) for v in vols]
    else:
        targets = sorted(
            p.stem.replace(f"{work}_", "")
            for p in INDEX_DIR.glob(f"{work}_*.json")
        )
    return [audit_volume(work, v) for v in targets]


def main() -> None:
    ap = argparse.ArgumentParser(description="合传卷人物段落错位扫描")
    ap.add_argument("--work", default="01史记")
    ap.add_argument("--vol", action="append", help="指定卷号，可多次；默认全卷")
    ap.add_argument("--json", dest="json_out", help="写出 JSON 报告路径")
    ap.add_argument("--fail-on-warn", action="store_true")
    args = ap.parse_args()

    reports = audit_all_hezhuan(args.work, args.vol)
    errors = warns = 0
    for r in reports:
        if len(r.protagonists) <= 1 and not r.issues:
            continue
        if not r.protagonists and not r.issues:
            continue
        sev_issues = [i for i in r.issues if i.severity != "info"]
        if not sev_issues and len(r.protagonists) <= 1:
            continue
        print(f"\n── 卷{r.vol} {r.volume_name} 传主={r.protagonists}")
        for i in r.issues:
            mark = {"error": "❌", "warn": "⚠️", "info": "·"}.get(i.severity, "?")
            print(f"  {mark} [{i.kind}] {i.message}")
            if i.severity == "error":
                errors += 1
            elif i.severity == "warn":
                warns += 1

    summary = {
        "work": args.work,
        "volumes": len(reports),
        "errors": errors,
        "warnings": warns,
        "reports": [
            {
                "vol": r.vol,
                "volume_name": r.volume_name,
                "protagonists": r.protagonists,
                "ok": r.ok,
                "issues": [
                    {
                        "kind": i.kind,
                        "severity": i.severity,
                        "message": i.message,
                        "paragraph": i.paragraph,
                        "protagonist": i.protagonist,
                    }
                    for i in r.issues
                ],
            }
            for r in reports
            if r.issues or len(r.protagonists) > 1
        ],
    }
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n报告已写: {args.json_out}")

    print(f"\n合计 error={errors} warn={warns}")
    if errors or (args.fail_on_warn and warns):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
