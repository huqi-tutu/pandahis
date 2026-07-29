"""朝代知识补全 · 遗漏审阅提示词（可复制给其他大模型做查漏）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import dynasty_supplement_lib as dkl

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


def load_phase1_names(histograph_root: Path, dynasty_id: str) -> dict[str, list[str]]:
    index_path = histograph_root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    out: dict[str, list[str]] = {c: [] for c in PROMPT_CATEGORIES}
    if not index_path.is_file():
        return out
    root = json.loads(index_path.read_text(encoding="utf-8"))
    entries = root.get("entries") if isinstance(root, dict) else root
    if not isinstance(entries, list):
        return out
    for e in entries:
        if not isinstance(e, dict):
            continue
        if str(e.get("朝代ID", "")).strip() != dynasty_id:
            continue
        cat = str(e.get("史略分类", "")).strip()
        name = str(e.get("史略名称", "")).strip()
        if cat in out and name:
            out[cat].append(name)
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


def _format_names_block(by_cat: dict[str, list[str]]) -> list[str]:
    lines: list[str] = []
    any_row = False
    for cat in PROMPT_CATEGORIES:
        names = by_cat.get(cat) or []
        if not names:
            continue
        any_row = True
        lines.append(f"**{cat}**：{'、'.join(names)}")
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
    if phase == "auto":
        phase = detect_phase(paths)

    dynasty_name = str(context.get("朝代名称") or "")
    start = context.get("开始时间", "")
    end = context.get("结束时间", "")
    dynasty_id = str(context.get("朝代ID") or "")

    extracted = _pick_source_names(paths, phase)
    phase1 = load_phase1_names(histograph_root, dynasty_id)
    supplement_cats = "、".join(PROMPT_CATEGORIES)

    lines: list[str] = [
        f"你是熟悉中国史的编辑。请帮我把**{dynasty_name}**（约 {start}—{end}）的「朝代知识补全」条目查漏。",
        "",
        "## 史略分类说明（我方选条尺度）",
        "",
        "以下解释每一类史略**泛指什么**；君王由帝王表与一期标注覆盖，**本次不需你补君王**。",
        "",
    ]
    for cat in PROMPT_CATEGORIES:
        gloss = CATEGORY_GLOSS.get(cat, "")
        lines.append(f"- **{cat}**：{gloss}")
    lines.append("")

    lines.extend(
        [
            "## 我已提取的史略（本期 · 仅名称）",
            "",
        ]
    )
    lines.extend(_format_names_block(extracted))
    lines.append("")

    if any(phase1[c] for c in PROMPT_CATEGORIES):
        lines.extend(
            [
                "## 一期卷级标注已有（仅名称 · 同样勿重复）",
                "",
            ]
        )
        lines.extend(_format_names_block(phase1))
        lines.append("")

    lines.extend(
        [
            "## 请你补充",
            "",
            f"除上列名称以外，**还有哪些史略值得补？** 请按分类（{supplement_cats}）列出**名称**，每条附一句理由。",
            "**不要补君王。**",
            "",
            "**入选标准**：",
            "- **够重要**：通史里常单独成段、后世常提起；",
            "- **有记忆点**：读者能用一个标签记住；",
            "- **粒度适中**：一条一个主题，不要太细。",
            "",
            "**请勿重复**上文已列的任何名称（含同义、别名）。若无补充，直接说「无」。",
            "",
            "## 跨朝代归属（硬纪律）",
            "",
            "除**君王/诸侯**（以**即位年**定归属）外，每条须先估算 **pick year**（峰值年 / 立国封制年 / 成书年 / 事件高潮年，见 `跨朝代归属规则.md`）。",
            f"**仅列 pick year 落在 {dynasty_name}（约 {start}—{end}）区间内的条目**；若应归相邻朝代，**不得列出**。",
            "",
            "**典型错误**：把 pick year 主要落在下一朝的人物/事略/典制/论著塞进本朝（如跑批战国时误列李斯、吕不韦、蒙恬、秦灭六国统一等应归秦者）。",
        ]
    )
    if trigger_step:
        lines.append("")
        lines.append(f"（生成步骤：{trigger_step}）")
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
    header = (
        f"<!-- {context.get('朝代名称', '')} · 遗漏审阅 · 复制正文到其他模型即可 -->\n\n"
    )
    out_path.write_text(header + body + "\n", encoding="utf-8")
    return out_path
