"""LLM 调用与翻译 prompt 组装。"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.openclaw_provider import default_state_dir, resolve_agent_id  # noqa: E402
from llm.provider import run_agent_turn as _run_agent_turn  # noqa: E402
from llm.config import PROVIDER_DEEPSEEK, ensure_deepseek_v4_pro, get_provider_name  # noqa: E402

from lib.config import DEFAULT_AGENT, TRANSLATE_DIR  # noqa: E402
from lib.mother_sentences import extract_mother_sentences, plan_min_sentence_ratio  # noqa: E402
from lib.rule_bundle import compile_rule_bundle  # noqa: E402


def translate_resolve_agent_id(preferred: str = DEFAULT_AGENT) -> str:
    return resolve_agent_id(
        preferred,
        env_key="TRANSLATE_AGENT",
        forbid_main_message="禁止翻译编排器回调 main agent。请设置 TRANSLATE_AGENT=hist-worker",
    )


def make_session_id(entry_id: str, job_id: int) -> str:
    slug = entry_id.replace("_", "-").lower()
    nonce = uuid.uuid4().hex[:8]
    return f"tr-{slug}-{job_id}-{nonce}"


def build_translate_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    source_plan_json: str,
    output_file: Path,
) -> str:
    """Legacy 单阶段 prompt；默认编排器走 Phase1+Phase2。"""
    tpl = (TRANSLATE_DIR / "prompts" / "translate.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="draft")
    return f"""【historiography-translate job】
史略ID: {entry_id}
产出路径: {output_file}

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- recalled ---
{recalled_json}
---

--- source_plan ---
{source_plan_json}
---

{tpl}
"""


def build_translate_mother_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    source_plan_json: str,
    mother_file: Path,
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "translate_mother.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="draft_mother")
    return f"""【historiography-translate Phase1: 母本顺译】
史略ID: {entry_id}
产出路径: {mother_file}

--- 规则（翻译规则.md 全量注入，动笔时须遵守）---
{bundle}
---

--- recalled ---
{recalled_json}
---

--- source_plan ---
{source_plan_json}
---

{tpl}
"""


def build_translate_structural_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    source_plan_json: str,
    output_file: Path,
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "translate_structural.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="draft_structural")
    return f"""【historiography-translate A: 结构顺译】
史略ID: {entry_id}
产出路径: {output_file}

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- recalled ---
{recalled_json}
---

--- coverage ledger ---
{source_plan_json}
---

{tpl}
"""


def build_translate_style_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    source_plan_json: str,
    structural_text: str,
    output_file: Path,
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "translate_style.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="draft_style")
    return f"""【historiography-translate B: 文风整饰】
史略ID: {entry_id}
产出路径: {output_file}

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- A 阶段结构顺译（须保留全部信息点）---
{structural_text}
---

--- recalled ---
{recalled_json}
---

--- coverage ledger ---
{source_plan_json}
---

{tpl}
"""


def build_translate_assemble_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    source_plan_json: str,
    styled_body: str,
    output_file: Path,
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "translate_assemble.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="draft_assemble")
    first_para = styled_body.split("\n\n")[0][:400] if styled_body else ""
    last_para = styled_body.split("\n\n")[-1][:400] if styled_body else ""
    return f"""【historiography-translate C: 前置引入 + 结尾】
史略ID: {entry_id}
产出路径: {output_file}

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- B 阶段正文（只读；勿改写；用于衔接头尾）---
正文首段：
{first_para}

正文末段：
{last_para}

（全文共约 {len(styled_body)} 字，此处仅首尾预览；中间正文由程序拼接。）
---

--- recalled ---
{recalled_json}
---

--- coverage ledger ---
{source_plan_json}
---

{tpl}
"""


def build_translate_ab_merged_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    source_plan_json: str,
    output_file: Path,
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "translate_mother.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="draft_ab_merged")
    ab_note = (
        "\n\n---\n\n"
        "【AB 合并模式】一次完成结构顺译 + 文风整饰，产出字段仍为 `母本顺译`。"
        "须遵守 translate_mother 的引用粒度、段落节奏与口语规范；禁止他书、引入、结尾、参考著作。"
    )
    return f"""【historiography-translate AB 合并（短篇）】
史略ID: {entry_id}
产出路径: {output_file}

--- 规则 ---
{bundle}
---

--- recalled ---
{recalled_json}
---

--- coverage ledger ---
{source_plan_json}
---

