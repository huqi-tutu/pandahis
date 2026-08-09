"""原文段落切分与路径解析（annotate / check_format / pipeline 共用）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from lib_config import get_histograph_root, paths

# 著作前缀 → 切分模式（indent=全角缩进行；line=非空行，用于史记等）
WORK_SPLIT_MODE = {
    "01史记": "line",  # 拆分 txt 按行分段；勿因少量全角缩进误判 indent
    "01A尚书": "line",  # 已归一化（无全角缩进），与史记统一
    "02汉书": "line",
    "03后汉书": "line",
}

YUANWEN_MARK = "【原文】"
CHRONO_HEADER_RE = re.compile(r"^起.+尽.+凡.+年")
VOLUME_MARKER_RE = re.compile(r"^[●◆■]?\s*卷")
PURE_BRACKET_RE = re.compile(r"^【[^】]+】$")
PART_SUBTITLE_RE = re.compile(
    r"^.+传第[一二三四五六七八九十百零廿卅]+[上下]?$",
)
SECTION_BOOK_RE = re.compile(r"^[虞夏商周][书][　\s]")
BENJI_RE = re.compile(r"^.+本纪第?[一二三四五六七八九十百]+")
SHIJIA_RE = re.compile(r"^.+世家第?[一二三四五六七八九十百]+")
NARRATIVE_STARTERS = (
    "帝",
    "王",
    "公",
    "太",
    "於是",
    "于是",
    "初",
    "禹",
    "尧",
    "舜",
    "黄",
    "陈",
    "魏",
    "秦",
    "汉",
    "武",
    "高",
    "项",
    "孔",
    "夫",
    "子",
    "先",
    "昔",
    "曰",
)


def split_mode_for_work(work: str, sample_text: str = "") -> str:
    if work in WORK_SPLIT_MODE:
        return WORK_SPLIT_MODE[work]
    if "尚书" in work:
        return "indent"
    if sample_text and sample_text.count("　　") >= 3:
        return "indent"
    return "line"


def _looks_like_narrative_body(text: str) -> bool:
    """正文特征：有句号/逗号长句，或以叙事起句。"""
    t = text.strip()
    if len(t) < 6:
        return False
    if "。" in t or ("，" in t and len(t) >= 10):
        return True
    return any(t.startswith(s) for s in NARRATIVE_STARTERS)


def _looks_like_standalone_volume_heading(text: str) -> bool:
    """独立卷名行（无【】）：如 ●卷第二百九十三、五帝本纪第一。"""
    t = text.strip()
    if len(t) > 48 or "。" in t:
        return False
    if VOLUME_MARKER_RE.match(t):
        return True
    if BENJI_RE.match(t) or SHIJIA_RE.match(t):
        return True
    if re.match(r"^.+纪第?[一二三四五六七八九十百]+", t) and len(t) <= 24:
        return True
    return False


def _is_file_metadata_line(text: str) -> bool:
    t = text.strip()
    return t.startswith("【此卷") or ("流芳阁" in t and "校对" in t)


# 粘连正文常见起句（用于从篇名后切开）
_GLUE_BODY_RE = re.compile(
    r"(?=禹别|禹|尧|舜|黄帝|陈胜|魏之|秦|汉|武帝|帝|王|曰|昔|初|乃|既|太|夫|子|先|世宗|高|项)"
)


def _split_yuanwen_remainder(remainder: str) -> Tuple[str, str]:
    """
    【原文】后的余文拆为 (篇名后缀, 正文)。
    返回 ('夏书　　禹贡', '') → 整行皆标题；
    返回 ('夏书　　禹贡', '禹别九州…') → 标题与正文粘连须拆开。
    """
    r = remainder.strip()
    if not r:
        return "", ""

    # 篇名与正文粘连：夏书　　禹贡 + 禹别九州…
    gm = re.match(
        r"^([虞夏商周][书][　\s]*(?:[^，。；！？\s]+?))" + _GLUE_BODY_RE.pattern,
        r,
    )
    if gm:
        head = gm.group(1).strip()
        tail = r[len(head) :].strip()
        if tail and _looks_like_narrative_body(tail):
            return head, tail

    if not _looks_like_narrative_body(r):
        return r, ""

    return "", r


def decompose_line_to_paragraphs(line: str) -> List[str]:
    """
    将文件中的一行拆为 1–N 个段落。
    处理：独立【原文】、篇名+正文粘连、【纪名】+纪年、【纪名】+正文、●卷标题 等。
    """
    s = line.strip()
    if not s or _is_file_metadata_line(s):
        return []

    if s.startswith(YUANWEN_MARK):
        rem = s[len(YUANWEN_MARK) :]
        title_suf, body = _split_yuanwen_remainder(rem)
        if not title_suf and not body:
            return [YUANWEN_MARK]
        if title_suf and not body:
            return [YUANWEN_MARK + title_suf]
        if not title_suf and body:
            return [YUANWEN_MARK, body]
        return [YUANWEN_MARK + title_suf, body]

    m = re.match(r"^(【[^】]+】)(.*)$", s)
    if m:
        head, tail = m.group(1), m.group(2).strip()
        if not tail:
            return [head]
        if CHRONO_HEADER_RE.match(tail):
            return [head, tail]
        if _looks_like_narrative_body(tail):
            return [head, tail]
        return [s]

    if _looks_like_standalone_volume_heading(s):
        return [s]

    return [s]


def is_volume_title_paragraph(text: str) -> bool:
    """计段但不做条目归属的卷首标题段。"""
    t = text.strip()
    if not t:
        return False
    if t == YUANWEN_MARK:
        return True
    if t.startswith(YUANWEN_MARK):
        rem = t[len(YUANWEN_MARK) :].strip()
        return not rem or not _looks_like_narrative_body(rem)
    if PURE_BRACKET_RE.match(t):
        return True
    if VOLUME_MARKER_RE.match(t) and not _looks_like_narrative_body(t):
        return True
    if _looks_like_standalone_volume_heading(t):
        return True
    return False


def normalize_heading_text(text: str) -> str:
    """去掉空白与段尾私用区/乱码，便于篇名行匹配。"""
    raw = re.sub(r"\s+", "", (text or "").strip())
    raw = re.sub(r"[\ue000-\uf8ff\ufffd]+.*", "", raw)
    return raw


def is_part_subtitle_paragraph(text: str) -> bool:
    """篇内小标题（如「西域传第六十六上」）：计段但不建 entry。"""
    raw = normalize_heading_text(text)
    if not raw or len(raw) > 28 or "。" in raw:
        return False
    return bool(PART_SUBTITLE_RE.match(raw))


def is_chronology_header_paragraph(text: str) -> bool:
    return bool(CHRONO_HEADER_RE.match(text.strip()))


def classify_paragraph_header(text: str) -> Optional[str]:
    """
    头段分类（用于 check_format 硬检）。
    返回 '卷首标题' | '篇内小标题' | '纯纪年' | None（正文段）。
    """
    if is_volume_title_paragraph(text):
        return "卷首标题"
    if is_part_subtitle_paragraph(text):
        return "篇内小标题"
    if is_chronology_header_paragraph(text):
        return "纯纪年"
    return None


def is_volume_title_line(text: str) -> bool:
    """兼容旧调用：是否为卷首标题段。"""
    return is_volume_title_paragraph(text)


def split_paragraphs(text: str, mode: str = "indent") -> List[str]:
    """按著作切分规则返回段落纯文本列表（段号从 1 起对应）。"""
    main = text.split("=" * 20)[0]
    paras: List[str] = []

    if mode == "indent":
        for line in main.splitlines():
            raw = line.strip()
            if not raw:
                continue
            if line.startswith("　　"):
                content = line.lstrip("　　").strip()
                for part in decompose_line_to_paragraphs(content):
                    paras.append(part)
            elif not paras:
                # 卷首非缩进行（【原文】、卷号等）
                for part in decompose_line_to_paragraphs(raw):
                    paras.append(part)
        return paras

    for line in main.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^[=─\-]+$", s):
            continue
        for part in decompose_line_to_paragraphs(s):
            paras.append(part)
    return paras


def work_from_skeleton_path(skeleton: Path) -> str:
    """01A尚书_058_周书_秦誓_skeleton.json → 01A尚书"""
    stem = skeleton.stem.replace("_skeleton", "")
    m = re.match(r"^(\d{1,2}[A-Za-z\u4e00-\u9fff]+)_\d{3}_", stem)
    if m:
        return m.group(1)
    m2 = re.match(r"^([^_]+)_\d{3}_", stem)
    return m2.group(1) if m2 else stem.split("_")[0]


def vol_from_skeleton_path(skeleton: Path) -> str:
    m = re.search(r"_(\d{3})_", skeleton.name)
    return m.group(1) if m else "000"


def resolve_source_file(
    data: dict,
    skeleton: Optional[Path] = None,
) -> Optional[Path]:
    """定位原文 .txt；容忍 skeleton 中错误的 source_file / 原文路径。"""
    root = get_histograph_root()
    data_root = paths()["data"]

    candidates: List[Path] = []
    for key in ("原文路径", "source_file"):
        rel = data.get(key)
        if not rel:
            continue
        p = Path(rel)
        if p.is_absolute():
            candidates.append(p)
        else:
            candidates.append(data_root / p)
            candidates.append(paths()["sources"] / p.name)
            # 兼容旧路径：data/02二十四史拆分后/...
            if "二十四史拆分后" in str(p):
                tail = Path(str(p).split("二十四史拆分后/")[-1])
                candidates.append(paths()["sources"] / tail)
            candidates.append(root / "史料合集" / p)
            candidates.append(root / "史料合集" / "二十四史拆分后" / p.name)

    if skeleton:
        work = work_from_skeleton_path(skeleton)
        vol = vol_from_skeleton_path(skeleton)
        src_root = paths()["sources"]
        for sub in sorted(src_root.iterdir()):
            if not sub.is_dir():
                continue
            if work not in sub.name and not sub.name.startswith(work):
                continue
            for f in sorted(sub.glob(f"*_{vol}_*.txt")):
                candidates.append(f)
            for f in sorted(sub.glob(f"{work}_{vol}_*.txt")):
                candidates.append(f)

    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        if c.is_file():
            return c
    return None


def count_source_paragraphs(
    source: Path,
    work: Optional[str] = None,
) -> Tuple[int, str, List[str]]:
    text = source.read_text(encoding="utf-8")
    mode = split_mode_for_work(work or "", text)
    paras = split_paragraphs(text, mode)
    return len(paras), mode, paras


def check_paragraph_count(
    data: dict,
    skeleton: Path,
    *,
    strict_works: Optional[set] = None,
) -> Tuple[bool, str, int, int]:
    """
    返回 (ok, message, declared, actual)。
    strict_works 内的著作：段数不等即失败；其余著作段数不等仅告警（史记等待对齐）。
    """
    if strict_works is None:
        strict_works = {"01A尚书", "02汉书"}

    declared = int(data.get("total_paragraphs", 0))
    attr = data.get("segment_attribution", [])
    source = resolve_source_file(data, skeleton)
    if not source:
        work = work_from_skeleton_path(skeleton)
        if work in strict_works:
            return False, "无法定位原文文件，不能校验段落数", declared, -1
        return True, "未找到原文，跳过段落数校验", declared, -1

    work = work_from_skeleton_path(skeleton)
    actual, mode, _ = count_source_paragraphs(source, work)

    # 压扁模板：无论著作是否在 strict_works，一律硬失败
    if actual >= 4 and declared <= 3:
        return (
            False,
            f"疑似压扁段落索引/模板：原文 {actual} 段却标为 {declared} 段，须重建段落索引并逐段重标",
            declared,
            actual,
        )

    if declared != actual:
        msg = (
            f"total_paragraphs={declared} ≠ 原文实际 {actual} 段 "
            f"(模式={mode}, 文件={source.name})"
        )
        if work in strict_works:
            return False, msg, declared, actual
        return True, f"⚠️ {msg}", declared, actual

    if len(attr) != actual:
        msg = f"segment_attribution 行数 {len(attr)} ≠ 原文实际 {actual} 段"
        if work in strict_works:
            return False, msg, declared, actual
        return True, f"⚠️ {msg}", declared, actual

    return True, f"段落数一致: {actual} 段 (模式={mode})", declared, actual
