"""翻译产出质检。"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.coverage import verify_mother_coverage
from lib.source_text import build_source_original, source_original_fingerprint
from lib.gloss_rules import detect_forbidden_gloss
from lib.citation_mode import count_short_quote_density
from lib.attribution import apply_attribution_fixes
from lib.draft_parse import extract_draft_body

_OPENCLAW_ROOT = Path(__file__).resolve().parents[2]
if str(_OPENCLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_OPENCLAW_ROOT))

from shared.ai_flavor_words import (  # noqa: E402
    AI_FLAVOR_WORDS,
    ai_flavor_verify_issues,
)
from shared.legend_quota import legend_quota_verify_issues  # noqa: E402
from shared.reference_works import KNOWN_MULTI_VOLUME_WORKS  # noqa: E402
from shared.vague_citation import VAGUE_CITATION_TRIGGERS  # noqa: E402

# 兼容旧 import 名
FORBIDDEN_PROSE = AI_FLAVOR_WORDS
VAGUE_CITATION_PATTERNS = VAGUE_CITATION_TRIGGERS
_KNOWN_MULTI_VOLUME_MOTHERS = KNOWN_MULTI_VOLUME_WORKS

PLACEHOLDER_PATTERNS = (
    r"TODO",
    r"待补充",
    r"此处省略",
    r"\[\.{3}\]",
)

# 通假标注：X（通『Y』）中 X 与 Y 必须不同
_TONGJIA_SAME_CHAR = re.compile(
    r"([\u4e00-\u9fff])（通[『「\"]([\u4e00-\u9fff])[』」\"]）"
)

# macOS / Windows 文件名非法字符
_UNSAFE_FILENAME = re.compile(r'[/\\:*?"<>|\n\r\t]')

# 描述性称呼检测（这家伙/这位爷）
_DESCRIPTIVE_REF_PATTERN = re.compile(r"[这那]家伙|这位爷")


def _as_warn(message: str) -> str:
    return message if message.startswith("[warn]") else f"[warn] {message}"


def _log_verify_warnings(warnings: List[str]) -> None:
    for raw in warnings:
        text = raw[7:] if raw.startswith("[warn]") else raw
        print(f"   ⚠️ {text}", flush=True)


def _must_phrase_min_ratio(checklist_size: int) -> float:
    """全局硬锚点命中率下限（与 coverage 同思路，按条数略放宽）。"""
    base = float(os.environ.get("TRANSLATE_MUST_PHRASE_MIN_RATIO", "0.40"))
    if checklist_size >= 80:
        return float(os.environ.get("TRANSLATE_MUST_PHRASE_MIN_RATIO_LONG", "0.40"))
    return base


def _must_phrase_min_total_for_ratio() -> int:
    """硬锚点总数低于此值时不用比例阻断（避免 0/1→0% 误杀）。"""
    return int(os.environ.get("TRANSLATE_MUST_PHRASE_MIN_TOTAL_FOR_RATIO", "5"))


def _must_phrase_max_miss_absolute() -> int:
    """小样本硬锚点：绝对缺失数达到此值才阻断。"""
    return int(os.environ.get("TRANSLATE_MUST_PHRASE_MAX_MISS_ABSOLUTE", "4"))


def _must_phrase_block_decision(
    total: int,
    hits: int,
    checklist_size: int,
) -> tuple[bool, float, float, int]:
    """返回 (是否阻断, 命中率, 比例阈值, 缺失数)。"""
    if total <= 0:
        return False, 1.0, _must_phrase_min_ratio(checklist_size), 0

    misses = total - hits
    ratio = hits / total
    min_ratio = _must_phrase_min_ratio(checklist_size)

    if total < _must_phrase_min_total_for_ratio():
        return misses >= _must_phrase_max_miss_absolute(), ratio, min_ratio, misses

    return ratio < min_ratio, ratio, min_ratio, misses

# 段末破折号：不再硬拦（自然过渡常用 —— 收束，改由人工审读）
_DASH_ENDING_PATTERN = re.compile(r"——\s*$", re.MULTILINE)

# 篇末空泛升华（出现即 error，不限频次）
_SUMMARY_ENDING_PHRASES: tuple[str, ...] = (
    "时代翻篇",
    "由此而来",
    "共同起点",
    "翻开新篇章",
    "历史的翻页",
)

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
    """定位产出文件：优先 canonical 名，再 glob，兼容旧版 {id}.json。

    忽略 `*.json.phase2_*.json` / `*.pre_*_backup.json` 等旁路备份，
    避免误把失败薄稿当作成稿而跳过重跑。
    """
    if entry_name:
        canonical = output_path(entry_id, base, entry_name)
        if canonical.is_file():
            return canonical
    matches = sorted(
        p
        for p in base.glob(f"{entry_id}_*.json")
        if p.name.count(".json") == 1 and ".json." not in p.name
    )
    if matches:
        return matches[0]
    legacy = base / f"{entry_id}.json"
    if legacy.is_file():
        return legacy
    return output_path(entry_id, base, entry_name)


def min_word_count(paragraph_count: int) -> int:
    """Legacy：分块模式等仍引用；终检/母本质检已改母本×比例软警告。"""
    base = 400
    extra = max(0, paragraph_count - 3) * 150
    return base + extra


def _source_char_len(text: str) -> int:
    """母本/史料原文字符数（去空白）。"""
    return len(re.sub(r"\s+", "", text or ""))


def translation_length_ratio() -> float:
    return float(os.environ.get("TRANSLATE_LENGTH_RATIO", "1.2"))


def expected_translation_min_chars(source_len: int) -> int:
    if source_len <= 0:
        return 0
    return max(1, int(source_len * translation_length_ratio()))


def translation_length_warning(
    wc: int,
    source_len: int,
    *,
    label: str = "成稿",
) -> str | None:
    """低于母本×比例时返回 [warn] 文案（不阻断 verify）。"""
    if source_len <= 0:
        return None
    floor = expected_translation_min_chars(source_len)
    if wc >= floor:
        return None
    ratio = translation_length_ratio()
    return (
        f"[warn] {label}字数偏少: {wc} < 母本×{ratio}={floor} "
        f"（软警告，不阻断落盘；请抽查是否漏译或 Phase2 补全不足）"
    )


_HAN_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
THIN_SOURCE_THRESHOLD = 100


def recalled_source_han_count(recalled: Dict[str, Any]) -> int:
    total = 0
    for block in recalled.get("blocks") or []:
        for para in block.get("paragraphs") or []:
            total += len(_HAN_CHAR_RE.findall(str(para.get("text") or "")))
    return total


def verify_source_thickness(recalled: Dict[str, Any], *, threshold: int = THIN_SOURCE_THRESHOLD) -> List[str]:
    """一期翻译准入：史料提取条目合计汉字须 ≥ threshold。"""
    source_kind = str(recalled.get("史略来源") or "史料提取").strip()
    if source_kind not in ("史料提取", ""):
        return []
    total = recalled_source_han_count(recalled)
    if total < threshold:
        return [
            f"史料原文合计仅{total}汉字（<{threshold}），禁止一期翻译；"
            "应走 merge 厚度门拒收 → 朝代知识补全（见 史料厚度门规则.md）"
        ]
    return []


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


def _detect_reference_section_format(detail: str) -> List[str]:
    """参考著作须独立成段：正文末段结束后空一行再写「参考著作：」。"""
    if "参考著作" not in detail:
        return []
    if re.search(r"\n\n参考著作\s*[:：]", detail):
        return []
    return ["参考著作须独立成段（前有空行 \\n\\n），禁止与正文末句同段"]


def _detect_reference_granularity(detail: str) -> List[str]:
    """参考著作须精确到卷篇；禁裸母书名及与同书卷篇重复。"""
    refs = _refs_from_detail_section(detail)
    if not refs:
        return []
    errors: List[str] = []
    vol_mothers = {t.split("·", 1)[0] for t in refs if "·" in t}
    for title in refs:
        if "·" in title:
            continue
        if title in _KNOWN_MULTI_VOLUME_MOTHERS:
            errors.append(f"参考著作须精确到卷篇，禁止仅列《{title}》")
        elif title in vol_mothers:
            errors.append(
                f"参考著作已有《{title}·…》卷篇，禁止重复列裸《{title}》"
            )
    return errors


def _detect_dash_ending(detail: str) -> List[str]:
    """段末破折号已放宽，不再作为 verify 硬失败项。"""
    _ = detail
    return []


def _legend_quota_hard_errors(detail: str, recalled: Dict[str, Any]) -> List[str]:
    """无《》二手表述（传说/据说/有人说等）统一走频次配额。"""
    priority = str(recalled.get("优先级") or "P1")
    return [
        msg
        for _code, msg, severity in legend_quota_verify_issues(detail, priority=priority)
        if severity == "error"
    ]


def _detect_markdown_bold(detail: str) -> List[str]:
    """禁止 ** markdown 加粗；加粗由小程序对「」内原文自动处理。"""
    if re.search(r"\*\*[^*]+\*\*", detail):
        return ["正文含 Markdown **加粗**（禁止；史料原文请用直角引号「」，由小程序自动加粗）"]
    return []


def _detect_excessive_descriptive_refs(detail: str) -> List[str]:
    """检测描述性称呼过度（这家伙/这位爷 ≥3次）。"""
    count = len(_DESCRIPTIVE_REF_PATTERN.findall(detail))
    if count > 3:
        return [f"描述性称呼过多: {count}处（这家伙/这位爷），上限3次"]
    return []


def _detect_summary_ending(detail: str) -> List[str]:
    """检测篇末（最后两段）空泛升华腔。"""
    body = detail
    if "参考著作" in body:
        body = body.split("参考著作", 1)[0]
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paras:
        return []
    tail = "\n".join(paras[-2:])
    hits = [ph for ph in _SUMMARY_ENDING_PHRASES if ph in tail]
    if hits:
        return [f"篇末空泛升华: {', '.join(hits)}（改用承接情节的叙事收束）"]
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
    batch_label: str = "",
) -> Tuple[bool, List[str]]:
    """Phase1 母本顺译质检。"""
    errors: List[str] = list(verify_source_thickness(recalled))
    if not mother_path.is_file():
        return False, [f"缺少母本顺译: {mother_path}"]
    try:
        data = json.loads(mother_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"母本顺译 JSON 解析失败: {exc}"]

    if data.get("史略ID") != entry_id:
        errors.append(f"母本顺译 史略ID 不一致: {data.get('史略ID')!r}")

    detail = extract_draft_body(data, "母本顺译", "翻译详情")
    if not detail:
        errors.append("母本顺译为空")
        return False, errors

    if "*参考著作*" in detail or detail.rstrip().endswith("参考著作"):
        errors.append("Phase1 不应含「参考著作」节")

    mother_work = str(recalled.get("母本著作") or "")
    mother_src = _mother_source_text(recalled)
    # 精简流水线分批成稿允许 plan 他书补全；旧 Phase1「禁他书」告警在此会误报，跳过。
    # legacy ABCD 的纯母本顺译仍保留该软警告。
    skip_foreign_warn = False
    try:
        from lib.pipeline_streamlined import streamlined_pipeline_enabled

        skip_foreign_warn = streamlined_pipeline_enabled()
    except Exception:
        skip_foreign_warn = os.environ.get("TRANSLATE_PIPELINE", "streamlined").strip().lower() not in (
            "abcd",
            "legacy",
        )
    if not skip_foreign_warn:
        _log_verify_warnings(
            _foreign_citations_in_mother(detail, mother_work, mother_src)
        )

    if plan and batch_mode:
        from lib.config import paths as _paths
        from lib.coverage import _coverage_mode

        batch_semantic = os.environ.get("TRANSLATE_BATCH_SEMANTIC", "0").strip() in {
            "1",
            "true",
            "yes",
        }
        if _coverage_mode() == "semantic" and batch_semantic:
            from lib.coverage_l2 import verify_mother_batch_semantic_coverage

            cov_ok, cov_errs = verify_mother_batch_semantic_coverage(
                detail,
                plan,
                entry_id=entry_id,
                entry_name=str(recalled.get("史略名称") or ""),
                work_dir=_paths()["translate_work"],
                batch_label=batch_label,
            )
            if not cov_ok:
                errors.extend([f"母本顺译 {e}" for e in cov_errs if not str(e).startswith("[info]")])
            else:
                for line in cov_errs:
                    if line.startswith("[info]"):
                        print(f"   ℹ️ {line[7:]}", flush=True)
        elif _coverage_mode() == "semantic":
            errors.extend(_verify_must_phrases(detail, plan, batch_mode=batch_mode))
    elif plan and not batch_mode:
        errors.extend(_verify_must_phrases(detail, plan, batch_mode=batch_mode))
        from lib.config import paths as _paths

        cov_ok, cov_errs = verify_mother_coverage(
            detail,
            plan,
            entry_id=entry_id,
            entry_name=str(recalled.get("史略名称") or ""),
            work_dir=_paths()["translate_work"],
        )
        if not cov_ok:
            errors.extend([f"母本顺译 {e}" for e in cov_errs if not str(e).startswith("[info]")])
        else:
            for line in cov_errs:
                if line.startswith("[info]"):
                    print(f"   ℹ️ {line[7:]}", flush=True)

    errors.extend(_detect_markdown_bold(detail))
    errors.extend(_detect_reference_section_format(detail))
    errors.extend(detect_forbidden_gloss(detail))
    if not batch_mode:
        short_q = count_short_quote_density(detail, threshold_len=4)
        short_q_limit = max(12, len(detail) // 95)
        if short_q >= short_q_limit:
            errors.append(
                f"「」引用宜以完整摘句、对话或并列句群为单位（当前 {short_q} 处，阈值 {short_q_limit}）"
            )

    errors.extend(_detect_dash_ending(detail))
    errors.extend(_detect_excessive_descriptive_refs(detail))

    wc = len(detail)
    if not batch_mode:
        src_len = _source_char_len(_mother_source_text(recalled))
        warn = translation_length_warning(wc, src_len, label="母本顺译")
        if warn:
            _log_verify_warnings([warn])

    return len(errors) == 0, errors


def verify_structural_draft(
    entry_id: str,
    recalled: Dict[str, Any],
    path: Path,
    plan: Dict[str, Any] | None = None,
    *,
    batch_mode: bool = False,
    batch_label: str = "",
) -> Tuple[bool, List[str]]:
    """A 阶段结构顺译质检（字段 结构顺译）。"""
    errors: List[str] = list(verify_source_thickness(recalled))
    if not path.is_file():
        return False, [f"缺少结构顺译: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"结构顺译 JSON 解析失败: {exc}"]

    if data.get("史略ID") != entry_id:
        errors.append(f"结构顺译 史略ID 不一致: {data.get('史略ID')!r}")

    detail = extract_draft_body(data, "结构顺译", "母本顺译", "翻译详情")
    if not detail:
        errors.append("结构顺译为空")
        return False, errors

    if "参考著作" in detail:
        errors.append("A 阶段不应含「参考著作」")

    mother_work = str(recalled.get("母本著作") or "")
    mother_src = _mother_source_text(recalled)
    _log_verify_warnings(_foreign_citations_in_mother(detail, mother_work, mother_src))

    if plan:
        if batch_mode:
            from lib.config import paths as _paths
            from lib.coverage import _coverage_mode

            batch_semantic = os.environ.get("TRANSLATE_BATCH_SEMANTIC", "0").strip() in {
                "1",
                "true",
                "yes",
            }
            if _coverage_mode() == "semantic" and batch_semantic:
                from lib.coverage_l2 import verify_mother_batch_semantic_coverage

                cov_ok, cov_errs = verify_mother_batch_semantic_coverage(
                    detail,
                    plan,
                    entry_id=entry_id,
                    entry_name=str(recalled.get("史略名称") or ""),
                    work_dir=_paths()["translate_work"],
                    batch_label=batch_label,
                )
                if not cov_ok:
                    errors.extend(
                        [f"结构顺译 {e}" for e in cov_errs if not str(e).startswith("[info]")]
                    )
        elif not batch_mode:
            errors.extend(_verify_must_phrases(detail, plan, batch_mode=batch_mode))
            from lib.config import paths as _paths

            cov_ok, cov_errs = verify_mother_coverage(
                detail,
                plan,
                entry_id=entry_id,
                entry_name=str(recalled.get("史略名称") or ""),
                work_dir=_paths()["translate_work"],
            )
            if not cov_ok:
                errors.extend(
                    [f"结构顺译 {e}" for e in cov_errs if not str(e).startswith("[info]")]
                )

    errors.extend(_detect_markdown_bold(detail))
    errors.extend(detect_forbidden_gloss(detail))

    return len(errors) == 0, errors


def _paragraph_count(text: str) -> int:
    body = text.split("参考著作", 1)[0]
    return len([p for p in body.split("\n\n") if p.strip()])


def _paragraph_similarity(a: str, b: str) -> float:
    def norm(s: str) -> str:
        return re.sub(r"[\s，。、；：\"\"''「」？！]", "", s)

    x, y = norm(a), norm(b)
    if not x or not y:
        return 0.0
    if x == y:
        return 1.0
    shorter, longer = (x, y) if len(x) <= len(y) else (y, x)
    hits = sum(1 for ch in shorter if ch in longer)
    return hits / max(len(shorter), 1)


def detect_adjacent_duplicate_paragraphs(detail: str) -> List[str]:
    """相邻段高度相似（全库 hard）。"""
    errors: List[str] = []
    body = detail.split("参考著作", 1)[0].strip()
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    threshold = float(os.environ.get("TRANSLATE_DUP_PARA_RATIO", "0.88"))
    for i in range(len(paras) - 1):
        sim = _paragraph_similarity(paras[i], paras[i + 1])
        if sim >= threshold:
            errors.append(
                f"相邻段重复（相似度 {sim:.0%}）：第 {i + 1}/{i + 2} 段"
            )
    return errors


def verify_enrich_vs_baseline(
    enriched_detail: str,
    baseline_detail: str,
) -> Tuple[bool, List[str]]:
    """D 相对 baseline：字数与段落不得缩水（hard）。"""
    import os

    errors: List[str] = []
    e_body = enriched_detail.split("参考著作", 1)[0].strip()
    b_body = baseline_detail.split("参考著作", 1)[0].strip()
    if not b_body:
        return True, []
    min_ratio = float(os.environ.get("TRANSLATE_ENRICH_MIN_RATIO", "1.05"))
    e_plain = re.sub(r"\s+", "", e_body)
    b_plain = re.sub(r"\s+", "", b_body)
    if len(e_plain) < int(len(b_plain) * min_ratio):
        errors.append(
            f"D 成稿短于 baseline×{min_ratio:.0%}: {len(e_plain)} < {int(len(b_plain)*min_ratio)}"
        )
    e_paras = _paragraph_count(e_body)
    b_paras = _paragraph_count(b_body)
    if e_paras < b_paras:
        errors.append(f"D 段落数少于 baseline: {e_paras} < {b_paras}")
    return len(errors) == 0, errors


def verify_assemble_parts(intro: str, tail: str) -> Tuple[bool, List[str]]:
    """终稿装配：引入 + 结尾/总结字数。"""
    errors: List[str] = []
    intro = (intro or "").strip()
    tail = (tail or "").strip()
    if not intro:
        errors.append("缺少前置引入")
    elif not (60 <= len(intro) <= 250):
        errors.append(f"前置引入字数须在 60–250：当前 {len(intro)}")
    if not tail:
        errors.append("缺少结尾/总结")
    elif not (100 <= len(tail) <= 250):
        errors.append(f"结尾/总结字数须在 100–250：当前 {len(tail)}")
    return len(errors) == 0, errors


def verify_intro_only(intro: str) -> Tuple[bool, List[str]]:
    intro = (intro or "").strip()
    if not intro:
        return False, ["缺少前置引入"]
    if not (60 <= len(intro) <= 250):
        return False, [f"前置引入字数须在 60–250：当前 {len(intro)}"]
    return True, []


def verify_ending_only(tail: str) -> Tuple[bool, List[str]]:
    tail = (tail or "").strip()
    if not tail:
        return False, ["缺少结尾/总结"]
    if not (100 <= len(tail) <= 250):
        return False, [f"结尾/总结字数须在 100–250：当前 {len(tail)}"]
    return True, []


def verify_baseline_draft(
    entry_id: str,
    recalled: Dict[str, Any],
    baseline_path: Path,
    plan: Dict[str, Any] | None = None,
    *,
    mother_body: str = "",
) -> Tuple[bool, List[str]]:
    """C 阶段 baseline 质检：含引入/正文/结尾/参考著作（母本）。"""
    errors: List[str] = []
    if not baseline_path.is_file():
        return False, [f"缺少 baseline 成稿: {baseline_path}"]
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"baseline JSON 解析失败: {exc}"]

    if data.get("史略ID") != entry_id:
        errors.append(f"baseline 史略ID 不一致: {data.get('史略ID')!r}")

    detail = (data.get("翻译详情") or "").strip()
    if not detail:
        errors.append("baseline 翻译详情为空")
        return False, errors

    intro = str(data.get("前置引入") or "").strip()
    body = str(data.get("正文") or "").strip()
    tail = str(data.get("结尾") or "").strip()
    if not intro or not body or not tail:
        errors.append("baseline 缺少显式字段：前置引入/正文/结尾")

    ver = str(data.get("翻译版本") or "").strip()
    if not ver:
        errors.append("baseline 缺少「翻译版本」标注")

    if "参考著作" not in detail:
        errors.append("baseline 缺少「参考著作」节")
    errors.extend(_detect_reference_section_format(detail))

    if intro and (len(intro) < 40 or len(intro) > 400):
        errors.append(f"前置引入篇幅异常: {len(intro)} 字（建议 60–250）")

    body_for_checks = body or detail.split("参考著作", 1)[0].strip()
    errors.extend(_detect_summary_ending(body_for_checks))

    detail_body = detail.split("参考著作", 1)[0].strip()
    detail_paras = [p.strip() for p in detail_body.split("\n\n") if p.strip()]
    if intro and detail_paras and detail_paras[0] != intro:
        if intro in detail_paras[0] and len(detail_paras[0]) > len(intro) + 20:
            errors.append("baseline 前置引入与正文首段粘连，须程序分隔为独立段")
    if intro and body and len(detail_paras) >= 2:
        if detail_paras[0] != intro:
            errors.append("baseline 翻译详情首段须为前置引入")

    if mother_body:
        ok2, errs2 = verify_style_retains_structural(
            mother_body, body or body_for_checks
        )
        errors.extend(errs2)

    if plan:
        from lib.config import paths as _paths

        cov_ok, cov_errs = verify_mother_coverage(
            body or body_for_checks,
            plan,
            entry_id=entry_id,
            entry_name=str(recalled.get("史略名称") or ""),
            work_dir=_paths()["translate_work"],
        )
        if not cov_ok:
            errors.extend(
                [f"baseline {e}" for e in cov_errs if not str(e).startswith("[info]")]
            )

    return len(errors) == 0, errors


def verify_style_retains_structural(
    structural_text: str,
    styled_text: str,
    *,
    min_ratio: float | None = None,
) -> Tuple[bool, List[str]]:
    """B 相对 A 不得明显缩水（防润色丢段）。"""
    import os

    ratio = min_ratio
    if ratio is None:
        ratio = float(os.environ.get("TRANSLATE_STYLE_MIN_RATIO", "0.85"))
    a = re.sub(r"\s+", "", structural_text or "")
    b = re.sub(r"\s+", "", styled_text or "")
    if not a:
        return True, []
    if len(b) < int(len(a) * ratio):
        return False, [
            f"文风整饰后字数偏少: {len(b)} < A×{ratio:.0%}={int(len(a)*ratio)}（疑遗漏段落）"
        ]
    return True, []


def _allowed_mother_citation(title: str, mother_work: str) -> bool:
    if "史记" in title:
        return True
    core = re.sub(r"^\d+[A-Z]?", "", mother_work)
    return bool(core and core in title)


def _foreign_citations_in_mother(
    detail: str, mother_work: str, mother_src: str = ""
) -> List[str]:
    """Phase1 母本外书名：仅警告，不阻断。"""
    warnings: List[str] = []
    src_plain = re.sub(r"\s+", "", mother_src)
    for title in re.findall(r"《([^》]+)》", detail):
        if _allowed_mother_citation(title, mother_work):
            continue
        if title in src_plain or title.replace("·", "") in src_plain:
            continue
        warnings.append(_as_warn(f"Phase1 出现母本以外引用: 《{title}》"))
    return warnings


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

    翻译规则 §第零部分「必现词分级」：硬锚点须在正文中自然出现；软锚点由 coverage 验收。
    """
    from lib.gloss_rules import is_l0_word  # noqa: PLC0415
    from lib.mother_sentences import _MUST_GENERIC, is_midword_fragment  # noqa: PLC0415

    orig_plain = re.sub(r"\s+", "", orig)
    hard: List[str] = []
    soft: List[str] = []
    for raw in phrases:
        p = str(raw).strip()
        if not p or is_l0_word(p) or is_midword_fragment(p, orig):
            continue
        if p in _MUST_GENERIC:
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
        # 无硬无软时不把普通短语抬成硬锚点（易误拦白话意译）
        return [], []

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


