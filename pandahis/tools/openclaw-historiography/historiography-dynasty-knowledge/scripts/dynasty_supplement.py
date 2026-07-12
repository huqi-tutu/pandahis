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

import dynasty_supplement_lib as dkl  # noqa: E402

HISTOGRAPH_ROOT = get_histograph_root()
DATA_DIR = HISTOGRAPH_ROOT / DIR_DATA
DYNASTY_JSON = DATA_DIR / "01历史坐标数据" / "朝代.json"
WORK_DIR = DATA_DIR / "05工作流中间产物" / SUBDIR_INTERMEDIATE_DYNASTY_KNOWLEDGE
OUTPUT_DIR = DATA_DIR / DIR_DYNASTY_KNOWLEDGE
ENTRIES_DIR = OUTPUT_DIR / SUBDIR_DYNASTY_KNOWLEDGE_ENTRIES
DETAILS_DIR = OUTPUT_DIR / SUBDIR_DYNASTY_KNOWLEDGE_DETAILS
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
    "fill-shilue",
    "fill-dianzhi",
    "fill-lunzhu",
    "fill-renwu",
    "compose-detail",
    "compose-pending",
    "gate",
    "gate-renwu",
    "enrich",
    "enrich-renwu",
)

REVIEW_PHASES = ("candidates", "entries")

RULES = {
    "总则": MODULE_ROOT / "reference" / "朝代知识补全总则.md",
    "纪律": MODULE_ROOT / "reference" / "执行纪律.md",
    "详情": MODULE_ROOT / "reference" / "详情撰写规则.md",
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

FORBIDDEN_PROSE = (
    "综上所述",
    "由此可见",
    "众所周知",
    "历史长河",
    "命运齿轮",
    "毫无疑问",
)


def _log(msg: str) -> None:
    print(msg, flush=True)


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
5. 不要列事略/典制/论著候选（后续分步）

## 规范摘要
{rules.get('总则', '')[:2500]}
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
            "子类：典籍/名篇/书画/思想理论。不含建筑。"
            "硬约束：成书/创作/提出之年须在本朝区间内；"
            "典籍一书一条，禁止《书名·篇名》按卷拆条；"
            "《尚书》成书于周，不归五帝论著。"
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

## 规范
{rules.get(category, '')[:7000]}

## 输出
JSON 数组，每项含：名称、建议年份、建议挂靠帝王、主要史料出处、边界备注、审核状态(pending)。
事略加：主语、参与人物(数组)、动作、结果、影响。
典制加：制度类型、主旨、确立或成熟年、影响。
论著加：子类、主旨、作者或提出者、成书或传播年、影响。
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

    other_note = ""
    for cat in ("事略", "典制", "论著"):
        items = supplement_knowledge.get(cat) or []
        if items:
            names = [str(x.get("名称", "")) for x in items[:30]]
            other_note += f"\n- 已补「{cat}」：{', '.join(names)}"

    person_rules_excerpt = rules.get("人物标注", "")[:12000]
    renwu_rules = rules.get("人物", "")[:5000]

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
    )
    if dry_run:
        _log("=== candidates-renwu preview ===")
        _log(f"一期人物 {len(phase1)} 条，帝王缺口 {len(emperor_gaps)} 条")
        _log(prompt[:4000])
        _log(f"...（共 {len(prompt)} 字）")
        return

    _log(f"🤖 LLM candidates-renwu（一期已标注 {len(phase1)} 条，禁止重复）…")
    text = dkl.call_llm(prompt, session_prefix="dk-cand-renwu-", timeout_sec=900, temperature=0)
    data = dkl.extract_json_object(text)
    if not data:
        raise RuntimeError("人物候选解析失败（须为 JSON 对象）")

    phase1_canonicals = {str(p.get("标准名", "")) for p in phase1}
    for cat in PERSON_CATEGORIES:
        rows = data.get(cat) or []
        if not isinstance(rows, list):
            raise RuntimeError(f"人物候选「{cat}」须为数组")
        filtered, dropped = filter_renwu_duplicates(rows, alias_index, phase1_canonicals)
        if dropped:
            _log(f"  ⚠️ {cat} 脚本剔除重复 {len(dropped)} 条：{'; '.join(dropped[:5])}")
        for row in filtered:
            if isinstance(row, dict):
                row.setdefault("史略分类", cat)
                row.setdefault("审核状态", "pending")
        payload["candidates"][cat] = filtered
        _log(f"  ✅ {cat}: {len(filtered)} 条候选")

    payload["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_json(paths["candidates"], payload)
    _log(f"✅ 人物候选已写入 {paths['candidates']}")


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
) -> str:
    return f"""将以下候选转为一条 GLBL 索引 JSON（单个对象，不要数组）。
史略ID 必须使用：{glbl_id}
史略分类：{category}
不要填原文字句、paragraphs、优先级（后续 enrichment）。
不要填人物标签（后续 person_tag.py）。

## 朝代
{json.dumps(context, ensure_ascii=False, indent=2)}

## 候选
{json.dumps(candidate, ensure_ascii=False, indent=2)}

## 格式规范摘要
{rules.get('格式', '')[:5000]}

只输出 JSON 对象，字段用中文键名。
"""


