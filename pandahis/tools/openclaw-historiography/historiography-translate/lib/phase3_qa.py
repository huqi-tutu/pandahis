"""Phase3 质检：程序预检 + LLM 报告（不重写正文）。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.citation_mode import apply_quote_style_fixes, detect_curly_source_quotes
from lib.longform_compat import (
    _is_heal_duplicate,
    _plain,
    detect_under_rewrite,
    detect_under_rewrite_warnings,
    heal_paraphrase_duplicates_in_detail,
    mother_enrich_overlap,
)
from lib.place_now import missing_first_now_places

DEFAULT_REPAIR_LEVELS = ("P0", "P1", "P2", "P3")


def phase3_enabled() -> bool:
    return (os.environ.get("TRANSLATE_PHASE3_QA") or "1").strip() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _strip_ref(text: str) -> str:
    body = str(text or "")
    for sep in ("\n\n参考著作\n", "\n参考著作\n", "\n\n参考著作"):
        if sep in body:
            return body.split(sep, 1)[0].rstrip()
    return body.rstrip()


def _paras(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", _strip_ref(text)) if p.strip()]


# 仅拦明确乱码残句；勿匹配正常「听了也受不了」
_GARBLED = re.compile(
    r"又了也受不了|(?<![听])又了也|这逻辑也是没谁了"
)

_LATE_MARKERS = ("征和", "轮台", "罪己", "晚而改过", "顾托得人")
_MID_AFTER_LATE = ("再次来到泰山", "又往东边巡游", "公玊带", "公玉带", "东泰山")


def program_qa_findings(
    *,
    mother: str,
    detail: str,
    plan: Optional[Dict[str, Any]] = None,
    source_original: str = "",
) -> List[Dict[str, str]]:
    """程序可稳定抓到的问题（不替代 LLM 史实判断）。"""
    plan_data = plan or {}
    findings: List[Dict[str, str]] = []
    body = _strip_ref(detail)
    plain_body = _plain(body)

    # 残句 / 明显乱码
    for m in _GARBLED.finditer(body):
        frag = body[max(0, m.start() - 8) : m.end() + 12]
        if "又了也" in m.group(0) or "又了也受不了" in m.group(0):
            # 排除正常「听了也受不了」
            if "听了也受不了" in frag and "又了也" not in frag.replace("听了也", ""):
                continue
            findings.append(
                {
                    "级别": "P0",
                    "类别": "标点",
                    "说明": "疑似生成残句/乱码",
                    "摘录": frag.replace("\n", " ")[:80],
                }
            )

    # 未闭合直角/弯引（粗检）
    if plain_body.count("「") != plain_body.count("」"):
        findings.append(
            {
                "级别": "P0",
                "类别": "标点",
                "说明": f"直角引号未配对（「{plain_body.count('「')} / 」{plain_body.count('」')}）",
                "摘录": "",
            }
        )
    if plain_body.count("“") != plain_body.count("”"):
        findings.append(
            {
                "级别": "P1",
                "类别": "标点",
                "说明": f"弯引号未配对（“{plain_body.count('“')} / ”{plain_body.count('”')}）",
                "摘录": "",
            }
        )

    from lib.prose_sanitize import detect_prose_punctuation_defects

    for note in detect_prose_punctuation_defects(body):
        findings.append(
            {
                "级别": "P0",
                "类别": "标点",
                "说明": note,
                "摘录": "",
            }
        )

    # 弯引装原文（对照史料原文全文，plan 摘句作补充）
    for err in detect_curly_source_quotes(
        body, plan_data, source_original=source_original, label="成稿"
    ):
        findings.append(
            {
                "级别": "P1",
                "类别": "标点",
                "说明": err[:120],
                "摘录": "",
            }
        )

    heading = re.search(r"(?m)^#{1,6}\s+\S.*$", body)
    if heading:
        findings.append(
            {
                "级别": "P0",
                "类别": "格式",
                "说明": "正文含 Markdown 章节标题；成稿须连续说书，禁止论文提纲",
                "摘录": heading.group(0).strip()[:80],
            }
        )

    missing_places = missing_first_now_places(body)
    if missing_places:
        shown = "、".join(missing_places[:12])
        findings.append(
            {
                "级别": "P1",
                "类别": "地名",
                "说明": (
                    "对照表内地名首次出现未标今地（对照表是已核实缓存，不是全库）："
                    + shown
                ),
                "摘录": shown[:120],
            }
        )

    from lib.annotation_ledger import missing_era_year_notes

    missing_years = missing_era_year_notes(body)
    if missing_years:
        shown = "、".join(missing_years[:10])
        findings.append(
            {
                "级别": "P1",
                "类别": "纪年",
                "说明": "显式年号/帝纪年缺公元并注：" + shown,
                "摘录": shown[:120],
            }
        )

    # 段落释义双写
    seen: List[str] = []
    for i, p in enumerate(_paras(detail), 1):
        pl = _plain(p)
        if len(pl) < 80:
            continue
        if _is_heal_duplicate(pl, seen):
            findings.append(
                {
                    "级别": "P0",
                    "类别": "重复",
                    "说明": f"第 {i} 段与前文情节近重复（换说法双写）",
                    "摘录": pl[:60],
                }
            )
        else:
            seen.append(pl)

    # 时间线：晚年标记后出现中期续写
    late_pos = -1
    for mk in _LATE_MARKERS:
        j = body.find(mk)
        if j >= 0 and (late_pos < 0 or j < late_pos):
            late_pos = j
    if late_pos >= 0:
        after = body[late_pos:]
        for mk in _MID_AFTER_LATE:
            if mk in after:
                findings.append(
                    {
                        "级别": "P0",
                        "类别": "时间线",
                        "说明": f"晚年叙述（约「{body[late_pos:late_pos+8]}…」）之后又出现中前期情节「{mk}」",
                        "摘录": mk,
                    }
                )
                break

    # 相对母本过短 / 重合异常（提示）
    mlen = len(_plain(mother))
    elen = len(plain_body)
    if mlen >= 400 and elen < int(mlen * 0.55):
        findings.append(
            {
                "级别": "P1",
                "类别": "漏译",
                "说明": f"成稿去空白字数偏短（{elen} < 母本×0.55={int(mlen*0.55)}），疑似漏段",
                "摘录": "",
            }
        )
    if mlen >= 400 and elen >= 200:
        cov = mother_enrich_overlap(mother, detail)
        if cov >= 0.95:
            findings.append(
                {
                    "级别": "P1",
                    "类别": "其他",
                    "说明": f"与母本重合 {cov:.0%}，润色可能不足（近誊抄）",
                    "摘录": "",
                }
            )

    # 有补充迹象却无参考著作
    has_ref_section = "参考著作" in detail
    titles = re.findall(r"《([^》]+)》", body)
    supplement_markers = (
        "另有记载",
        "《汉书》",
        "《后汉书》",
        "《资治通鉴》",
        "据《",
        "他书",
        "异说",
    )
    has_supplement_signal = any(m in body for m in supplement_markers) or len(titles) >= 2
    if has_supplement_signal and not has_ref_section:
        findings.append(
            {
                "级别": "P0",
                "类别": "史源",
                "说明": "正文似有他书补充/多书引用，但文末缺少「参考著作」列表",
                "摘录": "、".join(titles[:5]),
            }
        )
    elif not has_ref_section:
        findings.append(
            {
                "级别": "P1",
                "类别": "史源",
                "说明": "文末缺少「参考著作」列表（至少应列核心母本）",
                "摘录": "",
            }
        )

    from lib.mother_span import format_span_hole_errors, missing_mother_span_holes

    for err in format_span_hole_errors(
        missing_mother_span_holes(mother, detail, source_original)
    ):
        findings.append(
            {
                "级别": "P1",
                "类别": "漏译",
                "说明": err[:180],
                "摘录": err[err.find("段首：") + 3 :][:80] if "段首：" in err else "",
            }
        )

    return findings


def _clip(text: str, limit: int, head: int, tail: int) -> str:
    s = str(text or "")
    if len(s) <= limit:
        return s
    return s[:head] + "\n…\n" + s[-tail:]


def _fill_tpl(tpl: str, *, core_source: str, person: str) -> str:
    return (
        tpl.replace("{{CORE_SOURCE}}", core_source or "（未标注）")
        .replace("{{PERSON}}", person or "（未标注）")
    )


def extract_fenced_block(raw: str, name: str) -> str:
    """提取 <<<NAME ... NAME>>> 块。"""
    text = str(raw or "")
    m = re.search(
        rf"<<<{re.escape(name)}\s*([\s\S]*?)\s*{re.escape(name)}>>>",
        text,
    )
    if m:
        return m.group(1).strip()
    # 兼容无尾部 >>> 的宽松形式
    m2 = re.search(
        rf"<<<{re.escape(name)}\s*([\s\S]*?)\s*{re.escape(name)}\b",
        text,
    )
    return m2.group(1).strip() if m2 else ""


def _extract_qa_json(raw: str) -> Optional[Dict[str, Any]]:
    fenced = extract_fenced_block(raw, "QA_JSON")
    text = fenced or str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def build_phase3_qa_prompt(
    *,
    entry_id: str,
    mother: str,
    detail: str,
    output_file: Path,
    program_findings: List[Dict[str, str]],
    core_source: str = "",
    person: str = "",
) -> str:
    from lib.config import TRANSLATE_DIR

    tpl = _fill_tpl(
        (TRANSLATE_DIR / "prompts" / "phase3_qa.md").read_text(encoding="utf-8"),
        core_source=core_source,
        person=person,
    )
    from lib.quality_constitution import constitution_snip

    prog = json.dumps(program_findings, ensure_ascii=False, indent=2)
    mother_s = _clip(mother, 20000, 10000, 6000)
    detail_s = _clip(detail, 28000, 14000, 10000)
    constitution = constitution_snip(phase="phase3")
    return f"""【historiography-translate Phase3 · 第一轮质检 · 只找问题】
