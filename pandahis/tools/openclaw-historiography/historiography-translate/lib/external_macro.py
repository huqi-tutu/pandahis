"""外部补全两步法：宏观选题 →（判重）→ 挂锚嵌入。"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

from lib.config import TRANSLATE_DIR
from lib.source_citation import build_source_citation, display_work_name


def mother_work_label(recalled: Dict[str, Any]) -> str:
    """给人看的母本著作名，如《史记·高祖本纪》。"""
    cite = build_source_citation(recalled).strip()
    if cite:
        return cite if cite.startswith("《") else f"《{cite}》"
    work = display_work_name(str(recalled.get("母本著作") or ""))
    vol = ""
    for b in recalled.get("blocks") or []:
        if b.get("role") == "母本":
            vol = str(b.get("volume") or "").strip()
            if vol:
                break
    if work and vol:
        return f"《{work}·{vol}》"
    if work:
        return f"《{work}》"
    return str(recalled.get("母本著作") or "母本")


def build_external_macro_prompt(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    retry_feedback: str = "",
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "source_plan_external_macro.md").read_text(
        encoding="utf-8"
    )
    name = str(recalled.get("史略名称") or "").strip() or entry_id
    mother = mother_work_label(recalled)
    mother_code = str(recalled.get("母本著作") or "").strip()
    category = str(recalled.get("史略分类") or "").strip()
    feedback = ""
    if (retry_feedback or "").strip():
        feedback = (
            "\n--- 上次未通过（须修正）---\n"
            f"{retry_feedback.strip()}\n"
            "---\n"
        )
    return f"""【historiography-translate 外部补全 · 宏观选题】
史略ID: {entry_id}
史略名称: {name}
母本著作: {mother}
母本著作代码: {mother_code}
史略分类: {category or "（未标）"}
{feedback}
说明：本步不提供母本原文。通道只用于检索，不为覆盖通道凑 true。
第二层：只保留挂住主轴（合法性/制度/战局用人/历史评价/神话辩伪）的重要增量；宁缺毋滥。
出处禁止同一卷 {mother}；禁止现代评述与猎奇野史灌水。

{tpl}
"""


def build_external_anchor_prompt(
    entry_id: str,
    recalled: Dict[str, Any],
    external_items: List[Dict[str, Any]],
    checklist: List[Dict[str, Any]],
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "source_plan_external_anchor.md").read_text(
        encoding="utf-8"
    )
    lines: List[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("编号") or "").strip()
        info = str(item.get("信息点") or "").strip()
        if not mid:
            continue
        if len(info) > 48:
            info = info[:48] + "…"
        lines.append(f"{mid}\t{info}")
    total = len(lines)
    if len(lines) > 120:
        step = max(2, len(lines) // 80)
        sampled = lines[::step]
        if lines[-1] not in sampled:
            sampled.append(lines[-1])
        lines = sampled[:100]
        note = f"（清单共 {total} 条，已抽样展示 {len(lines)} 条）"
    else:
        note = f"（共 {len(lines)} 条）"
    payload = {
        "史略ID": entry_id,
        "史略名称": recalled.get("史略名称"),
        "外部补全": external_items,
    }
    return f"""【historiography-translate 外部补全 · 挂锚】
史略ID: {entry_id}

--- 待挂锚外部补全 ---
{json.dumps(payload, ensure_ascii=False, indent=2)}

--- 母本信息点 {note} ---
{chr(10).join(lines)}

