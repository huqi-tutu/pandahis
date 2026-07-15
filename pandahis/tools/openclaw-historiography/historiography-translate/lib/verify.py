"""翻译产出质检。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.coverage import verify_mother_coverage
from lib.source_text import build_source_original, source_original_fingerprint
from lib.gloss_rules import detect_forbidden_gloss
from lib.citation_mode import count_short_quote_density
from lib.intro_overlap import intro_mother_overlap
from lib.attribution import detect_foreign_exit_in_opening

FORBIDDEN_PROSE = (
    "此外",
    "综上所述",
    "值得注意的是",
    "堪称",
    "可谓",
    "不啻",
    "历史长河",
    "时代洪流",
    "命运齿轮",
    "拉开序幕",
    "翻开新篇章",
    "历史终将证明",
    "毫无疑问",
)

PLACEHOLDER_PATTERNS = (
    r"TODO",
    r"待补充",
    r"此处省略",
    r"\[\.{3}\]",
)

VAGUE_CITATION_PATTERNS = (
    "有资料说",
    "据说",
    "相传",
    "传说",
    "有人说",
    "历史上认为",
    "一般认为",
    "后世认为",
    "有观点认为",
)

# 通假标注：X（通『Y』）中 X 与 Y 必须不同
_TONGJIA_SAME_CHAR = re.compile(
    r"([\u4e00-\u9fff])（通[『「\"]([\u4e00-\u9fff])[』」\"]）"
)

# macOS / Windows 文件名非法字符
_UNSAFE_FILENAME = re.compile(r'[/\\:*?"<>|\n\r\t]')

# 描述性称呼检测（这家伙/这位爷）
_DESCRIPTIVE_REF_PATTERN = re.compile(r"[这那]家伙|这位爷")

# 段落破折号结尾检测
_DASH_ENDING_PATTERN = re.compile(r"——\s*$", re.MULTILINE)

# 正文首字符必须是汉字，禁止标点/书名号/引号/井号等开头
_PUNCTUATION_FIRST = re.compile(r"^[\u4e00-\u9fff]")

# 段落过碎检测：连续单句成段
_MIN_SENTENCES_PER_PARA = 1


def sanitize_entry_name(name: str) -> str:
    cleaned = _UNSAFE_FILENAME.sub("", (name or "").strip())
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned or "未命名"


def output_filename(entry_id: str, entry_name: str) -> str:
    safe = sanitize_entry_name(entry_name)
    return f"{entry_id}_{safe}.json"


def output_path(entry_id: str, base: Path, entry_name: str = "") -> Path:
    return base / output_filename(entry_id, entry_name)


def resolve_output_path(
    entry_id: str,
    base: Path,
    entry_name: str = "",
) -> Path:
    """定位产出文件：优先 canonical 名，再 glob，兼容旧版 {id}.json。"""
    if entry_name:
        canonical = output_path(entry_id, base, entry_name)
        if canonical.is_file():
            return canonical
    matches = sorted(base.glob(f"{entry_id}_*.json"))
    if matches:
        return matches[0]
    legacy = base / f"{entry_id}.json"
    if legacy.is_file():
        return legacy
    return output_path(entry_id, base, entry_name)


def min_word_count(paragraph_count: int) -> int:
    base = 400
    extra = max(0, paragraph_count - 3) * 150
    return base + extra


def _chunk_source_char_count(recalled_chunk: Dict[str, Any]) -> int:
    total = 0
    for block in recalled_chunk.get("blocks") or []:
        for para in block.get("paragraphs") or []:
            total += len(para.get("text") or "")
    return total


def chunk_body_min_word_count(recalled_chunk: Dict[str, Any]) -> int:
    """分块正文字数下限：母本块按段落估算，纯补充块按源文字数比例。"""
    mother_sents = 0
    has_mother = False
    for block in recalled_chunk.get("blocks") or []:
        if block.get("role") == "母本":
            has_mother = True
            for para in block.get("paragraphs") or []:
                t = para.get("text") or ""
                mother_sents += len(re.findall(r"[。！？\n]", t)) or (1 if t.strip() else 0)

    src_chars = _chunk_source_char_count(recalled_chunk)
    para_count = int(recalled_chunk.get("paragraph_count") or 1)

    # 纯索引补充分块：源文通常更短，不宜用母本段落公式
    if not has_mother or mother_sents == 0:
        return max(250, int(src_chars * 0.45))

    return int(min_word_count(para_count) * 0.65)


def load_output(
    entry_id: str,
    base: Path,
    entry_name: str = "",
) -> Tuple[bool, Dict[str, Any], List[str]]:
    errors: List[str] = []
    fp = resolve_output_path(entry_id, base, entry_name)
    if not fp.is_file():
        return False, {}, [f"缺少产出文件: {fp}"]
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, {}, [f"JSON 解析失败: {exc}"]
    return True, data, errors


def _mother_source_text(recalled: Dict[str, Any]) -> str:
    parts: List[str] = []
    for block in recalled.get("blocks") or []:
        if block.get("role") != "母本":
            continue
        for para in block.get("paragraphs") or []:
            parts.append(str(para.get("text") or ""))
    return "\n".join(parts)


def _detect_dash_ending(detail: str) -> List[str]:
    """检测段落以破折号结尾（禁止 —— 在段落末尾）。"""
    paragraphs = [p.strip() for p in detail.split("\n\n") if p.strip()]
    errors: List[str] = []
    for i, para in enumerate(paragraphs):
        if _DASH_ENDING_PATTERN.search(para):
            preview = para[-60:] if len(para) > 60 else para
            errors.append(f"段落以破折号结尾（第{i+1}段）: …{preview}")
    return errors


def _detect_punctuation_opening(detail: str) -> List[str]:
    """正文首字符必须是汉字，禁止以标点符号、书名号、引号、井号等开头。"""
    first_char = detail.lstrip()[0] if detail.strip() else ""
    if not _PUNCTUATION_FIRST.match(first_char):
        return [f"正文首字符非法: 「{first_char}」（必须以汉字开头，禁止标点/书名号/引号/井号）"]
    return []


def _detect_excessive_descriptive_refs(detail: str) -> List[str]:
    """检测描述性称呼过度（这家伙/这位爷 ≥3次）。"""
    count = len(_DESCRIPTIVE_REF_PATTERN.findall(detail))
    if count > 3:
        return [f"描述性称呼过多: {count}处（这家伙/这位爷），上限3次"]
    return []


def _detect_single_sentence_paragraphs(detail: str) -> List[str]:
    """检测连续单句成段的段落过碎问题（连续 ≥4 段单句即报错）。"""
    paragraphs = [p.strip() for p in detail.split("\n\n") if p.strip()]
    streak = 0
    max_streak = 0
    for para in paragraphs:
        sentence_count = len([c for c in para if c in "。！？"])
        if sentence_count <= _MIN_SENTENCES_PER_PARA:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    if max_streak >= 4:
        return [f"段落过碎: 连续{max_streak}段单句成段，建议合并"]
    return []


def verify_mother_draft(
    entry_id: str,
    recalled: Dict[str, Any],
    mother_path: Path,
    plan: Dict[str, Any] | None = None,
    *,
    batch_mode: bool = False,
) -> Tuple[bool, List[str]]:
    """Phase1 母本顺译质检。"""
    errors: List[str] = []
    if not mother_path.is_file():
        return False, [f"缺少母本顺译: {mother_path}"]
    try:
        data = json.loads(mother_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"母本顺译 JSON 解析失败: {exc}"]

    if data.get("史略ID") != entry_id:
        errors.append(f"母本顺译 史略ID 不一致: {data.get('史略ID')!r}")

    detail = (data.get("母本顺译") or data.get("翻译详情") or "").strip()
    if not detail:
        errors.append("母本顺译为空")
        return False, errors

    errors.extend(_detect_punctuation_opening(detail))

    if "*参考著作*" in detail or detail.rstrip().endswith("参考著作"):
        errors.append("Phase1 不应含「参考著作」节")

    mother_work = str(recalled.get("母本著作") or "")
    mother_src = _mother_source_text(recalled)
    errors.extend(_foreign_citations_in_mother(detail, mother_work, mother_src))

    if plan:
        errors.extend(_verify_must_phrases(detail, plan, batch_mode=batch_mode))
        cov_ok, cov_errs = verify_mother_coverage(detail, plan)
        if not cov_ok:
            errors.extend([f"母本顺译 {e}" for e in cov_errs])

    errors.extend(detect_forbidden_gloss(detail))
    if not batch_mode:
        short_q = count_short_quote_density(detail, threshold_len=4)
        short_q_limit = max(12, len(detail) // 95)
        if short_q >= short_q_limit:
            errors.append(
                f"母本引用过碎: ≤4字「」引用 {short_q} 处（阈值{short_q_limit}），并列句群应整簇引用"
            )

    errors.extend(_detect_dash_ending(detail))
    errors.extend(_detect_excessive_descriptive_refs(detail))

    wc = len(detail)
    if not batch_mode:
        mother_src = _mother_source_text(recalled)
        src_len = len(re.sub(r"\s+", "", mother_src))
        para_floor = int(min_word_count(int(recalled.get("paragraph_count") or 1)) * 0.55)
        src_floor = max(80, int(src_len * 2.2))
        floor = min(para_floor, src_floor) if src_len < 120 else para_floor
        if wc < floor:
            errors.append(f"母本顺译字数偏少: {wc} < {floor}")

    return len(errors) == 0, errors


def _allowed_mother_citation(title: str, mother_work: str) -> bool:
    if "史记" in title:
        return True
    core = re.sub(r"^\d+[A-Z]?", "", mother_work)
    return bool(core and core in title)


def _foreign_citations_in_mother(
    detail: str, mother_work: str, mother_src: str = ""
) -> List[str]:
    errors: List[str] = []
    src_plain = re.sub(r"\s+", "", mother_src)
    for title in re.findall(r"《([^》]+)》", detail):
        if _allowed_mother_citation(title, mother_work):
            continue
        if title in src_plain or title.replace("·", "") in src_plain:
            continue
        errors.append(f"Phase1 出现母本以外引用: 《{title}》")
    return errors


def _phrase_hit(phrase: str, body: str) -> bool:
    """锚点词是否出现在译文中（精确/引号内/顺序模糊）。"""
    p = str(phrase).strip()
    if not p:
        return True
    if p in body:
        return True
    # 引号内容自动算命中（硬锚点在「」内任意位置即通过）
    if f"「{p}」" in body:
        return True
    for m in re.finditer(r"「([^」]+)」", body):
        if p in m.group(1):
            return True
    # 两步过滤：去引号纯文本次序匹配
    plain = re.sub(r"[「」『』\s]", "", body)
    pi = 0
    for ch in plain:
        if pi < len(p) and ch == p[pi]:
            pi += 1
    if pi == len(p) and len(p) >= 2:
        return True
    return False


def _classify_must_phrases(
    phrases: List[Any],
    orig: str,
    *,
    batch_mode: bool = False,
) -> Tuple[List[str], List[str]]:
    """必现词分两级：硬锚点（专名/数字/氏/引号原文）须保留；软锚点（句读边界短语）仅记分不阻断。

    翻译规则 §第零部分「必现词分级」：硬锚点在 Phase1 用「」保留；软锚点由 coverage 验收。
    """
    from lib.mother_sentences import _MUST_GENERIC, is_midword_fragment  # noqa: PLC0415

    orig_plain = re.sub(r"\s+", "", orig)
    hard: List[str] = []
    soft: List[str] = []
    for raw in phrases:
        p = str(raw).strip()
        if not p or is_midword_fragment(p, orig):
            continue
        # 硬锚点：数字、X氏专名
        if re.search(r"\d", p) or ("氏" in p and len(p) >= 2):
            hard.append(p)
            continue
        # 硬锚点：≥4字且在原文中完整出现（专名/事件/地名）
        if len(p) >= 4 and p in orig_plain:
            hard.append(p)
            continue
        # 软锚点：句读边界短语（非专用名但有信息传递功能）
        if len(p) >= 3 and p in orig_plain and p not in _MUST_GENERIC:
            soft.append(p)

    def _dedup(items: List[str]) -> List[str]:
        out: List[str] = []
        for p in items:
            if any(p != q and p in q for q in items):
                continue
            if p not in out:
                out.append(p)
        return out

    hard = _dedup(hard)[:3]
    soft = _dedup(soft)[:2]

    if not hard and not soft:
        fallback = [
            str(p).strip()
            for p in phrases
            if len(str(p).strip()) >= 3 and not is_midword_fragment(str(p), orig)
        ][:3]
        return fallback, []

    if not batch_mode:
        return hard, soft

    critical = [
        p
        for p in hard
        if re.search(r"\d", p) or "氏" in p or len(p) <= 6
    ]
    return critical if critical else hard[:2], []


def _hard_must_phrases(
    phrases: List[Any],
    orig: str,
    *,
    batch_mode: bool = False,
) -> List[str]:
    """兼容旧接口：返回硬锚点列表。"""
    hard, _soft = _classify_must_phrases(phrases, orig, batch_mode=batch_mode)
    return hard


def _must_phrase_weak_ids(
    detail: str,
    plan: Dict[str, Any],
    *,
    ratio_floor: float = 0.50,
    batch_mode: bool = False,
) -> List[Tuple[str, List[str]]]:
    """返回硬锚点弱覆盖条目：(编号, 缺失硬锚点列表)。软锚点不参与阻断判定。"""
    body = re.sub(r"\s+", "", detail)
    weak: List[Tuple[str, List[str]]] = []
    checklist = plan.get("母本逐句清单") or []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("编号") or "")
        orig = str(item.get("原文摘句") or "")
        phrases = item.get("必现词") or []
        if not isinstance(phrases, list) or not phrases:
            continue
        hard, _soft = _classify_must_phrases(phrases, orig, batch_mode=batch_mode)
        if not hard:
            continue
        missing = [p for p in hard if not _phrase_hit(p, body)]
        hits = len(hard) - len(missing)
        ratio = hits / len(hard)
        if ratio < ratio_floor:
            weak.append((sid, missing))
    return weak


def collect_must_phrase_misses(
    detail: str,
    plan: Dict[str, Any],
    *,
    limit: int = 12,
    batch_mode: bool = False,
) -> List[str]:
    """生成 Phase1 重试提示：列出缺失的硬锚点。"""
    lines: List[str] = []
    for sid, missing in _must_phrase_weak_ids(detail, plan, batch_mode=batch_mode):
        if not missing:
            lines.append(f"- {sid}: 原词锚点覆盖不足，请对照原文摘句补全")
            continue
        shown = "、".join(missing[:4])
        if len(missing) > 4:
            shown += f" 等{len(missing)}个"
        lines.append(f"- {sid}: 译文须保留「{shown}」")
        if len(lines) >= limit:
            break
    return lines


def _verify_must_phrases(
    detail: str,
    plan: Dict[str, Any],
    *,
    batch_mode: bool = False,
) -> List[str]:
    """硬锚点阻断校验：只检查硬锚点（专名/数字/氏），软锚点不阻断。长条目自动放宽。
    
    分批模式下跳过 —— verify_mother_coverage 已经做了更精细的逐句覆盖校验，
    硬锚点校验在分批阶段是冗余且容易误判的。
    """
    if batch_mode:
        return []
    errors: List[str] = []
    checklist = plan.get("母本逐句清单") or []
    n = len(checklist)
    is_long = n > 40  # D: 长条目自动放宽

    ratio_floor = 0.25 if batch_mode else (0.35 if is_long else 0.50)
    weak = _must_phrase_weak_ids(detail, plan, ratio_floor=ratio_floor, batch_mode=batch_mode)
    weak_ids = [sid for sid, _ in weak]

    if is_long:
        fail_threshold = max(8, n // 4)  # D: 长条目阈值从 max(3, n/5) 放宽
    elif batch_mode:
        fail_threshold = max(4, n // 3)
    else:
        fail_threshold = max(3, n // 5)

    if len(weak_ids) >= fail_threshold:
        errors.append(
            f"必现词命中不足: {len(weak_ids)} 条 M 未保留硬锚点"
            f"（如 {', '.join(weak_ids[:6])}）"
        )
    return errors


def _collect_allowed_titles(
    recalled: Dict[str, Any],
    plan: Dict[str, Any] | None,
    mother_work: str,
) -> set[str]:
    allowed: set[str] = {"史记"}
    core = re.sub(r"^\d+[A-Z]?", "", mother_work)
    if core:
        allowed.add(core)
    for block in recalled.get("blocks") or []:
        work = str(block.get("work") or "")
        vol = str(block.get("vol") or "")
        volume = str(block.get("volume") or "")
        if work:
            allowed.add(work)
            allowed.add(re.sub(r"^\d+[A-Z]?", "", work))
        if volume:
            allowed.add(volume)
            allowed.add(f"{work}·{volume}" if work else volume)
        if vol and volume:
            allowed.add(f"{work}·{volume}")
    if plan:
        for ref in plan.get("参考著作") or []:
            if isinstance(ref, str):
                for t in re.findall(r"《([^》]+)》", ref):
                    allowed.add(t)
        for item in plan.get("外部补全") or []:
            if not isinstance(item, dict) or item.get("采用") is not True:
                continue
            src = str(item.get("出处") or "")
            for t in re.findall(r"《([^》]+)》", src):
                allowed.add(t)
        for src in plan.get("允许引用白名单") or []:
            for t in re.findall(r"《([^》]+)》", str(src)):
                allowed.add(t)
    return allowed


def _title_allowed(title: str, allowed: set[str], mother_src: str = "") -> bool:
    if "史记" in title:
        return True
    src_plain = re.sub(r"\s+", "", mother_src)
    if title in src_plain or title.replace("·", "") in src_plain:
        return True
    if title in allowed:
        return True
    for a in allowed:
        if a in title or title in a:
            return True
        if a.replace("·", "") in title.replace("·", ""):
            return True
    return False


def _unauthorized_citations(
    detail: str,
    allowed: set[str],
    mother_src: str = "",
) -> List[str]:
    errors: List[str] = []
    for title in re.findall(r"《([^》]+)》", detail):
        if not _title_allowed(title, allowed, mother_src):
            errors.append(f"未授权引用: 《{title}》")
    return errors


def verify_enrich_draft(
    entry_id: str,
    recalled: Dict[str, Any],
    output_path: Path,
    plan: Dict[str, Any] | None = None,
) -> Tuple[bool, List[str]]:
    """Phase2 成稿前置质检：禁模糊出处、白名单《》、参考著作节。"""
    errors: List[str] = []
    if not output_path.is_file():
        return False, [f"缺少译稿: {output_path}"]
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"译稿 JSON 解析失败: {exc}"]

    if data.get("史略ID") != entry_id:
        errors.append(f"史略ID 不一致: {data.get('史略ID')!r}")

    detail = (data.get("翻译详情") or "").strip()
    if not detail:
        errors.append("翻译详情为空")
        return False, errors

    errors.extend(_detect_punctuation_opening(detail))

    if re.search(r"^本条\s*\d+\s*段（母本", detail) or "已读完" in detail[:120]:
        errors.append("正文含「喊数/进度汇报」元叙述，须删除后再落盘")

    vague_hits = [w for w in VAGUE_CITATION_PATTERNS if w in detail]
    if vague_hits:
        errors.append(
            f"存在无明确出处表达: {vague_hits[:5]}"
            "（须改为「《书名·卷》载…」或删除）"
        )

    if "*参考著作*" not in detail and "参考著作" not in detail:
        errors.append("文末缺少「参考著作」列表")

    mother_work = str(recalled.get("母本著作") or "")
    mother_src = _mother_source_text(recalled)
    allowed = _collect_allowed_titles(recalled, plan, mother_work)
    errors.extend(_unauthorized_citations(detail, allowed, mother_src)[:5])

    subject = str(recalled.get("史略名称") or "")
    errors.extend(detect_foreign_exit_in_opening(detail, subject))
    errors.extend(detect_forbidden_gloss(detail))
    errors.extend(_detect_dash_ending(detail))
    errors.extend(_detect_excessive_descriptive_refs(detail))
    if plan:
        errors.extend(intro_mother_overlap(detail, plan))

    return len(errors) == 0, errors


def verify_output(
    entry_id: str,
    recalled: Dict[str, Any],
    output_dir: Path,
    plan: Dict[str, Any] | None = None,
) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    entry_name = str(recalled.get("史略名称") or "")
    ok, data, load_errs = load_output(entry_id, output_dir, entry_name)
    errors.extend(load_errs)
    if not ok:
        return False, errors

    keys = set(data.keys())
    allowed = {"史略ID", "翻译详情", "史料原文"}
    if keys != allowed:
        extra = keys - allowed
        missing = allowed - keys
        if extra:
            errors.append(f"多余字段: {sorted(extra)}")
        if missing:
            errors.append(f"缺少字段: {sorted(missing)}")

    expected_source = build_source_original(recalled)
    source = data.get("史料原文")
    if not isinstance(source, str) or not source.strip():
        errors.append("史料原文缺失或为空")
    elif source != expected_source:
        errors.append("史料原文与召回母本/索引补充不一致（须由编排器写入，禁止 LLM 改写）")

    if data.get("史略ID") != entry_id:
        errors.append(
            f"史略ID 不一致: 期望 {entry_id}，实际 {data.get('史略ID')!r}"
        )

    detail = (data.get("翻译详情") or "").strip()
    if not detail:
        errors.append("翻译详情为空")
    else:
        errors.extend(_detect_punctuation_opening(detail))

        if re.search(r"^本条\s*\d+\s*段（母本", detail) or (
            detail.startswith("本条") and "已读完" in detail.split("\n", 1)[0]
        ):
            errors.append("正文含「喊数/进度汇报」元叙述，须删除")

        wc = len(detail)
        para_count = int(recalled.get("paragraph_count") or 1)
        para_floor = min_word_count(para_count)
        src_len = len(re.sub(r"\s+", "", str(expected_source or "")))
        src_floor = max(100, int(src_len * 3.5))
        floor = min(para_floor, src_floor) if src_len < 150 else para_floor
        if wc < floor:
            errors.append(f"字数不足: {wc} < 下限 {floor}")

        if "*参考著作*" not in detail and "参考著作" not in detail:
            errors.append("文末缺少「参考著作」列表")

        for pat in PLACEHOLDER_PATTERNS:
            if re.search(pat, detail, re.I):
                errors.append(f"含占位符: {pat}")

        hits = [w for w in FORBIDDEN_PROSE if w in detail]
        if len(hits) >= 3:
            errors.append(f"书面腔词汇过多: {hits[:5]}")

        vague_hits = [w for w in VAGUE_CITATION_PATTERNS if w in detail]
        if vague_hits:
            errors.append(f"存在无明确出处表达: {vague_hits[:5]}")

        repeated = _repeated_long_paragraphs(detail)
        if repeated:
            errors.append(f"疑似重复段落/事件: {repeated[:2]}")

        tongjia_errs = _invalid_tongjia_annotations(detail)
        errors.extend(tongjia_errs)

        errors.extend(detect_forbidden_gloss(detail))
        errors.extend(_detect_dash_ending(detail))
        errors.extend(_detect_excessive_descriptive_refs(detail))
        errors.extend(_detect_single_sentence_paragraphs(detail))
        short_q = count_short_quote_density(detail, threshold_len=4)
        short_q_limit = max(15, len(detail) // 95)
        if short_q >= short_q_limit:
            errors.append(
                f"引用过碎: ≤4字「」引用 {short_q} 处（阈值{short_q_limit}），并列句群应整簇引用后统一解释"
            )

        subject = str(recalled.get("史略名称") or entry_name)
        errors.extend(detect_foreign_exit_in_opening(detail, subject))

        if plan:
            errors.extend(intro_mother_overlap(detail, plan))
            errors.extend(_verify_plan_sources_in_detail(detail, plan))
            cov_ok, cov_errs = verify_mother_coverage(detail, plan)
            if not cov_ok:
                errors.extend(cov_errs)
            else:
                for w in cov_errs:
                    if w.startswith("[warn]"):
                        print(f"   ⚠️ {w[7:]}", flush=True)

    block_count = int(recalled.get("block_count") or 1)
    if block_count > 1:
        mother = recalled.get("母本著作") or ""
        mother_name = re.sub(r"^\d+[A-Z]?", "", mother)
        if mother_name and mother_name not in detail:
            # 宽松：至少应出现常见母本简称或参考著作节
            if "参考著作" not in detail:
                errors.append("多源条目但正文/参考著作未体现母本")

    return len(errors) == 0, errors


def verify_chunk_body(
    body_path: Path,
    recalled_chunk: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """分块正文最小质检。"""
    errors: List[str] = []
    if not body_path.is_file():
        return False, [f"缺少分块正文: {body_path}"]
    text = body_path.read_text(encoding="utf-8").strip()
    if not text:
        return False, ["分块正文为空"]

    # 分块不写参考著作节
    if "*参考著作*" in text:
        errors.append("分块正文不应含「参考著作」节（合并时统一添加）")

    para_count = int(recalled_chunk.get("paragraph_count") or 1)
    floor = chunk_body_min_word_count(recalled_chunk)
    wc = len(text)
    if wc < floor:
        errors.append(f"分块字数不足: {wc} < 下限 {floor}")

    for pat in PLACEHOLDER_PATTERNS:
        if re.search(pat, text, re.I):
            errors.append(f"含占位符: {pat}")

    hits = [w for w in FORBIDDEN_PROSE if w in text]
    if len(hits) >= 3:
        errors.append(f"书面腔词汇过多: {hits[:5]}")

    errors.extend(_invalid_tongjia_annotations(text))
    errors.extend(detect_forbidden_gloss(text))

    return len(errors) == 0, errors


def _invalid_tongjia_annotations(text: str) -> List[str]:
    """检测「A（通『A』）」类无效通假标注。"""
    errors: List[str] = []
    seen: set[str] = set()
    for m in _TONGJIA_SAME_CHAR.finditer(text):
        orig, std = m.group(1), m.group(2)
        if orig != std:
            continue
        snippet = m.group(0)
        if snippet in seen:
            continue
        seen.add(snippet)
        errors.append(f"无效通假标注（内外同字）: {snippet}")
    return errors


def _repeated_long_paragraphs(detail: str) -> List[str]:
    chunks = [
        re.sub(r"\s+", "", p)
        for p in detail.split("\n\n")
        if len(re.sub(r"\s+", "", p)) >= 80
    ]
    seen: set[str] = set()
    repeated: List[str] = []
    for c in chunks:
        key = c[:80]
        if key in seen:
            repeated.append(c[:60] + "...")
        seen.add(key)
    return repeated


def _citation_present(source: str, detail: str, *, any_title: bool = False) -> bool:
    if not source:
        return True
    if source in detail:
        return True
    titles = re.findall(r"《([^》]+)》", source)
    if not titles:
        return False

    def _title_hit(title: str) -> bool:
        if f"《{title}》" in detail:
            return True
        # 《左传·庄公十年》 满足 plan 中的 《左传》
        if f"《{title}·" in detail:
            return True
        return False

    if any_title:
        return any(_title_hit(t) for t in titles)
    segments = re.split(r"[、；;]", source)
    if len(segments) > 1:
        return all(
            any(f"《{t}》" in detail for t in re.findall(r"《([^》]+)》", seg))
            for seg in segments
            if re.findall(r"《([^》]+)》", seg)
        )
    return all(f"《{t}》" in detail for t in titles)


def _refs_from_detail_section(detail: str) -> List[str]:
    """解析文末 *参考著作* 节列出的书目。"""
    if "*参考著作*" in detail:
        tail = detail.split("*参考著作*", 1)[1]
    elif "参考著作" in detail:
        tail = detail.rsplit("参考著作", 1)[1]
    else:
        return []
    return re.findall(r"《([^》]+)》", tail)


def _verify_plan_sources_in_detail(detail: str, plan: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    # 只验收「采用:true」的外部补全出处；plan.参考著作 为候选库，不要求全部入正文
    external = plan.get("外部补全") or []
    if isinstance(external, list):
        for item in external:
            if not isinstance(item, dict) or item.get("采用") is not True:
                continue
            source = str(item.get("出处") or "")
            if source and not _citation_present(source, detail, any_title=True):
                errors.append(f"外部补全出处未出现在译文中: {source}")

    # 文末参考著作节中列出的书，须在正文有对应引用
    for title in _refs_from_detail_section(detail):
        if not _citation_present(f"《{title}》", detail, any_title=True):
            errors.append(f"参考著作节书目未在正文引用: 《{title}》")
    return errors
