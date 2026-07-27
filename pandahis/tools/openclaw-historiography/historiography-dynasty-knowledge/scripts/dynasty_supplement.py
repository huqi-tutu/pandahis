#!/usr/bin/env python3
"""朝代知识补全流水线：事略 / 典制 / 论著 / 人物。

执行纪律：分步、详情逐条。详见 ../reference/执行纪律.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_ROOT = MODULE_ROOT.parent
COMPOSE_DIR = OPENCLAW_ROOT / "historiography-compose"
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(OPENCLAW_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from paths_config import (  # noqa: E402
    DIR_DATA,
    DIR_DYNASTY_KNOWLEDGE,
    SUBDIR_DYNASTY_KNOWLEDGE_DETAILS,
    SUBDIR_DYNASTY_KNOWLEDGE_ENTRIES,
    SUBDIR_INTERMEDIATE_DYNASTY_KNOWLEDGE,
    get_histograph_root,
)

import bibliography_lib as blib  # noqa: E402
from shared.reference_works import attach_reference_section  # noqa: E402
from shared.verify_format_autofix import (  # noqa: E402
    autofix_detail_format,
    can_autofix_verify_errors,
)
import detail_verify as dv  # noqa: E402
import detail_review as dr  # noqa: E402
import detail_fix as dfix  # noqa: E402
import coverage_check as cc  # noqa: E402
import review_warns_summary as rws  # noqa: E402
import dynasty_supplement_lib as dkl
import omission_prompt_report as opr  # noqa: E402
import wikipedia_client as wiki  # noqa: E402

HISTOGRAPH_ROOT = get_histograph_root()
DATA_DIR = HISTOGRAPH_ROOT / DIR_DATA
DYNASTY_JSON = DATA_DIR / "01历史坐标数据" / "朝代.json"
WORK_DIR = DATA_DIR / "05工作流中间产物" / SUBDIR_INTERMEDIATE_DYNASTY_KNOWLEDGE
OUTPUT_DIR = DATA_DIR / DIR_DYNASTY_KNOWLEDGE
ENTRIES_DIR = OUTPUT_DIR / SUBDIR_DYNASTY_KNOWLEDGE_ENTRIES
DETAILS_DIR = OUTPUT_DIR / SUBDIR_DYNASTY_KNOWLEDGE_DETAILS
ANCHORS_DIR = OUTPUT_DIR / "锚点"
WIKI_DIR = OUTPUT_DIR / "维基摘录"
SOURCE_GRAPH_DIR = OUTPUT_DIR / "史料图谱"
ANNOTATE_DIR = OPENCLAW_ROOT / "historiography-annotate"

CATEGORIES = ("事略", "典制", "论著")
CATEGORY_STEP_SUFFIX = {"事略": "shilue", "典制": "dianzhi", "论著": "lunzhu", "renwu": "renwu"}
SUFFIX_TO_CATEGORY = {v: k for k, v in CATEGORY_STEP_SUFFIX.items()}
PERSON_CATEGORIES = dkl.PERSON_CATEGORIES

STEPS = (
    "research",
    "candidates-shilue",
    "candidates-dianzhi",
    "candidates-lunzhu",
    "candidates-renwu",
    "export-review",
    "export-omission-prompt",
    "fill-shilue",
    "fill-dianzhi",
    "fill-lunzhu",
    "fill-renwu",
    "compose-detail",
    "compose-pending",
    "anchor-research",
    "bibliography-plan",
    "fetch-snippets",
    "verify-bibliography",
    "wiki-fetch",
    "verify-detail",
    "coverage-check",
    "review-detail",
    "fix-detail",
    "auto-fix-verify",
    "review-warns-summary",
    "patch-detail",
    "qa-detail",
    "test-display",
    "gate",
    "gate-renwu",
    "test-review-llm",
    "enrich",
    "enrich-renwu",
    "enrich-all",
    "repair-index",
)

REVIEW_PHASES = ("candidates", "entries")

RULES = {
    "总则": MODULE_ROOT / "reference" / "朝代知识补全总则.md",
    "纪律": MODULE_ROOT / "reference" / "执行纪律.md",
    "详情": MODULE_ROOT / "reference" / "详情撰写规则.md",
    "人物详情": MODULE_ROOT / "reference" / "人物详情撰写规则.md",
    "详情写作共用": MODULE_ROOT / "reference" / "详情写作_共用规范.md",
    "anchor纪律": MODULE_ROOT / "reference" / "anchor_research_纪律.md",
    "书目plan": MODULE_ROOT / "reference" / "bibliography_plan_纪律.md",
    "详情审校": MODULE_ROOT / "reference" / "详情审校规则.md",
    "事略": MODULE_ROOT / "reference" / "事略补全规则.md",
    "典制": MODULE_ROOT / "reference" / "典制补全规则.md",
    "典制思想分界": MODULE_ROOT / "reference" / "典制与思想分界.md",
    "论著": MODULE_ROOT / "reference" / "论著补全规则.md",
    "人物": MODULE_ROOT / "reference" / "人物补全规则.md",
    "人物标注": ANNOTATE_DIR / "reference" / "人物标注规则.md",
    "人物年份": ANNOTATE_DIR / "reference" / "人物年份规则.md",
    "翻译规则": COMPOSE_DIR / "references" / "翻译规则.md",
    "格式": MODULE_ROOT / "reference" / "朝代补全格式规范.md",
}

FORBIDDEN_PROSE = dkl.FORBIDDEN_PROSE_WORDS


def _log(msg: str) -> None:
    print(msg, flush=True)


def save_llm_prompt(
    logs_dir: Path,
    entry_id: str,
    step: str,
    prompt: str,
) -> Path:
    """落盘发给 LLM 的完整 prompt，供人工核验（所见即所执行）。"""
    out_dir = logs_dir / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{entry_id}_{step}.txt"
    header = (
        f"# LLM prompt 快照\n"
        f"# 史略ID: {entry_id}\n"
        f"# 步骤: {step}\n"
        f"# 说明: 下文即实际发给模型的完整提示词（含动态 JSON/维基块）\n"
        f"# 规范类 reference/*.md 全文注入（共用 + 类型专属），无 [:N] 隐藏截取\n"
        f"{'=' * 72}\n\n"
    )
    path.write_text(header + prompt, encoding="utf-8")
    return path


def save_compose_raw(
    logs_dir: Path,
    entry_id: str,
    attempt: int,
    label: str,
    raw_text: str,
) -> Path:
    """compose 解析失败时落盘 LLM 原始回复，便于排查。"""
    out_dir = logs_dir / "compose_raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{entry_id}_{label}_r{attempt}.txt"
    header = (
        f"# compose LLM 原始回复\n"
        f"# 史略ID: {entry_id}\n"
        f"# 步骤: {label}\n"
        f"# 尝试: {attempt}\n"
        f"{'=' * 72}\n\n"
    )
    path.write_text(header + (raw_text or ""), encoding="utf-8")
    return path


def _compose_json_retry_suffix(attempt: int) -> str:
    if attempt <= 1:
        return ""
    return (
        f"\n\n## ⚠️ 第 {attempt} 次重试\n"
        "上次输出无法解析为合法 JSON。请务必：只输出 {{\"史略ID\":\"...\",\"翻译详情\":\"...\"}}；"
        "正文内不要使用 ASCII 双引号 `\"`，换行用 \\n；不要 markdown 代码块外的说明文字。\n"
    )


def _load_dynasties() -> list[dict[str, Any]]:
    if not DYNASTY_JSON.is_file():
        raise FileNotFoundError(f"朝代数据不存在: {DYNASTY_JSON}")
    return json.loads(DYNASTY_JSON.read_text(encoding="utf-8"))


def resolve_dynasty(*, dynasty_id: str | None, dynasty_name: str | None) -> dict[str, Any]:
    rows = _load_dynasties()
    if dynasty_id:
        for row in rows:
            if str(row.get("朝代ID", "")).strip() == dynasty_id:
                return row
        raise ValueError(f"未找到朝代ID: {dynasty_id}")
    if dynasty_name:
        name = dynasty_name.strip()
        hits = [r for r in rows if str(r.get("朝代", "")).strip() == name]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ValueError(f"朝代名重复: {name}")
        raise ValueError(f"未找到朝代: {name}")
    raise ValueError("请指定 --dynasty-id 或 --dynasty")


def build_dynasty_context(dynasty: dict[str, Any]) -> dict[str, Any]:
    return {
        "朝代ID": dynasty.get("朝代ID"),
        "朝代名称": dynasty.get("朝代"),
        "文明": dynasty.get("文明"),
        "文明ID": dynasty.get("文明ID"),
        "简介": dynasty.get("朝代简介", ""),
        "开始时间": dynasty.get("开始时间"),
        "结束时间": dynasty.get("结束时间"),
    }


def load_rules_text() -> dict[str, str]:
    out: dict[str, str] = {}
    for key, path in RULES.items():
        if path.is_file():
            out[key] = path.read_text(encoding="utf-8")
    return out


def research_prompt(context: dict[str, Any], rules: dict[str, str]) -> str:
    return f"""你是一位中国史学者。请研究以下朝代，输出「朝代分析报告」（Markdown），不要输出 JSON。

## 朝代信息
{json.dumps(context, ensure_ascii=False, indent=2)}

## 任务
1. 政治、经济、军事、文化、制度、思想脉络
2. 按时间分段（前期/中期/后期或相当阶段）
3. 基于史学共识，不局限于单卷史书
4. 不要列人物传记清单
5. 不要列事略/典制/论著**候选 JSON**（后续分步）；但须在附录提供结构化盘点（见下）

## 附录（必填 · Markdown 表格或分节列表）
在正文后追加 **「文化成果盘点」**，按四类分别列项（每类 3–8 个通史可点名项）：
- **典籍**：成书于本朝的整书（一书一条；标注史书/子部/集部等类型）
- **名篇**：可独立点名的诗赋、歌谣、奏疏单篇（含从已列典籍中可单独成篇者，如《诗经》名篇）
- **思想理论**：本朝提出或可考的思想命题（须用学说名，**不得**用书名代替，如写「仁礼」而非仅写《论语》）
- **书画名作**：有传世名、史籍可考、能定创作年代者；若本朝无可考书画，写「无」并简述原因

每项须标注：**成书/提出是否落在本朝区间内**；若成书在后世（如《左传》成书战国），标「不纳入本朝论著」并说明。

## 规范（全文 · 朝代知识补全总则.md）
{rules.get('总则', '')}
"""


def candidates_prompt(
    context: dict[str, Any],
    category: str,
    rules: dict[str, str],
    research_md: str,
    existing_other: dict[str, list],
) -> str:
    extra = ""
    if category == "事略":
        extra = "五要素必填：主语、参与人物、动作、结果、影响。"
    if category == "论著":
        extra = (
            "子类：典籍/名篇/书画/思想理论。不含建筑。\n"
            "硬约束：成书/创作/提出之年须在本朝区间内；"
            "典籍一书一条，禁止《书名·篇名》按卷拆条；"
            "《尚书》成书于周，不归五帝论著。\n"
            "【子类平衡 · 强制】\n"
            "1. 必须按子类分别思考，每条 JSON 必填 `子类`。\n"
            "2. 禁止候选以史书典籍为主：典籍中编年史书（如《春秋》类）≤1 条。\n"
            "3. 思想理论：仅列**无法完整归入已列典籍**的独立命题（§三·二）；"
            "若学说即某典籍核心主张，写入该典籍论著标签，**禁止典籍+学说双条**。\n"
            "4. 名篇 ≥2 条：可从已列典籍中的著名单篇单独建条（先例：西周「鹿鸣」与《诗经》并存）。\n"
            "5. 书画：有可考则列，无则不要凑数。\n"
            "6. 成书不在本朝的一律不列（如《左传》《国语》成书战国则不纳入）。\n"
            "7. 候选池目标 7–12 条，四子类均须有所覆盖（书画可为 0 但须在边界备注说明）。"
        )
    if category == "典制":
        extra = (
            "须为国家/联盟强制落地的规则（见典制与思想分界.md）。"
            "制度与事略可同主题并存（禅让制+尧舜禅让）。"
            "不与同概念思想双条（禅让制 vs 禅让思想）。"
        )
    other_note = ""
    for cat, items in existing_other.items():
        if items:
            names = [str(x.get("名称", "")) for x in items[:40]]
            other_note += f"\n- 已列「{cat}」：{', '.join(names)}"
    return f"""仅输出「{category}」候选 JSON 数组。禁止输出其他类型。

## 朝代
{json.dumps(context, ensure_ascii=False, indent=2)}

## 研究报告
{research_md[:14000]}

## 已列其他类型
{other_note or '无'}

## 规范（全文）
{rules.get(category, '')}

## 输出
JSON 数组，每项含：名称、建议年份、建议挂靠帝王、主要史料出处、边界备注、审核状态(pending)。
事略加：主语、参与人物(数组)、动作、结果、影响。
典制加：制度类型、主旨、确立或成熟年、影响。
论著加：子类、论著标签（2-5字，概括最核心思想/主题，规则同人物标签字数）、主旨、作者或提出者、成书或传播年、影响。
{extra}
"""


def candidates_renwu_prompt(
    context: dict[str, Any],
    rules: dict[str, str],
    research_md: str,
    phase1_persons: list[dict[str, Any]],
    alias_index: dict[str, str],
    emperor_gaps: list[dict[str, str]],
    supplement_knowledge: dict[str, list],
    thin_deferred: list[dict[str, Any]] | None = None,
) -> str:
    """人物候选：一次调用，六类串行加工，附分类定义与一期去重清单。"""
    phase1_lines = []
    for p in phase1_persons:
        aliases = sorted(
            {a for a, c in alias_index.items() if c == p.get("标准名")} - {p.get("标准名")}
        )
        alias_note = f"（别名：{', '.join(aliases[:8])}）" if aliases else ""
        phase1_lines.append(
            f"- [{p.get('史略分类')}] {p.get('史略名称')} {alias_note} "
            f"← 已标注 {p.get('史略ID')}，**禁止再补**"
        )
    phase1_block = "\n".join(phase1_lines) if phase1_lines else "（本朝暂无已标注人物）"

    gap_lines = [
        f"- {g['帝王名称']}：{g['补全理由']}" for g in emperor_gaps
    ]
    gap_block = "\n".join(gap_lines) if gap_lines else "（帝王表君王均已有一期条目）"

    thin_lines = []
    for row in thin_deferred or []:
        thin_lines.append(
            f"- [{row.get('史略分类')}] {row.get('史略名称')} "
            f"（一期标注{row.get('source_char_count')}字，未升GLBL，{row.get('史略ID')}）"
        )
    thin_block = "\n".join(thin_lines) if thin_lines else "（本朝暂无薄标注待补条目）"

    other_note = ""
    for cat in ("事略", "典制", "论著"):
        items = supplement_knowledge.get(cat) or []
        if items:
            names = [str(x.get("名称", "")) for x in items[:30]]
            other_note += f"\n- 已补「{cat}」：{', '.join(names)}"

    person_rules_excerpt = rules.get("人物标注", "")
    renwu_rules = rules.get("人物", "")

    return f"""你是中国史学者。为本朝代**补全缺失的重要人物**候选（非卷级重抽）。

## 硬性纪律（违反即整批作废）

1. **禁止重复一期已标注人物**：下列「已标注人物」及其**所有别名**均不得出现在候选中。
2. **禁止别名重复建条**：不得用异名再建同一人（如已有「吕太后」则不得补「吕后」「吕雉」「汉高后」）。
3. **每人只归一类**：先定 `史略分类`，再填字段；分类须通过下方定义与边界校验。
4. **加工顺序**：必须按类串行思考——君王 → 宗戚 → 宦官 → 文臣 → 武将 → 庶众；每类完成后再下一类；**禁止**六类混写无序输出。
5. **仅补缺口**：帝王表强制项 + 通史重要人物；不打酱油、不世系链一笔带过。