def _must_phrase_hard_stats(
    detail: str,
    plan: Dict[str, Any],
    *,
    batch_mode: bool = False,
) -> Tuple[int, int, List[Tuple[str, List[str]]]]:
    """统计硬锚点全局命中：(总数, 命中数, [(M编号, 缺失词列表), …])。"""
    body = re.sub(r"\s+", "", detail)
    total = 0
    hits = 0
    by_sid: Dict[str, List[str]] = {}
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
        for p in hard:
            total += 1
            if _phrase_hit(p, body):
                hits += 1
            else:
                by_sid.setdefault(sid, []).append(p)
    misses = [(sid, ps) for sid, ps in by_sid.items() if ps]
    return total, hits, misses


def collect_must_phrase_misses(
    detail: str,
    plan: Dict[str, Any],
    *,
    limit: int = 12,
    batch_mode: bool = False,
) -> List[str]:
    """生成 Phase1 重试提示：列出缺失的硬锚点。"""
    lines: List[str] = []
    _total, _hits, misses = _must_phrase_hard_stats(
        detail, plan, batch_mode=batch_mode
    )
    for sid, missing in misses:
        if not missing:
            lines.append(f"- {sid}: 原词锚点覆盖不足，请对照原文摘句补全")
            continue
        shown = "、".join(missing[:4])
        if len(missing) > 4:
            shown += f" 等{len(missing)}个"
        lines.append(f"- {sid}: 译文须自然出现原词：{shown}")
        if len(lines) >= limit:
            break
    return lines