史略ID: {entry_id}
报告路径: {output_file}

--- 质量宪法（语义核对 + 反向取证）---
{constitution}
---

程序预检（供参考，请复核；本轮仍禁止改正文）：
{prog}

--- Phase1 母本顺译（对照用）---
{mother_s}
---

--- Phase2 成稿（质检对象）---
{detail_s}
---

{tpl}
"""


def merge_qa_report(
    program_findings: List[Dict[str, str]],
    llm_obj: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = list(program_findings)
    summary = ""
    llm_pass = None
    priority: List[str] = []
    if isinstance(llm_obj, dict):
        summary = str(llm_obj.get("摘要") or "")
        llm_pass = llm_obj.get("通过")
        priority = [str(x) for x in (llm_obj.get("优先修改") or []) if x]
        p0n = int(llm_obj.get("P0条数") or 0)
        if p0n > 0 and not any(str(x.get("级别")) == "P0" for x in issues):
            issues.append(
                {
                    "级别": "P0",
                    "类别": "其他",
                    "说明": f"LLM 报告含 {p0n} 条 P0（详见 .qa.md）",
                    "摘录": "",
                }
            )
        for it in llm_obj.get("问题") or []:
            if not isinstance(it, dict):
                continue
            issues.append(
                {
                    "级别": str(it.get("级别") or "P1"),
                    "类别": str(it.get("类别") or "其他"),
                    "说明": str(it.get("说明") or ""),
                    "摘录": str(it.get("摘录") or "")[:120],
                }
            )
    else:
        summary = "LLM 质检未返回有效 QA_JSON（请看 .qa.md 全文）"

    seen = set()
    uniq: List[Dict[str, str]] = []
    for it in issues:
        key = (it.get("级别"), it.get("类别"), (it.get("说明") or "")[:40])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)

    has_p0 = any(str(x.get("级别")) == "P0" for x in uniq)
    if llm_pass is False:
        passed = False
    elif llm_pass is True and not has_p0:
        passed = True
    else:
        passed = not has_p0

    return {
        "通过": passed,
        "问题": uniq,
        "摘要": summary,
        "优先修改": priority,
        "程序条数": len(program_findings),
        "LLM解析": bool(llm_obj),
    }


def load_qa_accept(path: Path) -> Dict[str, Any]:
    """可选覆盖文件（兼容旧流程）；默认流水线不再依赖人工确认。"""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def build_accepted_issue_text(
    qa_md: str,
    qa_json: Dict[str, Any],
    accept: Optional[Dict[str, Any]] = None,
    *,
    auto: bool = True,
    include_qa_md: bool = False,
    auto_levels: Optional[List[str]] = None,
) -> str:
    """整理须修复的问题清单。默认 auto=True：列入报告的 P0–P3 均须修。"""
    accept = accept or {}
    levels = list(auto_levels or list(DEFAULT_REPAIR_LEVELS))
    lines: List[str] = []

    # 点名接受可收窄；否则按级别自动采纳
    named = accept.get("接受") or accept.get("accepted") or []
    if named and not auto:
        lines.append("【点名接受】" + "、".join(str(x) for x in named))
    else:
        lines.append(f"【策略】自动采纳 {'/'.join(levels)}（无人工确认）。")
        for it in qa_json.get("问题") or []:
            lv = str(it.get("级别") or "")
            if lv in levels:
                lines.append(
                    f"- {lv} | {it.get('类别')}: {it.get('说明')} | 摘录:{it.get('摘录')}"
                )

    extra = str(accept.get("额外说明") or accept.get("note") or "").strip()
    if extra:
        lines.append("【额外说明】" + extra)
    pri = qa_json.get("优先修改") or []
    if pri:
        lines.append("【报告优先修改】" + "、".join(str(x) for x in pri))

    if include_qa_md and qa_md.strip():
        lines.append("\n--- 质检报告摘录（供定位）---\n")
        lines.append(_clip(qa_md, 8000, 4000, 3000))
    return "\n".join(lines) if lines else "（无待修问题）"


def issues_need_repair(qa_json: Dict[str, Any], *, levels: Optional[List[str]] = None) -> bool:
    want = set(levels or DEFAULT_REPAIR_LEVELS)
    return any(str(x.get("级别")) in want for x in (qa_json.get("问题") or []))



def build_phase4_repair_prompt(
    *,
    entry_id: str,
    detail: str,
    core_source: str,
    accepted_issues: str,
    output_file: Path,
) -> str:
    from lib.config import TRANSLATE_DIR

    tpl = (TRANSLATE_DIR / "prompts" / "phase4_repair.md").read_text(encoding="utf-8")
    detail_s = _clip(detail, 28000, 14000, 10000)
    return f"""【historiography-translate Phase4 · 定向修复】