## 朝代
{json.dumps(context, ensure_ascii=False, indent=2)}

## 研究报告
{research_md[:12000]}

## 已标注人物（一期 · 本朝 · 禁止再补）
{phase1_block}

## 别名归一提示（节选）
命中下列任一名称，视为同一人已覆盖，不得再候选：
{json.dumps(dict(list(alias_index.items())[:80]), ensure_ascii=False, indent=2)}
（完整别名表由脚本 gate 校验）

## 帝王表君王缺口（须优先列入君王类候选）
{gap_block}

## 薄标注待补（merge 厚度门 <100 字 · 一期有 skeleton 无 GLBL · 优先考虑）
{thin_block}
说明：下列人物已在二十四史标注中出现但史料过薄，**不宜一期顺译**；若符合知名度与可写性，可纳入候选，**人审可删**。

## 已补朝代知识（参考，勿重复为人物）
{other_note or '无'}

## 人物分类定义与边界（SSOT · 必须遵守）
{person_rules_excerpt}

## 人物补全规则摘要
{renwu_rules}

## 输出格式

只输出一个 JSON 对象（不要 Markdown），键为六类，值为候选数组。每类数组内每项：

```json
{{
  "名称": "标准名（君王须对齐帝王.json）",
  "史略分类": "君王|宗戚|宦官|文臣|武将|庶众",
  "分类判定理由": "为何归此类、为何不属其他类",
  "补全来源": "帝王表强制|择优推荐",
  "建议挂靠帝王": "",
  "主要史料出处": "",
  "边界备注": "",
  "去重自检": "说明未与一期哪几条重复、未用哪些别名",
  "审核状态": "pending"
}}
```

**禁止**输出已标注人物。若无合适候选，该类返回 `[]`。
"""


def run_candidates_renwu(
    context: dict[str, Any],
    paths: dict[str, Path],
    *,
    dry_run: bool,
) -> None:
    rules = load_rules_text()
    research_md = paths["research"].read_text(encoding="utf-8") if paths["research"].is_file() else ""
    if not research_md and not dry_run:
        raise SystemExit("请先运行 --step research")

    dynasty_id = str(context["朝代ID"])
    phase1, alias_index = dkl.load_phase1_person_index(HISTOGRAPH_ROOT, dynasty_id)
    emperor_gaps = dkl.load_emperor_gaps(HISTOGRAPH_ROOT, dynasty_id, alias_index)
    thin_deferred = dkl.load_thin_deferred_for_dynasty(
        HISTOGRAPH_ROOT,
        dynasty_id,
        dynasty_name=str(context.get("朝代名称") or context.get("二级朝代坐标") or ""),
    )

    payload = load_or_init_candidates(paths["candidates"], context)
    supplement = {c: list(payload["candidates"].get(c) or []) for c in CATEGORIES}

    prompt = candidates_renwu_prompt(
        context,
        rules,
        research_md,
        phase1,
        alias_index,
        emperor_gaps,
        supplement,
        thin_deferred,
    )
    if dry_run:
        _log("=== candidates-renwu preview ===")
        _log(f"一期人物 {len(phase1)} 条，帝王缺口 {len(emperor_gaps)} 条，薄标注 {len(thin_deferred)} 条")
        _log(prompt[:4000])
        _log(f"...（共 {len(prompt)} 字）")
        return

    _log(f"🤖 LLM candidates-renwu（一期已标注 {len(phase1)} 条，禁止重复）…")
    text = dkl.call_llm(prompt, session_prefix="dk-cand-renwu-", timeout_sec=900, temperature=0)
    data = dkl.extract_json_object(text)
    if not data:
        raise RuntimeError("人物候选解析失败（须为 JSON 对象）")

    phase1_canonicals = {str(p.get("标准名", "")) for p in phase1}
    alias_map = dkl.load_person_alias_maps()
    for cat in PERSON_CATEGORIES:
        rows = data.get(cat) or []
        if not isinstance(rows, list):
            raise RuntimeError(f"人物候选「{cat}」须为数组")
        filtered, dropped = filter_renwu_duplicates(rows, alias_index, phase1_canonicals)
        if dropped:
            _log(f"  ⚠️ {cat} 脚本剔除重复 {len(dropped)} 条：{'; '.join(dropped[:5])}")
        if cat == "君王":
            filtered = dkl.inject_mandatory_juwang_candidates(
                filtered,
                emperor_gaps=emperor_gaps,
                thin_deferred=thin_deferred,
                alias_index=alias_index,
                phase1_canonicals=phase1_canonicals,
            )
            cand_names = {str(r.get("名称", "")).strip() for r in filtered}
            for gap in emperor_gaps:
                gname = str(gap.get("帝王名称", "")).strip()
                if gname and gname not in cand_names:
                    raise RuntimeError(f"君王候选缺失强制项：{gname}")
        else:
            existing_names = {str(r.get("名称", "")).strip() for r in filtered}
            for td in thin_deferred:
                if str(td.get("史略分类", "")).strip() != cat:
                    continue
                seed = dkl.thin_deferred_to_candidate(td)
                name = seed["名称"]
                if not name or name in existing_names:
                    continue
                # 薄标注强制入候选：一期或有 GLBL 但厚度门拒收，须二期重写（不因一期去重跳过）
                seed["强制补全"] = True
                seed["审核状态"] = "mandatory"
                filtered.insert(0, seed)
                existing_names.add(name)
        for row in filtered:
            if isinstance(row, dict):
                row.setdefault("史略分类", cat)
                row.setdefault("审核状态", "pending")
        payload["candidates"][cat] = filtered
        _log(f"  ✅ {cat}: {len(filtered)} 条候选")

    payload["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_json(paths["candidates"], payload)
    _log(f"✅ 人物候选已写入 {paths['candidates']}")
    maybe_export_omission_prompt(
        context, paths, phase="candidates", trigger_step="candidates-renwu", dry_run=dry_run
    )


def filter_renwu_duplicates(
    rows: list[dict[str, Any]],
    alias_index: dict[str, str],
    phase1_canonicals: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """脚本侧剔除一期已有 / 别名命中。"""
    kept: list[dict[str, Any]] = []
    dropped: list[str] = []
    alias_map = dkl.load_person_alias_maps()
    for row in rows:
        name = str(row.get("名称", "")).strip()
        if not name:
            continue
        canon = alias_index.get(name) or dkl.normalize_person_name(name, alias_map)
        if canon in phase1_canonicals or name in phase1_canonicals:
            dropped.append(f"{name}→{canon}（一期已有）")
            continue
        kept.append(row)
    return kept, dropped


def review_category_keys() -> tuple[str, ...]:
    return (*CATEGORIES, *PERSON_CATEGORIES)


def load_approval(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def approved_names_for_phase(
    approval: dict[str, Any] | None,
    *,
    phase: str,
    category: str,
) -> set[str] | None:
    """返回批准名称集合；None 表示未启用审批过滤。"""
    if not approval:
        return None
    if str(approval.get("phase", "")).strip() != phase:
        return None
    items = approval.get("items") or {}
    names = items.get(category) or []
    if not isinstance(names, list):
        return set()
    return {str(n).strip() for n in names if str(n).strip()}


def ensure_fill_approval(
    paths: dict[str, Path],
    context: dict[str, Any],
    category: str,
    *,
    require_approval: bool,
) -> set[str] | None:
    approval = load_approval(paths["approval"])
    if require_approval and not approval:
        raise SystemExit(
            f"缺少人审批准文件：{paths['approval']}\n"
            f"请先运行 export-review，经用户确认后写入批准 JSON，再执行 fill。"
        )
    if require_approval and approval and str(approval.get("phase", "")) != "candidates":
        raise SystemExit(
            f"批准文件 phase 须为 candidates，当前为 {approval.get('phase')!r}"
        )
    return approved_names_for_phase(approval, phase="candidates", category=category)


def run_export_review(
    context: dict[str, Any],
    paths: dict[str, Path],
    *,
    phase: str,
) -> None:
    if phase not in REVIEW_PHASES:
        raise SystemExit(f"未知 review phase: {phase}")

    lines: list[str] = [
        f"# {context['朝代名称']} · 人审确认表",
        "",
        f"> phase=`{phase}` · 生成后**须用户确认**，agent 不得自动进入 fill / compose-detail。",
        "",
    ]
    items: dict[str, list[dict[str, Any]]] = {}

    if phase == "candidates":
        cand_doc = load_or_init_candidates(paths["candidates"], context)
        for cat in review_category_keys():
            rows = cand_doc["candidates"].get(cat) or []
            if rows:
                items[cat] = [r for r in rows if isinstance(r, dict)]
        lines.append("## 用途")
        lines.append("")
        lines.append("确认本表候选后，写入 `人审批准.json`（`phase=candidates`），再执行 `fill-*`。")
        lines.append("")
    else:
        for path_key, label in (("entries", "事略/典制/论著"), ("entries_renwu", "人物")):
            if not paths[path_key].is_file():
                continue
            doc = json.loads(paths[path_key].read_text(encoding="utf-8"))
            for e in doc.get("entries") or []:
                if not isinstance(e, dict):
                    continue
                cat = str(e.get("史略分类", ""))
                eid = str(e.get("史略ID", ""))
                name = str(e.get("史略名称", ""))
                if not eid or not name:
                    continue
                detail_files = list(paths["details_dir"].glob(f"{eid}_*.json"))
                if detail_files:
                    continue
                items.setdefault(cat, []).append(
                    {
                        "名称": name,
                        "史略ID": eid,
                        "史略分类": cat,
                        "史略简介": e.get("史略简介", ""),
                        "来源": label,
                    }
                )
        lines.append("## 用途")
        lines.append("")
        lines.append(
            "索引已产出、详情未写。确认后写入 `人审批准.json`（`phase=entries`），"
            "再后台执行 `compose-pending`。"
        )
        lines.append("")

    if not items:
        lines.append("_（当前无可审条目）_")
    else:
        for cat, rows in items.items():
            lines.append(f"## {cat}（{len(rows)}）")
            lines.append("")
            lines.append("| 勾选 | 名称 | 备注 |")
            lines.append("|------|------|------|")
            for row in rows:
                name = str(row.get("名称", ""))
                note_parts = []
                if row.get("史略ID"):
                    note_parts.append(str(row["史略ID"]))
                if row.get("补全来源"):
                    note_parts.append(str(row["补全来源"]))
                if row.get("史略简介"):
                    note_parts.append(str(row["史略简介"])[:30])
                if row.get("边界备注"):
                    note_parts.append(str(row["边界备注"])[:40])
                note = "；".join(note_parts)
                lines.append(f"| [ ] | {name} | {note} |")
            lines.append("")

    paths["review_md"].write_text("\n".join(lines) + "\n", encoding="utf-8")

    template = {
        "schema_version": 1,
        "朝代ID": context["朝代ID"],
        "朝代名称": context["朝代名称"],
        "phase": phase,
        "approved_at": None,
        "approved_by": "user",
        "items": {cat: [str(r.get("名称", "")) for r in rows] for cat, rows in items.items()},
    }
    template_path = paths["approval"].with_name(
        paths["approval"].stem + ".template.json"
    )
    save_json(template_path, template)
    _log(f"✅ 人审确认表 → {paths['review_md']}")
    _log(f"✅ 批准模板 → {template_path}")
    _log("⏸️  请用户确认后再继续；agent 禁止自动 fill / compose-detail。")


def run_compose_pending(
    context: dict[str, Any],
    paths: dict[str, Path],
    *,
    dry_run: bool,
    require_approval: bool,
) -> None:
    approval = load_approval(paths["approval"])
    if require_approval:
        if not approval or str(approval.get("phase", "")) != "entries":
            raise SystemExit(
                f"撰写详情前须 `phase=entries` 批准文件：{paths['approval']}\n"
                f"请先 export-review --review-phase entries，经用户确认后再执行。"
            )
    pending: list[tuple[str, str]] = []
    for path_key in ("entries", "entries_renwu"):
        if not paths[path_key].is_file():
            continue
        doc = json.loads(paths[path_key].read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            eid = str(e.get("史略ID", ""))
            name = str(e.get("史略名称", ""))
            cat = str(e.get("史略分类", ""))
            if not eid or not name:
                continue
            if list(paths["details_dir"].glob(f"{eid}_*.json")):
                continue
            approved = approved_names_for_phase(approval, phase="entries", category=cat)
            if approved is not None and name not in approved:
                continue
            pending.append((eid, name))

    if not pending:
        _log("⚠️ 无待撰写详情条目")
        return
    _log(f"📝 compose-pending：{len(pending)} 条")
    for i, (eid, name) in enumerate(pending, start=1):
        if dry_run:
            _log(f"  [{i}/{len(pending)}] {eid} {name}")
            continue
        _log(f"  [{i}/{len(pending)}] compose-detail {eid} {name}")
        run_compose_detail(paths, eid, dry_run=False)
    if not dry_run:
        _log(f"✅ compose-pending 完成（{len(pending)} 条）")
        maybe_export_omission_prompt(
            context, paths, phase="details", trigger_step="compose-pending", dry_run=False
        )


def spawn_background(args: list[str], paths: dict[str, Path], label: str) -> None:
    paths["logs_dir"].mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = paths["logs_dir"] / f"{label}_{ts}.log"
    cmd = [sys.executable, str(Path(__file__).resolve()), *args]
    with open(log_path, "ab") as logf:
        proc = subprocess.Popen(
            cmd,
            stdout=logf,
            stderr=subprocess.STDOUT,
            cwd=str(SCRIPTS_DIR),
            start_new_session=True,
        )
    _log(f"🚀 后台任务已启动 PID={proc.pid}")
    _log(f"   日志：{log_path}")
    _log("   agent 勿阻塞等待；用户可用 tail -f 查看进度。")


def fill_entry_prompt(
    context: dict[str, Any],
    category: str,
    candidate: dict[str, Any],
    glbl_id: str,
    rules: dict[str, str],
    *,
    emperor_catalog: str = "",
) -> str:
    attach = str(candidate.get("建议挂靠帝王") or "").strip()
    lunzhu_tag_note = ""
    if category == "论著":
        lunzhu_tag_note = (
            "\n论著条须填写 `论著标签`（2-5 字，概括最核心思想；优先沿用候选中的论著标签）。"
        )
    return f"""将以下候选转为一条 GLBL 索引 JSON（单个对象，不要数组）。
史略ID 必须使用：{glbl_id}
史略分类：{category}
不要填原文字句、paragraphs、优先级（后续 enrichment）。
不要填人物标签（后续 person_tag.py）。{lunzhu_tag_note}
**禁止填写任何坐标链字段**（四级帝王坐标、帝王ID、一级/二级/三级坐标、文明ID、朝代ID、政权ID）。
脚本将据候选「建议挂靠帝王」在本朝帝王表中**精确匹配**后自动写入（须与下表「帝王名称」一字不差）。
本批挂靠帝王：{attach or "（见候选）"}

## 本朝帝王表（建议挂靠帝王只能填下列帝王名称）
{emperor_catalog or "（无）"}

## 朝代
{json.dumps(context, ensure_ascii=False, indent=2)}

## 候选
{json.dumps(candidate, ensure_ascii=False, indent=2)}

## 格式规范（全文）
{rules.get('格式', '')}

只输出 JSON 对象，字段用中文键名。
"""


def fill_renwu_entry_prompt(
    context: dict[str, Any],
    category: str,
    candidate: dict[str, Any],
    glbl_id: str,
    rules: dict[str, str],
    *,
    emperor_catalog: str = "",
) -> str:
    year_note = (
        "君王：史略开始年=即位年，史略结束年=退位/崩年。"
        "宗戚/文臣/武将/宦官/庶众：史略开始年=出生年，史略结束年=去世年。"
        "传说期人物仅有活跃期时，可在考订依据注明；年份须在朝代区间内。"
    )
    attach_note = (
        "君王：史略名称须与本朝帝王表「帝王名称」完全一致。"
        if category == "君王"
        else "非君王：候选「建议挂靠帝王」须为本朝帝王表「帝王名称」，一字不差。"
    )
    return f"""将以下人物候选转为一条 GLBL 人物索引 JSON（单个对象，不要数组）。
