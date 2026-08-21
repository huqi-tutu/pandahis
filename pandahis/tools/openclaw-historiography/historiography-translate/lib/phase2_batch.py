"""Phase2 分批补全：长母本单次输出超限时分批 enrich 再合并。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from lib.openclaw import build_translate_enrich_prompt
from lib.plan_postprocess import plan_for_enrich_phase
from lib.recalled_window import (
    batch_window_guard_note,
    build_batch_recalled_payload,
)


def phase2_batch_char_threshold() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE2_BATCH_CHARS", "10000")))


def phase2_mode() -> str:
    """Phase2 长文模式。

    - chapter（默认）：合并若干 Phase1 批为「章」，以上章声口样例续写（保文风连贯）
    - legacy_batch：旧路径——按 Phase1 批逐批独立 enrich（易碎、易双写、声口不齐）
    """
    raw = (os.environ.get("TRANSLATE_PHASE2_MODE") or "chapter").strip().lower()
    if raw in {"legacy", "legacy_batch", "batch"}:
        return "legacy_batch"
    return "chapter"


def phase2_chapter_batch_count() -> int:
    """一章包含多少个 Phase1 母本批（默认 4 → ~72 句/章）。"""
    return max(1, int(os.environ.get("TRANSLATE_PHASE2_CHAPTER_BATCHES", "4")))


def phase2_voice_sample_chars() -> int:
    """注入下一章的上章声口样例字数（去情节后宜短）。"""
    return max(60, int(os.environ.get("TRANSLATE_PHASE2_VOICE_CHARS", "140")))


def discover_mother_batches(mother_file: Path) -> List[Path]:
    """仅返回 Phase1 母本分批文件（排除 *.enrich.json）。"""
    pattern = f"{mother_file.stem}-b*{mother_file.suffix}"
    rx = re.compile(
        rf"^{re.escape(mother_file.stem)}-b\d+{re.escape(mother_file.suffix)}$"
    )
    return sorted(p for p in mother_file.parent.glob(pattern) if rx.match(p.name))


def group_batches_into_chapters(
    batch_files: List[Path], *, chapter_batches: int | None = None
) -> List[List[Path]]:
    """把 Phase1 批文件收成更少的「章」，供 Phase2 声口连贯润色。"""
    n = chapter_batches if chapter_batches is not None else phase2_chapter_batch_count()
    n = max(1, n)
    if not batch_files:
        return []
    return [batch_files[i : i + n] for i in range(0, len(batch_files), n)]


_VOICE_PLOT_NOISE = re.compile(
    r"《[^》]{1,40}》"
    r"|[「“][^」”]{0,100}[」”]"
    r"|（今[^）]{1,24}）"
    r"|公元前\d{2,4}年"
    r"|\d{2,4}年"
)


def scrub_voice_sample_for_style(text: str) -> str:
    """去掉书名/引文/今地/年份等情节锚点，只留口气碎片。"""
    s = _VOICE_PLOT_NOISE.sub("…", str(text or ""))
    s = re.sub(r"…{2,}", "…", s)
    s = re.sub(r"\s+", "", s)
    # 过密专名链（连续顿号枚举）压成省略
    s = re.sub(r"(?:[\u4e00-\u9fff]{2,4}、){2,}[\u4e00-\u9fff]{2,4}", "…", s)
    return s.strip("…").strip()


def extract_voice_sample(detail: str, *, max_chars: int | None = None) -> str:
    """取上章末尾口气碎片（去情节），供下章接声口——不是情节摘要。

    故意不给完整叙事段：完整段会诱发下章换说法复述（章界双写）。
    """
    body = str(detail or "").strip()
    if "\n\n参考著作" in body:
        body = body.split("\n\n参考著作", 1)[0].rstrip()
    elif body.rstrip().endswith("参考著作"):
        body = re.sub(r"\n*参考著作\s*$", "", body).rstrip()
    if not body:
        return ""
    limit = max_chars if max_chars is not None else phase2_voice_sample_chars()
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    last = paras[-1] if paras else body
    sents = re.findall(r"[^。！？]+[。！？]", last)
    if not sents:
        chunk = last[-min(limit + 40, len(last)) :]
    elif len(sents[-1]) < 36 and len(sents) >= 2:
        chunk = "".join(sents[-2:])
    else:
        chunk = sents[-1]
    scrubbed = scrub_voice_sample_for_style(chunk)
    if len(scrubbed) > limit:
        scrubbed = scrubbed[-limit:]
    # 剥太狠时回退：仍截断原末句，但不给整段
    if len(scrubbed) < 24:
        raw = (sents[-1] if sents else last)[-limit:]
        scrubbed = scrub_voice_sample_for_style(raw) or raw[-min(80, len(raw)) :]
    return scrubbed.strip()


def _mother_batch_size() -> int:
    return max(0, int(os.environ.get("TRANSLATE_MOTHER_BATCH", "18")))


def _load_mother_text_from_file(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if isinstance(data, dict):
        for key in ("母本顺译", "翻译详情"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return raw.strip()


def concatenate_mother_batch_texts(batch_files: Sequence[Path]) -> str:
    parts = [_load_mother_text_from_file(p) for p in batch_files]
    return "\n\n".join(p for p in parts if p)


def _m_numbers_from_text(text: str) -> set[int]:
    return {int(m) for m in re.findall(r"M(\d+)", str(text))}


def _anchor_in_batch(anchor: str, batch_nums: set[int]) -> bool:
    nums = _m_numbers_from_text(anchor)
    if not nums:
        return False
    return bool(nums & batch_nums)


def plan_for_enrich_batch(plan_data: Dict[str, Any], batch_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """本批 M 清单 + 锚点落在本批的外部补全/索引补充。"""
    batch_nums = _m_numbers_from_text(
        " ".join(str(x.get("编号") or "") for x in batch_items)
    )
    base = plan_for_enrich_phase(plan_data)
    ext = [
        x
        for x in base.get("外部补全") or []
        if isinstance(x, dict)
        and _anchor_in_batch(str(x.get("母本锚点") or ""), batch_nums)
    ]
    idx = [
        x
        for x in base.get("索引补充处理") or []
        if isinstance(x, dict)
        and _anchor_in_batch(str(x.get("锚点") or x.get("母本锚点") or ""), batch_nums)
    ]
    return {
        **base,
        "母本逐句清单": batch_items,
        "外部补全": ext,
        "索引补充处理": idx,
    }


def batch_checklist_items(plan_data: Dict[str, Any], batch_index: int) -> List[Dict[str, Any]]:
    checklist = plan_data.get("母本逐句清单") or []
    if not isinstance(checklist, list):
        return []
    size = _mother_batch_size()
    if size <= 0:
        return []
    start = (batch_index - 1) * size
    return checklist[start : start + size]


def batch_mode_note(*, batch_no: int, total: int, include_intro: bool) -> str:
    from lib.longform_compat import enrich_batch_guard_extra

    lines = [
        "",
        "---",
        f"【分批补全模式】第 {batch_no}/{total} 批",
    ]
    if include_intro:
        lines.append(
            "【前置引入 · 硬】文首先写**独立成段**的宏观引入（约 **100–250 字**），"
            "段后空一行，再写本批母本正文。\n"
            "引入只写：是谁、为何重要、一生主线一句（人物名片，不是开场白）。\n"
            "❌ 禁止「今天要讲」「诸位看官」「本篇以…为主线」；"
            "❌ 禁止把封王/立太子/出生异兆写进首段；"
            "❌ 禁止先「登基那年新气象」再补身世。\n"
            "可用 plan「前置引入素材」。合格：`汉武帝刘彻，孝景帝之子……`；"
            "失败：气氛钩子+起传粘连一大段。"
        )
    else:
        lines.append(
            "【批首禁重开】若本批开头情节上批末尾已写过，禁止换说法再讲一遍"
            "（如「韩信受命东进 / 平原津 / 烹郦」）；只续写本批新信息点。"
        )
    lines.append(
        "输出 JSON 的「翻译详情」仅含本批正文（已穿插本批相关他书补全），"
        "勿写参考著作节；程序合并各批后统一添加。"
    )
    lines.append(
        enrich_batch_guard_extra(batch_no=batch_no, total=total).rstrip()
    )
    return "\n".join(lines) + "\n"


def classic_quote_must_embed_note(items: Sequence[Dict[str, Any]]) -> str:
    """把本章/本批经典引用候选的原文摘句顶出来，避免模型只见白话母本却漏「」。"""
    cands = [
        it
        for it in items
        if isinstance(it, dict) and it.get("经典引用候选") is True
    ]
    if not cands:
        return ""
    lines = [
        "",
        "---",
        f"【经典「」硬落地 · 本章/本批共 {len(cands)} 条】",
        "下列句**必须**在正文用直角「」镶嵌史料原文（可摘金句片段，勿整段堆砌）；",
        "用「」后优先白话接叙融合，勿默认同义破折号作业体。漏一处 → 质检失败。",
    ]
    for it in cands:
        mid = str(it.get("编号") or "?").strip()
        excerpt = str(it.get("原文摘句") or "").strip()
        if len(excerpt) > 120:
            excerpt = excerpt[:120] + "…"
        lines.append(f"- {mid} 须镶嵌：「{excerpt}」")
    return "\n".join(lines) + "\n"


def chapter_mode_note(
    *,
    chapter_no: int,
    total_chapters: int,
    batch_nos: Sequence[int],
    include_intro: bool,
    voice_sample: str = "",
) -> str:
    """分章 + 声口续写约束（Phase2 默认长文路径）。"""
    span = "、".join(f"b{n:02d}" for n in batch_nos)
    lines = [
        "",
        "---",
        f"【分章叙事模式】第 {chapter_no}/{total_chapters} 章"
        f"（覆盖 Phase1 母本批：{span}）",
        "目标：本段读起来像**同一篇**第三人称现代历史叙事的连续章节"
        "（节奏/场面可读，但**作者不出场**）。"
        "本章两职能都要做完：①锚点他书补全（见「本章须落地」清单，先补完）；"
        "②**必须改表达**——"
        "把本章 Phase1 直译腔重写成现代叙事；"
        "程序会比对与母本重合度，几乎誊抄 → 质检失败重试。"
        "补全漏条时优先定向补洞，勿指望整章重写蒙混。"
        "输出「翻译详情」仅含本章正文；勿写参考著作节（程序合并追加）。"
        "【成文洁净 · 硬】禁止「诸位看官/听客/上回讲到/下回再说」；"
        "禁止「本篇以…为主线」等加工说明；禁止「这位爷/他娘」；"
        "禁止输出「编辑已就位/结构账本/Phase2」等提示词残骸。",
    ]
    if include_intro:
        lines.append(
            "【前置引入 · 硬】文首先写**独立成段**的宏观引入（约 **100–250 字**），"
            "段后空一行，再写开篇正文。\n"
            "引入只写：是谁、为何重要、一生主线一句；"
            "❌ 勿写封王/立太子等起传细节；❌ 勿先登基气氛再补身世；"
            "❌ 禁止「今天要讲」「诸位看官」「本篇以《…》为主线」。\n"
            "合格：人物名片式宏观概括；失败：开场白/加工备注/与起传粘连。"
        )
    if chapter_no == total_chapters:
        lines.append(
            "【篇末收束 · 硬】本章是末章。母本身后事（崩葬/即位/子嗣等）写完后，"
            "**必须另起一段**做全文收束总结（约 80–220 字）：点明此人历史位置与一生主线，"
            "有收科感；不要母本写完就停。收束后再结束（勿写参考著作节）。"
        )
    if voice_sample.strip():
        lines.append(
            "【声口样例 · 口气碎片（硬）】下面**不是**上章情节摘要，"
            "只是程序剥过情节后的口气碎片（可能半截、有省略号）。"
            "请只学句式长短、口语浓度、引「」习惯；"
            "**禁止**根据样例回忆/复述上章故事（含换说法）。\n"
            "【章首对齐 · 硬】**情节必须从本章母本第一段写起**，"
            "不得先写「各位听客/接着上回/上回讲到」等接场套话，"
            "不得先写一段「承接上文」的复述桥，再进入本章。\n"
            "<<<VOICE_SAMPLE\n"
            f"{voice_sample.strip()}\n"
            "VOICE_SAMPLE>>>"
        )
    else:
        lines.append(
            "【开篇声口】本章起调即定全文声口：第三人称现代历史叙事，"
            "允许自然节奏与经典句「」；不要写成编年条或对照译；"
            "开篇禁止「今天要讲/诸位看官/本篇以」类场次或加工元叙述。"
        )
    lines.append(
        "【章界纪律】只写本章母本对应情节；禁止重开全传；"
        "禁止复述上章已写事件（含换说法复述）；"
        "禁止把下章情节提前写成短版预告。"
    )
    lines.append(
        "【改表达守恒 · 硬】专名/数字/官职/地名/年号/人数/胜负因果以本章母本为准；"
        "只许改说法，不许改事实；史料已有言语可改口语口气，禁止新编无据对白/心理；"
        "Phase1 信息点不可整段蒸发。"
    )
    lines.append(
        "【文风硬约束】禁止滥用「说白了」等无意义过场词；"
        "生僻字词/古语/古怪处须释义旁白（≤200字、事实白描、自然融入）；"
        "著名典故/成语情节写完后须点名对上号（先叙后点）；"
        "崩/薨/卒/是为等 L0 词禁止旁白过度解释；"
        "原文露出克制（「」仅金句等），"
        "用「」后优先融入接叙，反对句句同义 `「…」——…` 作业体（偶发增量破折号可用）；"
        "史料用「」，白话对话用 “”；未译原话禁止弯引；有名言/候选则「」镶嵌，无则勿硬凑；"
        "输出纯正文，禁止嵌套 JSON / 代码围栏。"
    )
    return "\n".join(lines) + "\n"


def append_reference_section(detail: str, plan_data: Dict[str, Any], recalled: Dict[str, Any]) -> str:
    """文末参考著作：优先按正文实际《》引用重建，避免 plan 占位（如·相关卷）。"""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from shared.reference_works import (
        format_reference_section,
        merge_reference_works,
        strip_reference_section,
    )

    body = strip_reference_section(detail).rstrip()
    refs = merge_reference_works(recalled, body, plan_data)
    # 丢掉不合规占位，并规范化 01史记
    cleaned: List[str] = []
    for r in refs:
        s = str(r).strip()
        if not s or "相关卷" in s:
            continue
        if s in ("01史记", "《01史记》") or re.fullmatch(r"《?0?\d*史记》?", s):
            s = "《史记》"
        if not s.startswith("《"):
            s = f"《{s.strip('《》')}》"
        if s not in cleaned:
            cleaned.append(s)
    # 不以 plan 采用项强行补书目（正文未引则不进列表，避免「书目齐了=补全生效」假象）
    if not cleaned:
        mother_work = str(recalled.get("母本著作") or plan_data.get("母本著作") or "").strip()
        if mother_work:
            cleaned = [
                mother_work if mother_work.startswith("《") else f"《{mother_work}》"
            ]
    if not cleaned:
        return body
    from lib.plan_postprocess import MAX_REFERENCE_WORKS, clamp_reference_works

    if len(cleaned) > MAX_REFERENCE_WORKS:
        print(
            f"   📎 成稿参考著作截断 {len(cleaned)} → {MAX_REFERENCE_WORKS}",
            flush=True,
        )
    cleaned = clamp_reference_works(cleaned)
    section = format_reference_section(cleaned)
    return f"{body}\n\n{section}"


def merge_enrich_batches(
    entry_id: str,
    parts: List[str],
    plan_data: Dict[str, Any],
    recalled: Dict[str, Any],
) -> str:
    """分章/分批 Phase2 正文按序拼接（含释义双写静默 heal），再挂参考著作。

    各章若自带「参考著作」，须先剥掉再拼接；否则 strip_reference_section
    会把第一章参考著作之后的后续章正文整段扔掉。
    """
    from lib.longform_compat import join_narrative_parts

    del entry_id
    try:
        from shared.reference_works import strip_reference_section
    except ImportError:
        strip_reference_section = lambda t: t  # type: ignore

    cleaned: List[str] = []
    for p in parts:
        s = str(p or "").strip()
        if not s:
            continue
        cleaned.append(strip_reference_section(s).rstrip())
    body = join_narrative_parts(cleaned)
    return append_reference_section(body, plan_data, recalled)


def build_batch_enrich_prompt(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_data: Dict[str, Any],
    mother_text: str,
    output_file: Path,
    *,
    batch_no: int,
    total_batches: int,
    include_intro: bool,
) -> str:
    batch_items = batch_checklist_items(plan_data, batch_no)
    batch_plan = plan_for_enrich_batch(plan_data, batch_items)
    window_payload = build_batch_recalled_payload(recalled, batch_items)
    from lib.enrich_landing import format_landing_checklist_note

    prompt = build_translate_enrich_prompt(
        entry_id,
        recalled,
        json.dumps(window_payload, ensure_ascii=False, indent=2),
        json.dumps(batch_plan, ensure_ascii=False, indent=2),
        mother_text,
        output_file,
    )
    return (
        prompt
        + batch_mode_note(
            batch_no=batch_no,
            total=total_batches,
            include_intro=include_intro,
        )
        + format_landing_checklist_note(batch_plan)
        + classic_quote_must_embed_note(batch_items)
        + batch_window_guard_note(window_payload)
    )


def build_chapter_enrich_prompt(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_data: Dict[str, Any],
    mother_text: str,
    output_file: Path,
    *,
    chapter_no: int,
    total_chapters: int,
    batch_nos: Sequence[int],
    include_intro: bool,
    voice_sample: str = "",
) -> str:
    """分章 enrich：多批 M 合并 + 上章声口样例。"""
    items: List[Dict[str, Any]] = []
    for bi in batch_nos:
        items.extend(batch_checklist_items(plan_data, bi))
    chapter_plan = plan_for_enrich_batch(plan_data, items)
    window_payload = build_batch_recalled_payload(recalled, items)
    prompt = build_translate_enrich_prompt(
        entry_id,
        recalled,
        json.dumps(window_payload, ensure_ascii=False, indent=2),
        json.dumps(chapter_plan, ensure_ascii=False, indent=2),
        mother_text,
        output_file,
    )
    from lib.enrich_landing import format_landing_checklist_note

    return (
        prompt
        + chapter_mode_note(
            chapter_no=chapter_no,
            total_chapters=total_chapters,
            batch_nos=batch_nos,
            include_intro=include_intro,
            voice_sample=voice_sample,
        )
        + format_landing_checklist_note(chapter_plan)
        + classic_quote_must_embed_note(items)
        + batch_window_guard_note(window_payload)
    )


def style_density_warnings(detail: str, *, min_corner_quotes: int = 3) -> List[str]:
    """成稿文风密度软警告（不阻断）：史料「」过少等。"""
    body = str(detail or "")
    warns: List[str] = []
    if len(body) < 2000:
        return warns
    q = body.count("「")
    if q < min_corner_quotes:
        warns.append(
            f"文风软警告：史料直角「」仅 {q} 处（长文建议 ≥{min_corner_quotes}），"
            "说书穿插原文可能不足"
        )
    # 极干信号：几乎无口语节奏词且无「」
    oral = sum(
        body.count(m)
        for m in ("却说", "谁料", "哪知", "偏偏", "倒是", "这一", "你道")
    )
    if q == 0 and oral == 0 and len(body) >= 8000:
        warns.append(
            "文风软警告：全文几乎无「」也无说书节奏词，疑似编年对照体"
        )
    return warns