def fill_renwu_entry_prompt(
    context: dict[str, Any],
    category: str,
    candidate: dict[str, Any],
    glbl_id: str,
    rules: dict[str, str],
) -> str:
    year_note = (
        "君王：史略开始年=即位年，史略结束年=退位/崩年。"
        "宗戚/文臣/武将/宦官/庶众：史略开始年=出生年，史略结束年=去世年。"
        "传说期人物仅有活跃期时，可在考订依据注明；年份须在朝代区间内。"
    )
    return f"""将以下人物候选转为一条 GLBL 人物索引 JSON（单个对象，不要数组）。
史略ID 必须使用：{glbl_id}
史略分类：{category}（已确定，勿改）
史略名称须用候选「名称」标准名；君王须对齐帝王.json「帝王名称」。
不要填原文字句、paragraphs、优先级、人物标签（后续 enrichment）。
史略简介 ≤20 字，必填。

## 朝代
{json.dumps(context, ensure_ascii=False, indent=2)}

## 候选
{json.dumps(candidate, ensure_ascii=False, indent=2)}

## 人物年份规则
{rules.get('人物年份', '')[:4000]}
{year_note}

## 格式规范摘要
{rules.get('格式', '')[:3000]}

只输出 JSON 对象，字段用中文键名。
"""


def pinyin_rules_excerpt(rules: dict[str, str]) -> str:
    """提取翻译规则七，供 compose-detail 硬性约束。"""
    text = rules.get("翻译规则", "")
    if not text:
        return ""
    m = re.search(r"## 规则七：注音标注.*?(?=\n## 规则八)", text, re.DOTALL)
    return m.group(0).strip() if m else text[:2500]


def compose_detail_prompt(entry: dict[str, Any], rules: dict[str, str]) -> str:
    pri = str(entry.get("优先级") or "P1")
    cat = str(entry.get("史略分类") or "")
    allow_list = "、".join(sorted(dkl._ALLOW_PINYIN_WORDS))
    return f"""为以下史略撰写详情。只输出 JSON：{{"史略ID":"...","翻译详情":"..."}}

## 条目
{json.dumps(entry, ensure_ascii=False, indent=2)}

## 撰写规范
{rules.get('详情', '')[:7000]}

## 硬性要求
- 分类 {cat}，优先级 {pri}，正文（不含参考著作）字数不得低于规范下限
- 起承转合齐全；开篇引入 100-200 字
- 文末 *参考著作：* 与主要史料出处一致
- 禁止【】、禁止 AI 腔
- **注音纪律（二期 · 默认全文不注音）**：
  - 本产品面向具备通识文史素养的读者，**不是**识字教辅/小程序
  - **禁止**给常见字、通识人名、通识地名、动物名、器物名注音
  - 禁止：许由（xǔ yóu）、箕山（jī shān）、颍水（yǐng shuǐ）、偃鼠（yǎn shǔ）、皋陶（gāo yáo）、伯益（yì）、夔（kuí）等
  - 禁止：尧舜禹黄帝、尧帝、五帝时代、丹朱、巢父、皇甫谧 等一切通识专名注音
  - **仅当**正文出现下列罕用字专名时，可保留该词注音：{allow_list}
  - 除上述白名单外，全文不得出现任何「汉字（拼音）」标注
"""


def slug_name(name: str) -> str:
    return name.replace(" ", "_")


