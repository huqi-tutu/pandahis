"""长文兼容档位（编排器层）。

不改动翻译规则 SSOT 的目标与原则：语义覆盖、顺译、幽默、口语、
《明朝那些事儿》笔调、经典句原文引用一律保留。

本模块只解决长卷执行压力：Phase1 分批禁越界、外部补全配额、分章拼接。
文风在 Phase1（口语顺译）+ Phase2（分章说书 + 声口样例）落地，无独立润色轮。

分批/分章合并 = **按顺序拼接**，不对正文做情节去重。
真正的去重只在 plan：外部补全 vs 全书母本信息点（`external_dedupe`）。
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Sequence


def longform_m_threshold() -> int:
    """母本 M 条数达到此值视为长文（与 Phase1 长条重试阈值对齐）。"""
    return max(1, int(os.environ.get("TRANSLATE_LONGFORM_M", "40")))


# 标志性史事词组：同组命中 ≥2 即视为同一事件指纹（覆盖释义双写）。
# 注：通用换说法双写主要靠 _is_paraphrase_duplicate；本组是补充保险。
# require_any：必须再命中「场面核心词」，避免后文仅提及专名（如「白帝/赤帝尚红」）
# 把真正的斩蛇正文顶掉。
_EVENT_TOKEN_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "id": "斩蛇",
        "tokens": ("斩蛇", "白帝", "赤帝", "大蛇", "老妪", "老妇", "探路"),
        "require_any": ("斩蛇", "大蛇", "老妪", "老妇", "探路"),
    },
    {
        "id": "鸿门",
        "tokens": ("鸿门", "项伯", "樊哙", "玉斗", "曹无伤"),
        "require_any": ("鸿门", "玉斗", "曹无伤"),
    },
    {
        "id": "约法三章",
        "tokens": ("约法三章", "霸上", "子婴", "函谷关"),
        "require_any": ("约法三章", "子婴"),
    },
    {
        "id": "垓下",
        "tokens": ("垓下", "四面楚歌", "东城", "鲁公"),
        "require_any": ("垓下", "四面楚歌", "东城"),
    },
    {
        "id": "大风歌",
        "tokens": ("大风歌", "沛宫", "汤沐邑", "大风起兮"),
        "require_any": ("大风歌", "大风起兮", "汤沐邑"),
    },
    {
        "id": "未央宫",
        "tokens": ("未央宫", "太上皇", "孰与仲多"),
        "require_any": ("未央宫", "孰与仲多"),
    },
    {
        "id": "纪信",
        "tokens": ("纪信", "荥阳", "东门", "诈为汉王"),
        "require_any": ("纪信", "诈为汉王"),
    },
    {
        "id": "鸿沟",
        "tokens": ("鸿沟", "中分天下", "归太公"),
        "require_any": ("鸿沟", "中分天下"),
    },
    {
        "id": "平原津",
        "tokens": ("平原津", "受命东进", "郦食其", "田广", "蒯通", "龙且"),
        "require_any": ("平原津", "受命东进", "龙且"),
    },
    {
        "id": "塞王",
        "tokens": ("塞王", "司马欣", "董翳", "申阳", "韩王昌"),
        "require_any": ("董翳", "申阳", "韩王昌"),
    },
)


def event_fingerprint(text: str) -> tuple[str, ...] | None:
    """从段落提取事件指纹；同组命中 ≥2 且满足场面核心词则返回规范 ID。"""
    if not text or len(_plain(text)) < 80:
        return None
    best_id: tuple[str, ...] | None = None
    best_n = 0
    for group in _EVENT_TOKEN_GROUPS:
        tokens: tuple[str, ...] = group["tokens"]
        require_any: tuple[str, ...] = group.get("require_any") or ()
        hits = [t for t in tokens if t in text]
        if len(hits) < 2:
            continue
        if require_any and not any(t in text for t in require_any):
            continue
        if len(hits) > best_n:
            best_n = len(hits)
            best_id = ("evt", str(group["id"]))
    return best_id


def find_repeated_event_fingerprints(detail: str) -> list[str]:
    """同一事件指纹出现在 ≥2 个长段 → **仅软警告文案**（不得用于删段/硬失败）。

    史传后文常回指前文专名；指纹只能提示人工抽查，不能当去重依据。
    """
    seen: dict[tuple[str, ...], int] = {}
    repeated: list[str] = []
    for para in str(detail or "").split("\n\n"):
        p = para.strip()
        if len(_plain(p)) < 80:
            continue
        fp = event_fingerprint(p)
        if not fp:
            continue
        seen[fp] = seen.get(fp, 0) + 1
        if seen[fp] == 2:
            label = fp[1] if len(fp) > 1 else str(fp)
            repeated.append(f"{label}（可能回指/双写，请人工抽查）")
    return repeated


def checklist_size(plan: Dict[str, Any] | None) -> int:
    if not plan:
        return 0
    cl = plan.get("母本逐句清单") or []
    return len(cl) if isinstance(cl, list) else 0


def is_longform(plan: Dict[str, Any] | None = None, *, m_count: int | None = None) -> bool:
    n = m_count if m_count is not None else checklist_size(plan)
    return n >= longform_m_threshold()


def external_adopt_quota(m_count: int) -> int:
    """长文外部补全「采用:true」软配额下限（仍须满足准入类型，禁止凑数重复母本）。"""
    if m_count < longform_m_threshold():
        return 0
    # 约每 20 句 1 条，夹在 3–8
    return max(3, min(8, m_count // 20))


def mother_batch_guard_note(*, batch_label: str, m_ids: Sequence[str]) -> str:
    """Phase1 分批硬约束：禁止整传重开 / 复述他批 / 批末越界写完下批事件。"""
    span = "、".join(str(x) for x in m_ids[:6])
    if len(m_ids) > 6:
        span += f"…共{len(m_ids)}条"
    last_m = str(m_ids[-1]) if m_ids else ""
    first_m = str(m_ids[0]) if m_ids else ""
    return (
        f"\n\n--- {batch_label}：长文分批硬约束 ---\n"
        f"1. **只译本批 M**：{span}；句序与原词锚点须保留。\n"
        "2. **禁止整传重开**：不得从传主姓名籍贯或本纪开头重写全文；"
        "不得把上一批/下一批的内容再写一遍。\n"
        "3. **篇幅对标本批**：输出信息量大致对应本批 M，勿写成全传缩写或全传扩写。\n"
        "4. 本批若不以「姓氏字籍」起句，文首勿擅自补传主履历开场白。\n"
        f"5. **批末禁越界**：本批最后一条为 {last_m} 时，写到该句信息点即可；"
        "不得为「把故事写圆」而续写下一批才开始的情节（如斩蛇、鸿门、告归之田等整段后事）。\n"
        f"6. **批首禁重开已写事件**：本批若从 {first_m} 起正接上批未完事件，"
        "只续写本批 M 尚未覆盖的句子；禁止用另一套说法把上批已写过的同一事件再讲一遍。\n"
        "7. **原文窗口**：recalled 为「本批 M 原文摘句」（`must_sentences` / "
        "`must_by_paragraph`）；只译列出的摘句，禁止整段灌译、禁止译未列入的同段邻句。\n"
        "8. **成稿分段**：按叙事场景合段；同段/同事件的多条 M 合写成连贯段落；"
        "**禁止「一条 M → 一个段落」**，也禁止一句一段的对照体。\n"
        "9. **文风**：流畅白话；「」仅金句等，用后优先融入接叙；"
        "反对句句 `「原文」——同义白话`（偶发增量破折号可用）；白话对话用 “”；"
        "禁止滥用「说白了」等无意义过场词；生僻/古怪处须释义旁白（≤200字、事实白描）；"
        "著名典故/成语情节写完后须点名对上号（先叙后点）；"
        "崩/薨/卒/是为等 L0 词禁止旁白拆词；"
        "`母本顺译` 值须为纯正文，禁止嵌套 JSON。\n"
    )


# 保留供诊断/抽查；不再作为 Phase2 软重试过关词表
_ORAL_MARKERS = (
    "偏偏",
    "倒是",
    "搁今天",
    "这就有意思",
)


def batch_is_mid_or_late(*, batch_no: int, total: int) -> bool:
    """第 1/3 批之后视为中后批（文风易塌陷区）。"""
    if total <= 1:
        return False
    return batch_no > max(1, (total + 2) // 3)


def batch_lacks_colloquial(detail: str) -> bool:
    """旧口语密度探测（已不再驱动重试；保留兼容测试）。"""
    text = str(detail or "")
    if len(text) < 80:
        return False
    return sum(text.count(m) for m in _ORAL_MARKERS) < 1


def enrich_batch_guard_extra(*, batch_no: int = 1, total: int = 1) -> str:
    base = (
        "【长文分批硬约束 · Phase2】\n"
        "只在本批母本段上锚点补全；禁止重开全传、禁止复述他批已写段落；"
        "禁止把下批情节提前写成短版（合并后会与下批长版双写）。\n"
        "recalled 窗口：仅处理 `must_translate`；`context_*` 禁止写入翻译详情。\n"
        "本批「翻译详情」不得含参考著作节（程序合并后统一追加）；"
        "值必须是纯正文，禁止再嵌套一层 JSON。\n"
        "【本批文风】写成流畅叙事（《明朝那些事儿》说书人笔调：短句/白描），"
        "原文露出克制：「」仅金句等，用后优先融入；反对句句同义 `「…」——…`；白话用 “”；"
        "诗赋/誓词先概括主旨再「」引文言。\n"
        "禁止滥用「说白了」「这么说很明白」「说实话」等无意义过场词撑场；"
        "释义旁白要自然融入（≤200字、事实白描），勿用过场词代替解释；"
        "著名典故/成语情节写完后须点名对上号（先叙后点）；"
        "允许改写本批表述使可读，禁止改史实或削覆盖锚点。\n"
    )
    if batch_is_mid_or_late(batch_no=batch_no, total=total):
        base += (
            f"【中后批提醒 · 第 {batch_no}/{total} 批】"
            "本批仍须可读，勿塌成干巴巴白描；用短句节奏与场面推进，"
            "**不要**靠插入「说白了」过关。禁止把文风留到后面某批。\n"
        )
    return base


def plan_longform_hint(m_count: int) -> str:
    if not is_longform(m_count=m_count):
        return ""
    q = external_adopt_quota(m_count)
    return (
        f"\n【长文兼容 · plan】本条母本约 {m_count} 句。\n"
        "1. **决策聚焦**：`母本逐句清单` 已由编排器按分句程序生成；"
        "你**不要**输出整表（可省略该字段）。核心产出是 "
        "`外部补全`、`索引补充处理`（可微调）、`写作结构`、`参考著作`、`风险提示`。\n"
        "2. **索引补充 ≠ 外部补全**：\n"
        "   - `索引补充处理`：只裁决 recalled 里已有的 role=补充块（引入/异说/去重），"
        "不得把整卷平行史复述进正文。\n"
        "   - `外部补全`：由你按史识**跨书选题**——可含《史记》他卷、平行正史、"
        "编年/别史等；**不限于**索引补充块里的那几部书；"
        "**补充范围**：只补全书母本未载或有差异者；禁止补母本已有（含后文才出现的同事件）；"
        "**禁止母本同一卷**。\n"
        f"3. `外部补全` **不得交空数组**；先列带《书·卷》+母本锚点的候选，"
        f"再标采用 true/false；须不少于 {q} 条合格「采用:true」。\n"
        "4. 禁止用「索引里有某书 → 外部补全只写该书」交差；"
        "禁止无检索地全标 false 或交 []。\n"
        "5. 与母本重复者、母本同一卷标 false，仍须留在候选并写清理由。\n"
        "6. 编排器会标注「经典引用候选」；勿要求句句引用，也勿交零引用策略。\n"
    )


def _plain(text: str) -> str:
    return re.sub(r"\s+", "", text)


def mother_enrich_overlap(mother: str, enrich: str) -> float:
    """Phase1 母本与 Phase2 成稿的去虚词 4-gram 重合率（越高越像誊抄）。"""
    a = _content_ngrams(_plain(mother), 4)
    b = _content_ngrams(_plain(enrich.split("参考著作")[0]), 4)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), len(b)))


def under_rewrite_soft_overlap() -> float:
    """达到此重合率 → 软警告（提示改表达不足）。默认 0.72。"""
    return float(os.environ.get("TRANSLATE_PHASE2_SOFT_MOTHER_OVERLAP", "0.72"))


def under_rewrite_hard_overlap(*, mother: str = "") -> float:
    """达到此重合率 → 硬失败（近誊抄）。

    - 短卷默认 0.95（仅拦几乎没改）
    - 长卷（母本去空白 ≥ TRANSLATE_PHASE2_LONG_MOTHER_CHARS，默认 8000）
      默认 **0.85**，避免 0.94 这类「刚过线」假改写入库
    """
    m_len = len(_plain(mother or ""))
    long_cut = max(0, int(os.environ.get("TRANSLATE_PHASE2_LONG_MOTHER_CHARS", "8000")))
    if mother and long_cut > 0 and m_len >= long_cut:
        return float(os.environ.get("TRANSLATE_PHASE2_MAX_MOTHER_OVERLAP_LONG", "0.85"))
    return float(os.environ.get("TRANSLATE_PHASE2_MAX_MOTHER_OVERLAP", "0.95"))


def detect_under_rewrite(
    mother: str,
    enrich: str,
    *,
    label: str = "成稿",
) -> list[str]:
    """几乎逐句誊抄母本 → 硬失败。"""
    m = (mother or "").strip()
    e = (enrich or "").strip()
    if len(_plain(m)) < 400 or len(_plain(e)) < 200:
        return []
    cov = mother_enrich_overlap(m, e)
    hard = under_rewrite_hard_overlap(mother=m)
    if cov < hard:
        return []
    return [
        f"{label}：相对 Phase1 母本几乎逐句誊抄"
        f"（去虚词 4-gram 重合 {cov:.0%} ≥ {hard:.0%}）；"
        "须按说书人笔调重写（见声口金标），禁止原文照搬"
    ]


def detect_under_rewrite_warnings(
    mother: str,
    enrich: str,
    *,
    label: str = "成稿",
) -> list[str]:
    """改表达偏弱 → 软警告（不阻断，推动下一轮提示词/重试策略）。"""
    m = (mother or "").strip()
    e = (enrich or "").strip()
    if len(_plain(m)) < 400 or len(_plain(e)) < 200:
        return []
    cov = mother_enrich_overlap(m, e)
    soft, hard = under_rewrite_soft_overlap(), under_rewrite_hard_overlap(mother=m)
    if cov < soft or cov >= hard:
        return []
    return [
        f"{label}：说书改表达偏弱（与母本重合 {cov:.0%}，目标大致 <{soft:.0%}；"
        f"好稿参考约 50%）；请加强口语/场面/「」金句，勿停留在通顺书面语"
    ]


def _content_ngrams(plain: str, n: int = 4) -> set[str]:
    """去虚词后的 n-gram，用于释义双写（换说法复述）检测。"""
    s = re.sub(r"[的了着过与和在于把被将则就又]", "", plain)
    if len(s) < n:
        return set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def _is_paraphrase_duplicate(plain: str, prev: str) -> bool:
    """两段是否为同一情节的换说法复述（批间双写常见形态）。

    不依赖写死书名事件表：靠去虚词后的 4-gram 重合率。
    """
    if len(plain) < 100 or len(prev) < 100:
        return False
    longer, shorter = (plain, prev) if len(plain) >= len(prev) else (prev, plain)
    if len(longer) > len(shorter) * 2.2:
        return False
    a, b = _content_ngrams(plain, 4), _content_ngrams(prev, 4)
    if not a or not b:
        return False
    inter = len(a & b)
    cov = inter / max(1, min(len(a), len(b)))
    # 相邻批换说法复述：共享锚点多且覆盖率够高
    return inter >= 10 and cov >= 0.28


# 章界/补洞 heal 用的强事件词（同现 ≥2 且篇幅接近 → 视为复述）
_HEAL_EVENT_TOKENS: tuple[str, ...] = (
    "霍嬗",
    "奉车子侯",
    "没遇上风雨",
    "一路没遇上风雨",
    "信得痴",
    "杀得狠",
    "封狼居胥",
    "轮台",
    "罪己",
    "画法",
    "天道将军",
    "乐通侯",
    "五利将军",
)


def _heal_event_token_hits(plain: str) -> set[str]:
    return {t for t in _HEAL_EVENT_TOKENS if t in plain}


def _is_heal_duplicate(plain: str, seen: List[str]) -> bool:
    """合并/补洞静默去重：略宽于 near_duplicate，仍避免误伤不同情节。"""
    if len(plain) < 48 or not seen:
        return False
    if _is_near_duplicate(plain, seen):
        return True
    a = _content_ngrams(plain, 4)
    tokens_a = _heal_event_token_hits(plain)
    for prev in seen:
        if len(prev) < 48:
            continue
        longer, shorter = (plain, prev) if len(plain) >= len(prev) else (prev, plain)
        if len(longer) > len(shorter) * 2.4:
            continue
        b = _content_ngrams(prev, 4)
        if a and b:
            inter = len(a & b)
            cov = inter / max(1, min(len(a), len(b)))
            # 略宽：浮点下 0.28 边界易漏
            if inter >= 10 and cov >= 0.24:
                return True
        shared = tokens_a & _heal_event_token_hits(prev)
        # 仅靠事件词易误伤（如「霍嬗」登泰山 vs 暴卒）；须同时有一定 n-gram 重合
        if len(shared) >= 2 and a and b:
            inter2 = len(a & b)
            cov2 = inter2 / max(1, min(len(a), len(b)))
            if inter2 >= 8 and cov2 >= 0.18:
                return True
    return False


def _para_key(plain: str, n: int = 96) -> str:
    return plain[:n] if len(plain) > n else plain


def _is_near_duplicate(plain: str, seen: List[str]) -> bool:
    """字面近重复，或释义双写（换说法复述同一情节）。"""
    if len(plain) < 48:
        return False
    key = _para_key(plain)
    for prev in seen:
        prev_key = _para_key(prev)
        if key == prev_key and abs(len(plain) - len(prev)) <= 24:
            return True
        # 新段几乎被旧段覆盖（短重启 / 整传缩写再贴一次）
        if len(plain) >= 80 and plain[: min(160, len(plain))] in prev:
            return True
        if len(plain) <= len(prev) and len(plain) >= 80:
            if plain in prev:
                return True
        # 等长开场白高度重合且新段不比旧段长出实质内容
        head_a, head_b = plain[:120], prev[:120]
        if len(head_a) >= 60 and len(head_b) >= 60 and len(plain) <= len(prev) + 16:
            shared = sum(1 for x, y in zip(head_a, head_b) if x == y)
            if shared / max(len(head_a), len(head_b)) >= 0.88:
                return True
        if _is_paraphrase_duplicate(plain, prev):
            return True
    return False


def _extension_of_seen(plain: str, seen: List[str]) -> int | None:
    """若某已见段是新段前缀，返回其在 seen 中的下标，便于替换为更长段。"""
    if len(plain) < 48:
        return None
    for i, prev in enumerate(seen):
        if len(prev) < 48:
            continue
        if plain.startswith(prev) and len(plain) > len(prev) + 12:
            return i
        head = prev[: min(96, len(prev))]
        if head and plain.startswith(head) and len(plain) > len(prev) + 12:
            return i
    return None


def join_narrative_parts(parts: Sequence[str]) -> str:
    """分批/分章正文按序拼接，并对「换说法复述同一情节」静默去重（heal）。

    - 保留先出现的段落，丢弃后文近重复 / 释义双写段（章界复述、补洞总评重复常见）。
    - **不**因此触发质检失败或整章重试；他书 vs 母本是否重复仍由 plan `external_dedupe` 管。
    - 短段（<48 字去空白）不去重，以免误伤转场句。
    """
    out: List[str] = []
    seen: List[str] = []
    for part in parts:
        if not part or not str(part).strip():
            continue
        for para in re.split(r"\n\s*\n", str(part).strip()):
            p = para.strip()
            if not p:
                continue
            plain = _plain(p)
            if len(plain) >= 48 and _is_heal_duplicate(plain, seen):
                continue
            out.append(p)
            if len(plain) >= 48:
                seen.append(plain)
    return "\n\n".join(out)


def dedupe_narrative_parts(parts: Sequence[str], *, min_para_chars: int = 48) -> str:
    """与 join_narrative_parts 相同（heal 去重）；min_para_chars 保留兼容。"""
    del min_para_chars
    return join_narrative_parts(parts)


def heal_paraphrase_duplicates_in_detail(detail: str) -> str:
    """单篇正文内静默去掉释义双写段（保留参考著作节）。"""
    text = str(detail or "")
    ref = ""
    body = text
    for sep in ("\n\n参考著作\n", "\n参考著作\n", "\n\n参考著作"):
        if sep in text:
            body, _, rest = text.partition(sep)
            ref = sep.lstrip("\n") + rest
            break
    healed = join_narrative_parts([body.strip()] if body.strip() else [])
    if not ref:
        return healed
    return f"{healed}\n\n{ref.lstrip()}" if healed else text.strip()


def find_evaporated_paragraphs(
    parts: Sequence[str],
    merged: str,
    *,
    min_chars: int = 80,
) -> List[str]:
    """拼接后若某源段头消失则报警。

    heal 去重故意丢掉的后段近重复不算蒸发。
    """
    merged_body = str(merged or "")
    merged_plain = _plain(merged_body)
    kept: List[str] = []
    for para in re.split(r"\n\s*\n", merged_body.strip()):
        pl = _plain(para)
        if len(pl) >= 48:
            kept.append(pl)
    lost: List[str] = []
    for part in parts:
        if not part:
            continue
        for para in str(part).split("\n\n"):
            p = para.strip()
            plain = _plain(p)
            if len(plain) < min_chars:
                continue
            if plain in merged_plain or (
                len(plain) >= 80 and plain[: min(120, len(plain))] in merged_body
            ):
                continue
            if kept and _is_heal_duplicate(plain, kept):
                continue
            tip = re.sub(r"\s+", "", p)[:48]
            if tip and tip not in lost:
                lost.append(tip)
    return lost


def scrub_event_duplicate_paragraphs(detail: str) -> str:
    """兼容旧名：改为调用 heal（静默去双写，不门禁）。"""
    return heal_paraphrase_duplicates_in_detail(detail)
