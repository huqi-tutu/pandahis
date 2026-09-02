"""朝代知识补全 · 遗漏审阅提示词（可复制给其他大模型做查漏）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import dynasty_supplement_lib as dkl


def _strip_peerage_prefix(name: str) -> str:
    """酂侯萧何 → 萧何；夏侯等复姓不剥离。"""
    n = (name or "").strip()
    if not n or n.startswith("夏侯"):
        return n
    # 仅当「…侯 + 2–4 字名」时剥离封号，避免误伤复姓/单名
    m = re.match(r"^(.+?侯)([\u4e00-\u9fff]{2,4})$", n)
    if not m:
        return n
    return m.group(2)

CATEGORIES = ("事略", "典制", "论著")
PERSON_CATEGORIES = tuple(c for c in dkl.PERSON_CATEGORIES if c != "君王")
PROMPT_CATEGORIES = (*CATEGORIES, *PERSON_CATEGORIES)

# 各史略分类的笼统定义（帮助外部模型理解选条尺度，非逐条释义）
CATEGORY_GLOSS: dict[str, str] = {
    "事略": "本朝可独立成篇的重大事件或事态，一条一事；主语是「什么事」，不是人物传记。",
    "典制": "国家或共主强制落地的规则体系（谁管、怎么运作、违制后果），如分封、礼乐、刑罚。",
    "论著": "可点名的典籍、名篇或思想命题；主语是作品或学说，不是人，也不是制度或事件。",
    "诸侯": "分封诸侯国的世袭君主（列国国君），不是周天子。",
    "宗戚": "王室亲属、后妃、太后等同姓宗室人物。",
    "宦官": "以内官、阉人、近幸身份为主轴的人物。",
    "文臣": "以行政、谏诤、外交、史学等文事为主轴的仕宦人物。",
    "武将": "以征战、将帅、军功为主轴的人物。",
    "蕃祚": "方国、部族、边陲政权等集体条目（非个人传记）。",
    "庶众": "无王位、无封国，但以事迹载入史册的游侠、义人、平民等。",
}


def _name_from_row(row: dict[str, Any]) -> str:
    for k in ("名称", "史略名称"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def load_phase1_names(
    histograph_root: Path,
    dynasty_id: str,
    dynasty_name: str = "",
) -> dict[str, list[str]]:
    """一期史料标注（V2 全局索引 + 后汉三国合并索引）。"""
    index_paths = dkl.phase1_index_paths(histograph_root)
    out: dict[str, list[str]] = {c: [] for c in PROMPT_CATEGORIES}
    seen: dict[str, set[str]] = {c: set() for c in PROMPT_CATEGORIES}

    def _add(cat: str, name: str) -> None:
        if cat not in out or not name or name in seen[cat]:
            return
        seen[cat].add(name)
        out[cat].append(name)
        short = _strip_peerage_prefix(name)
        if short != name and short not in seen[cat]:
            seen[cat].add(short)
            out[cat].append(short)

    for index_path in index_paths:
        if not index_path.is_file():
            continue
        root = json.loads(index_path.read_text(encoding="utf-8"))
        entries = root.get("entries") if isinstance(root, dict) else root
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            if dkl.infer_entry_dynasty_id(e) != dynasty_id:
                continue
            cat = str(e.get("史略分类", "")).strip()
            name = str(e.get("史略名称", "")).strip()
            _add(cat, name)
    for cat in PROMPT_CATEGORIES:
        out[cat] = sorted(set(out[cat]), key=lambda x: (len(x), x))
    return out


def load_supplement06_names(
    histograph_root: Path,
    dynasty_id: str,
) -> dict[str, list[str]]:
    """06 朝代知识补全已入库条目（本朝）。"""
    out: dict[str, list[str]] = {c: [] for c in PROMPT_CATEGORIES}
    entries_dir = histograph_root / "data" / "06朝代知识补全" / "索引条目"
    if not entries_dir.is_dir():
        return out
    seen: dict[str, set[str]] = {c: set() for c in PROMPT_CATEGORIES}
    for fp in sorted(entries_dir.glob("*.json")):
        doc = json.loads(fp.read_text(encoding="utf-8"))
        rows = doc.get("entries") if isinstance(doc, dict) else doc
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            if str(e.get("朝代ID", "")).strip() != dynasty_id:
                continue
            cat = str(e.get("史略分类", "")).strip()
            name = _name_from_row(e)
            if cat in out and name and name not in seen[cat]:
                seen[cat].add(name)
                out[cat].append(name)
    for cat in PROMPT_CATEGORIES:
        out[cat] = sorted(set(out[cat]), key=lambda x: (len(x), x))
    return out


def load_candidates_names(paths: dict[str, Path]) -> dict[str, list[str]]:
    path = paths["candidates"]
    if not path.is_file():
        return {c: [] for c in PROMPT_CATEGORIES}
    doc = json.loads(path.read_text(encoding="utf-8"))
    cand = doc.get("candidates") or {}
    return {
        c: [_name_from_row(r) for r in (cand.get(c) or []) if isinstance(r, dict) and _name_from_row(r)]
        for c in PROMPT_CATEGORIES
    }


def load_filled_names(paths: dict[str, Path]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {c: [] for c in PROMPT_CATEGORIES}
    for path_key in ("entries", "entries_renwu"):
        p = paths.get(path_key)
        if not p or not p.is_file():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            if not isinstance(e, dict):
                continue
            cat = str(e.get("史略分类", "")).strip()
            name = _name_from_row(e)
            if cat in out and name:
                out[cat].append(name)
    return out


def _pick_source_names(paths: dict[str, Path], phase: str) -> dict[str, list[str]]:
    filled = load_filled_names(paths)
    if any(filled[c] for c in PROMPT_CATEGORIES) and phase in ("entries", "details", "auto"):
        return filled
    return load_candidates_names(paths)


def detect_phase(paths: dict[str, Path]) -> str:
    filled = load_filled_names(paths)
    if any(filled[c] for c in PROMPT_CATEGORIES):
        return "entries"
    if paths.get("candidates") and paths["candidates"].is_file():
        doc = json.loads(paths["candidates"].read_text(encoding="utf-8"))
        cand = doc.get("candidates") or {}
        if any(cand.get(c) for c in PROMPT_CATEGORIES):
            return "candidates"
    return "research"


def _format_names_block(
    by_cat: dict[str, list[str]],
    *,
    include_juwang: bool = True,
    names_per_line: int = 15,
) -> list[str]:
    lines: list[str] = []
    any_row = False
    for cat in PROMPT_CATEGORIES:
        if cat == "君王" and not include_juwang:
            continue
        names = by_cat.get(cat) or []
        if not names:
            continue
        any_row = True
        lines.append(f"【{cat}】共 {len(names)} 条：")
        for i in range(0, len(names), names_per_line):
            chunk = names[i : i + names_per_line]
            lines.append("、".join(chunk))
        lines.append("")
    if not any_row:
        lines.append("（暂无）")
    return lines


def build_omission_prompt(
    context: dict[str, Any],
    paths: dict[str, Path],
    *,
    histograph_root: Path,
    phase: str = "auto",
    trigger_step: str = "",
) -> str:
    del trigger_step  # 不写入提示词正文，避免复制时出现内部步骤标记
    if phase == "auto":
        phase = detect_phase(paths)

    dynasty_name = str(context.get("朝代名称") or "")
    start = context.get("开始时间", "")
    end = context.get("结束时间", "")
    dynasty_id = str(context.get("朝代ID") or "")

    extracted = _pick_source_names(paths, phase)
    phase1 = load_phase1_names(histograph_root, dynasty_id, dynasty_name=dynasty_name)
    supplement06 = load_supplement06_names(histograph_root, dynasty_id)
    supplement_cats = "、".join(PROMPT_CATEGORIES)

    lines: list[str] = [
        f"你是熟悉中国史的编辑。请帮我把「{dynasty_name}」（约 {start}—{end}）的朝代知识补全条目查漏。",
        "",
        "说明：下文列出我方已占用的全部史略名称（史料标注 + 本期候选 + 已入库补全）。请勿与其中任何名称重复（含同义、别名、爵号变体）。",
        "",
        "## 史略分类说明（我方选条尺度）",
        "",
        "君王由帝王表与史料标注覆盖，本次不需你补君王；但下表仍会列出已有君王名称供你对照勿重复。",
        "",
    ]
    for cat in PROMPT_CATEGORIES:
        gloss = CATEGORY_GLOSS.get(cat, "")
        lines.append(f"- {cat}：{gloss}")
    lines.append("")

    lines.extend(
        [
            "## 一、史料标注已有（二十四史卷级提取 · 请勿重复）",
            "",
            "来源：10新标注条目全局索引（含后汉书等已标注卷）。",
            "",
        ]
    )
    lines.extend(_format_names_block(phase1, include_juwang=True))
    lines.append("")

    lines.extend(
        [
            "## 二、本期朝代知识补全候选（研究/候选步骤已产出 · 请勿重复）",
            "",
            "来源：本朝候选清单（事略/典制/论著/人物六类）。",
            "",
        ]
    )
    lines.extend(_format_names_block(extracted, include_juwang=False))
    lines.append("")

    if any(supplement06[c] for c in PROMPT_CATEGORIES):
        lines.extend(
            [
                "## 三、已入库朝代知识补全（06 · 请勿重复）",
                "",
            ]
        )
        lines.extend(_format_names_block(supplement06, include_juwang=False))
        lines.append("")

    lines.extend(
        [
            "## 请你补充",
            "",
            f"除上文已列名称外，还有哪些史略值得补？请按分类（{supplement_cats}）列出名称，每条附一句理由。",
            "不要补君王。",
            "",
            "入选标准：",
            "- 够重要：通史里常单独成段、后世常提起；",
            "- 有记忆点：读者能用一个标签记住；",
            "- 粒度适中：一条一个主题，不要太细。",
            "",
            "若无补充，直接回复「无」。",
            "",
            "## 跨朝代归属（硬纪律）",
            "",
            "除君王、诸侯（以即位年定归属）外，每条须先估算 pick year：峰值年 / 立国或封制年 / 成书年 / 事件高潮年，取最能代表该条历史重心的一年。",
            f"仅列 pick year 落在 {dynasty_name}（约 {start}—{end}）区间内的条目；若应归相邻朝代，不得列出。",
            "",
            "典型错误：把主要活动或成书年代在下一朝的人物、事略、典制、论著塞进本朝。",
            "相邻朝已建条：王莽已在新朝以君王建条，勿再补人物「王莽」。",
        ]
    )
    return "\n".join(lines)


def write_omission_prompt_report(
    context: dict[str, Any],
    paths: dict[str, Path],
    *,
    histograph_root: Path,
    phase: str = "auto",
    trigger_step: str = "",
) -> Path:
    out_path = paths["omission_prompt"]
    body = build_omission_prompt(
        context,
        paths,
        histograph_root=histograph_root,
        phase=phase,
        trigger_step=trigger_step,
    )
    header = f"{context.get('朝代名称', '')} · 遗漏审阅提示词（复制全文到其他模型即可，勿含链接）\n\n"
    out_path.write_text(header + body + "\n", encoding="utf-8")
    return out_path
