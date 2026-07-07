"""翻译产出质检。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.coverage import verify_mother_coverage
from lib.source_text import build_source_original, source_original_fingerprint

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

    if "*参考著作*" in detail or detail.rstrip().endswith("参考著作"):
        errors.append("Phase1 不应含「参考著作」节")

    mother_work = str(recalled.get("母本著作") or "")
    mother_src = _mother_source_text(recalled)
    errors.extend(_foreign_citations_in_mother(detail, mother_work, mother_src))

    if plan:
        errors.extend(_verify_must_phrases(detail, plan))
        cov_ok, cov_errs = verify_mother_coverage(detail, plan)
        if not cov_ok:
            errors.extend([f"母本顺译 {e}" for e in cov_errs])

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
    p = str(phrase).strip()
    if not p:
        return True
    if p in body:
        return True
    if f"「{p}」" in body:
        return True
    for m in re.finditer(r"「([^」]+)」", body):
        if p in m.group(1):
            return True
    plain = re.sub(r"[「」『』\s]", "", body)
    pi = 0
    for ch in plain:
        if pi < len(p) and ch == p[pi]:
            pi += 1
    if pi == len(p) and len(p) >= 2:
        return True
    return False


def _hard_must_phrases(phrases: List[Any], orig: str) -> List[str]:
    """从必现词中筛硬锚点；优先专名、数字、原文连续片段。"""
    from lib.mother_sentences import _MUST_GENERIC  # noqa: PLC0415

    orig_plain = re.sub(r"\s+", "", orig)
    hard: List[str] = []
    for raw in phrases:
        p = str(raw).strip()
        if not p:
            continue
        if re.search(r"\d", p):
            hard.append(p)
            continue
        if "氏" in p and len(p) >= 2:
            hard.append(p)
            continue
        if len(p) >= 4 and p in orig_plain:
            hard.append(p)
            continue
        if len(p) >= 3 and p in orig_plain and p not in _MUST_GENERIC:
            hard.append(p)
    if not hard:
        hard = [str(p) for p in phrases if len(str(p).strip()) >= 3][:3]
    return hard


def _verify_must_phrases(detail: str, plan: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    body = re.sub(r"\s+", "", detail)
    weak: List[str] = []
    checklist = plan.get("母本逐句清单") or []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("编号") or "")
        orig = str(item.get("原文摘句") or "")
        phrases = item.get("必现词") or []
        if not isinstance(phrases, list) or not phrases:
            continue
        hard = _hard_must_phrases(phrases, orig)
        hits = sum(1 for p in hard if _phrase_hit(p, body))
        ratio = hits / len(hard) if hard else 1.0
        if ratio < 0.34:
            weak.append(sid)
    if len(weak) >= max(3, len(checklist) // 5):
        errors.append(
            f"必现词命中不足: {len(weak)} 条 M 未保留母本原词锚点"
            f"（如 {', '.join(weak[:6])}）"
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
    if not isinstance(source, dict):
        errors.append("史料原文缺失或格式无效")
    elif source_original_fingerprint(source) != source_original_fingerprint(
        expected_source
    ):
        errors.append("史料原文与召回母本/索引补充不一致（须由编排器写入，禁止 LLM 改写）")
    elif not (source.get("text") or "").strip():
        errors.append("史料原文.text 为空")

    if data.get("史略ID") != entry_id:
        errors.append(
            f"史略ID 不一致: 期望 {entry_id}，实际 {data.get('史略ID')!r}"
        )

    detail = (data.get("翻译详情") or "").strip()
    if not detail:
        errors.append("翻译详情为空")
    else:
        if re.search(r"^本条\s*\d+\s*段（母本", detail) or (
            detail.startswith("本条") and "已读完" in detail.split("\n", 1)[0]
        ):
            errors.append("正文含「喊数/进度汇报」元叙述，须删除")

        wc = len(detail)
        para_count = int(recalled.get("paragraph_count") or 1)
        para_floor = min_word_count(para_count)
        src_len = len(re.sub(r"\s+", "", str(expected_source.get("text") or "")))
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

        if plan:
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


    # --- 前置引入检查 ---
    has_intro_intro = False
    first_para = detail.split("\n\n")[0].strip() if "\n\n" in detail else detail[:200]
    # 检查第一段是否包含朝代/时代/身份类词（表明有人物定位）
    intro_keywords = re.findall(
        r"[夏商周秦汉魏晋南北隋唐宋元明清]|"
        r"世纪|时代|公元前|时期|即位|君主|天子|帝王|诸侯|"
        r"首领|领袖|君王|贵族|名臣|名将|宰相|大臣|始祖",
        first_para,
    )
    # 如果第一段包含直接引自母本的内容（《》引用 + 母本原文片段）但无定位词，视为缺引入
    has_direct_citation = bool(re.search(r"《[^》]+》[记载写说]", first_para[:150]))
    if has_direct_citation and len(intro_keywords) < 1:
        errors.append("正文开头缺少前置引入：建议在顺译前先写一段人物背景介绍。")


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
