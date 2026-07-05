"""LLM 调用与编排 prompt 组装。"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.config import PROVIDER_DEEPSEEK, get_provider_name  # noqa: E402
from llm.openclaw_provider import default_state_dir, resolve_agent_id  # noqa: E402
from llm.provider import run_agent_turn as _run_agent_turn  # noqa: E402

from lib.config import ORCH_DIR, paths  # noqa: E402
from lib.work_text_structure import work_text_structure_hint  # noqa: E402

# (著作, 卷号) → Step4 卷级史学提醒（防 LLM 用卒年/归附误判主轴）
VOLUME_STEP4_HINTS: dict[tuple[str, str], str] = {
    ("02汉书", "042"): (
        "【卷042 张耳陈馀传 — 四级帝王考订】\n"
        "张耳、陈馀：四级帝王坐标统一取 **汉高祖**（标准名，禁止写汉高帝）。\n"
        "张耳本传终局为归汉封赵王；陈馀败亡于汉军。须在 `_auto_filled._坐标主轴说明` "
        "据本传仕宦/封爵/终局史实说明为何取汉高祖。"
    ),
}


def orch_resolve_agent_id(preferred: str = "hist-worker") -> str:
    return resolve_agent_id(
        preferred,
        env_key="HIST_OPENCLAW_AGENT",
        forbid_main_message=(
            "禁止编排器回调 main agent（会与飞书对话死锁）。"
            "请在 catalog 使用 hist-worker，或设置 HIST_OPENCLAW_AGENT=hist-worker；"
            "也可改用 HIST_LLM_PROVIDER=deepseek。"
        ),
    )


def make_session_id(work: str, vol: str, step: str, job_id: int) -> str:
    slug = "".join(c for c in work if c.isascii() and (c.isalnum() or c in "-_"))
    if not slug:
        slug = uuid.uuid4().hex[:8]
    nonce = uuid.uuid4().hex[:8]
    return f"hist-{slug}-{vol}-s{step}-{job_id}-{nonce}"


def expected_skeleton_path(work: str, vol: str, index: dict) -> Path:
    vol = vol.zfill(3)
    source_file = str(index.get("source_file") or "")
    if source_file.endswith(".txt"):
        stem = source_file[:-4]
    elif source_file:
        stem = source_file
    else:
        stem = f"{work}_{vol}"
    return paths()["annotations"] / f"{stem}_skeleton.json"


def audit_markdown_path(work: str) -> Path:
    return paths()["audit"] / f"{work}_标注审计.md"


def build_protagonist_prompt(work: str, vol: str, index: dict) -> str:
    """Step1a：著作+卷名+常识 → protagonists.json（先于 blocks/skeleton）。"""
    from lib.config import get_work_config
    from lib.blocks_workflow import volume_display_name
    from lib.protagonist_workflow import protagonists_path

    prompts_dir = ORCH_DIR / "prompts"
    tpl_path = prompts_dir / "step1_protagonists.md"
    extra = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else ""
    vol_name = volume_display_name(work, vol, index)
    provider = get_provider_name()
    cfg = get_work_config(work)
    work_title = cfg.get("title", work)
    sys.path.insert(0, str(ROOT / "historiography-annotate"))
    from identity_gate import identity_hint_for_protagonist_prompt  # noqa: E402

    id_hint = identity_hint_for_protagonist_prompt(
        work, vol, vol_name, work_title=work_title
    )
    struct_hint = work_text_structure_hint(work)
    out_path = protagonists_path(work, vol)
    base = f"""【historiography-orchestrator · Step1a 主轴人物理解】
著作: {work}（{work_title}）  卷: {vol}
卷名: {vol_name}
段落数: {index['total']}（本步**不必**读段落正文，只据卷名+常识）
LLM provider: {provider}

