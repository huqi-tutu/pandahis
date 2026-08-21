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

--- recalled（本批原文窗口：must_translate + 前后文 context；勿译 context）---
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
    return f"""【historiography-translate Phase1 · 母本顺译】
史略ID: {entry_id}
产出路径: {mother_file}

角色：你是「时络历史」母本顺译编辑——只把本条母本译成准确可读的现代汉语骨架；不补他书、不做说书发挥；不限定单一文明。

--- 规则（本阶段切片：母本顺译主场；动笔时须遵守）---
{bundle}
---

--- recalled（本批 M 原文摘句：must_sentences / must_by_paragraph；只译列出摘句；同组合段，禁一条 M 一段）---
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
    """Phase2 提示结构（系统层）：声口置顶 → 金标示范 → 母本素材 → 约束。

    旧结构把大段规则+母本堆在前面、细则扔在最后，模型易誊抄母本、丢掉说书腔。
    v7 能出味道，靠的是说书示范与表达空间；仅加门禁拦不住誊抄。
    """
    tpl = (TRANSLATE_DIR / "prompts" / "translate_enrich.md").read_text(encoding="utf-8")
    fewshot_path = TRANSLATE_DIR / "prompts" / "voice_fewshot.md"
    fewshot = (
        fewshot_path.read_text(encoding="utf-8")
        if fewshot_path.is_file()
        else ""
    )
    bundle = compile_rule_bundle(recalled, phase="draft_enrich")
    return f"""【historiography-translate Phase2】
史略ID: {entry_id}
产出路径: {output_file}

【任务卡 · 只两件事 · 置顶】
1) 锚点补全：plan 已采用他书/索引异说 → 写入正文并出现对应《书·卷》
2) 改表达：把下面 Phase1 母本**重写**成《明朝那些事儿》说书人口语（短句、场面、人物口气、自然反差）
几乎原样誊抄母本 = 失败。通顺书面语 ≠ 说书。

{fewshot}

--- Phase1 母本顺译 = **素材**（须重写表达；信息点保留；仅在锚点补他书）---
{mother_text}
---

--- recalled（仅 must_translate 可写入译文；context_* 勿写入）---
{recalled_json}
---

--- source_plan ---
{source_plan_json}
---

--- 规则切片（约束；与任务卡冲突时：说书改表达优先，但史实/专名/数字守恒）---
{bundle}
---

