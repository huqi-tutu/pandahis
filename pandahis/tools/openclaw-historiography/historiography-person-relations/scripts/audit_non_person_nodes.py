#!/usr/bin/env python3
"""审核关系表叶子节点是否为国家/政权/少数民族等非人物。

流程：
1. --scan         扫描全部 07 关系表，汇总疑似/硬规则命中
2. --apply-hard   按硬规则删除明确非人物节点（及空二级枢纽）
3. --llm-audit    对其余标题分批问 LLM（只判是否国/政权/民族/职衔空名）
4. --apply-llm    按 LLM 报告删除非人物节点

报告目录：data/05工作流中间产物/人物关系补全/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
OPENCLAW_ROOT = SKILL_ROOT.parent

if str(OPENCLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENCLAW_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from paths_config import histograph_paths, validate_histograph_root  # noqa: E402
from relations_lib import call_llm, extract_json_array, load_env  # noqa: E402

HUB_TITLES = frozenset(
    {
        "父母",
        "配偶",
        "兄弟姐妹",
        "君王",
        "同僚",
        "臣子",
        "内敌",
        "外敌",
        "老师",
        "学生",
        "好友",
    }
)

# 硬规则：明确为国/族/政权/职衔空名（不做氏姓误杀：*氏 不进此表）
HARD_NON_PERSON = frozenset(
    {
        # 族/部
        "犬戎",
        "淮夷",
        "三苗",
        "东夷",
        "西戎",
        "山戎",
        "北戎",
        "猃狁",
        "徐戎",
        "荆楚",
        "东胡",
        "林胡",
        "赤狄",
        "白狄",
        "长狄",
        "蛮夷",
        "蓝夷",
        "畎夷",
        "玄夷",
        "白夷",
        "赤夷",
        "风夷",
        "阳夷",
        "海岱诸部",
        "东夷部落联盟",
        "姜氏之戎",
        "燕京之戎",
        "余无之戎",
        "始呼之戎",
        "翳徒之戎",
        "义渠戎",
        "大荔戎",
        "陆浑戎",
        "西落鬼戎",
        "薰育戎狄",
        # 国/政权
        "秦国",
        "齐国",
        "晋国",
        "燕国",
        "韩国",
        "郑国",
        "赵国",
        "魏国",
        "吴国",
        "楚国",
        "宋国",
        "陈国",
        "舒国",
        "庸国",
        "沈国",
        "越国",
        "蔡国",
        "唐国",
        "中山",
        "中山国",
        "奄",
        "赵",
        "魏",
        # 职衔空名
        "中山国君",
        "东周君",
        "西周君",
        "虢国国君",
        "郑国国君",
        "鲁国国君",
    }
)

# 仅高置信后缀；禁止用「…戎/夷/狄/国」泛匹配（会误杀伯夷、简狄、孔安国、芈戎等）
HARD_SUFFIX_RE = re.compile(r"(部落联盟|诸部|之戎|之夷|之狄)$")
HARD_TITLE_LORD_RE = re.compile(r".+(国君|周君)$")
# 单字国名代称：仅当出现在敌对类别时由调用方结合类别判断
HARD_SINGLE_STATE = frozenset({"赵", "魏", "韩", "齐", "楚", "燕", "秦", "宋", "鲁", "卫"})

REPORT_DIR_REL = Path("data/05工作流中间产物/人物关系补全")


def _relations_dir(paths: dict[str, Path]) -> Path:
    return paths["root"] / "data" / "07人物关系"


def _report_dir(paths: dict[str, Path]) -> Path:
    d = paths["root"] / REPORT_DIR_REL
    d.mkdir(parents=True, exist_ok=True)
    return d


def _is_hub(rec: dict[str, Any]) -> bool:
    if str(rec.get("节点类型") or "").strip() == "二级分类":
        return True
    title = str(rec.get("关系节点标题") or "").strip()
    return title in HUB_TITLES


def hard_reason(title: str, *, cat: str = "") -> str | None:
    """高置信硬规则。宁漏勿杀；其余交给 LLM。"""
    t = title.strip()
    if not t or t in HUB_TITLES:
        return None
    if t in HARD_NON_PERSON:
        return "hard_list"
    if HARD_TITLE_LORD_RE.search(t):
        return "title_lord"  # 东周君 / 中山国君 / 鲁国国君
    if HARD_SUFFIX_RE.search(t):
        return "suffix_polity"
    # 「X国」仅当整词为常见国名（已在 HARD_NON_PERSON）；再兜底一字国号+国（秦国）
    # 绝不匹配「孔安国」等三字以上人名
    if re.fullmatch(r"[\u4e00-\u9fff]国", t):
        return "state_name"
    if t in {"中山国"}:
        return "state_name"
    if cat == "敌对" and t in HARD_SINGLE_STATE:
        return "single_state_foe"
    return None


def iter_relation_files(rel_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in rel_dir.glob("*关系表.json")
        if p.is_file() and not p.name.endswith("_manifest.json")
    )


def scan_leaves(rel_dir: Path) -> dict[str, Any]:
    by_title: dict[str, dict[str, Any]] = {}
    hits: list[dict[str, Any]] = []
    hard_hits: list[dict[str, Any]] = []
    files = 0
    for path in iter_relation_files(rel_dir):
        files += 1
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(rows, list):
            continue
        subject = path.name.replace("关系表.json", "")
        for rec in rows:
            if not isinstance(rec, dict) or _is_hub(rec):
                continue
            title = str(rec.get("关系节点标题") or "").strip()
            if not title:
                continue
            cat = str(rec.get("关系类别") or "").strip()
            lvl = str(rec.get("关系层级") or "").strip()
            hub = str(rec.get("所属一级关系") or "").strip()
            row = {
                "subject": subject,
                "file": path.name,
                "title": title,
                "cat": cat,
                "hub": hub,
                "lvl": lvl,
            }
            hits.append(row)
            bucket = by_title.setdefault(
                title, {"count": 0, "subjects": [], "cats": set(), "hard": None}
            )
            bucket["count"] += 1
            if subject not in bucket["subjects"]:
                bucket["subjects"].append(subject)
            bucket["cats"].add(cat)
            reason = hard_reason(title, cat=cat)
            if reason:
                bucket["hard"] = reason
                hard_hits.append({**row, "reason": reason})

    # serialize sets
    by_title_out = {
        k: {
            "count": v["count"],
            "subjects": v["subjects"],
            "cats": sorted(v["cats"]),
            "hard": v["hard"],
        }
        for k, v in sorted(by_title.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    }
    hard_titles = sorted({h["title"] for h in hard_hits})
    suspect_re = re.compile(
        r"(部落联盟|部落|诸部|方国|之戎|之夷|之狄|国君|周君|家族|氏$|"
        r"^[戎夷狄蛮胡]人$|^狄人$|^诸侯$|^戎王$|^戎州$|^人方|"
        r"[（(].*(夷|戎|狄|蛮|胡|族).*[)）])"
    )
    # 整词国名形态：秦国 / 中山国（不含孔安国：安国不在此）
    state_like_re = re.compile(r"^[\u4e00-\u9fff]{1,2}国$")

    def is_llm_suspect(title: str) -> bool:
        t = title.strip()
        if len(t) == 1:
            return True
        if re.fullmatch(r"[\u4e00-\u9fff]君", t):  # 虢君、徐君
            return True
        if state_like_re.fullmatch(t):
            return True
        return bool(suspect_re.search(t))

    # LLM 候选：敌对中硬规则未命中、且形迹可疑（其余真人名不送审）
    llm_candidates = sorted(
        t
        for t, meta in by_title_out.items()
        if "敌对" in meta["cats"] and not meta["hard"] and is_llm_suspect(t)
    )
    # 全量敌对未硬命中（供 --all-foe-llm）
    all_foe_unhard = sorted(
        t
        for t, meta in by_title_out.items()
        if "敌对" in meta["cats"] and not meta["hard"]
    )
    return {
        "scannedFiles": files,
        "leafRows": len(hits),
        "uniqueTitles": len(by_title_out),
        "hardTitles": hard_titles,
        "hardHitRows": len(hard_hits),
        "llmCandidates": llm_candidates,
        "allFoeUnhard": all_foe_unhard,
        "byTitle": by_title_out,
        "hardHits": hard_hits,
    }


def _prune_empty_hubs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """删除其下已无任何子节点的二级分类枢纽。"""
    child_parents: set[tuple[str, str]] = set()
    for rec in rows:
        if _is_hub(rec):
            continue
        cat = str(rec.get("关系类别") or "").strip()
        parent = str(rec.get("所属一级关系") or "").strip()
        if parent:
            child_parents.add((cat, parent))
        # 三级/四级：所属二级等也算占用
        for key in ("所属二级关系", "所属三级关系"):
            p = str(rec.get(key) or "").strip()
            if p:
                child_parents.add((cat, p))

    out: list[dict[str, Any]] = []
    for rec in rows:
        if not _is_hub(rec):
            out.append(rec)
            continue
        cat = str(rec.get("关系类别") or "").strip()
        title = str(rec.get("关系节点标题") or "").strip()
        if (cat, title) in child_parents:
            out.append(rec)
        # else drop empty hub
    return out


def remove_titles_from_file(
    path: Path, titles: set[str]
) -> tuple[int, list[str]]:
    """从文件删除标题在 titles 中的非枢纽节点；返回 (删除条数, 被删标题列表)。"""
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        return 0, []
    removed: list[str] = []
    kept: list[dict[str, Any]] = []
    for rec in rows:
        if not isinstance(rec, dict):
            continue
        title = str(rec.get("关系节点标题") or "").strip()
        if (not _is_hub(rec)) and title in titles:
            removed.append(title)
            continue
        kept.append(rec)
    if not removed:
        return 0, []
    kept = _prune_empty_hubs(kept)
    path.write_text(
        json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(removed), removed


def apply_hard(rel_dir: Path, scan: dict[str, Any]) -> dict[str, Any]:
    titles = set(scan.get("hardTitles") or [])
    if not titles:
        return {"removedRows": 0, "touchedFiles": [], "titles": []}
    touched: dict[str, list[str]] = defaultdict(list)
    total = 0
    for path in iter_relation_files(rel_dir):
        n, rem = remove_titles_from_file(path, titles)
        if n:
            total += n
            touched[path.name] = rem
    return {
        "removedRows": total,
        "touchedFiles": sorted(touched.keys()),
        "perFile": dict(touched),
        "titles": sorted(titles),
    }


def build_llm_prompt(batch: list[str]) -> str:
    lines = "\n".join(f"- {t}" for t in batch)
    return f"""你是中国古代史名称分类助手。请判断下列「关系图谱节点名」是否属于**非具体人物**。

