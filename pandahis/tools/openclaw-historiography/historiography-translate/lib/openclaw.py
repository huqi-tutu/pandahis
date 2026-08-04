"""LLM 调用与翻译 prompt 组装。"""

from __future__ import annotations

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
    return f"""【historiography-translate Phase2: 补全成稿】
史略ID: {entry_id}
产出路径: {output_file}

--- 规则（翻译规则.md 全量注入，动笔时须遵守）---
{bundle}
---

--- Phase1 母本顺译（勿删改骨架，仅在锚点补入）---
{mother_text}
---

--- recalled ---
{recalled_json}
---

--- source_plan ---
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