史略ID 必须使用：{glbl_id}
史略分类：{category}（已确定，勿改）
{attach_note}
不要填原文字句、paragraphs、优先级、人物标签（后续 enrichment）。
史略简介 ≤20 字，必填。
**禁止填写任何坐标链字段**（四级帝王坐标、帝王ID、一级/二级/三级坐标、文明ID、朝代ID、政权ID）。
脚本将据候选「建议挂靠帝王」或君王名在本朝帝王表中精确匹配后自动写入。

## 本朝帝王表（建议挂靠帝王 / 君王名只能填下列帝王名称）
{emperor_catalog or "（无）"}

## 朝代
{json.dumps(context, ensure_ascii=False, indent=2)}

## 候选
{json.dumps(candidate, ensure_ascii=False, indent=2)}

## 人物年份规则（全文）
{rules.get('人物年份', '')}
{year_note}

## 格式规范（全文）
{rules.get('格式', '')}

只输出 JSON 对象，字段用中文键名。
"""


def _find_sibling_entries(
    paths: dict[str, Path],
    entry: dict[str, Any],
) -> list[dict[str, str]]:
    """同朝代姊妹条（典制↔事略等），供 compose 互斥提示。"""
    name = str(entry.get("史略名称") or "")
    cat = dkl.normalize_category(str(entry.get("史略分类") or ""))
    pairs: list[tuple[str, str]] = []
    if cat == "典制" and name.endswith("制"):
        pairs.append((name[:-1], "事略"))
    if cat == "事略" and "禅让" in name:
        pairs.append(("禅让制", "典制"))
    found: list[dict[str, str]] = []
    for path_key in ("entries", "entries_renwu"):
        p = paths.get(path_key)
        if not p or not p.is_file():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            ename = str(e.get("史略名称") or "")
            ecat = dkl.normalize_category(str(e.get("史略分类") or ""))
            for needle, expect_cat in pairs:
                if needle in ename and ecat == expect_cat:
                    found.append(
                        {
                            "史略ID": str(e.get("史略ID") or ""),
                            "史略名称": ename,
                            "史略分类": ecat,
                        }
                    )
    return found


def _compose_category_discipline(
    entry: dict[str, Any],
    siblings: list[dict[str, str]],
) -> str:
    cat = dkl.normalize_category(str(entry.get("史略分类") or ""))
    name = str(entry.get("史略名称") or "")
    lines = [f"## 分类主轴（{cat} · 硬约束）"]
    if cat == "典制":
        lines += [
            f"- 主语是**制度/程序/规则**（「{name}」），不是某一桩故事",
            "- 起承转：写制度痛点、运作机制、合法性来源、争议与制度史意义",
            "- 尧舜/黄帝等**仅可 1 句例证**，禁止按时间线展开事件",
        ]
    elif cat == "事略":
        lines += [
            f"- 主语是**事件过程与结果**（「{name}」）",
            "- 可关联同主题典制，但不展开制度通论",
        ]
    elif cat in dkl.PERSON_INDEX_CATEGORIES:
        lines += [
            f"- 主语是**人物**（「{name}」）",
            "- 有出处记载为主；相传/传说仅合段补充，不可当家",
        ]
    if siblings:
        lines.append("- **姊妹条互斥**（勿复述其详情）：")
        for s in siblings:
            lines.append(f"  · {s.get('史略ID')} {s.get('史略名称')}（{s.get('史略分类')}）")
    lines += [
        "",
        "## 传说层纪律",
        "- 传说/相传/据说**可以写**（不必每句《》），但须克制",
        "- 起承转以 primary 池 + hard_facts 为主；传说 ≤5 触发词，连续传说段 ≤1",
    ]
    return "\n".join(lines)


def compose_detail_prompt(
    entry: dict[str, Any],
    rules: dict[str, str],
    *,
    anchor: dict[str, Any] | None = None,
    bibliography_plan: dict[str, Any] | None = None,
    wiki_digest: dict[str, Any] | None = None,
    revise_issues: list[str] | None = None,
    sibling_entries: list[dict[str, str]] | None = None,
) -> str:
    pri = str(entry.get("优先级") or "P1")
    cat = dkl.normalize_category(str(entry.get("史略分类") or ""))
    is_person = cat in dkl.PERSON_INDEX_CATEGORIES
    common_rules = rules.get("详情写作共用", "")
    type_rules = rules.get("人物详情" if is_person else "详情", "")
    type_label_file = "人物详情撰写规则.md" if is_person else "详情撰写规则.md"
    fmt_rules = f"""### 共用（详情写作_共用规范.md）
{common_rules}

### 专属（{type_label_file}）
{type_rules}"""
    compose_temp = dkl.detail_compose_temperature(cat)
    type_label = f"人物·{cat}" if is_person else cat
    density = dkl.resolve_source_density(entry, anchor)
    floor = dkl.detail_effective_floor(cat, pri, entry, anchor)
    category_block = _compose_category_discipline(entry, sibling_entries or [])
    anchor_block = ""
    if anchor:
        anchor_block = cc.format_claims_for_compose(anchor)
    bib_block = ""
    if bibliography_plan:
        bib_text = blib.format_plan_for_prompt(bibliography_plan)
        overall = (bibliography_plan.get("material_summary") or {}).get("overall") or "C"
        bib_block = f"""
## 史料书目 Plan（拓展认知路 · 主底池）
整体材料档 {overall}。二十四史正文见翻译详录；下文为史外书目与已校验摘句。

{bib_text}
"""
    wiki_block = ""
    if wiki_digest:
        wiki_text = wiki.format_digest_for_prompt(wiki_digest, entry)
        scope_text = wiki.format_scope_discipline(entry)
        wiki_block = f"""
## 写作主轴（条目坐标，不得偏题）
{scope_text}

## 维基百科底稿（分层：核心→起承转；延伸→合段收束后世；排除→勿用）
来源：{wiki_digest.get("page_url") or "zh.wikipedia.org"} · 检索词：{wiki_digest.get("query")}

{wiki_text}

维基底稿纪律：
- 【核心】层：**叙事底池** — 起、承、转的主体；围绕本条目所属朝代；可编排、白话化，**不可在核心层之外新增硬史实**
- 【延伸】层：合段后世影响、制度史意义（简略、可选）；须用「后世/制度史上」等 framing
- 【排除】层：年表/导航/现当代专题/其他朝代链 — **勿写入正文**
- 主轴=史略所属朝代；禁止跨时代拼接同名制度（如禅让）的细节
- **优先级**：锚点 hard_facts + 索引「主要史料出处」＞ 维基【核心】；冲突以锚点为准
- 底稿与锚点均未载处：用叙事性留白（共用规范 §0.3）
"""
    revise_block = ""
    if revise_issues:
        revise_block = f"""
## 上一轮质检未通过（须整篇重写修正，禁止只改局部导致重复段/丢开篇）
{chr(10).join(f"- {x}" for x in revise_issues)}
"""
    mode = "修订重写成稿" if revise_issues else "首次成稿"
    density_note = ""
    if bibliography_plan:
        overall = (bibliography_plan.get("material_summary") or {}).get("overall") or "C"
        density_note = (
            f"\n- **书目 plan 材料档 {overall}**：锚点 hard_facts 必覆盖；"
            f"A 档可展开 verified 摘句，B 档仅书目级异说，C 档留白；"
            f"**禁止** B/C 档写过程细节；字数不足用异说并陈/后世诠释/留白，"
            f"**禁止**编造细节凑 {floor} 字"
        )
    elif density in ("S0", "S1"):
        density_note = (
            f"\n- **史料丰度 {density}**：以维基底稿【核心】+ 锚点为主；"
            f"字数不足时用异说并陈、后世诠释、制度史意义、叙事性留白充实，"
            f"**禁止**编造细节、元叙述或合规口号凑 {floor} 字"
        )
    fact_source = (
        "书目 plan A/B 档 + 锚点 hard_facts"
        if bibliography_plan
        else "维基底稿【核心】+ 锚点 hard_facts"
    )
    return f"""为以下史略撰写详情（{mode}）。**只输出一个 JSON 对象**，格式：{{"史略ID":"...","翻译详情":"..."}}，不要 markdown 围栏外任何文字。

## 输出格式（硬性格式，违反则解析失败）
- **仅**输出上述 JSON；`翻译详情` 值为整篇正文（含换行时用 \\n，或写成单行）
- **段与段之间必须用 \\n\\n 空行分隔**（单 \\n 不算分段）
- JSON 字符串内**禁止** ASCII 双引号 `"`（会破坏解析）；史料原文用「」、术语强调亦用「」或不用引号
- 禁止在 JSON 外写「好的/如下/说明」等前缀后缀

## 条目
{json.dumps(entry, ensure_ascii=False, indent=2)}

{category_block}
{anchor_block}{bib_block}{wiki_block}{revise_block}
## 撰写规范
{fmt_rules}

