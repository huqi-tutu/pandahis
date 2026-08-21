"""外部补全 vs 全书母本清单信息点：脚本粗筛 + 可选 LLM 精判。"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

_DIFF_MARKERS = (
    "未载",
    "略写",
    "带过",
    "更详",
    "较详",
    "异说",
    "不同",
    "冲突",
    "差异",
    "另记",
    "另载",
    "则记",
    "则载",
    "多出",
    "增量",
    "母本无",
    "本纪未",
    "仅略",
    "未提",
    "未写",
    "未详",
    "补充细节",
    "评价差异",
)

_PLAIN_RE = re.compile(r"[^\u4e00-\u9fff0-9A-Za-z]+")


def _env_flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _plain(text: str) -> str:
    return _PLAIN_RE.sub("", str(text or ""))


def _bigrams(text: str) -> set[str]:
    p = _plain(text)
    if len(p) < 2:
        return {p} if p else set()
    return {p[i : i + 2] for i in range(len(p) - 1)}


def overlap_ratio(query: str, corpus: str) -> float:
    """query 的字双字母有多少落在 corpus 中（0–1）。"""
    bq = _bigrams(query)
    if not bq:
        return 0.0
    bc = _bigrams(corpus)
    if not bc:
        return 0.0
    return len(bq & bc) / len(bq)


def has_diff_marker(text: str) -> bool:
    t = str(text or "")
    return any(m in t for m in _DIFF_MARKERS)


def build_mother_info_rows(plan: Dict[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in plan.get("母本逐句清单") or []:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("编号") or "").strip()
        info = str(item.get("信息点") or "").strip()
        orig = str(item.get("原文摘句") or item.get("text") or "").strip()
        must = item.get("必现词") or []
        must_s = "".join(str(x) for x in must) if isinstance(must, list) else str(must)
        blob = f"{info}{orig}{must_s}"
        if not mid and not blob:
            continue
        rows.append({"编号": mid or "?", "文本": blob, "信息点": info, "原文摘句": orig})
    return rows


def score_external_against_mother(
    item: Dict[str, Any],
    mother_rows: Sequence[Dict[str, str]],
) -> Tuple[float, str]:
    """返回 (最高重叠分, 撞车 M 编号)。"""
    theme = str(item.get("主题") or "")
    rel = str(item.get("与母本关系") or item.get("理由") or "")
    query = f"{theme} {rel}".strip()
    if not query or not mother_rows:
        return 0.0, ""
    full = "".join(r["文本"] for r in mother_rows)
    q_plain = _plain(query)
    # 整段主题被母本原文吃掉
    if len(q_plain) >= 8 and q_plain in _plain(full):
        # 找最先包含的 M
        for r in mother_rows:
            if q_plain in _plain(r["文本"]):
                return 0.95, r["编号"]
        return 0.95, mother_rows[0]["编号"]

    best = 0.0
    best_m = ""
    for r in mother_rows:
        s = overlap_ratio(query, r["文本"])
        # 主题单独对信息点再比一次（关系字段很长时稀释）
        if theme.strip():
            s = max(s, overlap_ratio(theme, r["文本"]))
        if s > best:
            best = s
            best_m = r["编号"]
    # 对全书拼接再比，捕捉跨句分散的同事件
    s_full = overlap_ratio(theme or query, full) if theme.strip() else overlap_ratio(query, full)
    if s_full > best:
        return s_full, best_m or (mother_rows[0]["编号"] if mother_rows else "")
    return best, best_m


def _confident_duplicate(score: float, rel: str) -> bool:
    """脚本可直接降级：高重叠且无差异话术，或极高重叠。"""
    if score >= 0.72:
        return True
    if score >= 0.52 and not has_diff_marker(rel):
        return True
    return False


def _suspicious(score: float, rel: str) -> bool:
    if score < 0.36:
        return False
    if _confident_duplicate(score, rel):
        return False
    return True


def looks_trivial_variant_admission(text: str) -> bool:
    """模型自承无实质分歧（仅异字/沿用/更简）→ 应降级。"""
    t = str(text or "")
    # 蛟龙↔交龙：仅当把异字当增量时降级；「禁止比较异字」等禁令说明不降级
    if "蛟龙" in t and "交龙" in t:
        if not any(neg in t for neg in ("禁止", "不得", "勿", "严禁", "不要")):
            return True
    if "仅用字" in t or ("异字" in t and "禁止" not in t and "严禁" not in t):
        return True
    markers = (
        "实质相同",
        "基本沿用",
        "基本相同",
        "大体相同",
        "记载略同",
        "情节略有不同",
        "细节略有不同",
        "文字差异",
        "细微变化",
        "可视为异文",
        "仅文字",
        "用字不同",
        "更简略",
        "较为简略",
        "写得更短",
        "未提供新",
        "无更大信息",
        "沿用史记",
        "沿用母本",
    )
    if not any(m in t for m in markers):
        return False
    # 若同时强调评价/权谋/因果等强增量，不因一句「略有」误杀
    strong = ("评价", "赞曰", "权谋", "因果", "分歧", "冲突", "另载", "未载", "未详述", "更详", "多出")
    if any(s in t for s in strong) and not any(
        m in t
        for m in (
            "实质相同",
            "基本沿用",
            "基本相同",
            "可视为异文",
            "记载略同",
            "更简略",
        )
    ):
        return False
    return True


def script_demote_duplicates(plan: Dict[str, Any]) -> Dict[str, Any]:
    """粗筛：明显与全书母本信息点撞车的采用项 → 采用:false。

    返回统计：{"demoted": n, "suspicious": [{...}, ...]}
    """
    mother_rows = build_mother_info_rows(plan)
    external = plan.get("外部补全")
    demoted = 0
    suspicious: List[Dict[str, Any]] = []
    if not isinstance(external, list):
        return {"demoted": 0, "suspicious": []}

    for i, item in enumerate(external):
        if not isinstance(item, dict) or item.get("采用") is not True:
            continue
        rel = str(item.get("与母本关系") or item.get("理由") or "")
        if looks_trivial_variant_admission(rel):
            item["采用"] = False
            reason = "无实质分歧（脚本）：关系说明自承实质相同/仅异文，自动降级"
            prev = str(item.get("理由") or "").strip()
            item["理由"] = f"{prev}；{reason}" if prev and "无实质分歧" not in prev else reason
            item["_判重"] = "trivial_demote"
            demoted += 1
            continue
        if not mother_rows:
            continue
        score, hit_m = score_external_against_mother(item, mother_rows)
        item["_判重分"] = round(score, 3)
        item["_判重撞车M"] = hit_m
        if _confident_duplicate(score, rel):
            item["采用"] = False
            reason = (
                f"全书母本信息点判重（脚本）：与 {hit_m or '母本'} 高度重合"
                f"（分={score:.2f}），自动降级"
            )
            prev = str(item.get("理由") or "").strip()
            item["理由"] = f"{prev}；{reason}" if prev and "全书母本信息点判重" not in prev else reason
            item["_判重"] = "script_demote"
            demoted += 1
        elif _suspicious(score, rel):
            suspicious.append(
                {
                    "index": i,
                    "主题": str(item.get("主题") or "")[:80],
                    "出处": str(item.get("出处") or ""),
                    "母本锚点": str(item.get("母本锚点") or ""),
                    "与母本关系": rel[:160],
                    "判重分": round(score, 3),
                    "撞车M": hit_m,
                }
            )
            item["_判重"] = "suspicious"
    return {"demoted": demoted, "suspicious": suspicious}


def _llm_dedupe_call(entry_id: str, prompt: str) -> str:
    from llm.config import PROVIDER_DEEPSEEK, ensure_deepseek_v4_pro, get_provider_name
    from llm.deepseek_provider import run_deepseek_turn
    from lib.openclaw import run_agent_turn

    if get_provider_name() == PROVIDER_DEEPSEEK:
        ensure_deepseek_v4_pro()
    nonce = uuid.uuid4().hex[:8]
    session_id = f"tr-extdedupe-{entry_id.replace('_', '-').lower()}-{nonce}"
    if get_provider_name() == PROVIDER_DEEPSEEK:
        res = run_deepseek_turn(
            prompt,
            session_id=session_id,
            timeout_sec=180,
            temperature=0,
            response_format={"type": "json_object"},
        )
        return str(res.get("result") or "")
    return str(run_agent_turn(prompt, session_id=session_id, timeout_sec=180))


def _parse_llm_dedupe_json(raw: str) -> List[Dict[str, Any]]:
    from llm.artifacts import extract_best_json

    obj = extract_best_json(raw) if raw else None
    if isinstance(obj, dict):
        items = obj.get("裁决") or obj.get("items") or obj.get("results") or []
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    return []


def refine_suspicious_with_llm(
    plan: Dict[str, Any],
    suspicious: Sequence[Dict[str, Any]],
    *,
    entry_id: str,
) -> int:
    """对可疑项做 LLM 精判；确认为重复则降级。返回降级数。"""
    if not suspicious:
        return 0
    mother_rows = build_mother_info_rows(plan)
    # 压缩母本信息点，控制 prompt
    lines = []
    for r in mother_rows[:220]:
        tip = (r.get("信息点") or r.get("原文摘句") or "")[:48]
        if tip:
            lines.append(f"{r['编号']}: {tip}")
    mother_block = "\n".join(lines)
    cand_lines = []
    for s in suspicious[:12]:
        cand_lines.append(
            json.dumps(
                {
                    "index": s["index"],
                    "主题": s.get("主题"),
                    "出处": s.get("出处"),
                    "母本锚点": s.get("母本锚点"),
                    "与母本关系": s.get("与母本关系"),
                    "脚本撞车M": s.get("撞车M"),
                    "脚本分": s.get("判重分"),
                },
                ensure_ascii=False,
            )
        )
    prompt = (
        "你是史料计划质检。判断下列「外部补全」候选相对**全书母本信息点**是否重复。\n"
        "重复 = 主体事件+结果与母本某句（含后文）实质相同，仅换书换说法。"
        "不重复 = 母本未载、或确有异说/冲突评价/母本略而他书详的增量。\n"
        "只输出 JSON：{\"裁决\":[{\"index\":0,\"重复\":true,\"撞车M\":\"M010\",\"理由\":\"...\"}]}\n\n"
        "--- 全书母本信息点（摘要）---\n"
        f"{mother_block}\n\n"
        "--- 待裁决外部补全 ---\n"
        + "\n".join(cand_lines)
    )
    try:
        raw = _llm_dedupe_call(entry_id or str(plan.get("史略ID") or "x"), prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"   ⚠️ 外部补全 LLM 判重失败（保留脚本结果）: {exc}", flush=True)
        return 0

    verdicts = _parse_llm_dedupe_json(raw)
    external = plan.get("外部补全")
    if not isinstance(external, list):
        return 0
    demoted = 0
    by_index = {int(v["index"]): v for v in verdicts if "index" in v}
    for s in suspicious:
        idx = int(s["index"])
        v = by_index.get(idx)
        if not v:
            continue
        dup = v.get("重复")
        if dup is True or dup == "true" or dup == 1:
            if idx < 0 or idx >= len(external) or not isinstance(external[idx], dict):
                continue
            item = external[idx]
            if item.get("采用") is not True:
                continue
            item["采用"] = False
            hit = str(v.get("撞车M") or s.get("撞车M") or "")
            reason = str(v.get("理由") or "全书母本信息点判重（LLM）").strip()
            item["理由"] = (
                f"{reason}；撞车 {hit}" if hit and hit not in reason else reason
            )
            item["_判重"] = "llm_demote"
            demoted += 1
        elif isinstance(external[idx], dict):
            external[idx]["_判重"] = "llm_keep"
    return demoted


def apply_external_mother_dedupe(
    plan: Dict[str, Any],
    *,
    entry_id: str = "",
    use_llm: bool = False,
) -> Dict[str, Any]:
    """混合判重入口。返回 {script_demoted, llm_demoted, suspicious}。"""
    if not _env_flag("TRANSLATE_EXTERNAL_DEDUPE", "1"):
        return {"script_demoted": 0, "llm_demoted": 0, "suspicious": 0}

    stats = script_demote_duplicates(plan)
    llm_n = 0
    allow_llm = use_llm and _env_flag("TRANSLATE_EXTERNAL_DEDUPE_LLM", "1")
    if allow_llm and stats["suspicious"]:
        llm_n = refine_suspicious_with_llm(
            plan,
            stats["suspicious"],
            entry_id=entry_id or str(plan.get("史略ID") or ""),
        )
    meta = plan.get("_外部补全判重") if isinstance(plan.get("_外部补全判重"), dict) else {}
    plan["_外部补全判重"] = {
        **meta,
        "script_demoted": stats["demoted"],
        "llm_demoted": llm_n,
        "suspicious": len(stats["suspicious"]),
    }
    if stats["demoted"] or llm_n:
        print(
            f"   🔎 外部补全全书判重: 脚本降级 {stats['demoted']}，"
            f"LLM 降级 {llm_n}，可疑 {len(stats['suspicious'])}",
            flush=True,
        )
    return {
        "script_demoted": stats["demoted"],
        "llm_demoted": llm_n,
        "suspicious": len(stats["suspicious"]),
    }