史略ID: {entry_id}
产出路径: {output_file}

【第一部分：原始成稿】
{detail_s}

【第二部分：已经确认须修改的问题清单】
{accepted_issues}

【第三部分：核心原典】
{core_source or "（未标注）"}

{tpl}
"""


def build_phase5_recheck_prompt(
    *,
    entry_id: str,
    core_source: str,
    person: str,
    before: str,
    after: str,
    qa_md: str,
    output_file: Path,
    issue_digest: str = "",
) -> str:
    from lib.config import TRANSLATE_DIR

    tpl = _fill_tpl(
        (TRANSLATE_DIR / "prompts" / "phase5_recheck.md").read_text(encoding="utf-8"),
        core_source=core_source,
        person=person,
    )
    # 复检以「修复后全文 + 短清单」为主；修复前只留头尾对照，避免双倍灌文
    digest = issue_digest or _clip(qa_md, 6000, 3000, 2000)
    return f"""【historiography-translate Phase5 · 最终复检】
史略ID: {entry_id}
报告路径: {output_file}

【核心原典】{core_source or "（未标注）"}
【核心人物】{person or "（未标注）"}

【须复核的问题清单】
{digest}

【修复前成稿（头尾对照，非全文）】
{_clip(before, 8000, 4000, 3000)}

