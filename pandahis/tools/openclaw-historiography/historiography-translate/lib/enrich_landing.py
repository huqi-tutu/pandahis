"""Phase2 外部补全落地：逐条验收 + 章级清单 + 定向补洞（L2）。

设计目标：
- plan 采用项必须逐条进正文（出处《》+ 主题指纹），禁止「见过任意一本他书」过关
- 分章 plan 去掉 `采用` 后仍可识别须落地项
- 漏嵌时优先小范围补洞，避免整章重写烧 Token
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 常见增量词（出现在「主题/与母本关系」时优先抽作指纹）
_THEME_SEEDS = (
    "豁达大度",
    "郡国并行",
    "斩蛇起义",
    "约法三章",
    "背关怀楚",
    "放逐义帝",
    "入关约法",
    "任贤使能",
    "孤立之败",
    "蛟龙",
    "已而有娠",
    "宽仁爱人",
    "意豁如也",
    "正统",
    "唐帝",
    "同姓",
    "感生",
    "梦与神遇",
    "盐铁",
    "均输",
    "平准",
    "卫青",
    "霍去病",
    "封狼居胥",
    "轮台",
    "罪己",
)


def enrich_patch_max() -> int:
    """每章定向补洞最大次数（不含整章重写）。"""
    return max(0, int(os.environ.get("TRANSLATE_ENRICH_PATCH_MAX", "2")))


def _is_external_must_land(item: Dict[str, Any]) -> bool:
    """外部补全是否须落地。

    - 原始 plan：仅 `采用:true`
    - enrich 切片：已过滤为采用项并去掉 `采用` → 有出处即须落地
    - 显式 `采用:false` / `_须落地:false` → 不检
    """
    if not isinstance(item, dict):
        return False
    if item.get("_须落地") is False or item.get("采用") is False:
        return False
    if item.get("采用") is True or item.get("_须落地") is True:
        return bool(str(item.get("出处") or "").strip())
    if "采用" not in item and "_须落地" not in item:
        return bool(str(item.get("出处") or "").strip())
    return False


def _source_titles(src: str) -> List[str]:
    src = str(src or "").strip()
    if not src:
        return []
    found = re.findall(r"《([^》]+)》", src)
    if found:
        return [t.strip() for t in found if t.strip()]
    plain = src.strip("《》").strip()
    return [plain] if plain else []


def extract_landing_keywords(item: Dict[str, Any]) -> List[str]:
    """从主题/与母本关系抽 2～4 个验收指纹（宜短、宜稳）。"""
    theme = str(item.get("主题") or "").strip()
    rel = str(item.get("与母本关系") or "").strip()
    reason = str(item.get("理由") or "").strip()
    blob = f"{theme}。{rel}。{reason}"
    out: List[str] = []
    skip = {
        "汉武帝",
        "时期",
        "政策",
        "任用",
        "战功",
        "对比",
        "评价",
        "活动",
        "经济",
        "及其",
    }

    def _add(w: str) -> None:
        w = w.strip().strip("「」『』\"“”")
        if len(w) < 2 or len(w) > 12 or w in out or w in skip:
            return
        if w == theme and len(theme) > 12:
            return
        out.append(w)

    for m in re.findall(r"[「『\"“]([^」』\"”]{2,16})[」』\"”]", blob):
        _add(m)
    for seed in _THEME_SEEDS:
        if seed in blob:
            _add(seed)
    # 专名优先：2–4 字（卫青、霍去病、盐铁、均输…）
    for m in re.findall(r"[\u4e00-\u9fff]{2,4}", theme):
        _add(m)
        if len(out) >= 4:
            break
    if len(out) < 2:
        for m in re.findall(r"[\u4e00-\u9fff]{4,8}", re.sub(r"[、，,（）()]", "", theme)):
            _add(m)
            if len(out) >= 4:
                break
    return out[:4]


def iter_external_landing_items(plan: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    """须逐条验收的外部补全项（含规范化字段）。"""
    if not plan:
        return []
    rows: List[Dict[str, Any]] = []
    for i, item in enumerate(plan.get("外部补全") or []):
        if not _is_external_must_land(item):
            continue
        src = str(item.get("出处") or "").strip()
        titles = _source_titles(src)
        if not titles:
            continue
        kws = extract_landing_keywords(item)
        # 允许 plan 预填验收词
        extra = item.get("验收关键词") or item.get("须出现")
        if isinstance(extra, list):
            for x in extra:
                s = str(x).strip()
                if s and s not in kws:
                    kws.append(s)
            kws = kws[:6]
        elif isinstance(extra, str) and extra.strip():
            for x in re.split(r"[,，、|;；]", extra):
                s = x.strip()
                if s and s not in kws:
                    kws.append(s)
            kws = kws[:6]
        rows.append(
            {
                "index": i,
                "kind": "外部补全",
                "主题": str(item.get("主题") or "").strip() or f"补全#{i}",
                "出处": src if src.startswith("《") else f"《{src.strip('《》')}》",
                "titles": titles,
                "keywords": kws,
                "母本锚点": str(item.get("母本锚点") or item.get("锚点") or "").strip(),
                "与母本关系": str(item.get("与母本关系") or "").strip(),
                "raw": item,
            }
        )
    return rows


def iter_index_landing_titles(plan: Dict[str, Any] | None) -> List[str]:
    """索引「引入|异说」：只按出处书名去重要求出现（不抽主题指纹）。"""
    if not plan:
        return []
    titles: List[str] = []
    for item in plan.get("索引补充处理") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("处理") or "").strip() not in ("引入", "异说"):
            continue
        for t in _source_titles(str(item.get("出处") or "")):
            if t not in titles:
                titles.append(t)
    return titles


def cross_book_title_hit(required: str, body_books: List[str]) -> bool:
    """出处与正文《》是否对上（允许卷名省略/包含）。"""
    req = required.strip().strip("《》")
    if not req:
        return False

    def _norm(s: str) -> str:
        s = re.sub(r"第[一二三四五六七八九十百零〇\d]+[上下]?", "", s)
        return s.replace(" ", "")

    req_n = _norm(req)
    req_tail = req.split("·")[-1]
    req_tail_n = _norm(req_tail)
    for b in body_books:
        bn = _norm(b)
        if req == b or req_n == bn or req in b or b in req or req_n in bn or bn in req_n:
            return True
        if req_tail_n and len(req_tail_n) >= 2 and req_tail_n in bn:
            return True
        if "·" in req and req.split("·", 1)[0] == b:
            return True
        if "·" in req and "·" in b and req.split("·", 1)[0] == b.split("·", 1)[0]:
            if _norm(req.split("·", 1)[1]) in _norm(b.split("·", 1)[1]) or _norm(
                b.split("·", 1)[1]
            ) in _norm(req.split("·", 1)[1]):
                return True
    return False


def _body_books(detail: str) -> List[str]:
    body = str(detail or "").split("参考著作")[0]
    return re.findall(r"《([^》]+)》", body)


def check_item_landing(detail: str, item: Dict[str, Any]) -> Tuple[bool, str]:
    """单条外部补全：须出处命中；有指纹时至少命中 1 个关键词。"""
    body = str(detail or "").split("参考著作")[0]
    books = _body_books(detail)
    titles: List[str] = list(item.get("titles") or [])
    if not any(cross_book_title_hit(t, books) for t in titles):
        src = item.get("出处") or (titles[0] if titles else "?")
        return False, f"缺出处 {src}"
    kws: List[str] = list(item.get("keywords") or [])
    if kws and not any(k in body for k in kws):
        return False, f"已挂出处但缺主题指纹（须含其一：{'、'.join(kws[:4])}）"
    return True, ""


def missing_landing_items(
    detail: str, plan: Dict[str, Any] | None
) -> List[Dict[str, Any]]:
    """未落地的外部补全项（带 miss_reason）。"""
    miss: List[Dict[str, Any]] = []
    for item in iter_external_landing_items(plan):
        ok, reason = check_item_landing(detail, item)
        if not ok:
            miss.append({**item, "miss_reason": reason})
    return miss


def missing_index_titles(detail: str, plan: Dict[str, Any] | None) -> List[str]:
    books = _body_books(detail)
    return [t for t in iter_index_landing_titles(plan) if not cross_book_title_hit(t, books)]


def cross_book_landing_errors(
    detail: str, plan: Dict[str, Any] | None, *, label: str
) -> List[str]:
    """逐条硬失败（外部补全逐项 + 索引异说按书名）。"""
    if not plan:
        return []
    errors: List[str] = []
    for item in missing_landing_items(detail, plan):
        theme = item.get("主题") or "?"
        anchor = item.get("母本锚点") or "（无锚点）"
        reason = item.get("miss_reason") or "未落地"
        errors.append(
            f"{label}：外部补全未落地「{theme}」@ {anchor} — {reason}；"
            f"请按锚点写入差异点并出现 {item.get('出处')}"
        )
    for t in missing_index_titles(detail, plan):
        errors.append(
            f"{label}：索引引入/异说须出现《{t}》；请按锚点写入差异点，禁止整卷复述母本"
        )
    return errors


def format_landing_checklist_note(plan: Dict[str, Any] | None) -> str:
    """章/批 prompt 追加：本章须落地清单。"""
    items = iter_external_landing_items(plan)
    if not items:
        return ""
    lines = [
        "",
        f"【本章须落地 · 外部补全 {len(items)} 条 · 硬】",
        "先完成下列补嵌，再改表达。漏一条 = 本章失败（程序逐条验收）。",
        "每条须：①出现对应《书·卷》；②写出该条声明的增量（勿只挂书名）。",
    ]
    for i, it in enumerate(items, 1):
        kws = "、".join(it["keywords"][:4]) if it.get("keywords") else "（写清与母本差异即可）"
        lines.append(
            f"{i}. 锚点 {it.get('母本锚点') or '本章合适处'} | {it.get('出处')} | "
            f"主题：{it.get('主题')}\n"
            f"   增量指纹（正文宜出现其一）：{kws}"
        )
        rel = it.get("与母本关系") or ""
        if rel:
            short = rel if len(rel) <= 120 else rel[:120] + "…"
            lines.append(f"   与母本关系：{short}")
    lines.append("全部写完后再进入改表达。")
    return "\n".join(lines) + "\n"


def is_landing_only_failure(errors: Sequence[str]) -> bool:
    """质检失败是否仅因补全落地（可走 L2 补洞）。"""
    if not errors:
        return False
    keys = ("外部补全未落地", "索引引入/异说须出现", "plan 已采用/异说须落地")
    others = [
        e
        for e in errors
        if not any(k in str(e) for k in keys)
    ]
    return len(others) == 0


def build_landing_patch_prompt(
    *,
    entry_id: str,
    chapter_body: str,
    missing: Sequence[Dict[str, Any]],
    output_file: Path,
) -> str:
    """定向补洞：只输出 inserts JSON，禁止重写全章。"""
    spec = []
    for it in missing:
        spec.append(
            {
                "主题": it.get("主题"),
                "出处": it.get("出处"),
                "母本锚点": it.get("母本锚点"),
                "与母本关系": (it.get("与母本关系") or "")[:200],
                "验收关键词": it.get("keywords") or [],
                "失败原因": it.get("miss_reason"),
            }
        )
    return f"""【historiography-translate Phase2 · 定向补洞 L2】