{tpl}
"""


def _extract_json_obj(text: str) -> Dict[str, Any]:
    from llm.artifacts import extract_best_json, extract_plan_json

    plan = extract_plan_json(text)
    if isinstance(plan, dict):
        return plan
    best = extract_best_json(text)
    return best if isinstance(best, dict) else {}


def normalize_macro_external(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item.setdefault("母本锚点", "")
        if "采用" not in item:
            item["采用"] = True
        out.append(item)
    return out


def merge_anchors_into_external(
    external: List[Dict[str, Any]],
    anchored: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """按主题/出处对齐挂锚结果；对不齐则顺序回填。"""
    if not anchored:
        return external
    by_key: Dict[str, Dict[str, Any]] = {}
    for a in anchored:
        if not isinstance(a, dict):
            continue
        key = f"{a.get('主题')}|{a.get('出处')}"
        by_key[key] = a
    merged: List[Dict[str, Any]] = []
    for i, item in enumerate(external):
        key = f"{item.get('主题')}|{item.get('出处')}"
        src = by_key.get(key)
        if src is None and i < len(anchored) and isinstance(anchored[i], dict):
            src = anchored[i]
        out = dict(item)
        if src:
            anchor = str(src.get("母本锚点") or "").strip()
            if anchor:
                out["母本锚点"] = anchor
        merged.append(out)
    return merged


def fallback_anchors(
    external: List[Dict[str, Any]],
    checklist: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """无 LLM 挂锚时：采用项均匀挂到清单节点。"""
    mids = [
        str(x.get("编号") or "").strip()
        for x in checklist
        if isinstance(x, dict) and str(x.get("编号") or "").strip()
    ]
    if not mids:
        return external
    adopted_idx = [
        i for i, x in enumerate(external) if isinstance(x, dict) and x.get("采用") is True
    ]
    n = len(adopted_idx)
    out: List[Dict[str, Any]] = [dict(x) if isinstance(x, dict) else x for x in external]  # type: ignore[misc]
    for k, i in enumerate(adopted_idx):
        item = out[i]
        if not isinstance(item, dict):
            continue
        if str(item.get("母本锚点") or "").strip():
            continue
        pos = int((k + 0.5) * (len(mids) - 1) / max(n, 1)) if n else 0
        pos = min(max(pos, 0), len(mids) - 1)
        item["母本锚点"] = f"{mids[pos]} 后"
    return out


def run_macro_external_select(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    session_id: str,
    timeout_sec: int = 900,
    retry_feedback: str = "",
) -> Tuple[Dict[str, Any], str]:
    """返回 (解析后的决策 dict, 原始 response)。"""
    from llm.config import PROVIDER_DEEPSEEK, get_provider_name
    from llm.deepseek_provider import run_deepseek_turn
    from llm.provider import run_agent_turn

    prompt = build_external_macro_prompt(
        entry_id, recalled, retry_feedback=retry_feedback
    )
    if get_provider_name() == PROVIDER_DEEPSEEK:
        result = run_deepseek_turn(
            prompt,
            session_id=session_id,
            timeout_sec=timeout_sec,
            response_format={"type": "json_object"},
            max_attempts=2,
        )
    else:
        result = run_agent_turn(
            prompt, session_id=session_id, timeout_sec=timeout_sec
        )
    raw = str(result.get("result") or "")
    parsed = _extract_json_obj(raw)
    return parsed, raw


def run_anchor_external(
    entry_id: str,
    recalled: Dict[str, Any],
    external_items: List[Dict[str, Any]],
    checklist: List[Dict[str, Any]],
    *,
    session_id: str,
    timeout_sec: int = 600,
) -> Tuple[List[Dict[str, Any]], str]:
    need = [
        x
        for x in external_items
        if isinstance(x, dict)
        and x.get("采用") is True
        and not str(x.get("母本锚点") or "").strip()
    ]
    if not need:
        return external_items, ""

    from llm.config import PROVIDER_DEEPSEEK, get_provider_name
    from llm.deepseek_provider import run_deepseek_turn
    from llm.provider import run_agent_turn

    prompt = build_external_anchor_prompt(
        entry_id, recalled, external_items, checklist
    )
    if get_provider_name() == PROVIDER_DEEPSEEK:
        result = run_deepseek_turn(
            prompt,
            session_id=session_id,
            timeout_sec=timeout_sec,
            response_format={"type": "json_object"},
            max_attempts=2,
        )
    else:
        result = run_agent_turn(
            prompt, session_id=session_id, timeout_sec=timeout_sec
        )
    raw = str(result.get("result") or "")
    parsed = _extract_json_obj(raw)
    anchored = parsed.get("外部补全") if isinstance(parsed, dict) else None
    if not isinstance(anchored, list):
        return fallback_anchors(external_items, checklist), raw
    return merge_anchors_into_external(external_items, anchored), raw


def macro_plan_enabled() -> bool:
    """旧宏观选题两步法开关。默认随 plan 是否挖外部补全：polish 路径关闭。"""
    if not plan_external_hunt_enabled():
        return False
    return os.environ.get("TRANSLATE_EXTERNAL_MACRO", "1").strip() not in (
        "0",
        "false",
        "False",
        "no",
    )


def plan_external_hunt_enabled() -> bool:
    """plan 是否仍做跨书外部补全选题。

    默认关闭（交由 Phase2 润色自挖 + Phase3 质检）。
    仅当 TRANSLATE_PLAN_EXTERNAL=1，或 Phase2 走旧 enrich 模式时开启。
    """
    raw = (os.environ.get("TRANSLATE_PLAN_EXTERNAL") or "").strip()
    if raw:
        return raw.lower() not in {"0", "false", "no", "off"}
    mode = (os.environ.get("TRANSLATE_PHASE2_MODE") or "polish").strip().lower()
    return mode in {
        "enrich",
        "enrich_legacy",
        "chapter",
        "legacy",
        "legacy_batch",
        "batch",
    }


def build_decision_from_macro(
    entry_id: str,
    recalled: Dict[str, Any],
    macro: Dict[str, Any],
    external: List[Dict[str, Any]],
) -> Dict[str, Any]:
    refs = macro.get("参考著作") if isinstance(macro.get("参考著作"), list) else []
    if not refs:
        refs = []
        for x in external:
            if not isinstance(x, dict):
                continue
            src = str(x.get("出处") or "").strip()
            if src and src not in refs:
                refs.append(src)
    risks = macro.get("风险提示") if isinstance(macro.get("风险提示"), list) else []
    if not risks:
        risks = [
            "外部补全仅收冲突/另说/背景/异评；禁雕花与无实质异文",
            "仅限古代资料；嵌入前已做全书母本判重",
        ]
    # 不截断：超限由门禁拦下重试；通过后 apply_reference_works_cap
    cleaned: List[str] = []
    for r in refs:
        s = str(r or "").strip()
        if s and s not in cleaned:
            cleaned.append(s)
    return {
        "史略ID": entry_id,
        "史略名称": recalled.get("史略名称"),
        "母本著作": recalled.get("母本著作"),
        "外部补全": external,
        "参考著作": cleaned,
        "写作结构": [{"小节": "本传", "说明": "宏观选题后挂锚嵌入分批"}],
        "风险提示": risks,
    }


def macro_reference_count(macro: Dict[str, Any], external: List[Dict[str, Any]]) -> int:
    """未截断的参考著作条数（用于门禁是否超限）。"""
    refs = macro.get("参考著作") if isinstance(macro.get("参考著作"), list) else []
    if refs:
        seen: List[str] = []
        for r in refs:
            s = str(r or "").strip()
            if s and s not in seen:
                seen.append(s)
        return len(seen)
    seen = []
    for x in external:
        if not isinstance(x, dict):
            continue
        src = str(x.get("出处") or "").strip()
        if src and src not in seen:
            seen.append(src)
    return len(seen)