def output_paths(dynasty_name: str) -> dict[str, Path]:
    slug = slug_name(dynasty_name)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "research": WORK_DIR / f"{slug}_研究报告.md",
        "candidates": WORK_DIR / f"{slug}_候选清单.json",
        "overlap": WORK_DIR / f"{slug}_重叠审查.md",
        "entries": ENTRIES_DIR / f"{slug}_事略典制论著.json",
        "entries_renwu": ENTRIES_DIR / f"{slug}_人物.json",
        "details_dir": DETAILS_DIR,
        "approval": WORK_DIR / f"{slug}_人审批准.json",
        "review_md": WORK_DIR / f"{slug}_人审确认表.md",
        "logs_dir": WORK_DIR / "logs",
    }


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
    counter = [dkl.max_glbl_num(HISTOGRAPH_ROOT)]

    for idx, cand in enumerate(candidates, start=1):
        name = str(cand.get("名称", "")).strip()
        if not name or name in done_names:
            continue
        glbl_id = dkl.allocate_glbl_id(counter)
        prompt = fill_entry_prompt(context, category, cand, glbl_id, rules)
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
        row = dkl.apply_coord_defaults(row, context)
        emp = resolve_emperor(
            str(cand.get("建议挂靠帝王") or row.get("四级帝王坐标") or ""),
            emperors,
        )
        if emp:
            row.update(emp)
        dykn_cat = CATEGORY_STEP_SUFFIX[category].upper()
        slug = slug_name(str(context["朝代名称"]))
        seq = len([e for e in entries_doc["entries"] if e.get("史略分类") == category]) + 1
        row.setdefault("母本史略ID", f"DYKN_{slug}_{dykn_cat}_{seq:02d}")
        entries_doc["entries"].append(row)
        save_json(paths["entries"], entries_doc)
        _log(f"  ✅ 索引已写入 {glbl_id}")
        if compose_after:
            run_compose_detail(paths, glbl_id, dry_run=False)

    if not dry_run:
        _log(f"✅ fill-{CATEGORY_STEP_SUFFIX[category]} 完成 → {paths['entries']}")


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
            prompt = fill_renwu_entry_prompt(context, cat, cand, glbl_id, rules)
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
            row = dkl.apply_coord_defaults(row, context)
            emp = resolve_emperor(
                str(cand.get("建议挂靠帝王") or row.get("四级帝王坐标") or ""),
                emperors,
            )
            if emp:
                row.update(emp)
            if cat == "君王" and not row.get("帝王ID"):
                emp2 = resolve_emperor(name, emperors)
                if emp2:
                    row.update(emp2)
            seq_by_cat[cat] += 1
            cat_slug = dkl.PERSON_CAT_SLUG.get(cat, "RENWU")
            row.setdefault("母本史略ID", f"DYKN_{slug}_{cat_slug}_{seq_by_cat[cat]:02d}")
            row.setdefault("五级细坐标", f"{context['朝代名称']}·{cat}·{seq_by_cat[cat]:02d}")
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


def run_compose_detail(
    paths: dict[str, Path],
    entry_id: str,
    *,
    dry_run: bool,
    entries_path: Path | None = None,
) -> None:
    if not entry_id:
        raise SystemExit("compose-detail 必须 --entry-id")
    entry, _src = _load_entry_by_id(paths, entry_id, entries_path=entries_path)
    rules = load_rules_text()
    prompt = compose_detail_prompt(entry, rules)
    title = str(entry.get("史略名称") or "未命名")
    cat = str(entry.get("史略分类") or "")
    temp = dkl.detail_compose_temperature(cat)
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)
    out_path = paths["details_dir"] / f"{entry_id}_{safe_title}.json"
    if dry_run:
        _log(f"=== compose-detail {entry_id} preview (temp={temp}) ===")
        _log(prompt[:2000])
        return
    _log(f"🤖 compose-detail {entry_id} {title} (temp={temp}) …")
    text = dkl.call_llm(
        prompt,
        session_prefix=f"dk-det-{entry_id}-",
        timeout_sec=900,
        temperature=temp,
    )
    data = dkl.extract_json_object(text)
    if not data or not str(data.get("翻译详情", "")).strip():
        raise RuntimeError(f"{entry_id} 详情解析失败")
    data["史略ID"] = entry_id
    save_json(out_path, {"史略ID": entry_id, "翻译详情": data["翻译详情"]})
    body_len = len(dkl.strip_detail_body(data["翻译详情"]))
    _log(f"  ✅ 详情 {out_path.name} ({body_len} 字)")


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
                issues.append(f"[{eid}] {name} 君王开始年=结束年，疑为误标")
            if isinstance(peak_year, int) and (peak_year < lo or peak_year > hi):
                issues.append(
                    f"[{eid}] {name} 峰值年 {peak_year} 不在 [{lo}, {hi}]"
                )

    return issues