protagonists 产出路径: {out_path}
须将 **protagonists JSON** 写入上述路径（DeepSeek 模式下在回复中给出**单个** ```json 代码块）。
禁止输出 blocks / skeleton / segment_attribution。

{struct_hint}

{id_hint}

"""
    return base + extra


def build_step_prompt(
    work: str,
    vol: str,
    step: str,
    index: dict,
    volume_name: str = "",
    *,
    use_blocks: bool = False,
) -> str:
    prompts_dir = ORCH_DIR / "prompts"
    if step == "1" and use_blocks:
        tpl_path = prompts_dir / "step1_blocks.md"
    else:
        tpl_path = prompts_dir / f"step{step}.md"
    extra = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else ""
    total = index["total"]
    src = index.get("source_path", "")
    provider = get_provider_name()

    struct_hint = work_text_structure_hint(work)
    base = f"""【historiography-orchestrator job】
著作: {work}  卷: {vol}  步: Step{step}
卷名: {volume_name or '(见索引)'}
段落数: {total}（来自段落索引，禁止自猜、禁止 2 段模板）
原文: {src}
段落索引 SSOT: data/03索引标注条目/段落索引/{work}_{vol}.json（Step1/3 须按段阅读原文 text 字段）
LLM provider: {provider}

{struct_hint}

硬性要求:
- 只处理本卷；完成后不要标下一卷
- 块优先标注（人物清单→叙事块→边界精判→展开 segment_attribution）；按人物标注规则提取，禁止仅扫人名；合传须复核块边界
- 禁止自创批量脚本；禁止 mark --force
- 由 orchestrator 跑 verify
- **禁止**未落盘就回复「已完成」；文件不存在则必须重新写入

"""
    if step == "1" and use_blocks:
        from lib.blocks_workflow import blocks_path, volume_display_name

        blocks_out = blocks_path(work, vol)
        skeleton_out = expected_skeleton_path(work, vol, index)
        vol_name = volume_display_name(work, vol, index)
        sys.path.insert(0, str(ROOT / "historiography-annotate"))
        from identity_gate import identity_hint_for_prompt  # noqa: E402

        id_hint = identity_hint_for_prompt(work, vol, vol_name)
        manifest_block = ""
        from lib.protagonist_workflow import format_manifest_for_prompt, load_protagonists

        manifest = load_protagonists(work, vol)
        if manifest:
            manifest_block = format_manifest_for_prompt(manifest) + "\n\n"
        base += (
            f"⚠️ blocks 模式：禁止输出完整 skeleton（由 expand_blocks 展开）。\n"
            f"blocks 产出路径: {blocks_out}\n"
            f"（脚本将展开为 skeleton: {skeleton_out}）\n"
            "须将 **blocks 草稿 JSON** 写入 blocks 路径（DeepSeek 模式下在回复中给出**单个** ```json 代码块）。\n"
            "必填：total_paragraphs, blocks[]；可选 excludes[]。\n\n"
            f"{manifest_block}"
            f"{id_hint}\n\n"
        )
    elif step == "1":
        skeleton_out = expected_skeleton_path(work, vol, index)
        sys.path.insert(0, str(ROOT / "historiography-annotate"))
        from identity_gate import identity_hint_for_prompt  # noqa: E402
        from lib.blocks_workflow import entry_id_prefix, volume_display_name

        vol_name = volume_display_name(work, vol, index)
        id_hint = identity_hint_for_prompt(work, vol, vol_name)
        manifest_block = ""
        from lib.protagonist_workflow import format_manifest_for_prompt, load_protagonists

        manifest = load_protagonists(work, vol)
        if manifest:
            manifest_block = format_manifest_for_prompt(manifest) + "\n\n"
        eid_prefix = entry_id_prefix(work)
        vol_z = vol.zfill(3)
        base += (
            f"skeleton 产出路径: {skeleton_out}\n"
            "须将**完整** skeleton JSON 写入上述路径（DeepSeek 模式下在回复中给出**单个** ```json 代码块）。\n\n"
            "**禁止**自创字段：`attribution`、`entry_index`、`from`/`to`、entries 内嵌段落 `text`。\n"
            "segment_attribution 每行须为 `owners[]` 或 `exclude_reason`；entries.paragraphs 须为 "
            "`paragraph_from`/`paragraph_to`。\n\n"
            f"示例 entry 字段：史略ID={eid_prefix}_{vol_z}_01, 史略名称=帝王表标准名, "
            "史略分类=君王|士臣|庶众|宗戚, 原文字句=开篇段逐字摘录≥12字\n\n"
            f"{manifest_block}"
            f"{id_hint}\n\n"
        )
    elif step == "3":
        base += (
            "Step3 已由编排器脚本从 skeleton 生成审计 MD，本步无需 LLM 输出。\n\n"
        )
    elif step == "4" and provider == PROVIDER_DEEPSEEK:
        skeleton_out = expected_skeleton_path(work, vol, index)
        if skeleton_out.is_file():
            sk_text = skeleton_out.read_text(encoding="utf-8").strip()
            base += (
                f"skeleton 产出路径: {skeleton_out}\n"
                "须将**完整** skeleton JSON 写入上述路径（DeepSeek 模式下在回复中给出**单个** ```json 代码块）。\n"
                "只补/改 entries 内待补正式字段；**原样保留** segment_attribution、entries 结构与已有字段。\n"
                "禁止仅用 Markdown 列表描述字段；禁止未输出 JSON 就回复 STEP4_DONE。\n\n"
                "【当前 skeleton JSON — 在此基础上修改后整份输出】\n"
                f"```json\n{sk_text}\n```\n\n"
            )

    vol_key = vol.zfill(3)
    if step == "4":
        hint = VOLUME_STEP4_HINTS.get((work, vol_key))
        if hint:
            base += f"{hint}\n\n"

    return base + extra


def run_agent_turn(*args, **kwargs):
    kwargs.setdefault("openclaw_env_key", "HIST_OPENCLAW_AGENT")
    kwargs.setdefault("openclaw_local_env_key", "HIST_OPENCLAW_LOCAL")
    kwargs.setdefault(
        "forbid_main_message",
        (
            "禁止编排器回调 main agent（会与飞书对话死锁）。"
            "请在 catalog 使用 hist-worker，或设置 HIST_OPENCLAW_AGENT=hist-worker；"
            "也可改用 HIST_LLM_PROVIDER=deepseek。"
        ),
    )
    return _run_agent_turn(*args, **kwargs)