只判断是否为以下之一（是则 nonPerson=true）：
1. 国家 / 政权 / 方国名（如秦国、齐国、奄、中山）
2. 少数民族 / 部族 / 部落联盟（如犬戎、淮夷、三苗、姜氏之戎）
3. 职衔式空名、无具体人名（如东周君、中山国君、某国国君）

下列算**具体人物侧、应保留**（nonPerson=false）：
- 具名人物（纣、蚩尤、吴起）
- 家族 / 氏姓习惯称谓（鲍氏、高氏、崔氏）——即使是群体，也保留

注意：
- 「有扈氏」「有苏氏」等：若主要指方国/部族政权而非家族人物集合，判 nonPerson=true；若更像家族/氏族指称可作关系对象，判 false。
- 单字国名代称（赵、魏）作敌对对象时判 nonPerson=true。

只输出 JSON 数组，每项：
{{"name":"…","nonPerson":true/false,"kind":"person|clan|state|ethnic|title_empty|other","note":"≤20字"}}

待判名称：
{lines}
"""


def run_llm_audit(
    candidates: list[str], *, batch_size: int, report_path: Path
) -> dict[str, Any]:
    load_env()
    results: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i : i + batch_size]
        prompt = build_llm_prompt(batch)
        try:
            raw = call_llm(prompt, session_prefix=f"rel-np-audit-{i // batch_size}-")
            arr = extract_json_array(raw)
            if not arr:
                errors.append(f"batch {i}: empty parse; raw_head={raw[:200]!r}")
                continue
            for item in arr:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                results[name] = {
                    "nonPerson": bool(item.get("nonPerson")),
                    "kind": str(item.get("kind") or ""),
                    "note": str(item.get("note") or ""),
                }
        except Exception as exc:  # noqa: BLE001
            errors.append(f"batch {i}: {exc}")
    missing = [t for t in candidates if t not in results]
    report = {
        "candidates": candidates,
        "classified": results,
        "missing": missing,
        "errors": errors,
        "nonPersonNames": sorted(
            n for n, meta in results.items() if meta.get("nonPerson")
        ),
        "keepNames": sorted(
            n for n, meta in results.items() if not meta.get("nonPerson")
        ),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def apply_llm(rel_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    titles = set(report.get("nonPersonNames") or [])
    if not titles:
        return {"removedRows": 0, "touchedFiles": [], "titles": []}
    touched: dict[str, list[str]] = defaultdict(list)
    total = 0
    for path in iter_relation_files(rel_dir):
        n, rem = remove_titles_from_file(path, titles)
        if n:
            total += n
            touched[path.name] = rem
    return {
        "removedRows": total,
        "touchedFiles": sorted(touched.keys()),
        "perFile": dict(touched),
        "titles": sorted(titles),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="审核并清除非人物关系节点")
    parser.add_argument("--scan", action="store_true", help="扫描并写 non_person_audit_scan.json")
    parser.add_argument("--apply-hard", action="store_true", help="应用硬规则删除")
    parser.add_argument("--llm-audit", action="store_true", help="对敌对中未硬命中标题分批 LLM")
    parser.add_argument("--apply-llm", action="store_true", help="按 LLM 报告删除")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument(
        "--all-foe-llm",
        action="store_true",
        help="LLM 审核全部敌对未硬命中标题（默认仅可疑形态）",
    )
    parser.add_argument(
        "--all-cats-llm",
        action="store_true",
        help="LLM 候选扩到全类别未硬命中且可疑的标题",
    )
    args = parser.parse_args()

    if not any([args.scan, args.apply_hard, args.llm_audit, args.apply_llm]):
        parser.print_help()
        return 2

    validate_histograph_root()
    paths = histograph_paths()
    rel_dir = _relations_dir(paths)
    out_dir = _report_dir(paths)
    scan_path = out_dir / "non_person_audit_scan.json"
    llm_path = out_dir / "non_person_llm_audit.json"
    apply_path = out_dir / "non_person_apply_report.json"

    scan = scan_leaves(rel_dir)
    if args.scan or args.apply_hard or args.llm_audit:
        scan_path.write_text(
            json.dumps(scan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"scan: files={scan['scannedFiles']} leaves={scan['leafRows']} "
            f"hardTitles={len(scan['hardTitles'])} llmCandidates={len(scan['llmCandidates'])}"
        )
        print(f"wrote {scan_path}")

    apply_report: dict[str, Any] = {}
    if args.apply_hard:
        hard_res = apply_hard(rel_dir, scan)
        apply_report["hard"] = hard_res
        print(
            f"apply-hard: removed={hard_res['removedRows']} "
            f"files={len(hard_res['touchedFiles'])}"
        )

    if args.llm_audit:
        if args.all_cats_llm:
            suspect_re = re.compile(
                r"(国|戎|夷|狄|蛮|胡|部落|诸部|方国|联盟|氏|君$|王$|侯$|[（(].+[)）])"
            )
            cands = sorted(
                t
                for t, meta in scan["byTitle"].items()
                if not meta.get("hard")
                and (len(t) == 1 or suspect_re.search(t))
            )
        elif args.all_foe_llm:
            cands = list(scan.get("allFoeUnhard") or scan["llmCandidates"])
        else:
            cands = list(scan["llmCandidates"])
        print(f"llm-audit: {len(cands)} titles, batch={args.batch_size}")
        report = run_llm_audit(cands, batch_size=args.batch_size, report_path=llm_path)
        print(
            f"llm done: nonPerson={len(report['nonPersonNames'])} "
            f"keep={len(report['keepNames'])} missing={len(report['missing'])} "
            f"errors={len(report['errors'])}"
        )
        print(f"wrote {llm_path}")

    if args.apply_llm:
        if not llm_path.is_file():
            print(f"missing {llm_path}; run --llm-audit first", file=sys.stderr)
            return 1
        report = json.loads(llm_path.read_text(encoding="utf-8"))
        llm_res = apply_llm(rel_dir, report)
        apply_report["llm"] = llm_res
        print(
            f"apply-llm: removed={llm_res['removedRows']} "
            f"files={len(llm_res['touchedFiles'])}"
        )

    if apply_report:
        # 再扫一次便于确认
        after = scan_leaves(rel_dir)
        apply_report["afterScan"] = {
            "hardTitles": after["hardTitles"],
            "hardHitRows": after["hardHitRows"],
            "llmCandidates": after["llmCandidates"],
        }
        apply_path.write_text(
            json.dumps(apply_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {apply_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