{tpl}{ab_note}
"""


def build_enrich_plan_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    baseline_body: str,
    plan_file: Path,
    *,
    baseline_file: Path | None = None,
    gap_ledger: dict | None = None,
    seed_index: list | None = None,
) -> str:
    import json

    tpl = (TRANSLATE_DIR / "prompts" / "source_enrich_plan.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="enrich_plan")
    if baseline_file and baseline_file.is_file() and len(baseline_body) > 12000:
        baseline_section = (
            f"（全文见 baseline 文件，请读取）\n路径: {baseline_file}\n\n"
            f"--- 首尾预览 ---\n{baseline_body[:4000]}\n\n…\n\n{baseline_body[-3000:]}"
        )
    else:
        baseline_section = baseline_body
    gap_block = ""
    if gap_ledger:
        gap_block = f"\n--- enrich gap ledger（程序缺口，须逐条响应）---\n{json.dumps(gap_ledger, ensure_ascii=False, indent=2)}\n"
    seed_block = ""
    if seed_index:
        seed_block = f"\n--- 索引补充 seed（程序生成，请保留/细化，勿删除「引入」项）---\n{json.dumps(seed_index, ensure_ascii=False, indent=2)}\n"
    return f"""【historiography-translate enrich plan（D 前置）】
史略ID: {entry_id}
计划路径: {plan_file}

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- baseline 成稿（已含引入/正文/结尾）---
{baseline_section}
---
{gap_block}{seed_block}
--- recalled ---
{recalled_json}
---

{tpl}
"""


def build_expansive_plan_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    plan_file: Path,
) -> str:
    import json

    tpl = (TRANSLATE_DIR / "prompts" / "expansive_plan.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="expansive_plan")
    plan_preview = ""
    if plan_file.is_file():
        plan_preview = plan_file.read_text(encoding="utf-8")[:12000]
    return f"""【historiography-translate 发散式 plan · 方案 A】
史略ID: {entry_id}
计划路径: {plan_file}

--- 规则 ---
{bundle}
---

--- 程序已生成的 plan（勿改 母本逐句清单）---
{plan_preview}
---

--- recalled ---
{recalled_json}
---

{tpl}
"""


def build_batch_draft_prompt(
    entry_id: str,
    recalled: dict,
    batch_items: list,
    batch_plan_json: str,
    output_file: Path,
    *,
    continuity_block: str = "",
    prev_batch_tail: str = "",
) -> str:
    from lib.batch_recall import batch_recalled_meta

    tpl = (TRANSLATE_DIR / "prompts" / "batch_draft.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(
        recalled,
        phase="batch_draft",
        batch_m_count=len(batch_items),
    )
    meta_json = batch_recalled_meta(recalled, batch_items)
    ctx = (continuity_block or "").strip()
    if not ctx and prev_batch_tail.strip():
        ctx = f"--- 上批末段（勿重复）---\n{prev_batch_tail.strip()}\n"
    ctx_block = f"{ctx}\n" if ctx else ""
    return f"""【historiography-translate 分批成稿】
史略ID: {entry_id}
产出路径: {output_file}

--- 规则（本阶段写作纪律）---
{bundle}
---
{ctx_block}--- 本批上下文（元数据；母本原文见下方 M 清单）---
{meta_json}
---

--- 本批 M 清单（编号 + 原文摘句；验收字段见磁盘 plan）---
{batch_plan_json}
---

{tpl}
"""


def _entry_meta_for_frame(recalled: dict) -> dict:
    """引入/结尾用的轻量字段（不用 plan 前置素材）。"""
    work = str(recalled.get("母本著作") or "").strip()
    # 01史记 → 史记
    work_display = re.sub(r"^\d+", "", work).strip() or work
    return {
        "史略名称": str(recalled.get("史略名称") or "").strip(),
        "一级文明": str(recalled.get("一级文明坐标") or "").strip(),
        "二级朝代": str(recalled.get("二级朝代坐标") or "").strip(),
        "母本著作": work_display,
        "主要史料出处": str(recalled.get("主要史料出处") or "").strip(),
    }


def build_intro_prompt(
    entry_id: str,
    recalled: dict,
    output_file: Path,
) -> str:
    """精简四步：只写前置引入（短提示，不灌规则包 / plan 素材）。"""
    tpl = (TRANSLATE_DIR / "prompts" / "translate_intro.md").read_text(encoding="utf-8")
    meta = _entry_meta_for_frame(recalled)
    meta_block = "\n".join(f"- {k}：{v or '（无）'}" for k, v in meta.items())
    return f"""【historiography-translate：前置引入】
史略ID: {entry_id}
产出路径: {output_file}

## 本条信息

{meta_block}

{tpl}
"""


def build_ending_prompt(
    entry_id: str,
    recalled: dict,
    body: str,
    output_file: Path,
) -> str:
    """精简四步：只写篇末人物总结（不注入正文；不报著作）。"""
    _ = body  # 兼容旧调用签名；结尾不再参考正文末段
    tpl = (TRANSLATE_DIR / "prompts" / "translate_ending.md").read_text(encoding="utf-8")
    meta = _entry_meta_for_frame(recalled)
    meta_block = "\n".join(
        f"- {k}：{meta[k] or '（无）'}"
        for k in ("史略名称", "一级文明", "二级朝代")
    )
    return f"""【historiography-translate：篇末结尾】