## 硬性要求
- **交付物**：`翻译详情` = 小程序读者正文；完整、流畅、可读；《明朝那些事儿》口语叙事（见共用规范 §0）；**禁止**编辑备注、质检说明、元叙述入正文
- 分类 {cat}（{type_label}），优先级 {pri}，史料丰度 {density}，**撰写温度 {compose_temp}**
- 正文（不含开篇引入、不含参考著作）字数不得低于 **{floor}** 字
- **事实底稿**：{fact_source} 为叙事主体；不得在未授权材料处新增硬史实
- 起承转合齐全；开篇引入 100-200 字（独立一段）
- 文末 *参考著作：* 须包含：**索引「主要史料出处」** + **正文实际引用的全部《书名》**（compose 落盘时会自动合并；**禁止**手写与正文卷篇矛盾的参考书目）
- **引用 ↔ 参考著作双端一致**：正文出现《书名·卷篇》时，文末须**同名同卷**；改正文典籍名须同步改参考著作（fix-detail 亦同；fix 后会按正文重合并参考书目）
- **史料原文 + 译述**（对齐一期翻译详录）：经典句、金句、异说原文须 `《书名》…「原文」——白话译述`；母本短句对话用 `某说：「原文」——译述`（禁止 `「"…"」`）；长篇誓词可全白话弯引号；**禁止**《书名》载/记/曰 后用弯引号标史料原文
- 书目 plan **A 档 verified 摘句**须完整写入「」并展开译述
- 底稿无载处：用叙事性留白（§0.3），全文 ≤2 处；禁止「正文不宜…」式合规口号
- 传说/相传/据说可写但须克制（§9；verify legend_dominance）；其余模糊词仍须同句《》或删除
- 禁止【】、小标题、列表符号；**AI 腔词**（此外/综上所述/堪称 等，见共用规范 §3.5）全文合计与单词均 **< 5 次**（≥5 次 verify fail）
- 禁止编造人物心理活动（除非正史明确记载）{density_note}
"""


def slug_name(name: str) -> str:
    return name.replace(" ", "_")


def output_paths(dynasty_name: str) -> dict[str, Path]:
    slug = slug_name(dynasty_name)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    ANCHORS_DIR.mkdir(parents=True, exist_ok=True)
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    bibliography_dir = WORK_DIR / "bibliography"
    bibliography_dir.mkdir(parents=True, exist_ok=True)
    logs = WORK_DIR / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "coverage").mkdir(parents=True, exist_ok=True)
    (logs / "reviews").mkdir(parents=True, exist_ok=True)
    (logs / "verify").mkdir(parents=True, exist_ok=True)
    (logs / "qa_state").mkdir(parents=True, exist_ok=True)
    return {
        "research": WORK_DIR / f"{slug}_研究报告.md",
        "candidates": WORK_DIR / f"{slug}_候选清单.json",
        "overlap": WORK_DIR / f"{slug}_重叠审查.md",
        "entries": ENTRIES_DIR / f"{slug}_事略典制论著.json",
        "entries_renwu": ENTRIES_DIR / f"{slug}_人物.json",
        "details_dir": DETAILS_DIR,
        "anchors_dir": ANCHORS_DIR,
        "wiki_dir": WIKI_DIR,
        "bibliography_dir": bibliography_dir,
        "source_graph_dir": SOURCE_GRAPH_DIR,
        "approval": WORK_DIR / f"{slug}_人审批准.json",
        "review_md": WORK_DIR / f"{slug}_人审确认表.md",
        "omission_prompt": WORK_DIR / f"{slug}_遗漏审阅提示词.md",
        "logs_dir": WORK_DIR / "logs",
    }


def maybe_export_omission_prompt(
    context: dict[str, Any],
    paths: dict[str, Path],
    *,
    phase: str = "auto",
    trigger_step: str = "",
    dry_run: bool = False,
) -> None:
    """各生成步骤结束后自动产出可复制到其他大模型的查漏提示词。"""
    if dry_run:
        return
    out = opr.write_omission_prompt_report(
        context,
        paths,
        histograph_root=HISTOGRAPH_ROOT,
        phase=phase,
        trigger_step=trigger_step,
    )
    _log(f"📋 遗漏审阅提示词 → {out}")


def run_export_omission_prompt(
    context: dict[str, Any],
    paths: dict[str, Path],
    *,
    phase: str = "auto",
    trigger_step: str = "",
) -> None:
    maybe_export_omission_prompt(
        context,
        paths,
        phase=phase,
        trigger_step=trigger_step or "export-omission-prompt",
        dry_run=False,
    )


def _default_candidates_dict() -> dict[str, list]:
    out: dict[str, list] = {c: [] for c in CATEGORIES}
    for c in PERSON_CATEGORIES:
        out[c] = []
    return out


def load_or_init_candidates(path: Path, context: dict[str, Any]) -> dict[str, Any]:
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        cand = doc.setdefault("candidates", _default_candidates_dict())
        for k, v in _default_candidates_dict().items():
            cand.setdefault(k, v if isinstance(v, list) else [])
        return doc
    return {
        "schema_version": 1,
        "朝代ID": context["朝代ID"],
        "朝代名称": context["朝代名称"],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidates": _default_candidates_dict(),
    }


def load_or_init_entries(path: Path, context: dict[str, Any]) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "著作": "朝代知识补全",
        "朝代ID": context["朝代ID"],
        "朝代名称": context["朝代名称"],
        "source_phase": "dynasty_supplement_v1",
        "entries": [],
    }


def step_to_category(step: str) -> str | None:
    if step.startswith(("candidates-", "fill-")):
        return SUFFIX_TO_CATEGORY.get(step.split("-", 1)[1])
    return None


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_research(context: dict[str, Any], paths: dict[str, Path], *, dry_run: bool) -> None:
    rules = load_rules_text()
    prompt = research_prompt(context, rules)
    if dry_run:
        _log("=== research prompt preview ===")
        _log(prompt[:2000])
        return
    _log("🤖 LLM research …")
    text = dkl.call_llm(prompt, session_prefix="dk-res-", timeout_sec=900)
    if len(text) < 500:
        raise RuntimeError(f"研究报告过短: {len(text)} 字")
    paths["research"].write_text(text + "\n", encoding="utf-8")
    _log(f"✅ 研究报告: {paths['research']} ({len(text)} 字)")
    maybe_export_omission_prompt(
        context, paths, phase="research", trigger_step="research", dry_run=dry_run
    )


def run_candidates_one(
    context: dict[str, Any],
    paths: dict[str, Path],
    category: str,
    *,
    dry_run: bool,
) -> None:
    rules = load_rules_text()
    research_md = paths["research"].read_text(encoding="utf-8") if paths["research"].is_file() else ""
    if not research_md and not dry_run:
        raise SystemExit("请先运行 --step research")
    payload = load_or_init_candidates(paths["candidates"], context)
    existing_other = {c: list(payload["candidates"].get(c) or []) for c in CATEGORIES if c != category}
    prompt = candidates_prompt(context, category, rules, research_md, existing_other)
    if dry_run:
        _log(f"=== candidates-{CATEGORY_STEP_SUFFIX[category]} preview ===")
        _log(prompt[:2000])
        return
    _log(f"🤖 LLM candidates ({category} only) …")
    text = dkl.call_llm(prompt, session_prefix=f"dk-cand-{category}-", timeout_sec=900)
    rows = dkl.extract_json_array(text)
    if not rows:
        raise RuntimeError(f"{category} 候选解析失败")
    for row in rows:
        row.setdefault("审核状态", "pending")
    payload["candidates"][category] = rows
    payload["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_json(paths["candidates"], payload)
    _log(f"✅ {category} 候选 {len(rows)} 条 → {paths['candidates']}")
    maybe_export_omission_prompt(
        context,
        paths,
        phase="candidates",
        trigger_step=f"candidates-{CATEGORY_STEP_SUFFIX[category]}",
        dry_run=dry_run,
    )


def _filled_names(entries_doc: dict[str, Any], category: str) -> set[str]:
    names: set[str] = set()
    for e in entries_doc.get("entries") or []:
        if str(e.get("史略分类", "")) == category:
            names.add(str(e.get("史略名称", "")).strip())
    return names


def run_fill_category(
    context: dict[str, Any],
    paths: dict[str, Path],
    category: str,
    *,
    dry_run: bool,
    compose_after: bool,
    require_approval: bool,
) -> None:
    rules = load_rules_text()
    approved = ensure_fill_approval(
        paths, context, category, require_approval=require_approval
    )
    cand_doc = load_or_init_candidates(paths["candidates"], context)
    candidates = list(cand_doc["candidates"].get(category) or [])
    if approved is not None:
        candidates = [c for c in candidates if str(c.get("名称", "")).strip() in approved]
    if not candidates:
        _log(f"⚠️ {category} 无候选或未获批准，跳过 fill")
        return
    entries_doc = load_or_init_entries(paths["entries"], context)
    done_names = _filled_names(entries_doc, category)
    emperors = dkl.load_emperors(HISTOGRAPH_ROOT, str(context["朝代ID"]))
    emperor_catalog = dkl.format_emperor_catalog(emperors)
    counter = [dkl.max_glbl_num(HISTOGRAPH_ROOT)]

    for idx, cand in enumerate(candidates, start=1):
        name = str(cand.get("名称", "")).strip()
        if not name or name in done_names:
            continue
        glbl_id = dkl.allocate_glbl_id(counter)
        attach = dkl.determine_attach_emperor_name(category, cand, name)
        try:
            dkl.validate_attach_emperor_name(attach, emperors, entry_id=glbl_id)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        prompt = fill_entry_prompt(
            context, category, cand, glbl_id, rules, emperor_catalog=emperor_catalog
        )
        if dry_run:
            _log(f"=== fill {category} #{idx} {name} preview ===")
            _log(prompt[:1500])
            continue
        _log(f"🤖 fill [{category}] {idx}/{len(candidates)} {name} ({glbl_id}) …")
        text = dkl.call_llm(prompt, session_prefix=f"dk-fill-{glbl_id}-", timeout_sec=600, temperature=0)
        row = dkl.extract_json_object(text) or {}
        row["史略ID"] = glbl_id
        row["史略分类"] = category
        row.setdefault("史略名称", name)
        row = dkl.strip_llm_coordinate_fields(row)
        row = dkl.apply_coord_defaults(row, context)
        row, _ = dkl.align_entry_emperor_coords(row, emperors, attach_emperor=attach)
        dykn_cat = CATEGORY_STEP_SUFFIX[category].upper()
        slug = slug_name(str(context["朝代名称"]))
        seq = len([e for e in entries_doc["entries"] if e.get("史略分类") == category]) + 1
        row.setdefault("母本史略ID", f"DYKN_{slug}_{dykn_cat}_{seq:02d}")
        if category == "论著":
            cand_tag = str(cand.get("论著标签") or "").strip()
            if cand_tag and not str(row.get("论著标签") or "").strip():
                row["论著标签"] = cand_tag
        entries_doc["entries"].append(row)
        save_json(paths["entries"], entries_doc)
        _log(f"  ✅ 索引已写入 {glbl_id}")
        if compose_after:
            run_compose_detail(paths, glbl_id, dry_run=False)

    if not dry_run:
        _log(f"✅ fill-{CATEGORY_STEP_SUFFIX[category]} 完成 → {paths['entries']}")
        maybe_export_omission_prompt(
            context,
            paths,
            phase="entries",
            trigger_step=f"fill-{CATEGORY_STEP_SUFFIX[category]}",
            dry_run=False,
        )


def _renwu_done_names(entries_doc: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for e in entries_doc.get("entries") or []:
        if str(e.get("史略分类", "")) in PERSON_CATEGORIES:
            names.add(str(e.get("史略名称", "")).strip())
    return names


def run_fill_renwu(
    context: dict[str, Any],
    paths: dict[str, Path],
    *,
    dry_run: bool,
    compose_after: bool,
    require_approval: bool,
) -> None:
    rules = load_rules_text()
    cand_doc = load_or_init_candidates(paths["candidates"], context)
    entries_doc = load_or_init_entries(paths["entries_renwu"], context)
    done_names = _renwu_done_names(entries_doc)
    emperors = dkl.load_emperors(HISTOGRAPH_ROOT, str(context["朝代ID"]))
    emperor_catalog = dkl.format_emperor_catalog(emperors)
    counter = [dkl.max_glbl_num(HISTOGRAPH_ROOT)]
    slug = slug_name(str(context["朝代名称"]))
    total = sum(len(cand_doc["candidates"].get(c) or []) for c in PERSON_CATEGORIES)
    if total == 0:
        _log("⚠️ 人物无候选，请先运行 candidates-renwu")
        return

    seq_by_cat: dict[str, int] = {c: 0 for c in PERSON_CATEGORIES}
    filled = 0
    for cat in PERSON_CATEGORIES:
        approved = ensure_fill_approval(
            paths, context, cat, require_approval=require_approval
        )
        candidates = list(cand_doc["candidates"].get(cat) or [])
        if approved is not None:
            candidates = [
                c for c in candidates if str(c.get("名称", "")).strip() in approved
            ]
        if not candidates:
            continue
        for idx, cand in enumerate(candidates, start=1):
            name = str(cand.get("名称", "")).strip()
            if not name or name in done_names:
                continue
            glbl_id = dkl.allocate_glbl_id(counter)
            attach = dkl.determine_attach_emperor_name(cat, cand, name)
            try:
                dkl.validate_attach_emperor_name(attach, emperors, entry_id=glbl_id)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            prompt = fill_renwu_entry_prompt(
                context, cat, cand, glbl_id, rules, emperor_catalog=emperor_catalog
            )
            if dry_run:
                _log(f"=== fill-renwu {cat} #{idx} {name} preview ===")
                _log(prompt[:1500])
                continue
            _log(f"🤖 fill-renwu [{cat}] {idx}/{len(candidates)} {name} ({glbl_id}) …")
            text = dkl.call_llm(
                prompt, session_prefix=f"dk-fill-{glbl_id}-", timeout_sec=600, temperature=0
            )
            row = dkl.extract_json_object(text) or {}
            row["史略ID"] = glbl_id
            row["史略分类"] = cat
            row.setdefault("史略名称", name)
            row = dkl.strip_llm_coordinate_fields(row)
            row = dkl.apply_coord_defaults(row, context)
            row, _ = dkl.align_entry_emperor_coords(row, emperors, attach_emperor=attach)
            row = dkl.align_junji_entry_with_emperor_list(row, emperors, force=True)
            seq_by_cat[cat] += 1
            cat_slug = dkl.PERSON_CAT_SLUG.get(cat, "RENWU")
            row.setdefault("母本史略ID", f"DYKN_{slug}_{cat_slug}_{seq_by_cat[cat]:02d}")
            entries_doc["entries"].append(row)
            save_json(paths["entries_renwu"], entries_doc)
            done_names.add(name)
            filled += 1
            _log(f"  ✅ 索引已写入 {glbl_id}")
            if compose_after:
                run_compose_detail(paths, glbl_id, dry_run=False, entries_path=paths["entries_renwu"])

    if dry_run:
        return
    _log(f"✅ fill-renwu 完成 {filled} 条 → {paths['entries_renwu']}")
    maybe_export_omission_prompt(
        context, paths, phase="entries", trigger_step="fill-renwu", dry_run=False
    )


def resolve_emperor(name: str, emperors: list[dict[str, Any]]) -> dict[str, str] | None:
    return dkl.resolve_emperor(name, emperors)


def _load_entry_by_id(
    paths: dict[str, Path], entry_id: str, *, entries_path: Path | None = None
) -> tuple[dict[str, Any], Path]:
    search_paths = []
    if entries_path is not None:
        search_paths.append(entries_path)
    for key in ("entries", "entries_renwu"):
        p = paths.get(key)
        if p and p not in search_paths:
            search_paths.append(p)
    for path in search_paths:
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        entry = next(
            (e for e in doc.get("entries") or [] if str(e.get("史略ID")) == entry_id),
            None,
        )
        if entry:
            return entry, path
    raise SystemExit(f"未找到 {entry_id}")


def _anchor_category_discipline(entry: dict[str, Any]) -> str:
    cat = dkl.normalize_category(str(entry.get("史略分类") or ""))
    name = str(entry.get("史略名称") or "")
    if cat != "典制":
        return ""
    return f"""
## 分类主轴（典制 · anchor 须遵守）
- 主语是**制度/程序/规则**（「{name}」），不是某一桩人物故事
- hard_facts 须写：制度定义、运作程序、合法性来源、与世袭制的区别
- core_enumerations 须列**制度要素**（如推举程序、考察环节），勿把尧舜故事步骤当作唯一主轴
- 尧舜/黄帝等仅作**1 条** hard_fact 例证时可引用，不得占 checklist 大半
- 姊妹事略「尧舜禅让」已专述故事线；本 anchor **禁止**复写完整禅让叙事 checklist
"""


def anchor_research_prompt(entry: dict[str, Any], rules: dict[str, str]) -> str:
    discipline = rules.get("anchor纪律", "")
    cat_block = _anchor_category_discipline(entry)
    return f"""为以下史略条目研究锚点（撰写蓝图 SSOT）。只输出 JSON，不要 markdown 围栏。

## 条目
{json.dumps(entry, ensure_ascii=False, indent=2)}
{cat_block}
## 规范纪律
{discipline}

## 输出 schema
{{
  "schema": "dynasty-knowledge-anchor/v1",
  "史略ID": "...",
  "史料丰度": "S0|S1|S2|S3",
  "coverage_claims": [
    {{"id": "c01", "claim": "须传达的自然语言主张一句（不要求正文出现特定词语）"}}
  ],
  "legend_facts": [
    {{"text": "传说/异说一句", "keywords": ["..."]}}
  ],
  "forbidden_inventions": ["原文未载不可编造的过程细节"]
}}

勿再输出 hard_facts / core_enumerations / checklist（已由 coverage_claims 取代）。
"""


def _load_detail_file(paths: dict[str, Path], entry_id: str) -> tuple[dict[str, Any], Path]:
    files = list(paths["details_dir"].glob(f"{entry_id}_*.json"))
    if not files:
        raise SystemExit(f"未找到详情 {entry_id}")
    path = files[0]
    return json.loads(path.read_text(encoding="utf-8")), path


def run_anchor_research(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
) -> None:
    if not entry_id:
        raise SystemExit("anchor-research 必须 --entry-id")
    entry, _ = _load_entry_by_id(paths, entry_id)
    rules = load_rules_text()
    prompt = anchor_research_prompt(entry, rules)
    out_path = paths["anchors_dir"] / f"{entry_id}.json"
    prompt_path = save_llm_prompt(paths["logs_dir"], entry_id, "anchor-research", prompt)
    if dry_run:
        _log(f"=== anchor-research {entry_id} dry-run ===")
        _log(f"  📄 完整 prompt 已写入: {prompt_path}")
        return
    _log(f"🤖 anchor-research {entry_id} …")
    _log(f"  📄 prompt 快照: {prompt_path}")
    text = dkl.call_llm(
        prompt,
        session_prefix=f"dk-anc-{entry_id}-",
        timeout_sec=600,
        temperature=0,
    )
    data = dkl.extract_json_object(text)
    if not data:
        raise RuntimeError(f"{entry_id} 锚点解析失败")
    data["史略ID"] = entry_id
    data.setdefault("schema", "dynasty-knowledge-anchor/v1")
    dkl.save_anchor(paths["anchors_dir"], entry_id, data)
    if data.get("史料丰度") in dkl.SOURCE_DENSITY_LEVELS:
        entry["史料丰度"] = data["史料丰度"]
    _log(f"  ✅ 锚点 {out_path.name}（claims={len(data.get('coverage_claims') or cc.extract_coverage_claims(data))}）")


def bibliography_plan_prompt(
    entry: dict[str, Any],
    rules: dict[str, str],
    *,
    anchor: dict[str, Any] | None = None,
) -> str:
    discipline = rules.get("书目plan", "")
    anchor_block = ""
    if anchor:
        anchor_block = f"""
## 锚点（plan 不得与之矛盾）
{json.dumps(anchor, ensure_ascii=False, indent=2)}
"""
    return f"""为以下史略条目制定**史料书目 plan**（拓展认知路：史外文献发现，非二十四史摘句）。只输出 JSON，不要 markdown 围栏。

## 条目
{json.dumps(entry, ensure_ascii=False, indent=2)}
{anchor_block}
## 规范纪律
{discipline}

## 输出 schema
{{
  "schema": "dynasty-knowledge-bibliography/v1",
  "史略ID": "...",
  "写作结构": "建议 compose 如何分配：正史见翻译 / 史外异说 / 留白",
  "候选著作": [
    {{
      "出处": "《书名·卷篇》",
      "tier": "先秦文献|辑佚/出土|经注/杂史|正史-见翻译|后世综述",
      "pool": "primary|legend",
      "与本主题关系": "一句话说明该文献与本条目的关系",
      "检索词": "供 ctext 检索的 2-6 字词",
      "采用": true,
      "原文摘句": "若已知可写 15-80 字摘句；未知可留空",
      "snippet_verified": false,
      "material_tier": "B"
    }}
  ]
}}