def _verify_must_phrases(
    detail: str,
    plan: Dict[str, Any],
    *,
    batch_mode: bool = False,
) -> List[str]:
    """硬锚点阻断：仅当全局命中率低于阈值时失败（非「任一 M 缺失即拦」）。

    分批模式下跳过 —— 合并后再做全局命中率校验。
    """
    if batch_mode:
        return []
    checklist = plan.get("母本逐句清单") or []
    if not checklist:
        return []

    total, hits, misses = _must_phrase_hard_stats(detail, plan, batch_mode=batch_mode)
    if total == 0:
        return []

    should_block, ratio, min_ratio, miss_count = _must_phrase_block_decision(
        total, hits, len(checklist)
    )
    if not should_block:
        return []

    sample_ids = [sid for sid, _ in misses[:6]]
    sid_hint = f"；如 {', '.join(sample_ids)}" if sample_ids else ""
    if total < _must_phrase_min_total_for_ratio():
        max_miss = _must_phrase_max_miss_absolute()
        return [
            f"必现词硬锚点缺失过多: {miss_count}/{total}（硬锚点总数<{_must_phrase_min_total_for_ratio()}，"
            f"用绝对阈值≥{max_miss}才阻断{sid_hint}）"
        ]
    return [
        f"必现词硬锚点命中率不足: {hits}/{total} ({ratio:.0%} < {min_ratio:.0%}{sid_hint}）"
    ]