史略ID: {entry_id}
产出路径: {output_file}

## 本条信息

{meta_block}

{tpl}
"""


def build_final_assemble_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    body: str,
    output_file: Path,
) -> str:
    """兼容旧调用；精简流水线请用 build_intro_prompt + build_ending_prompt。"""
    tpl = (TRANSLATE_DIR / "prompts" / "translate_assemble.md").read_text(encoding="utf-8")
    first_para = body.split("\n\n")[0][:500] if body else ""
    last_para = body.split("\n\n")[-1][:500] if body else ""
    return f"""【historiography-translate 终稿装配：引入 + 结尾 · legacy】
史略ID: {entry_id}
产出路径: {output_file}

--- 正文（只读；勿改写；程序拼接）---
正文首段：
{first_para}

正文末段：
{last_para}

（全文约 {len(body)} 字）
---

--- recalled ---
{recalled_json}
---

{tpl}
"""


def build_translate_enrich_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    source_plan_json: str,
    mother_text: str,
    output_file: Path,
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "translate_enrich.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="draft_enrich")
    return f"""【historiography-translate D: 知识增强 enrich】
史略ID: {entry_id}
产出路径: {output_file}

--- 规则（翻译规则.md 全量注入，动笔时须遵守）---
{bundle}
---

--- baseline 成稿（勿删改引入/结尾骨架，仅在锚点插入补全）---
{mother_text}
---

--- recalled ---
{recalled_json}
---

--- enrich plan ---
{source_plan_json}
---

{tpl}
"""


def build_source_plan_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    plan_file: Path,
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "source_plan.md").read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="plan")
    mother_sents = extract_mother_sentences(recalled)
    min_items = max(1, int(len(mother_sents) * plan_min_sentence_ratio()))
    baseline = "\n".join(
        f"  - M{i:03d} | {s['段落']} | {s['原文摘句'][:80]}"
        for i, s in enumerate(mother_sents[:12], start=1)
    )
    if len(mother_sents) > 12:
        baseline += f"\n  …共 {len(mother_sents)} 句，须全部列入清单"
    return f"""【historiography-translate source-plan job】
史略ID: {entry_id}
计划路径: {plan_file}
母本分句数: {len(mother_sents)}（清单至少 {min_items} 条，每条仅一个分句）

--- 母本分句基准（前12句示例，须全部覆盖）---
{baseline}
---

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- recalled ---
{recalled_json}
---

{tpl}
"""


def build_chunk_source_plan_prompt(
    entry_id: str,
    recalled_chunk: dict,
    recalled_json: str,
    plan_file: Path,
    *,
    sentence_id_start: int,
    sentence_id_end: int,
    chunk_id: int,
    chunk_total: int,
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "source_plan_chunk.md").read_text(
        encoding="utf-8"
    )
    bundle = compile_rule_bundle(recalled_chunk, phase="plan")
    return f"""【historiography-translate chunk source-plan】
史略ID: {entry_id}
分块: {chunk_id}/{chunk_total}
母本清单编号: M{sentence_id_start:03d} — M{sentence_id_end:03d}
计划路径: {plan_file}

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- recalled（本分块）---
{recalled_json}
---

{tpl}
"""


def build_chunk_translate_prompt(
    entry_id: str,
    recalled_chunk: dict,
    recalled_json: str,
    source_plan_json: str,
    body_file: Path,
    *,
    chunk_id: int,
    chunk_total: int,
    previous_tail: str = "",
) -> str:
    tpl = (TRANSLATE_DIR / "prompts" / "translate_chunk.md").read_text(
        encoding="utf-8"
    )
    bundle = compile_rule_bundle(recalled_chunk, phase="draft")
    tail_block = ""
    if previous_tail:
        tail_block = f"""
--- 上一分块结尾（仅供衔接，勿重复）---
{previous_tail}
---
"""
    return f"""【historiography-translate chunk draft】
史略ID: {entry_id}
分块: {chunk_id}/{chunk_total}
分块正文路径: {body_file}

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- recalled（本分块）---
{recalled_json}
---
{tail_block}
--- source_plan（本分块）---
{source_plan_json}
---

{tpl}
"""


def run_agent_turn(*args, **kwargs):
    if get_provider_name() == PROVIDER_DEEPSEEK:
        ensure_deepseek_v4_pro()
    kwargs.setdefault("openclaw_env_key", "TRANSLATE_AGENT")
    kwargs.setdefault("openclaw_local_env_key", "TRANSLATE_OPENCLAW_LOCAL")
    kwargs.setdefault(
        "forbid_main_message",
        "禁止翻译编排器回调 main agent。请设置 TRANSLATE_AGENT=hist-worker",
    )
    return _run_agent_turn(*args, **kwargs)