【修复后成稿（主检对象）】
{_clip(after, 28000, 14000, 10000)}

{tpl}
"""


def extract_repaired_body(raw: str) -> str:
    body = extract_fenced_block(raw, "REPAIRED")
    if body:
        return body.strip()
    # 回退：若整份就是 JSON 翻译详情
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("翻译详情"), str):
            return data["翻译详情"].strip()
    except json.JSONDecodeError:
        pass
    # 回退：模型直接输出正文（无围栏）——取「版本A」后或全文叙事段
    text = str(raw or "").strip()
    if not text:
        return ""
    for marker in ("### 版本A", "## 版本A", "版本A：", "版本A:"):
        if marker in text:
            text = text.split(marker, 1)[1]
            break
    # 去掉修改记录表格之后的部分
    for cut in ("### 版本B", "## 版本B", "<<<REPAIR_JSON", "修改记录"):
        if cut in text:
            text = text.split(cut, 1)[0]
    text = text.strip()
    # 至少像一篇文章
    if (len(text) >= 80 and "参考著作" in text) or len(text) >= 400:
        return text
    return ""


def extract_repair_json(raw: str) -> Optional[Dict[str, Any]]:
    fenced = extract_fenced_block(raw, "REPAIR_JSON")
    return _extract_qa_json(fenced or raw)


def extract_recheck_json(raw: str) -> Optional[Dict[str, Any]]:
    fenced = extract_fenced_block(raw, "RECHECK_JSON")
    return _extract_qa_json(fenced or raw)


def verify_polish_draft_light(
    *,
    entry_id: str,
    detail: str,
    mother: str,
    source_original: str = "",
    out_dir: Optional[Path] = None,
    entry_name: str = "",
    exclude_version: str = "",
    plan: Optional[Dict[str, Any]] = None,
    check_intro: bool = False,
    check_epilogue: bool = False,
) -> Tuple[bool, List[str]]:
    """Phase2 润色后轻量门禁（不做他书补全硬拦）。

    必须拦住近誊抄、偏薄、漏段；可选相对旧优稿回归门禁。
    分章时：仅首章 check_intro、末章 check_epilogue；整篇两者皆开。
    """
    errs: List[str] = []
    body = _strip_ref(detail)
    if len(_plain(body)) < 80:
        errs.append("Phase2 成稿过短或为空")
    if "又了也受不了" in body or re.search(r"(?<![听])又了也", body):
        errs.append("成稿含疑似残句「又了也…」")
    if "参考著作" not in detail:
        errs.append("文末缺少「参考著作」列表（有补充必须列出实际用到的书）")
    if re.search(r"(?m)^#{1,6}\s+\S", body):
        errs.append("成稿含 Markdown 章节标题（# / ##）；须连续说书，禁止论文提纲")
    errs.extend(detect_under_rewrite(mother, body, label="Phase2 成稿"))
    # 偏薄默认硬拦（说书加厚）；TRANSLATE_PHASE2_MIN_LENGTH_RATIO_HARD=0 可降回仅警告
    m_len = len(_plain(mother))
    b_len = len(_plain(body))
    min_ratio = float(os.environ.get("TRANSLATE_PHASE2_MIN_LENGTH_RATIO", "1.15"))
    hard_len_raw = (os.environ.get("TRANSLATE_PHASE2_MIN_LENGTH_RATIO_HARD") or "1").strip().lower()
    hard_len = hard_len_raw not in {"0", "false", "no", "off"}
    if m_len >= 400 and b_len < m_len * min_ratio:
        msg = (
            f"Phase2 成稿偏薄（{b_len} < 母本×{min_ratio:.2f}={int(m_len * min_ratio)}）；"
            "须主动加 L3/L4 延伸讲解与说书场面，勿近誊抄母本顺译；禁止用压缩母本事件换篇幅"
        )
        if hard_len:
            errs.append(msg)
        else:
            print(f"   ⚠️ {msg}", flush=True)
    for w in detect_under_rewrite_warnings(mother, body, label="Phase2 成稿"):
        print(f"   ⚠️ {w}", flush=True)
    from lib.mother_span import format_span_hole_errors, missing_mother_span_holes
    from lib.annotation_ledger import format_annotation_gate_errors
    from lib.structure_ledger import structure_order_warnings

    src = str(source_original or "")
    errs.extend(
        format_span_hole_errors(missing_mother_span_holes(mother, body, src))
    )
    for w in structure_order_warnings(body, mother, src):
        print(f"   ⚠️ {w}", flush=True)
    errs.extend(format_annotation_gate_errors(body, mother=mother))
    from lib.prose_cleanliness import detect_prose_cleanliness_errors

    errs.extend(detect_prose_cleanliness_errors(body, label="Phase2 成稿"))
    if check_intro:
        from lib.intro_frame import detect_macro_intro_failures

        errs.extend(
            detect_macro_intro_failures(detail, plan, mother=mother)
        )
    if check_epilogue:
        from lib.intro_frame import detect_macro_epilogue_failures

        # 末章单独验时：若章内段数少，用宽松 plan 仍要求末段收束
        errs.extend(detect_macro_epilogue_failures(detail, plan or {"前置引入档位": "框架引入"}))
    _ = heal_paraphrase_duplicates_in_detail(detail)
    if out_dir is not None:
        from lib.baseline_quality import detect_baseline_regression

        errs.extend(
            detect_baseline_regression(
                entry_id,
                detail,
                out_dir=out_dir,
                entry_name=entry_name,
                exclude_version=exclude_version,
                mother=mother,
            )
        )
    return (not errs), errs


def apply_post_polish_heals(
    path: Path,
    entry_id: str,
    *,
    plan: Optional[Dict[str, Any]] = None,
    source_original: str = "",
    mother: str = "",
) -> List[str]:
    """润色落盘后：引号 autofix + 双写 heal + 地名/纪年程序补注（不触发重试）。"""
    from lib.annotation_ledger import apply_annotation_autofix
    from lib.enrich_landing import load_detail_from_enrich_file, save_detail_to_enrich_file

    detail = load_detail_from_enrich_file(path)
    src = str(source_original or "")
    if not src:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            src = str(data.get("史料原文") or "")
        except (OSError, json.JSONDecodeError, TypeError):
            src = ""
    changes: List[str] = []
    fixed, q_changes = apply_quote_style_fixes(detail, plan or {}, src)
    if q_changes:
        detail = fixed
        changes.extend(q_changes)
    healed = heal_paraphrase_duplicates_in_detail(detail)
    if healed != detail:
        changes.append("释义双写静默去重")
        detail = healed
    from lib.prose_sanitize import heal_prose_punctuation

    punct = heal_prose_punctuation(detail)
    if punct != detail:
        changes.append("标点硬错愈合（：， / 。”， / 」，—— / 段首——）")
        detail = punct
    from lib.prose_cleanliness import heal_prose_cleanliness

    cleaned, clean_changes = heal_prose_cleanliness(detail)
    if clean_changes:
        detail = cleaned
        changes.extend(clean_changes)
    # Markdown 章节标题 → 连续说书（模型偶发输出 ##）
    md_stripped = re.sub(r"(?m)^#{1,6}\s+", "", detail)
    if md_stripped != detail:
        changes.append("去除 Markdown 章节标题")
        detail = md_stripped
    # Markdown 加粗
    bold_stripped = re.sub(r"\*\*([^*]+)\*\*", r"\1", detail)
    if bold_stripped != detail:
        changes.append("去除 Markdown 加粗")
        detail = bold_stripped
    # 参考著作前孤立 --- 分隔线（会误触发篇末过短）
    hr_stripped = re.sub(r"\n---+\s*\n+(?=参考著作)", "\n\n", detail)
    if hr_stripped != detail:
        changes.append("去除参考著作前 Markdown 分隔线")
        detail = hr_stripped
    # 元叙述开场（「好的，编辑已就位」等）
    meta_lead = re.match(
        r"^(?:好的[，,]?\s*)?(?:编辑已就位[。．]?|这是对第\d+/\d+章.*?(?:\n+|——\s*))+",
        detail,
    )
    if meta_lead:
        detail = detail[meta_lead.end() :].lstrip("-\n 　")
        changes.append("去除元叙述开场")
    annotated, a_changes = apply_annotation_autofix(detail, mother=mother)
    if a_changes:
        detail = annotated
        changes.extend(a_changes)
    if changes:
        save_detail_to_enrich_file(path, entry_id, detail)
    return changes