def verify_enrich_draft(
    entry_id: str,
    recalled: Dict[str, Any],
    output_path: Path,
    plan: Dict[str, Any] | None = None,
    *,
    baseline_detail: str = "",
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

    if re.search(r"^本条\s*\d+\s*段（母本", detail) or "已读完" in detail[:120]:
        errors.append("正文含「喊数/进度汇报」元叙述，须删除后再落盘")

    errors.extend(_detect_markdown_bold(detail))
    errors.extend(_legend_quota_hard_errors(detail, recalled))

    for _code, message, _severity in ai_flavor_verify_issues(detail):
        errors.append(message)

    if "*参考著作*" not in detail and "参考著作" not in detail:
        errors.append("文末缺少「参考著作」列表")

    errors.extend(_detect_reference_section_format(detail))
    errors.extend(detect_forbidden_gloss(detail))
    errors.extend(_detect_dash_ending(detail))
    errors.extend(_detect_excessive_descriptive_refs(detail))
    errors.extend(_detect_summary_ending(detail))
    errors.extend(detect_adjacent_duplicate_paragraphs(detail))
    if baseline_detail.strip():
        ok_bl, bl_errs = verify_enrich_vs_baseline(detail, baseline_detail)
        if not ok_bl:
            errors.extend(bl_errs)

    return len(errors) == 0, errors


def verify_enrich_batch_slice(
    entry_id: str,
    recalled: Dict[str, Any],
    output_path: Path,
    *,
    batch_mother_text: str = "",
    batch_label: str = "",
) -> Tuple[bool, List[str]]:
    """Phase2 分批落盘质检（不含参考著作节；终检仍走 verify_output）。"""
    errors: List[str] = []
    if not output_path.is_file():
        return False, [f"缺少本批译稿: {output_path}"]
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"本批译稿 JSON 解析失败: {exc}"]

    if data.get("史略ID") not in (entry_id, None):
        errors.append(f"本批译稿 史略ID 不一致: {data.get('史略ID')!r}")

    detail = (data.get("翻译详情") or "").strip()
    if not detail:
        errors.append("本批翻译详情为空")
        return False, errors

    if re.search(r"^本条\s*\d+\s*段（母本", detail) or "已读完" in detail[:120]:
        errors.append("正文含「喊数/进度汇报」元叙述，须删除后再落盘")

    if "*参考著作*" in detail or detail.rstrip().endswith("参考著作"):
        errors.append("分批 Phase2 本批不应含「参考著作」节")

    errors.extend(_detect_markdown_bold(detail))
    errors.extend(detect_forbidden_gloss(detail))
    errors.extend(_detect_dash_ending(detail))

    wc = len(detail)
    src = _source_char_len(batch_mother_text)
    warn = translation_length_warning(
        wc, src, label=batch_label or "本批成稿"
    )
    if warn:
        _log_verify_warnings([warn])

    return len(errors) == 0, errors