纪律提醒：
- **primary 池**：有明确记载/篇卷，fetch 优先，供起承转主叙事
- **legend 池**：后世综述/口传附会，**最多 1 条** 采用:true，仅合段补充
- 索引「主要史料出处」若为二十四史：tier=正史-见翻译，pool=primary，采用=false
"""


def run_bibliography_plan(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    force: bool = False,
) -> None:
    if not entry_id:
        raise SystemExit("bibliography-plan 必须 --entry-id")
    entry, _ = _load_entry_by_id(paths, entry_id)
    bib_dir = paths["bibliography_dir"]
    out_path = blib.plan_path(bib_dir, entry_id)
    if out_path.is_file() and not force and not dry_run:
        _log(f"  📋 书目 plan 已存在 {out_path.name}（--force-bibliography 可重跑）")
        return
    anchor = dkl.load_anchor(paths["anchors_dir"], entry_id)
    if not anchor and not dry_run:
        _log(f"📌 无锚点，先 anchor-research {entry_id} …")
        run_anchor_research(paths, entry_id, dry_run=False)
        anchor = dkl.load_anchor(paths["anchors_dir"], entry_id)
    rules = load_rules_text()
    prompt = bibliography_plan_prompt(entry, rules, anchor=anchor)
    prompt_path = save_llm_prompt(paths["logs_dir"], entry_id, "bibliography-plan", prompt)
    if dry_run:
        _log(f"=== bibliography-plan {entry_id} dry-run ===")
        _log(f"  📄 完整 prompt 已写入: {prompt_path}")
        return
    _log(f"🤖 bibliography-plan {entry_id} …")
    _log(f"  📄 prompt 快照: {prompt_path}")
    text = dkl.call_llm(
        prompt,
        session_prefix=f"dk-bib-{entry_id}-",
        timeout_sec=600,
        temperature=0,
    )
    data = dkl.extract_json_object(text)
    if not data:
        raise RuntimeError(f"{entry_id} 书目 plan 解析失败")
    data["史略ID"] = entry_id
    data.setdefault("schema", blib.SCHEMA)
    data = blib.normalize_plan_pools(data)
    data = blib.fetch_all_snippets(data, dry_run=True)
    for src in data.get("候选著作") or []:
        if isinstance(src, dict):
            src.setdefault("snippet_verified", False)
            src.setdefault("material_tier", "B" if src.get("采用") else "C")
    blib.save_plan(bib_dir, entry_id, data)
    adopted = sum(1 for s in (data.get("候选著作") or []) if isinstance(s, dict) and s.get("采用"))
    _log(f"  ✅ 书目 plan {out_path.name}（候选 {len(data.get('候选著作') or [])}，采用 {adopted}）")


def run_fetch_snippets(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
) -> None:
    if not entry_id:
        raise SystemExit("fetch-snippets 必须 --entry-id")
    bib_dir = paths["bibliography_dir"]
    plan = blib.load_plan(bib_dir, entry_id)
    if not plan:
        raise SystemExit(f"未找到书目 plan：{entry_id}，请先 bibliography-plan")
    if dry_run:
        adopted = [s for s in (plan.get("候选著作") or []) if isinstance(s, dict) and s.get("采用")]
        _log(f"=== fetch-snippets {entry_id} dry-run ===")
        _log(f"  将采用条目 {len(adopted)} 条尝试 ctext")
        for s in adopted[:5]:
            _log(f"    · {s.get('出处')} 检索词={s.get('检索词')}")
        return
    _log(f"📥 fetch-snippets {entry_id} …")
    updated = blib.fetch_all_snippets(plan, dry_run=False)
    updated = blib.normalize_plan_pools(updated)
    blib.save_plan(bib_dir, entry_id, updated)
    summary = updated.get("material_summary") or {}
    _log(
        f"  ✅ A={summary.get('A_verified', 0)} "
        f"B={summary.get('B_bibliography_only', 0)} "
        f"overall={summary.get('overall', '?')}"
    )


def run_verify_bibliography(
    paths: dict[str, Path],
    entry_id: str,
    *,
    strict: bool = True,
    persist_graph: bool = True,
) -> int:
    if not entry_id:
        raise SystemExit("verify-bibliography 必须 --entry-id")
    bib_dir = paths["bibliography_dir"]
    plan = blib.load_plan(bib_dir, entry_id)
    if not plan:
        raise SystemExit(f"未找到书目 plan：{entry_id}")
    anchor = dkl.load_anchor(paths["anchors_dir"], entry_id)
    report = blib.verify_plan(plan, entry_id=entry_id, anchor=anchor)
    out = paths["logs_dir"] / "verify" / f"{entry_id}_bibliography_verify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for issue in report.issues:
        icon = "❌" if issue.severity == "error" else "⚠️"
        _log(f"  {icon} {issue.code}: {issue.message}")
    if report.passed:
        _log(f"✅ verify-bibliography {entry_id} 通过 → {out.name}")
        if persist_graph:
            graph = blib.build_source_graph(plan)
            gpath = blib.save_source_graph(paths["source_graph_dir"], entry_id, graph)
            _log(f"  📎 史料图谱 {gpath.name}")
        return 0
    _log(f"❌ verify-bibliography {entry_id} 未通过 → {out.name}")
    return 1 if strict else 0


def _ensure_bibliography_plan(
    paths: dict[str, Path],
    entry_id: str,
    entry: dict[str, Any],
    *,
    dry_run: bool,
    skip: bool = False,
    force: bool = False,
) -> dict[str, Any] | None:
    if skip:
        return None
    bib_dir = paths["bibliography_dir"]
    plan = blib.load_plan(bib_dir, entry_id)
    if plan and not force:
        if not plan.get("material_summary"):
            if dry_run:
                _log(f"  [dry-run] plan 缺 material_summary，将 fetch-snippets")
            else:
                run_fetch_snippets(paths, entry_id, dry_run=False)
            plan = blib.load_plan(bib_dir, entry_id)
        return plan
    if dry_run:
        _log(f"  [dry-run] 将运行 bibliography-plan + fetch-snippets")
        return plan
    run_bibliography_plan(paths, entry_id, dry_run=False, force=force)
    run_fetch_snippets(paths, entry_id, dry_run=False)
    return blib.load_plan(bib_dir, entry_id)


def _ensure_wiki_digest(
    paths: dict[str, Path],
    entry_id: str,
    entry: dict[str, Any],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    """拉取或读取维基摘录；dry_run 时不请求网络。"""
    wiki_dir = paths["wiki_dir"]
    entry_name = str(entry.get("史略名称") or "").strip()
    if not force:
        cached = wiki.load_wiki_digest(wiki_dir, entry_id)
        if cached and cached.get("full_extract"):
            cached = wiki.apply_scope_to_digest(cached, entry)
            _log(f"  📚 维基摘录已缓存 {entry_id} → {cached.get('resolved_title')}")
            return cached
    if dry_run:
        _log(f"  [dry-run] 将检索维基：{entry_name}")
        return None
    _log(f"📚 wiki-fetch {entry_id} 「{entry_name}」…")
    digest = wiki.fetch_for_entry(
        entry_id,
        entry_name,
        force=True,
        wiki_dir=wiki_dir,
        entry=entry,
    )
    _log(
        f"  ✅ 维基 {digest.get('resolved_title')} "
        f"(核心 {len((digest.get('scoped') or {}).get('core_sections') or [])} 节)"
    )
    return digest


def run_wiki_fetch(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    force: bool = False,
    entries_path: Path | None = None,
) -> None:
    if not entry_id:
        raise SystemExit("wiki-fetch 必须 --entry-id")
    entry, _ = _load_entry_by_id(paths, entry_id, entries_path=entries_path)
    name = str(entry.get("史略名称") or "").strip()
    if dry_run:
        _log(f"=== wiki-fetch {entry_id} preview ===")
        _log(f"  检索词: {name}")
        _log(wiki.format_scope_discipline(entry))
        candidates = wiki.search_titles(name) if name else []
        _log(f"  opensearch 候选: {candidates[:5]}")
        return
    _ensure_wiki_digest(paths, entry_id, entry, force=force, dry_run=False)


def _apply_verify_format_autofix(
    paths: dict[str, Path],
    entry: dict[str, Any],
    entry_id: str,
    out_path: Path,
    report: dv.VerifyReport,
) -> dv.VerifyReport:
    """verify 未通过且均为可机械修复项时，0 token 改稿并重验。"""
    if not can_autofix_verify_errors(report.issues):
        return report
    detail_doc = json.loads(out_path.read_text(encoding="utf-8"))
    raw = str(detail_doc.get("翻译详情") or "")
    new_raw, fixes = autofix_detail_format(raw, entry)
    if not fixes:
        return report
    detail_doc["翻译详情"] = new_raw
    out_path.write_text(
        json.dumps(detail_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _log(f"🔧 auto-fix-verify {entry_id}：{', '.join(fixes)}")
    report2 = dv.verify_detail(
        entry,
        detail_doc,
        anchor=dkl.load_anchor(paths["anchors_dir"], entry_id),
        bibliography_plan=blib.load_plan(paths["bibliography_dir"], entry_id),
    )
    dkl.save_verify_artifact(paths["logs_dir"], entry_id, report2.to_dict())
    if report2.passed:
        _log(f"✅ auto-fix-verify 后 verify 通过")
    return report2


def run_auto_fix_verify(
    paths: dict[str, Path],
    entry_id: str | None,
    *,
    dry_run: bool,
) -> int:
    """批量或单条：机械修复 refs_volume_mismatch / source_curved_quote / nested_corner_quote。"""
    targets: list[tuple[str, dict[str, Any]]] = []
    for path_key in ("entries", "entries_renwu"):
        if not paths[path_key].is_file():
            continue
        doc = json.loads(paths[path_key].read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            eid = str(e.get("史略ID", ""))
            if not eid:
                continue
            if entry_id and eid != entry_id:
                continue
            targets.append((eid, e))
    if entry_id and not targets:
        raise SystemExit(f"未找到条目 {entry_id}")
    fixed = 0
    for eid, entry in targets:
        files = list(paths["details_dir"].glob(f"{eid}_*.json"))
        if not files:
            continue
        out_path = files[0]
        detail_doc = json.loads(out_path.read_text(encoding="utf-8"))
        raw = str(detail_doc.get("翻译详情") or "")
        new_raw, fixes = autofix_detail_format(raw, entry)
        if not fixes:
            continue
        if dry_run:
            _log(f"🔍 auto-fix-verify {eid}：{', '.join(fixes)}")
            fixed += 1
            continue
        detail_doc["翻译详情"] = new_raw
        out_path.write_text(
            json.dumps(detail_doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report = dv.verify_detail(
            entry,
            detail_doc,
            anchor=dkl.load_anchor(paths["anchors_dir"], eid),
            bibliography_plan=blib.load_plan(paths["bibliography_dir"], eid),
        )
        dkl.save_verify_artifact(paths["logs_dir"], eid, report.to_dict())
        status = "通过" if report.passed else "仍有问题"
        _log(f"🔧 auto-fix-verify {eid}：{', '.join(fixes)} → verify {status}")
        fixed += 1
    _log(f"✅ auto-fix-verify 完成（{fixed} 条）")
    return 0


def run_verify_detail(
    paths: dict[str, Path],
    entry_id: str,
    *,
    strict: bool = True,
) -> int:
    if not entry_id:
        raise SystemExit("verify-detail 必须 --entry-id")
    entry, _ = _load_entry_by_id(paths, entry_id)
    detail, _ = _load_detail_file(paths, entry_id)
    anchor = dkl.load_anchor(paths["anchors_dir"], entry_id)
    bib_plan = blib.load_plan(paths["bibliography_dir"], entry_id)
    report = dv.verify_detail(
        entry, detail, anchor=anchor, bibliography_plan=bib_plan
    )
    out = dkl.save_verify_artifact(paths["logs_dir"], entry_id, report.to_dict())
    for line in dv.format_verify_issues(report):
        _log(f"  {'⚠️' if 'warn' in line else '❌' if not report.passed else '·'} {line}")
    if report.passed:
        _log(f"✅ verify-detail {entry_id} 通过 → {out.name}")
        return 0
    _log(f"❌ verify-detail {entry_id} 未通过（{len(report.issues)} 项）→ {out.name}")
    return 1 if strict else 0


def run_coverage_check(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    strict: bool = False,
) -> int:
    if not entry_id:
        raise SystemExit("coverage-check 必须 --entry-id")
    entry, _ = _load_entry_by_id(paths, entry_id)
    detail, _ = _load_detail_file(paths, entry_id)
    anchor = dkl.load_anchor(paths["anchors_dir"], entry_id)
    prompt = cc.build_coverage_check_prompt(
        entry, str(detail.get("翻译详情") or ""), anchor
    )
    prompt_path = save_llm_prompt(paths["logs_dir"], entry_id, "coverage-check", prompt)
    if dry_run:
        _log(f"  📄 完整 prompt: {prompt_path}")
        return 0
    _log(f"🎯 coverage-check {entry_id} …")
    try:
        report = cc.run_coverage_check_llm(entry, detail, anchor=anchor, prompt=prompt)
    except RuntimeError as exc:
        state = dkl.load_qa_state(paths["logs_dir"], entry_id)
        state["coverage_status"] = "error"
        dkl.save_qa_state(paths["logs_dir"], state)
        _log(f"  ⚠️ coverage-check {entry_id} 解析失败（不阻断后续 qa）: {exc}")
        return 0
    out = cc.save_coverage_artifact(paths["logs_dir"], entry_id, report)
    state = dkl.load_qa_state(paths["logs_dir"], entry_id)
    if report.passed:
        state["coverage_status"] = "pass"
        _log(f"✅ coverage-check {entry_id} 通过 → {out.name}")
    else:
        state["coverage_status"] = "fail"
        state["status"] = "needs_human"
        for issue in report.issues[:5]:
            _log(f"  ❌ coverage: {issue}")
        _log(f"⚠️ coverage-check {entry_id} 未通过 → {out.name}")
    dkl.save_qa_state(paths["logs_dir"], state)
    return 1 if (strict and not report.passed) else 0


def run_review_warns_summary(
    paths: dict[str, Path],
    context: dict[str, Any],
) -> int:
    entries: list[dict[str, Any]] = []
    for key in ("entries", "entries_renwu"):
        p = paths.get(key)
        if p and p.is_file():
            doc = json.loads(p.read_text(encoding="utf-8"))
            entries.extend(doc.get("entries") or [])
    json_path, md_path = rws.write_review_warns_summary(
        paths["logs_dir"],
        entries=entries,
        dynasty_name=str(context.get("朝代名称") or "朝代"),
        details_dir=paths.get("details_dir"),
    )
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    _log(f"📋 Kimi 人工关注汇总 {doc['entry_count']} 条 → {md_path.name} / {json_path.name}")
    return 0


def run_fix_detail(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    review: dict[str, Any] | None = None,
    fix_round: int = 1,
    dynasty_name: str = "朝代",
) -> bool:
    """按 Kimi factual_errors 精准改稿。返回是否已成功应用全部 edits 且典籍同步通过。"""
    if not entry_id:
        raise SystemExit("fix-detail 必须 --entry-id")
    entry, _ = _load_entry_by_id(paths, entry_id)
    detail, detail_path = _load_detail_file(paths, entry_id)
    if review is None:
        review = dkl.load_review_artifact(paths["logs_dir"], entry_id)
    if not review:
        raise SystemExit(f"未找到审校产物，请先 review-detail {entry_id}")

    errors = [
        e
        for e in (review.get("factual_errors") or [])
        if isinstance(e, dict) and (e.get("quote") or e.get("reason"))
    ]
    if not review.get("has_factual_errors") or not errors:
        _log(f"✅ fix-detail {entry_id} 无 Kimi 硬错误，跳过")
        return True

    raw = str(detail.get("翻译详情") or "")
    prompt = dfix.build_factual_fix_prompt(
        entry, raw, errors, fix_round=fix_round
    )
    label = f"fix-detail-r{fix_round}"
    prompt_path = save_llm_prompt(paths["logs_dir"], entry_id, label, prompt)
    if dry_run:
        _log(f"  📄 完整 prompt: {prompt_path}（{len(prompt):,} 字符）")
        return False

    _log(f"✏️ fix-detail {entry_id} 第 {fix_round} 轮（{len(errors)} 处）…")
    _log(f"  📄 prompt 快照: {prompt_path}")
    text = dkl.call_llm(
        prompt,
        session_prefix=f"dk-fix-{entry_id}-r{fix_round}-",
        timeout_sec=600,
        temperature=0,
    )
    edits = dfix.parse_fix_response(text)
    fix_result = dfix.apply_factual_edits_to_full_text(raw, edits, fix_round=fix_round)
    refs_ok, sync_issues = dfix.validate_citation_sync(
        fix_result.text_after, errors, edits
    )
    fix_result.refs_sync_ok = refs_ok
    fix_result.issues.extend(sync_issues)
    if sync_issues:
        fix_result.all_applied = False

    fix_log = paths["logs_dir"] / "fixes" / f"{entry_id}_fix_r{fix_round}.json"
    fix_log.parent.mkdir(parents=True, exist_ok=True)
    fix_log.write_text(
        json.dumps(fix_result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    applied_n = sum(1 for e in fix_result.edits if e.applied)
    _log(f"  📝 应用 {applied_n}/{len(fix_result.edits)} 处替换 → {fix_log.name}")
    for issue in fix_result.issues:
        _log(f"  ⚠️ {issue}")

    anchor = dkl.load_anchor(paths["anchors_dir"], entry_id)
    bib_plan = blib.load_plan(paths["bibliography_dir"], entry_id)
    new_body = attach_reference_section(
        fix_result.text_after,
        entry,
        bib_plan,
    )
    save_json(detail_path, {"史略ID": entry_id, "翻译详情": new_body})
    state = dkl.load_qa_state(paths["logs_dir"], entry_id)
    state["patch_attempts"] = int(state.get("patch_attempts") or 0) + 1
    state["last_fix_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["last_fix_round"] = fix_round
    dkl.save_qa_state(paths["logs_dir"], state)
    _log(f"  ✅ 已写回 {detail_path.name}")

    report = dv.verify_detail(
        entry,
        json.loads(detail_path.read_text(encoding="utf-8")),
        anchor=anchor,
        bibliography_plan=bib_plan,
    )
    dkl.save_verify_artifact(paths["logs_dir"], entry_id, report.to_dict())
    if report.passed:
        _log(f"  ✅ fix 后 verify 通过")
    else:
        for i in report.issues[:3]:
            if i.severity == "error":
                _log(f"  ❌ verify/{i.code}: {i.message}")

    return fix_result.all_applied and refs_ok


def _save_kimi_review(
    paths: dict[str, Path],
    entry_id: str,
    review: dict[str, Any],
    *,
    review_round: int,
    forced_pass: bool = False,
) -> Path:
    review["schema"] = dr.REVIEW_SCHEMA_V2
    review["史略ID"] = entry_id
    review["reviewed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    review["pipeline_blocking"] = False
    review["review_fix_round"] = review_round
    review["forced_pass"] = forced_pass
    if forced_pass:
        review["has_factual_errors"] = bool(review.get("has_factual_errors"))
        review["overall_verdict"] = "forced_pass"
        review["human_review_required"] = True
    else:
        review["human_review_required"] = bool(review.get("has_factual_errors"))
    return dkl.save_review_artifact(paths["logs_dir"], entry_id, review)


def run_review_fix_loop(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    dynasty_name: str = "朝代",
    auto_fix_on_review: bool = True,
) -> int:
    """Kimi 核查 ↔ 精准改稿，最多 MAX_REVIEW_FIX_ROUNDS 轮；末轮仍有问题则 forced_pass。"""
    entry, _ = _load_entry_by_id(paths, entry_id)
    state = dkl.load_qa_state(paths["logs_dir"], entry_id)

    for review_round in range(1, dkl.MAX_REVIEW_FIX_ROUNDS + 1):
        detail, _ = _load_detail_file(paths, entry_id)
        prompt = dr.build_review_prompt(entry, str(detail.get("翻译详情", "")))
        prompt_path = save_llm_prompt(
            paths["logs_dir"], entry_id, f"review-detail-r{review_round}", prompt
        )
        if dry_run:
            _log(f"  📄 Kimi 第 {review_round} 轮 prompt: {prompt_path}")
            return 0

        _log(
            f"🔍 review-detail {entry_id}（Kimi · 第 {review_round}/"
            f"{dkl.MAX_REVIEW_FIX_ROUNDS} 轮）…"
        )
        review = dr.run_detail_review(entry, detail, prompt=prompt, timeout_sec=600)
        n_err = len(review.get("factual_errors") or [])

        if not review.get("has_factual_errors"):
            _save_kimi_review(
                paths, entry_id, review, review_round=review_round
            )
            _log(f"  ✅ 第 {review_round} 轮：未发现硬史实错误")
            state["review_fix_round"] = review_round
            state["review_fix_forced_pass"] = False
            dkl.save_qa_state(paths["logs_dir"], state)
            break

        out = _save_kimi_review(paths, entry_id, review, review_round=review_round)
        _log(
            f"  🟡 第 {review_round} 轮：{n_err} 处硬史实问题 → {out.name}"
        )

        if review_round >= dkl.MAX_REVIEW_FIX_ROUNDS:
            _save_kimi_review(
                paths,
                entry_id,
                review,
                review_round=review_round,
                forced_pass=True,
            )
            _log(
                f"  ⏭️ 已达 {dkl.MAX_REVIEW_FIX_ROUNDS} 轮 Kimi 核查上限，"
                f"forced_pass（不再自动改稿，见 review_warns_汇总）"
            )
            state["review_fix_round"] = review_round
            state["review_fix_forced_pass"] = True
            dkl.save_qa_state(paths["logs_dir"], state)
            break

        if not auto_fix_on_review:
            state["review_fix_round"] = review_round
            dkl.save_qa_state(paths["logs_dir"], state)
            break

        ok = run_fix_detail(
            paths,
            entry_id,
            dry_run=False,
            review=review,
            fix_round=review_round,
            dynasty_name=dynasty_name,
        )
        state["review_fix_round"] = review_round
        dkl.save_qa_state(paths["logs_dir"], state)
        if not ok:
            _log(f"  ⚠️ 第 {review_round} 轮改稿未完全落地，进入下一轮 Kimi 核查")

    run_review_warns_summary(paths, {"朝代名称": dynasty_name})
    return 0


def run_review_detail(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    dynasty_name: str = "朝代",
    auto_fix_on_review: bool = True,
) -> int:
    if not entry_id:
        raise SystemExit("review-detail 必须 --entry-id")
    return run_review_fix_loop(
        paths,
        entry_id,
        dry_run=dry_run,
        dynasty_name=dynasty_name,
        auto_fix_on_review=auto_fix_on_review,
    )


def patch_detail_prompt(
    entry: dict[str, Any],
    paragraphs: list[str],
    fixes: list[dict[str, Any]],
) -> str:
    blocks = []
    for fix in fixes:
        idx = int(fix.get("paragraph_index", -1))
        if 0 <= idx < len(paragraphs):
            blocks.append(
                f"[P{idx}] 原文：\n{paragraphs[idx]}\n"
                f"问题：{'; '.join(fix.get('issues') or [])}\n"
                f"建议：{fix.get('suggested_fix') or '按锚点修正'}"
            )
    return f"""按审校意见修订以下段落。只输出 JSON：
{{"paragraphs": [{{"paragraph_index": 0, "text": "修订后段落"}}]}}