def run_gate_renwu(paths: dict[str, Path], context: dict[str, Any]) -> int:
    issues: list[str] = []
    if not paths["entries_renwu"].is_file():
        issues.append("缺少人物索引文件")
        _report_gate(issues)
        return 1
    doc = json.loads(paths["entries_renwu"].read_text(encoding="utf-8"))
    entries = doc.get("entries") or []
    dynasty_id = str(context["朝代ID"])
    phase1, alias_index = dkl.load_phase1_person_index(HISTOGRAPH_ROOT, dynasty_id)
    phase1_canonicals = {str(p.get("标准名")) for p in phase1}
    issues.extend(
        gate_validate_person_entries(
            entries, context, phase1_canonicals=phase1_canonicals, alias_index=alias_index
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
        body = dkl.strip_detail_body(str(detail.get("翻译详情", "")))
        pri = str(e.get("优先级") or "P1")
        floor = dkl.detail_min_chars(cat, pri)
        if len(body) < floor:
            issues.append(f"[{eid}] {name} 详情 {len(body)} 字 < 下限 {floor}")
        if "参考著作" not in str(detail.get("翻译详情", "")):
            issues.append(f"[{eid}] 缺少参考著作")
        for w in FORBIDDEN_PROSE:
            if w in body:
                issues.append(f"[{eid}] 含禁词 {w}")
        for pin in dkl.detect_over_pinyin(body):
            issues.append(f"[{eid}] {name} 多余注音：{pin}")
    _report_gate(issues)
    if issues:
        return 1
    _log(f"✅ gate-renwu 通过（{len(entries)} 条）")
    return 0


def run_gate(paths: dict[str, Path], context: dict[str, Any]) -> int:
    issues: list[str] = []
    if not paths["entries"].is_file():
        issues.append("缺少索引文件")
        _report_gate(issues)
        return 1
    doc = json.loads(paths["entries"].read_text(encoding="utf-8"))
    entries = doc.get("entries") or []
    issues.extend(gate_validate_entries(entries, context))
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
        body = dkl.strip_detail_body(str(detail.get("翻译详情", "")))
        pri = str(e.get("优先级") or "P1")
        floor = dkl.detail_min_chars(cat, pri)
        if len(body) < floor:
            issues.append(f"[{eid}] {name} 详情 {len(body)} 字 < 下限 {floor}")
        if "参考著作" not in str(detail.get("翻译详情", "")):
            issues.append(f"[{eid}] 缺少参考著作")
        for w in FORBIDDEN_PROSE:
            if w in body:
                issues.append(f"[{eid}] 含禁词 {w}")
        for pin in dkl.detect_over_pinyin(body):
            issues.append(f"[{eid}] {name} 多余注音：{pin}")
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
    for script, label in (
        ("dynasty_priority.py", "优先级"),
        ("peak_year.py", "峰值年"),
        ("person_tag.py", "人物标签"),
    ):
        cmd = [py, str(ANNOTATE_DIR / script), str(idx), "--llm", "--dynasty-id", dynasty_id]
        _log(f"🤖 {label}: {' '.join(cmd[-4:])}")
        subprocess.run(cmd, check=True, cwd=str(ANNOTATE_DIR.parent))
    _log("✅ enrich-renwu 完成")
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
        run_compose_detail(paths, (args.entry_id or "").strip(), dry_run=args.dry_run)
    elif step == "compose-pending":
        run_compose_pending(
            context,
            paths,
            dry_run=args.dry_run,
            require_approval=require_approval,
        )
    elif step == "gate":
        code = run_gate(paths, context)
        if code == 0:
            aggregate_details(paths)
        return code
    elif step == "gate-renwu":
        code = run_gate_renwu(paths, context)
        if code == 0:
            aggregate_details(paths)
        return code
    elif step == "enrich":
        return run_enrich(paths, context, dry_run=args.dry_run)
    elif step == "enrich-renwu":
        return run_enrich_renwu(paths, context, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