--- 执行细则 ---
{tpl}
---
"""


def build_translate_polish_prompt(
    entry_id: str,
    mother_text: str,
    output_file: Path,
    *,
    source_original: str = "",
    chapter_no: int = 0,
    total_chapters: int = 0,
    voice_sample: str = "",
    include_intro: bool = True,
    include_epilogue: bool = False,
    intro_material: dict | None = None,
) -> str:
    """Phase2 说书润色：不注 plan/recalled；可整篇或分章切片（同一套规则）。"""
    tpl = (TRANSLATE_DIR / "prompts" / "translate_polish.md").read_text(encoding="utf-8")
    fewshot_path = TRANSLATE_DIR / "prompts" / "voice_fewshot.md"
    fewshot = ""
    if fewshot_path.is_file():
        # 只取金标前段，避免把旧长提示整块塞回
        raw = fewshot_path.read_text(encoding="utf-8").strip()
        fewshot = raw[:1200] + ("…" if len(raw) > 1200 else "")
    from lib.annotation_ledger import format_annotation_ledger
    from lib.quality_constitution import constitution_snip
    from lib.structure_ledger import format_structure_ledger

    structure = format_structure_ledger(mother_text, source_original)
    annotation = format_annotation_ledger(mother_text)
    constitution = constitution_snip(phase="polish")
    chaptered = chapter_no > 0 and total_chapters > 0
    mode_title = (
        f"分章润色 第 {chapter_no}/{total_chapters} 章"
        if chaptered
        else "整篇润色"
    )
    scope_note = (
        "本章只润本章母本切片；接上章声口，勿复述上章情节；章末勿提前写后章。"
        if chaptered
        else "整篇理解上下文，但须按结构账本 S001→S…推进；不要拆章、不要按外部补全清单打卡。"
    )
    if include_intro:
        mat_lines = []
        if isinstance(intro_material, dict) and intro_material:
            for k, v in intro_material.items():
                if str(v).strip():
                    mat_lines.append(f"- {k}：{v}")
        mat_block = ("\n".join(mat_lines) + "\n") if mat_lines else ""
        intro_note = (
            "【前置引入 · 硬】文首先写**独立成段**的宏观引入（约 100–250 字），"
            "段后空一行，再进入母本开篇顺叙。\n"
            "引入只写：是谁、为何重要、一生主线一句；"
            "❌ 勿写封王/立太子/出生异兆等起传细节；"
            "❌ 勿先「登基那年新气象」再补身世；"
            "❌ 看官套话与「本篇以…为主线」加工说明。\n"
            + (f"【前置引入素材】\n{mat_block}" if mat_block else "")
        )
    else:
        intro_note = "本章非开篇：禁止重写全书开场白/前置引入。"
    if include_epilogue or (not chaptered):
        epilogue_note = (
            "【篇末收束 · 硬】母本身后事写完后**另起一段**人物总结（约 80–220 字），"
            "点明历史位置与一生主线；再接参考著作。勿母本写完就停。"
        )
    else:
        epilogue_note = ""
    voice_block = ""
    if voice_sample.strip():
        voice_block = (
            "\n--- 上章声口样例（只接口气，禁止复述其中情节）---\n"
            f"{voice_sample.strip()}\n---\n"
        )
    return f"""【historiography-translate Phase2 · {mode_title}】
史略ID: {entry_id}
产出路径: {output_file}

【任务卡 · 置顶 · 两件事不可偏废】
1) **改表达（硬）**：把 Phase1 母本**重写**成第三人称现代历史叙事（短句、场面、人物口气）。几乎原样誊抄母本 = 失败。通顺书面语 ≠ 合格叙事。过门禁≠可贴母本。
2) **八大守恒（硬）**：守恒的是事件/顺序/主体/因果/时间/范围/认知/来源，**不是**保留母本原句。可换说法，不可整段删情节、不可概括顶替多段、不可重排 S 序。
3) **说书加厚（硬）**：成稿须明显高于母本篇幅（讲解/场面/异说），禁止注水重复；偏薄或近誊抄均失败。
4) **成文洁净（硬）**：**作者隐身**。禁止「诸位看官/听客/上回下回/今儿个」；禁止「本篇以…为主线/以母本为准」等加工说明；禁止「这位爷/他娘」市井称谓。自然感来自句法与叙事，不来自俚语喊话。
5) **有头有尾（硬）**：开篇宏观前置引入 + 篇末人物收束；缺一不可（分章时仅首章写引入、末章写收束）。

角色：你是「时络历史」历史叙事撰稿编辑；L1 完整后按需做 L3/L4（须挂 S 锚点）；须列参考著作；不限定单一文明。

{scope_note}
{intro_note}
{epilogue_note}
体量目标是「可读讲解密度」而非注水：禁止整段删情节或概括顶替；**凡年号年/帝纪年须逐一并注公历**；标注账本中的表内地名首次须标（今…）；有母本外补充时文末必须列出「参考著作」。

--- 质量宪法（须遵守）---
{constitution}
---

{tpl}
{voice_block}
--- 结构账本（程序会检漏段；顺序须遵守）---
{structure}
---

--- 标注账本（程序会硬检地名/纪年）---
{annotation}
---

--- 声口参考（节选）---
{fewshot or "（无）"}
---