## 条目
{json.dumps({k: entry.get(k) for k in ('史略ID', '史略名称', '史略分类', '主要史料出处')}, ensure_ascii=False, indent=2)}

## 待修段落
{chr(10).join(blocks)}

纪律：只改指定段落；过程禁编；保留未列段落不动；不要【】。"""


def run_patch_detail(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
) -> int:
    if not entry_id:
        raise SystemExit("patch-detail 必须 --entry-id")
    entry, _ = _load_entry_by_id(paths, entry_id)
    detail, detail_path = _load_detail_file(paths, entry_id)
    review = dkl.load_review_artifact(paths["logs_dir"], entry_id)
    if not review:
        raise SystemExit(f"未找到审校产物，请先 review-detail {entry_id}")

    state = dkl.load_qa_state(paths["logs_dir"], entry_id)
    patch_n = int(state.get("patch_attempts") or 0)
    if patch_n >= dkl.MAX_PATCH_ROUNDS:
        raise SystemExit(
            f"{entry_id} patch 已达上限 {dkl.MAX_PATCH_ROUNDS}；"
            f"请 compose-detail 整篇重写，勿再 patch"
        )

    raw = str(detail.get("翻译详情") or "")
    body = dkl.strip_detail_body(raw)
    paragraphs = dkl.split_detail_paragraphs(raw)
    refs = ""
    if "参考著作" in raw:
        refs = raw.split("参考著作", 1)[1]
        refs = "*参考著作" + refs if not refs.strip().startswith("*") else "参考著作" + refs

    fixes = [
        r
        for r in review.get("paragraph_reviews") or []
        if str(r.get("verdict")) in ("fail", "warn")
        and (r.get("issues") or r.get("suggested_fix"))
    ]
    if not fixes:
        _log(f"✅ patch-detail {entry_id} 无需修订")
        return 0

    prompt = patch_detail_prompt(entry, paragraphs, fixes)
    if dry_run:
        _log(prompt[:2000])
        return 0

    _log(f"🤖 patch-detail {entry_id}（{len(fixes)} 段）…")
    text = dkl.call_llm(
        prompt,
        session_prefix=f"dk-pat-{entry_id}-",
        timeout_sec=600,
        temperature=0.2,
    )
    data = dkl.extract_json_object(text)
    patches = data.get("paragraphs") or []
    for patch in patches:
        idx = int(patch.get("paragraph_index", -1))
        new_text = str(patch.get("text") or "").strip()
        if 0 <= idx < len(paragraphs) and new_text:
            paragraphs[idx] = new_text

    new_body = "\n\n".join(paragraphs)
    if refs:
        new_body = new_body.rstrip() + "\n\n" + refs.strip()
    detail["翻译详情"] = new_body
    save_json(detail_path, {"史略ID": entry_id, "翻译详情": new_body})
    state["patch_attempts"] = patch_n + 1
    dkl.save_qa_state(paths["logs_dir"], state)
    _log(f"  ✅ 已写回 {detail_path.name}")
    return run_verify_detail(paths, entry_id, strict=True)


def run_qa_detail(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    skip_review: bool = False,
    skip_coverage: bool = False,
    dynasty_name: str = "朝代",
    auto_fix_on_review: bool = True,
) -> int:
    """质检链：verify → coverage-check → review（Kimi 不阻断）。"""
    if not entry_id:
        raise SystemExit("qa-detail 必须 --entry-id")
    state = dkl.load_qa_state(paths["logs_dir"], entry_id)
    code = run_verify_detail(paths, entry_id, strict=True)
    if code != 0:
        state["status"] = "needs_human"
        dkl.save_qa_state(paths["logs_dir"], state)
        return code
    if not skip_coverage:
        run_coverage_check(paths, entry_id, dry_run=dry_run, strict=False)
    if skip_review:
        state["status"] = "verify_pass"
        dkl.save_qa_state(paths["logs_dir"], state)
        return 0
    if dry_run:
        return run_review_fix_loop(
            paths,
            entry_id,
            dry_run=True,
            dynasty_name=dynasty_name,
            auto_fix_on_review=auto_fix_on_review,
        )
    run_review_fix_loop(
        paths,
        entry_id,
        dry_run=False,
        dynasty_name=dynasty_name,
        auto_fix_on_review=auto_fix_on_review,
    )
    state["status"] = "qa_pass"
    dkl.save_qa_state(paths["logs_dir"], state)
    return 0


def run_test_display(paths: dict[str, Path], entry_id: str | None = None) -> int:
    """本地内容展现测试：模拟小程序分段 + 可选 API 探测。"""
    from test_content_display import run_display_tests  # noqa: WPS433

    return run_display_tests(paths["details_dir"], entry_id=entry_id)


def _compose_and_save_detail(
    paths: dict[str, Path],
    entry: dict[str, Any],
    entry_id: str,
    rules: dict[str, str],
    *,
    anchor: dict[str, Any] | None,
    bibliography_plan: dict[str, Any] | None,
    wiki_digest: dict[str, Any] | None,
    revise_issues: list[str] | None,
    sibling_entries: list[dict[str, str]] | None,
    out_path: Path,
) -> str:
    cat = dkl.normalize_category(str(entry.get("史略分类") or ""))
    temp = dkl.detail_compose_temperature(cat)
    prompt = compose_detail_prompt(
        entry,
        rules,
        anchor=anchor,
        bibliography_plan=bibliography_plan,
        wiki_digest=wiki_digest,
        revise_issues=revise_issues,
        sibling_entries=sibling_entries,
    )
    label = "compose-revise" if revise_issues else "compose-detail"
    prompt_path = save_llm_prompt(paths["logs_dir"], entry_id, label, prompt)
    _log(f"  📄 prompt 快照: {prompt_path}")
    _log(f"🤖 {label} {entry_id} {entry.get('史略名称')} (temp={temp}) …")

    data: dict[str, Any] | None = None
    last_raw = ""
    for attempt in range(1, dkl.MAX_COMPOSE_PARSE_ATTEMPTS + 1):
        eff_prompt = prompt + _compose_json_retry_suffix(attempt)
        if attempt > 1:
            _log(f"  ↻ compose JSON 解析重试 {attempt}/{dkl.MAX_COMPOSE_PARSE_ATTEMPTS} …")
        text = dkl.call_llm(
            eff_prompt,
            session_prefix=f"dk-det-{entry_id}-a{attempt}-",
            timeout_sec=900,
            temperature=temp,
        )
        last_raw = text
        data = dkl.parse_compose_detail_response(text)
        if data:
            if attempt > 1:
                _log(f"  ✅ 第 {attempt} 次解析成功")
            break
        save_compose_raw(paths["logs_dir"], entry_id, attempt, label, text)
        _log(f"  ⚠️ compose 第 {attempt} 次输出非合法 JSON → compose_raw/{entry_id}_{label}_r{attempt}.txt")

    if not data:
        raise RuntimeError(
            f"{entry_id} 详情解析失败（{dkl.MAX_COMPOSE_PARSE_ATTEMPTS} 次尝试）；"
            f"见 logs/compose_raw/{entry_id}_{label}_r*.txt"
        )
    data["史略ID"] = entry_id
    detail_text = attach_reference_section(
        str(data["翻译详情"]),
        entry,
        bibliography_plan,
    )
    save_json(out_path, {"史略ID": entry_id, "翻译详情": detail_text})
    return detail_text


def run_compose_detail(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    entries_path: Path | None = None,
    skip_verify: bool = False,
    skip_coverage: bool = False,
    skip_wiki: bool = False,
    skip_bibliography: bool = False,
    force_wiki: bool = False,
    force_bibliography: bool = False,
    auto_revise: bool = False,
) -> None:
    if not entry_id:
        raise SystemExit("compose-detail 必须 --entry-id")
    entry, _src = _load_entry_by_id(paths, entry_id, entries_path=entries_path)
    rules = load_rules_text()
    title = str(entry.get("史略名称") or "未命名")
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)
    out_path = paths["details_dir"] / f"{entry_id}_{safe_title}.json"

    anchor = dkl.load_anchor(paths["anchors_dir"], entry_id)
    if not anchor and not dry_run:
        _log(f"📌 无锚点，先 anchor-research {entry_id} …")
        run_anchor_research(paths, entry_id, dry_run=False)
        anchor = dkl.load_anchor(paths["anchors_dir"], entry_id)

    bibliography_plan = _ensure_bibliography_plan(
        paths,
        entry_id,
        entry,
        dry_run=dry_run,
        skip=skip_bibliography,
        force=force_bibliography,
    )
    # 有书目 plan 时默认不拉维基（拓展路主底池切换）
    effective_skip_wiki = skip_wiki or bool(bibliography_plan)

    wiki_digest: dict[str, Any] | None = None
    if not effective_skip_wiki:
        if dry_run:
            wiki_digest = wiki.load_wiki_digest(paths["wiki_dir"], entry_id)
            if wiki_digest:
                wiki_digest = wiki.apply_scope_to_digest(wiki_digest, entry)
        else:
            wiki_digest = _ensure_wiki_digest(
                paths,
                entry_id,
                entry,
                force=force_wiki,
                dry_run=False,
            )

    state = dkl.load_qa_state(paths["logs_dir"], entry_id)
    siblings = _find_sibling_entries(paths, entry)
    prompt = compose_detail_prompt(
        entry,
        rules,
        anchor=anchor,
        bibliography_plan=bibliography_plan,
        wiki_digest=wiki_digest,
        sibling_entries=siblings,
    )
    prompt_path = save_llm_prompt(paths["logs_dir"], entry_id, "compose-detail", prompt)
    if dry_run:
        cat = dkl.normalize_category(str(entry.get("史略分类") or ""))
        type_file = (
            "人物详情撰写规则.md"
            if cat in dkl.PERSON_INDEX_CATEGORIES
            else "详情撰写规则.md"
        )
        _log(f"=== compose-detail {entry_id} dry-run ===")
        _log(f"  📄 完整 prompt 已写入: {prompt_path}")
        _log(
            f"  📏 总长 {len(prompt):,} 字符"
            f"（撰写规范 = 详情写作_共用规范 + {type_file} 全文）"
        )
        if bibliography_plan:
            ms = bibliography_plan.get("material_summary") or {}
            _log(f"  📋 书目 plan overall={ms.get('overall', '?')}")
        return

    if int(state.get("compose_attempts") or 0) >= dkl.MAX_QA_DETAIL_ROUNDS:
        raise RuntimeError(
            f"{entry_id} 已达撰写上限 {dkl.MAX_QA_DETAIL_ROUNDS} 次，"
            f"状态={state.get('status')}，请人工处理或重置 qa_state"
        )

    _compose_and_save_detail(
        paths,
        entry,
        entry_id,
        rules,
        anchor=anchor,
        bibliography_plan=bibliography_plan,
        wiki_digest=wiki_digest,
        revise_issues=None,
        sibling_entries=siblings,
        out_path=out_path,
    )
    state["compose_attempts"] = int(state.get("compose_attempts") or 0) + 1
    body_len = len(dkl.strip_detail_body(str(json.loads(out_path.read_text())["翻译详情"])))
    _log(f"  ✅ 详情 {out_path.name} ({body_len} 字)")

    if skip_verify:
        state["status"] = "composed"
        dkl.save_qa_state(paths["logs_dir"], state)
        if not skip_coverage:
            run_coverage_check(paths, entry_id, dry_run=False, strict=False)
        return

    report = dv.verify_detail(
        entry,
        json.loads(out_path.read_text(encoding="utf-8")),
        anchor=anchor,
        bibliography_plan=bibliography_plan,
    )
    dkl.save_verify_artifact(paths["logs_dir"], entry_id, report.to_dict())
    verify_ok = report.passed
    if verify_ok:
        _log(f"✅ verify-detail {entry_id} 通过")
    else:
        issues = [f"{i.code}: {i.message}" for i in report.issues if i.severity == "error"]
        for i in report.issues:
            if i.severity == "warn":
                _log(f"  ⚠️ verify/{i.code}: {i.message}")
        report = _apply_verify_format_autofix(
            paths, entry, entry_id, out_path, report
        )
        verify_ok = report.passed
        if not verify_ok:
            issues = [
                f"{i.code}: {i.message}"
                for i in report.issues
                if i.severity == "error"
            ]
        if (
            not verify_ok
            and auto_revise
            and int(state.get("compose_attempts") or 0) < dkl.MAX_QA_DETAIL_ROUNDS
        ):
            _log(f"↻ compose-revise {entry_id}（1 次上限，整篇重写）…")
            _compose_and_save_detail(
                paths,
                entry,
                entry_id,
                rules,
                anchor=anchor,
                bibliography_plan=bibliography_plan,
                wiki_digest=wiki_digest,
                revise_issues=issues,
                sibling_entries=siblings,
                out_path=out_path,
            )
            state["compose_attempts"] = int(state.get("compose_attempts") or 0) + 1
            report2 = dv.verify_detail(
                entry,
                json.loads(out_path.read_text(encoding="utf-8")),
                anchor=anchor,
                bibliography_plan=bibliography_plan,
            )
            dkl.save_verify_artifact(paths["logs_dir"], entry_id, report2.to_dict())
            verify_ok = report2.passed
            if verify_ok:
                _log(f"✅ compose-revise 后 verify 通过")
            else:
                issues = [
                    f"{i.code}: {i.message}"
                    for i in report2.issues
                    if i.severity == "error"
                ]
        if not verify_ok:
            _log(
                f"⚠️ verify-detail {entry_id} 未通过（草稿已落盘 → {out_path.name}）；"
                f"问题：{'; '.join(issues[:5])}"
            )

    if not skip_coverage:
        try:
            run_coverage_check(paths, entry_id, dry_run=False, strict=False)
        except Exception as exc:
            _log(f"  ⚠️ compose 收尾 coverage-check 异常（成稿已落盘，继续）: {exc}")

    if verify_ok:
        state["status"] = "verify_pass"
    else:
        state["status"] = "needs_human"
    dkl.save_qa_state(paths["logs_dir"], state)
    return


def parse_dynasty_year(text: Any) -> int | None:
    if text is None:
        return None
    s = str(text).strip()
    m = re.search(r"-?\d+", s)
    return int(m.group()) if m else None


def gate_validate_entries(
    entries: list[dict[str, Any]],
    context: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    dynasty_start = parse_dynasty_year(context.get("开始时间"))
    dynasty_end = parse_dynasty_year(context.get("结束时间"))
    if dynasty_start is not None and dynasty_end is not None and dynasty_start > dynasty_end:
        dynasty_start, dynasty_end = dynasty_end, dynasty_start

    names_by_cat: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for e in entries:
        cat = str(e.get("史略分类", ""))
        name = str(e.get("史略名称", ""))
        if cat in names_by_cat:
            names_by_cat[cat].append(name)

    has_dianzhi_chanyi = any("禅让" in n and "制" in n for n in names_by_cat["典制"])
    has_lunzhu_chanyi_thought = any(
        "禅让" in n and ("思想" in n or "观" in n) for n in names_by_cat["论著"]
    )

    for e in entries:
        eid = str(e.get("史略ID", ""))
        name = str(e.get("史略名称", ""))
        cat = str(e.get("史略分类", ""))
        start_year = e.get("史略开始年")
        end_year = e.get("史略结束年")
        peak_year = e.get("峰值年")

        if dynasty_start is not None and dynasty_end is not None:
            if isinstance(start_year, int) and (
                start_year < dynasty_start or start_year > dynasty_end
            ):
                issues.append(
                    f"[{eid}] {name} 史略开始年 {start_year} 不在朝代"
                    f" [{dynasty_start}, {dynasty_end}] 区间内"
                )
            if isinstance(end_year, int) and (
                end_year < dynasty_start or end_year > dynasty_end
            ):
                issues.append(
                    f"[{eid}] {name} 史略结束年 {end_year} 不在朝代"
                    f" [{dynasty_start}, {dynasty_end}] 区间内"
                )

        if isinstance(start_year, int) and isinstance(end_year, int):
            lo, hi = min(start_year, end_year), max(start_year, end_year)
            if cat in ("典制", "论著") and start_year != end_year:
                issues.append(
                    f"[{eid}] {name} {cat} 史略开始年≠结束年"
                    f"（应锚定单年：确立/成熟年或成书年）"
                )
            if isinstance(peak_year, int) and (peak_year < lo or peak_year > hi):
                issues.append(
                    f"[{eid}] {name} 峰值年 {peak_year} 不在"
                    f" [{lo}, {hi}]（见峰值年规则 §三）"
                )

        if cat == "论著":
            if re.search(r"《[^》]+·[^》]+》", name):
                issues.append(f"[{eid}] {name} 论著禁止按篇拆书（《书名·篇名》）")
            if "尚书" in name:
                issues.append(f"[{eid}] {name} 《尚书》成书于周，不归本朝论著")
            tag = str(e.get("论著标签") or "").strip()
            if not tag:
                issues.append(f"[{eid}] {name} 缺少论著标签（2-5 字）")
            elif not dkl.LUNZHU_TAG_RE.fullmatch(tag):
                issues.append(f"[{eid}] {name} 论著标签「{tag}」不符合 2-5 汉字")

        if cat == "论著" and dynasty_start is not None and dynasty_end is not None:
            if isinstance(start_year, int) and (
                start_year < dynasty_start or start_year > dynasty_end
            ):
                issues.append(
                    f"[{eid}] {name} 成书年 {start_year} 不在朝代"
                    f" [{dynasty_start}, {dynasty_end}] 区间内"
                )

        if has_dianzhi_chanyi and has_lunzhu_chanyi_thought:
            if cat == "论著" and "禅让" in name:
                issues.append(
                    f"[{eid}] {name} 与典制「禅让制」同概念，"
                    "思想面写入详情，不另建论著条"
                )

    return issues


def gate_validate_person_entries(
    entries: list[dict[str, Any]],
    context: dict[str, Any],
    *,
    phase1_canonicals: set[str],
    alias_index: dict[str, str],
) -> list[str]:
    issues: list[str] = []
    dynasty_start = parse_dynasty_year(context.get("开始时间"))
    dynasty_end = parse_dynasty_year(context.get("结束时间"))
    if dynasty_start is not None and dynasty_end is not None and dynasty_start > dynasty_end:
        dynasty_start, dynasty_end = dynasty_end, dynasty_start

    alias_map = dkl.load_person_alias_maps()
    seen_canonical: dict[str, str] = {}

    for e in entries:
        eid = str(e.get("史略ID", ""))
        name = str(e.get("史略名称", ""))
        cat = str(e.get("史略分类", ""))
        start_year = e.get("史略开始年")
        end_year = e.get("史略结束年")
        peak_year = e.get("峰值年")

        if cat not in PERSON_CATEGORIES:
            issues.append(f"[{eid}] {name} 非法人物分类「{cat}」")
            continue

        canon = alias_index.get(name) or dkl.normalize_person_name(name, alias_map)
        if canon in phase1_canonicals or name in phase1_canonicals:
            if not dkl.is_dynasty_supplement_entry(e):
                issues.append(f"[{eid}] {name} 与一期已标注人物重复（含别名）")
        if canon in seen_canonical:
            issues.append(
                f"[{eid}] {name} 与本批 {seen_canonical[canon]} 为同一人（别名重复）"
            )
        else:
            seen_canonical[canon] = eid

        if dynasty_start is not None and dynasty_end is not None:
            for label, yr in (("史略开始年", start_year), ("史略结束年", end_year)):
                if isinstance(yr, int) and (yr < dynasty_start or yr > dynasty_end):
                    issues.append(
                        f"[{eid}] {name} {label} {yr} 不在朝代"
                        f" [{dynasty_start}, {dynasty_end}] 区间内"
                    )

        if isinstance(start_year, int) and isinstance(end_year, int):
            lo, hi = min(start_year, end_year), max(start_year, end_year)
            if cat == "君王" and start_year == end_year:
                if not dkl.is_dynasty_supplement_entry(e):
                    issues.append(f"[{eid}] {name} 君王开始年=结束年，疑为误标")
            if isinstance(peak_year, int) and (peak_year < lo or peak_year > hi):
                issues.append(
                    f"[{eid}] {name} 峰值年 {peak_year} 不在 [{lo}, {hi}]"
                )

    dynasty_id = str(context.get("朝代ID", "")).strip()
    if dynasty_id:
        issues.extend(dkl.validate_junji_years_for_dynasty(entries, dynasty_id))

    return issues


def _gate_detail_qa(
    paths: dict[str, Path],
    entry: dict[str, Any],
    detail: dict[str, Any],
    *,
    require_review: bool,
) -> list[str]:
    """详情 QA：verify + 可选 review 产物检查。"""
    issues: list[str] = []
    eid = str(entry.get("史略ID", ""))
    name = str(entry.get("史略名称", ""))
    anchor = dkl.load_anchor(paths["anchors_dir"], eid)
    bib_plan = blib.load_plan(paths["bibliography_dir"], eid)
    report = dv.verify_detail(
        entry, detail, anchor=anchor, bibliography_plan=bib_plan
    )
    dkl.save_verify_artifact(paths["logs_dir"], eid, report.to_dict())
    for issue in report.issues:
        if issue.severity == "error":
            issues.append(f"[{eid}] {name} verify/{issue.code}: {issue.message}")
        else:
            _log(f"  ⚠️ [{eid}] verify/{issue.code}: {issue.message}")

    review = dkl.load_review_artifact(paths["logs_dir"], eid)
    if require_review and not review:
        issues.append(f"[{eid}] {name} 缺少 review-detail 审校产物")
    elif not review:
        _log(f"  ⚠️ [{eid}] 未跑 review-detail（建议 qa-detail）")
    elif review.get("has_factual_errors"):
        n = len(review.get("factual_errors") or [])
        _log(
            f"  🟡 [{eid}] Kimi 硬史实问题 {n} 处："
            f"{str(review.get('summary') or '')[:80]}（见 review_warns_汇总.md）"
        )
    elif str(review.get("overall_verdict")) in ("warn", "fail"):
        _log(
            f"  🟡 [{eid}] Kimi {review.get('overall_verdict')}: "
            f"{str(review.get('summary') or '')[:80]}（见 review_warns_汇总.md）"
        )
    return issues


def run_gate_renwu(paths: dict[str, Path], context: dict[str, Any], *, require_review: bool = False) -> int:
    issues: list[str] = []
    if not paths["entries_renwu"].is_file():
        issues.append("缺少人物索引文件")
        _report_gate(issues)
        return 1
    doc = json.loads(paths["entries_renwu"].read_text(encoding="utf-8"))
    entries = doc.get("entries") or []
    dynasty_id = str(context["朝代ID"])
    emperors = dkl.load_emperors(HISTOGRAPH_ROOT, dynasty_id)
    aligned_entries, align_changes = dkl.align_junji_entries_with_emperor_list(
        entries, emperors, force=True
    )
    if align_changes:
        doc["entries"] = aligned_entries
        save_json(paths["entries_renwu"], doc)
        entries = aligned_entries
        _log(f"🔧 gate-renwu：已自动对齐君王年份 {len(align_changes)} 处")
    phase1, alias_index = dkl.load_phase1_person_index(HISTOGRAPH_ROOT, dynasty_id)
    phase1_canonicals = {str(p.get("标准名")) for p in phase1}
    issues.extend(
        gate_validate_person_entries(
            entries, context, phase1_canonicals=phase1_canonicals, alias_index=alias_index
        )
    )
    issues.extend(
        dkl.validate_mandatory_emperor_coverage(
            HISTOGRAPH_ROOT,
            dynasty_id,
            alias_index,
            extra_entries=entries,
        )
    )
    for e in entries:
        eid = str(e.get("史略ID", ""))
        name = str(e.get("史略名称", ""))
        cat = str(e.get("史略分类", ""))
        if e.get("原文字句"):
            issues.append(f"[{eid}] 不应含原文字句")
        if not str(e.get("史略简介", "")).strip():
            issues.append(f"[{eid}] 缺少史略简介")
        detail_files = list(paths["details_dir"].glob(f"{eid}_*.json"))
        if not detail_files:
            issues.append(f"[{eid}] {name} 缺少详情 JSON")
            continue
        detail = json.loads(detail_files[0].read_text(encoding="utf-8"))
        issues.extend(dkl.validate_detail_schema(detail, detail_id=eid))
        issues.extend(
            _gate_detail_qa(paths, e, detail, require_review=require_review)
        )
    _report_gate(issues)
    if issues:
        return 1
    _log(f"✅ gate-renwu 通过（{len(entries)} 条）")
    return 0


def run_gate(paths: dict[str, Path], context: dict[str, Any], *, require_review: bool = False) -> int:
    issues: list[str] = []
    if not paths["entries"].is_file():
        issues.append("缺少索引文件")
        _report_gate(issues)
        return 1
    doc = json.loads(paths["entries"].read_text(encoding="utf-8"))
    entries = doc.get("entries") or []
    issues.extend(gate_validate_entries(entries, context))

    # Schema validation for all entries
    for e in entries:
        eid = str(e.get("史略ID", ""))
        issues.extend(dkl.validate_entry_schema(e, entry_id=eid))

    for e in entries:
        eid = str(e.get("史略ID", ""))
        name = str(e.get("史略名称", ""))
        cat = str(e.get("史略分类", ""))
        if e.get("原文字句"):
            issues.append(f"[{eid}] 不应含原文字句")
        if not str(e.get("史略简介", "")).strip():
            issues.append(f"[{eid}] 缺少史略简介")
        detail_files = list(paths["details_dir"].glob(f"{eid}_*.json"))
        if not detail_files:
            issues.append(f"[{eid}] {name} 缺少详情 JSON")
            continue
        detail = json.loads(detail_files[0].read_text(encoding="utf-8"))
        issues.extend(dkl.validate_detail_schema(detail, detail_id=eid))
        issues.extend(
            _gate_detail_qa(paths, e, detail, require_review=require_review)
        )
    _report_gate(issues)
    if issues:
        return 1
    _log(f"✅ gate 通过（{len(entries)} 条）")
    return 0


def _report_gate(issues: list[str]) -> None:
    if issues:
        _log(f"❌ gate 问题 {len(issues)} 项：")
        for line in issues[:30]:
            _log(f"  - {line}")


def run_enrich_renwu(paths: dict[str, Path], context: dict[str, Any], *, dry_run: bool) -> int:
    if dry_run:
        _log("enrich-renwu dry-run skip")
        return 0
    if not paths["entries_renwu"].is_file():
        raise SystemExit(f"缺少人物索引: {paths['entries_renwu']}")
    py = sys.executable
    dynasty_id = str(context["朝代ID"])
    idx = paths["entries_renwu"]
    for script, label, extra in (
        ("dynasty_priority.py", "优先级", ()),
        ("peak_year.py", "峰值年", ()),
        ("person_tag.py", "人物标签", ("--no-empty",)),
    ):
        cmd = [py, str(ANNOTATE_DIR / script), str(idx), "--llm", *extra, "--dynasty-id", dynasty_id]
        _log(f"🤖 {label}: {' '.join(cmd[-4:])}")
        subprocess.run(cmd, check=True, cwd=str(ANNOTATE_DIR.parent))
    # —— person_tag 后验证：补全人物必须有标签 ——
    idx_data = json.loads(idx.read_text(encoding="utf-8"))
    missing_tags: list[str] = []
    for e in idx_data.get("entries") or []:
        cat = str(e.get("史略分类", ""))
        if cat not in PERSON_CATEGORIES:
            continue
        eid = str(e.get("史略ID", ""))
        name = str(e.get("史略名称", ""))
        tag = str(e.get("人物标签", "")).strip()
        auto = e.get("_auto_filled") or {}
        if not tag and not auto.get("_人物标签留空"):
            missing_tags.append(f"[{eid}] {name}")
    if missing_tags:
        _log(f"❌ 补全人物标签缺失 {len(missing_tags)} 条（person_tag.py --no-empty 未产出且无留空标记，需人工复核）：")
        for line in missing_tags[:20]:
            _log(f"  - {line}")
        return 1
    _log("✅ enrich-renwu 完成")
    return 0


def run_repair_index(
    paths: dict[str, Path],
    context: dict[str, Any],
    *,
    dry_run: bool,
) -> int:
    dynasty_id = str(context["朝代ID"])
    emperors = dkl.load_emperors(HISTOGRAPH_ROOT, dynasty_id)
    alias_map = dkl.load_person_alias_maps()
    total_changes = 0
    for key in ("entries", "entries_renwu"):
        path = paths.get(key)
        if not path or not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        entries = list(doc.get("entries") or [])
        if not entries:
            continue
        repaired, changes = dkl.repair_supplement_entries(
            entries, emperors, alias_map=alias_map
        )
        if changes:
            _log(f"🔧 repair-index {path.name}: {len(changes)} 处")
            for line in changes[:20]:
                _log(f"  - {line}")
            if len(changes) > 20:
                _log(f"  … 另有 {len(changes) - 20} 处")
            total_changes += len(changes)
        if dry_run:
            continue
        doc["entries"] = repaired
        save_json(path, doc)
    if dry_run:
        _log(f"repair-index dry-run: 预计修改 {total_changes} 处")
    else:
        _log(f"✅ repair-index 完成（{total_changes} 处）")
    return 0


def run_enrich(paths: dict[str, Path], context: dict[str, Any], *, dry_run: bool) -> int:
    if dry_run:
        _log("enrich dry-run skip")
        return 0
    py = sys.executable
    dynasty_id = str(context["朝代ID"])
    idx = paths["entries"]
    for script, label in (
        ("dynasty_priority.py", "优先级"),
        ("peak_year.py", "峰值年"),
    ):
        cmd = [py, str(ANNOTATE_DIR / script), str(idx), "--llm", "--dynasty-id", dynasty_id]
        _log(f"🤖 {label}: {' '.join(cmd[-4:])}")
        subprocess.run(cmd, check=True, cwd=str(ANNOTATE_DIR.parent))
    _log("✅ enrich 完成")
    return 0


def run_test_review_llm() -> int:
    """独立质检模型连通性测试（Moonshot Kimi / OpenAI 兼容）。"""
    from llm.config import review_settings  # noqa: WPS433
    from llm.review_provider import test_review_connectivity  # noqa: WPS433

    cfg = review_settings()
    _log(f"🔌 test-review-llm → {cfg['model']} @ {cfg['base_url']}")
    try:
        out = test_review_connectivity()
    except Exception as exc:
        _log(f"❌ Review LLM 连通失败: {exc}")
        return 1
    _log(f"✅ Review LLM 连通成功（model={out.get('model')} session={out.get('session_id')}）")
    preview = str(out.get("result", "")).strip().replace("\n", " ")[:80]
    _log(f"   回复预览: {preview}")
    return 0


def aggregate_details(paths: dict[str, Path]) -> None:
    entries_out = []
    for p in sorted(paths["details_dir"].glob("GLBL_*.json")):
        if p.name.startswith("朝代知识"):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        stem = p.stem
        parts = stem.split("_", 1)
        entries_out.append(
            {
                "史略ID": d.get("史略ID"),
                "史略名称": parts[1] if len(parts) > 1 else "",
                "翻译详情": d.get("翻译详情"),
            }
        )
    agg = {
        "schema": "dynasty-knowledge-detail/v1",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(entries_out),
        "entries": entries_out,
    }
    out = paths["details_dir"] / "朝代知识详情_汇总.json"
    save_json(out, agg)
    _log(f"✅ 详情汇总 {out} ({len(entries_out)} 条)")


def main() -> int:
    dkl.load_env()
    parser = argparse.ArgumentParser(description="朝代知识补全（五帝试点）")
    parser.add_argument("--dynasty-id")
    parser.add_argument("--dynasty")
    parser.add_argument("--step", choices=STEPS, required=True)
    parser.add_argument("--entry-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--compose-after-fill",
        action="store_true",
        help="fill 后立即 compose-detail（默认关闭；须用户批准后再写详情）",
    )
    parser.add_argument(
        "--skip-approval",
        action="store_true",
        help="跳过人审批准检查（仅开发调试，agent 禁止使用）",
    )
    parser.add_argument(
        "--review-phase",
        choices=REVIEW_PHASES,
        default="candidates",
        help="export-review 阶段：candidates=候选清单；entries=已产出索引待写详情",
    )
    parser.add_argument(
        "--omission-phase",
        choices=("auto", "research", "candidates", "entries", "details"),
        default="auto",
        help="export-omission-prompt 审阅阶段；各生成步骤结束后自动导出时用 auto",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="compose-detail 落盘后跳过 verify-detail（仅调试）",
    )
    parser.add_argument(
        "--skip-coverage",
        action="store_true",
        help="compose-detail / qa-detail 跳过 coverage-check",
    )
    parser.add_argument(
        "--skip-wiki",
        action="store_true",
        help="compose-detail 跳过维基底稿拉取",
    )
    parser.add_argument(
        "--skip-bibliography",
        action="store_true",
        help="compose-detail 跳过书目 plan 路（回退维基主底池）",
    )
    parser.add_argument(
        "--force-bibliography",
        action="store_true",
        help="bibliography-plan / compose-detail 强制重跑书目 plan",
    )
    parser.add_argument(
        "--auto-revise",
        action="store_true",
        help="verify 失败时自动 compose-revise 一次（默认关闭）",
    )
    parser.add_argument(
        "--force-wiki",
        action="store_true",
        help="compose-detail / wiki-fetch 强制重新拉取维基摘录",
    )
    parser.add_argument(
        "--require-review",
        action="store_true",
        help="gate 强制要求已有 review-detail 产物",
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="qa-detail 跳过 Kimi 审校",
    )
    parser.add_argument(
        "--no-auto-fix-review",
        action="store_true",
        help="Kimi 发现硬错误时不自动 fix-detail 精准改稿",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="后台执行本步骤（写日志后立即返回，不占用对话）",
    )
    args = parser.parse_args()

    dynasty = resolve_dynasty(dynasty_id=args.dynasty_id, dynasty_name=args.dynasty)
    context = build_dynasty_context(dynasty)
    paths = output_paths(str(context["朝代名称"]))

    bg_args = [
        *(["--dynasty-id", args.dynasty_id] if args.dynasty_id else []),
        *(["--dynasty", args.dynasty] if args.dynasty else []),
        "--step",
        args.step,
    ]
    if args.entry_id:
        bg_args += ["--entry-id", args.entry_id]
    if args.dry_run:
        bg_args.append("--dry-run")
    if args.compose_after_fill:
        bg_args.append("--compose-after-fill")
    if args.skip_approval:
        bg_args.append("--skip-approval")
    if args.step == "export-review":
        bg_args += ["--review-phase", args.review_phase]
    if args.skip_verify:
        bg_args.append("--skip-verify")
    if args.skip_coverage:
        bg_args.append("--skip-coverage")
    if args.skip_wiki:
        bg_args.append("--skip-wiki")
    if args.skip_bibliography:
        bg_args.append("--skip-bibliography")
    if args.force_bibliography:
        bg_args.append("--force-bibliography")
    if args.auto_revise:
        bg_args.append("--auto-revise")
    if args.force_wiki:
        bg_args.append("--force-wiki")
    if args.background:
        spawn_background(bg_args, paths, f"{context['朝代名称']}_{args.step}")
        return 0

    _log(f"模块: historiography-dynasty-knowledge | 朝代: {context['朝代名称']}")
    _log(f"LLM: {dkl.llm_model_label()}")

    step = args.step
    compose_after = args.compose_after_fill
    require_approval = not args.skip_approval

    if step == "research":
        run_research(context, paths, dry_run=args.dry_run)
    elif step == "export-review":
        run_export_review(context, paths, phase=args.review_phase)
        maybe_export_omission_prompt(
            context,
            paths,
            phase=args.omission_phase,
            trigger_step=f"export-review({args.review_phase})",
            dry_run=args.dry_run,
        )
    elif step == "export-omission-prompt":
        run_export_omission_prompt(
            context,
            paths,
            phase=args.omission_phase,
            trigger_step="export-omission-prompt",
        )
    elif step == "candidates-renwu":
        run_candidates_renwu(context, paths, dry_run=args.dry_run)
    elif step == "fill-renwu":
        run_fill_renwu(
            context,
            paths,
            dry_run=args.dry_run,
            compose_after=compose_after,
            require_approval=require_approval,
        )
    elif step.startswith("candidates-"):
        cat = step_to_category(step)
        if not cat:
            raise SystemExit(f"未知步骤 {step}")
        run_candidates_one(context, paths, cat, dry_run=args.dry_run)
    elif step.startswith("fill-"):
        cat = step_to_category(step)
        if not cat:
            raise SystemExit(f"未知步骤 {step}")
        run_fill_category(
            context,
            paths,
            cat,
            dry_run=args.dry_run,
            compose_after=compose_after,
            require_approval=require_approval,
        )
    elif step == "compose-detail":
        run_compose_detail(
            paths,
            (args.entry_id or "").strip(),
            dry_run=args.dry_run,
            skip_verify=args.skip_verify,
            skip_coverage=args.skip_coverage,
            skip_wiki=args.skip_wiki,
            skip_bibliography=args.skip_bibliography,
            force_wiki=args.force_wiki,
            force_bibliography=args.force_bibliography,
            auto_revise=args.auto_revise,
        )
    elif step == "compose-pending":
        run_compose_pending(
            context,
            paths,
            dry_run=args.dry_run,
            require_approval=require_approval,
        )
    elif step == "anchor-research":
        run_anchor_research(paths, (args.entry_id or "").strip(), dry_run=args.dry_run)
    elif step == "bibliography-plan":
        run_bibliography_plan(
            paths,
            (args.entry_id or "").strip(),
            dry_run=args.dry_run,
            force=args.force_bibliography,
        )
    elif step == "fetch-snippets":
        run_fetch_snippets(paths, (args.entry_id or "").strip(), dry_run=args.dry_run)
    elif step == "verify-bibliography":
        return run_verify_bibliography(paths, (args.entry_id or "").strip())
    elif step == "wiki-fetch":
        run_wiki_fetch(
            paths,
            (args.entry_id or "").strip(),
            dry_run=args.dry_run,
            force=args.force_wiki,
        )
    elif step == "verify-detail":
        return run_verify_detail(paths, (args.entry_id or "").strip())
    elif step == "coverage-check":
        return run_coverage_check(
            paths,
            (args.entry_id or "").strip(),
            dry_run=args.dry_run,
            strict=False,
        )
    elif step == "review-detail":
        return run_review_detail(
            paths,
            (args.entry_id or "").strip(),
            dry_run=args.dry_run,
            dynasty_name=str(context.get("朝代名称") or "朝代"),
            auto_fix_on_review=not args.no_auto_fix_review,
        )
    elif step == "fix-detail":
        return run_review_fix_loop(
            paths,
            (args.entry_id or "").strip(),
            dry_run=args.dry_run,
            dynasty_name=str(context.get("朝代名称") or "朝代"),
            auto_fix_on_review=not args.no_auto_fix_review,
        )
    elif step == "auto-fix-verify":
        return run_auto_fix_verify(
            paths,
            (args.entry_id or "").strip() or None,
            dry_run=args.dry_run,
        )
    elif step == "review-warns-summary":
        return run_review_warns_summary(paths, context)
    elif step == "patch-detail":
        return run_patch_detail(paths, (args.entry_id or "").strip(), dry_run=args.dry_run)
    elif step == "qa-detail":
        return run_qa_detail(
            paths,
            (args.entry_id or "").strip(),
            dry_run=args.dry_run,
            skip_review=args.skip_review,
            skip_coverage=args.skip_coverage,
            dynasty_name=str(context.get("朝代名称") or "朝代"),
            auto_fix_on_review=not args.no_auto_fix_review,
        )
    elif step == "test-display":
        return run_test_display(paths, (args.entry_id or "").strip() or None)
    elif step == "gate":
        code = run_gate(paths, context, require_review=args.require_review)
        if code == 0:
            aggregate_details(paths)
        return code
    elif step == "gate-renwu":
        code = run_gate_renwu(paths, context, require_review=args.require_review)
        if code == 0:
            aggregate_details(paths)
        return code
    elif step == "test-review-llm":
        return run_test_review_llm()
    elif step == "enrich":
        return run_enrich(paths, context, dry_run=args.dry_run)
    elif step == "enrich-renwu":
        return run_enrich_renwu(paths, context, dry_run=args.dry_run)
    elif step == "enrich-all":
        code = run_repair_index(paths, context, dry_run=args.dry_run)
        if code != 0:
            return code
        code = run_enrich(paths, context, dry_run=args.dry_run)
        if code != 0:
            return code
        return run_enrich_renwu(paths, context, dry_run=args.dry_run)
    elif step == "repair-index":
        return run_repair_index(paths, context, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