def verify_output(
    entry_id: str,
    recalled: Dict[str, Any],
    output_dir: Path,
    plan: Dict[str, Any] | None = None,
    *,
    coverage: str = "strict",
    verify_mode: str = "full",
) -> Tuple[bool, List[str], List[str]]:
    """终检。coverage=report 时覆盖不足可降为工单；verify_mode=baseline 为母本降级稿。"""
    is_baseline = verify_mode == "baseline"
    coverage_report = str(coverage).strip().lower() == "report"
    errors: List[str] = list(verify_source_thickness(recalled))
    entry_name = str(recalled.get("史略名称") or "")
    output_path = resolve_output_path(entry_id, output_dir, entry_name)
    ok, data, load_errs = load_output(entry_id, output_dir, entry_name)
    errors.extend(load_errs)
    if not ok:
        return False, errors, []

    detail_raw = str(data.get("翻译详情") or "")
    if detail_raw:
        fixed, fix_changes = apply_attribution_fixes(detail_raw, recalled, plan)
        if fixed != detail_raw:
            data["翻译详情"] = fixed
            output_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"   🔧 终检引号校正: {', '.join(fix_changes[:5])}", flush=True)

    keys = set(data.keys())
    required = {"史略ID", "翻译详情", "史料原文"}
    allowed = required | {
        "原文出处",
        "翻译版本",
        "_baseline_meta",
        "_pipeline_meta",
        "_版本说明",
    }
    extra = keys - allowed
    missing = required - keys
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

    from lib.source_citation import build_source_citation

    expected_cite = build_source_citation(recalled)
    cite = data.get("原文出处")
    if expected_cite:
        if not isinstance(cite, str) or cite.strip() != expected_cite:
            errors.append(
                "原文出处与母本典籍篇名不一致（须为《史记五帝本纪》形态，禁止排序用卷号与「第X」次序）"
            )
    elif cite not in (None, ""):
        errors.append("原文出处应为空（无法从母本 source_file 解析典籍卷名）")

    if data.get("史略ID") != entry_id:
        errors.append(
            f"史略ID 不一致: 期望 {entry_id}，实际 {data.get('史略ID')!r}"
        )

    detail = (data.get("翻译详情") or "").strip()
    if not detail:
        errors.append("翻译详情为空")
    else:
        errors.extend(_detect_markdown_bold(detail))

        if re.search(r"^本条\s*\d+\s*段（母本", detail) or (
            detail.startswith("本条") and "已读完" in detail.split("\n", 1)[0]
        ):
            errors.append("正文含「喊数/进度汇报」元叙述，须删除")

        wc = len(detail)
        src_len = _source_char_len(str(expected_source or ""))
        warn = translation_length_warning(wc, src_len, label="成稿")
        if warn:
            _log_verify_warnings([warn])

        if not is_baseline:
            if "*参考著作*" not in detail and "参考著作" not in detail:
                errors.append("文末缺少「参考著作」列表")

        for pat in PLACEHOLDER_PATTERNS:
            if re.search(pat, detail, re.I):
                errors.append(f"含占位符: {pat}")

        for _code, message, _severity in ai_flavor_verify_issues(detail):
            errors.append(message)

        errors.extend(_legend_quota_hard_errors(detail, recalled))

        repeated = _repeated_long_paragraphs(detail)
        if repeated:
            errors.append(f"疑似重复段落/事件: {repeated[:2]}")
        errors.extend(detect_adjacent_duplicate_paragraphs(detail))

        tongjia_errs = _invalid_tongjia_annotations(detail)
        errors.extend(tongjia_errs)

        errors.extend(_detect_reference_section_format(detail))
        if not is_baseline:
            errors.extend(_detect_reference_granularity(detail))
        errors.extend(detect_forbidden_gloss(detail))
        errors.extend(_detect_dash_ending(detail))
        errors.extend(_detect_excessive_descriptive_refs(detail))
        errors.extend(_detect_single_sentence_paragraphs(detail))
        errors.extend(_detect_summary_ending(detail))
        short_q = count_short_quote_density(detail, threshold_len=4)
        short_q_limit = max(15, len(detail) // 95)
        if short_q >= short_q_limit:
            errors.append(
                f"「」引用宜以完整摘句、对话或并列句群为单位（当前 {short_q} 处，阈值 {short_q_limit}）"
            )

        if plan:
            if not is_baseline:
                errors.extend(_verify_plan_sources_in_detail(detail, plan))
            from lib.config import paths as _paths

            cov_ok, cov_errs = verify_mother_coverage(
                detail,
                plan,
                entry_id=entry_id,
                entry_name=entry_name,
                work_dir=_paths()["translate_work"],
            )
            if not cov_ok:
                cov_hard = [e for e in cov_errs if not str(e).startswith("[info]")]
                if coverage_report or is_baseline:
                    for w in cov_hard:
                        _log_verify_warnings([f"覆盖: {w}"])
                else:
                    errors.extend(cov_hard)
            else:
                for w in cov_errs:
                    if w.startswith("[info]"):
                        print(f"   ℹ️ {w[7:]}", flush=True)
                    elif w.startswith("[warn]"):
                        print(f"   ⚠️ {w[7:]}", flush=True)

    block_count = int(recalled.get("block_count") or 1)
    if block_count > 1 and not is_baseline:
        mother = recalled.get("母本著作") or ""
        mother_name = re.sub(r"^\d+[A-Z]?", "", mother)
        if mother_name and mother_name not in detail:
            if "参考著作" not in detail:
                errors.append("多源条目但正文/参考著作未体现母本")

    return _finalize_verify_errors(
        errors,
        verify_mode=verify_mode,
        coverage_report=coverage_report,
    )


def _finalize_verify_errors(
    errors: List[str],
    *,
    verify_mode: str = "full",
    coverage_report: bool = False,
) -> Tuple[bool, List[str], List[str]]:
    from lib.verify_tiers import partition_verify_errors

    blocks, tickets, logs = partition_verify_errors(
        errors,
        verify_mode=verify_mode,
        coverage_report=coverage_report,
    )
    for line in logs:
        if line.startswith("[info]"):
            print(f"   ℹ️ {line[7:]}", flush=True)
    for ticket in tickets:
        _log_verify_warnings([f"质检工单: {ticket}"])
    return len(blocks) == 0, blocks, tickets


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

    for _code, message, _severity in ai_flavor_verify_issues(text):
        errors.append(message)

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
    # plan 外部补全「采用:true」仅作写作提示，不强制每条都写入正文（避免 plan 脏数据误杀成稿）
    # 文末参考著作节中列出的书，须在正文有对应引用
    for title in _refs_from_detail_section(detail):
        if not _citation_present(f"《{title}》", detail, any_title=True):
            errors.append(f"参考著作节书目未在正文引用: 《{title}》")
    return errors