--- Phase1 母本顺译（须重写表达，保留信息与结构顺序）---
{mother_text}
---
"""

def build_translate_polish_backfill_prompt(
    entry_id: str,
    mother_text: str,
    current_detail: str,
    output_file: Path,
    retry_note: str,
) -> str:
    """Phase2 漏段补洞：在成稿夹缝局部补情节，禁止整篇重写，禁止程序硬塞原文。"""
    return f"""【historiography-translate Phase2 · 漏段补回（禁止整篇重写）】
史略ID: {entry_id}
产出路径: {output_file}

上轮润色删掉了连续母本情节。程序**没有**往正文里塞母本原文，只标出「应插在哪两段之间」。
你的任务：
1. 只在标明的夹缝补回情节，改成与前后文一致的说书口吻；
2. 若附近已有一句概括顶替（把多段情节压成一句），删掉或改写该概括，禁止详写+概括双写；
3. 输出**完整**翻译详情（含参考著作）；夹缝外前后文尽量原样保留。

{retry_note}

--- 当前成稿（勿整篇重写；只在夹缝补情节）---
{current_detail}
---

--- Phase1 母本顺译（对照用，勿当誊抄稿整篇重写）---
{mother_text}
---
"""


def build_source_plan_prompt(
    entry_id: str,
    recalled: dict,
    recalled_json: str,
    plan_file: Path,
    *,
    retry_feedback: str = "",
) -> str:
    mother_sents = extract_mother_sentences(recalled)
    from lib.longform_compat import is_longform, plan_longform_hint

    longform = is_longform(m_count=len(mother_sents))
    tpl_name = "source_plan_longform.md" if longform else "source_plan.md"
    tpl = (TRANSLATE_DIR / "prompts" / tpl_name).read_text(encoding="utf-8")
    bundle = compile_rule_bundle(recalled, phase="plan")
    min_items = max(1, int(len(mother_sents) * plan_min_sentence_ratio()))
    baseline = "\n".join(
        f"  - M{i:03d} | {s['段落']} | {s['原文摘句'][:80]}"
        for i, s in enumerate(mother_sents[:12], start=1)
    )
    if len(mother_sents) > 12:
        baseline += (
            f"\n  …共 {len(mother_sents)} 句（清单由编排器程序生成，禁止输出整表）"
            if longform
            else f"\n  …共 {len(mother_sents)} 句，须全部列入清单"
        )
    long_hint = plan_longform_hint(len(mother_sents))
    decision_mode = ""
    if longform:
        decision_mode = (
            "\n【输出模式 · 长文决策 JSON · 最高优先级】\n"
            "只输出：`史略ID` `史略名称` `母本著作` `外部补全` `索引补充处理` "
            "`写作结构` `参考著作` `风险提示`。\n"
            "**禁止**输出 `母本逐句清单`。\n"
            "`外部补全` 必须为非空数组；写不出 true 也须留候选。\n"
            "`参考著作` 硬上限 ≤10，只交最重要书目。\n"
            "编排器会把决策合并到已生成的母本清单上。\n"
        )
    feedback_block = ""
    if (retry_feedback or "").strip():
        feedback_block = (
            "\n--- 上次 plan 未通过（须逐项修正）---\n"
            f"{retry_feedback.strip()}\n"
            "---\n"
        )
    # 长文 plan 用压缩召回：只保留卷名与段落头尾，避免灌全文挤掉外部补全输出
    recalled_block = recalled_json
    if longform:
        from lib.fingerprint import recalled_summary_for_plan

        recalled_block = recalled_summary_for_plan(recalled)
    return f"""【historiography-translate source-plan job】
史略ID: {entry_id}
计划路径: {plan_file}
母本分句数: {len(mother_sents)}（{'长文：清单已生成，你勿整表' if longform else f'清单至少 {min_items} 条'}）
{long_hint}{decision_mode}{feedback_block}
--- 母本分句基准（前12句示例）---
{baseline}
---

--- 规则（翻译规则.md 节选，唯一 SSOT）---
{bundle}
---

--- recalled ---
{recalled_block}
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