史略ID: {entry_id}
产出路径: {output_file}

任务：下列 plan 采用项在本章正文中未落地。请**只生成插入句**，不要重写全章。

硬约束：
1. 每条 inserts[] 对应一条缺失补全；paragraph 须含对应《书·卷》与增量事实。
2. marker 必须是下面「本章正文」里**已有**的连续原文（8～40 字），插入点在该 marker 所在句之后。
3. 禁止改动 marker 以外已有情节；禁止编造 plan 未声明的硬史实；禁止输出整章正文。
4. 只输出一个 JSON 对象，不要 Markdown 围栏。

JSON schema:
{{"inserts":[{{"marker":"正文已有片段","paragraph":"插入的说书旁白（含《书·卷》）"}}]}}

--- 缺失项 ---
{json.dumps(spec, ensure_ascii=False, indent=2)}

--- 本章正文 ---
{chapter_body}
---
"""


def _extract_json_obj(raw: str) -> Optional[Dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return None
    # 产出常被写成 {"史略ID","翻译详情":"```json ..."} —— 先剥外壳
    if text.startswith("{"):
        try:
            outer = json.loads(text)
            if isinstance(outer, dict) and isinstance(outer.get("inserts"), list):
                return outer
            if isinstance(outer, dict) and isinstance(outer.get("翻译详情"), str):
                text = outer["翻译详情"].strip()
        except json.JSONDecodeError:
            pass
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _quote_depths_at(text: str, pos: int) -> Tuple[int, int]:
    """pos 处未闭合的直角「」/弯引“”层数。"""
    corner = 0
    curly = 0
    i = 0
    n = min(max(0, pos), len(text))
    while i < n:
        ch = text[i]
        if ch == "「":
            corner += 1
        elif ch == "」":
            corner = max(0, corner - 1)
        elif ch == "“":
            curly += 1
        elif ch == "”":
            curly = max(0, curly - 1)
        i += 1
    return corner, curly


def _existing_long_paras(body: str) -> List[str]:
    from lib.longform_compat import _plain

    out: List[str] = []
    for para in re.split(r"\n\s*\n", str(body or "")):
        pl = _plain(para)
        if len(pl) >= 48:
            out.append(pl)
    return out


def apply_landing_inserts(body: str, inserts: Sequence[Dict[str, Any]]) -> Tuple[str, int]:
    """按 marker 在句后插入 paragraph；返回 (新正文, 成功插入数)。

    静默跳过（不触发整章重试）：
    - marker 落在未闭合「」/“”内（避免截断金句）
    - 插入段与已有段落近重复 / 释义双写（主题总评已写过）
    """
    from lib.longform_compat import _is_heal_duplicate, _plain

    text = str(body or "")
    applied = 0
    for row in inserts:
        if not isinstance(row, dict):
            continue
        marker = str(row.get("marker") or "").strip()
        para = str(row.get("paragraph") or "").strip()
        if not marker or not para or marker not in text:
            continue
        idx = text.find(marker)
        if idx < 0:
            continue
        end = idx + len(marker)
        corner, curly = _quote_depths_at(text, end)
        if corner or curly:
            continue
        para_plain = _plain(para)
        if len(para_plain) >= 48 and _is_heal_duplicate(
            para_plain, _existing_long_paras(text)
        ):
            continue
        stop = end
        while stop < len(text) and text[stop] not in "。！？\n":
            stop += 1
        if stop < len(text) and text[stop] in "。！？":
            stop += 1
        # 句末仍在引号内则跳过
        c2, q2 = _quote_depths_at(text, stop)
        if c2 or q2:
            continue
        insert = para if para.startswith("\n") else ("\n" + para)
        if not insert.endswith(("。", "！", "？", "\n")):
            insert += "。"
        text = text[:stop] + insert + text[stop:]
        applied += 1
    return text, applied


def load_detail_from_enrich_file(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if isinstance(data, dict):
        for k in ("翻译详情", "母本顺译"):
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return raw.strip()


def save_detail_to_enrich_file(path: Path, entry_id: str, detail: str) -> None:
    """写回翻译详情；保留已有史料原文/出处/版本等字段，避免被冲掉。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    keep: Dict[str, Any] = {}
    if path.is_file():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(prev, dict):
                for k in ("史料原文", "原文出处", "翻译版本", "_版本说明"):
                    if prev.get(k) not in (None, ""):
                        keep[k] = prev[k]
        except (json.JSONDecodeError, OSError):
            pass
    payload = {"史略ID": entry_id, "翻译详情": detail, **keep}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def try_parse_and_apply_patch(
    path: Path, entry_id: str, llm_raw_or_file_detail: str
) -> Tuple[bool, str]:
    """解析 L2 JSON 并写回本章文件。llm 可能直接把 JSON 写入产出路径。"""
    detail_now = load_detail_from_enrich_file(path) if path.is_file() else ""
    # 优先从文件内容解析（若模型把 JSON 落盘到 output）
    candidates = [llm_raw_or_file_detail, detail_now]
    obj = None
    for c in candidates:
        obj = _extract_json_obj(c)
        if obj and isinstance(obj.get("inserts"), list):
            break
        obj = None
    if not obj:
        return False, "定向补洞未解析到 inserts JSON"
    # 基文必须是补洞前的叙事正文，不能是 JSON
    base = detail_now
    if base.strip().startswith("{") and "inserts" in base[:200]:
        return False, "本章正文已被 JSON 覆盖，无法补洞"
    new_body, n = apply_landing_inserts(base, obj.get("inserts") or [])
    if n <= 0:
        return False, "定向补洞 inserts 未命中任何 marker"
    save_detail_to_enrich_file(path, entry_id, new_body)
    return True, f"定向补洞已插入 {n} 处"
