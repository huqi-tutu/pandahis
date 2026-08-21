"""标注账本：地名今地 + 显式纪年公元并注（程序生成清单 + 门禁）。

模型负责把标注放进正文；程序负责验收。对照表外地名不猜、不拦。
"""

from __future__ import annotations

import os
import re
from typing import Iterable, List, Optional, Sequence

from lib.place_now import load_gazetteer, missing_first_now_places

# 常见帝纪/年号年显式写法（可扩展；宁少勿滥误伤「三年后」等）
_ERA_YEAR = re.compile(
    r"(?:"
    r"汉[元正一二三四五六七八九十]+年|"
    r"秦二世[元一二三四五六七八九十]+年|"
    r"秦[元一二三四五六七八九十]+年|"
    r"(?:建元|元光|元朔|元狩|元鼎|元封|太初|天汉|太始|征和|后元|"
    r"黄龙|初元|永光|建昭|竟宁|神爵|五凤|甘露|黄龙|"
    r"贞观|开元|天宝|至德|乾元|永泰|大历|建中|兴元|贞元|"
    r"元和|长庆|宝历|太和|开成|会昌|大中|咸通|乾符|中和|"
    r"洪武|永乐|嘉靖|万历|康熙|雍正|乾隆|嘉庆|道光|咸丰|同治|光绪|宣统)"
    r"[元一二三四五六七八九十百]+年"
    r")"
)
_YEAR_NOTE = re.compile(r"^[（(]\s*(?:前|公元)\s*\d{1,4}\s*年\s*[）)]")
_MONTH_THEN_YEAR_NOTE = re.compile(
    r"^(?:十月|十一月|十二月|正月|[正一二三四五六七八九十]+月)"
    r"[（(]\s*(?:前|公元)\s*\d{1,4}\s*年\s*[）)]"
)


def place_gate_enabled() -> bool:
    return (os.environ.get("TRANSLATE_PLACE_NOW_GATE") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def era_year_gate_enabled() -> bool:
    return (os.environ.get("TRANSLATE_ERA_YEAR_GATE") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def places_in_text(
    text: str,
    *,
    gazetteer: Optional[Iterable[dict]] = None,
) -> List[dict]:
    """母本/成稿中出现的对照表地名（最长名优先去重）。"""
    rows = list(gazetteer) if gazetteer is not None else load_gazetteer()
    body = str(text or "")
    found: List[dict] = []
    occupied: List[tuple[int, int]] = []
    for row in rows:
        name = str(row.get("name") or "")
        if len(name) < 2 or name not in body:
            continue
        # 取首次出现，避开已被更长名占用的区间
        start = 0
        while True:
            idx = body.find(name, start)
            if idx < 0:
                break
            if any(a <= idx < b for a, b in occupied):
                start = idx + len(name)
                continue
            occupied.append((idx, idx + len(name)))
            found.append({"name": name, "now": str(row.get("now") or "")})
            break
    return found


def format_annotation_ledger(
    mother: str,
    *,
    classic_quotes: Optional[Sequence[str]] = None,
    max_places: int = 40,
    max_quotes: int = 12,
) -> str:
    """注入 Phase2：地点必标 + 纪年规则提醒 + 可选经典摘句。"""
    places = places_in_text(mother)[:max_places]
    lines = [
        "标注账本（程序会硬检；只处理下列已知项，表外地名不要猜今地）：",
        "",
        "【地点 · 正文首次出现须紧跟（今…）】",
    ]
    if places:
        for p in places:
            now = str(p["now"] or "").strip()
            if now.startswith("（") and "今" in now:
                gloss = now
            elif now.startswith("今"):
                gloss = f"（{now}）"
            else:
                gloss = f"（今{now}）"
            lines.append(f"- {p['name']} → {gloss}")
    else:
        lines.append("- （本篇母本未命中对照表必标地名）")

    lines.extend(
        [
            "",
            "【纪年 · 每个显式年号/帝纪年须并注公历】",
            "- 例：汉二年（前205年）；贞观三年（公元629年）",
            "- 禁止只注个别关键年、其余干写「汉×年」",
            "",
            "【引号】",
            "- 史料著作原文 →「」；已译白话对话 →“”",
        ]
    )
    quotes = [q.strip() for q in (classic_quotes or []) if str(q or "").strip()]
    if quotes:
        lines.append("- 下列经典摘句须在成稿落地直角「」：")
        for q in quotes[:max_quotes]:
            short = q if len(q) <= 40 else q[:18] + "…" + q[-12:]
            lines.append(f"  · {short}")
    return "\n".join(lines)


def missing_era_year_notes(detail: str) -> List[str]:
    """成稿中显式纪年未紧跟（前N年）/（公元N年）的列表（去重保序）。"""
    body = str(detail or "")
    missing: List[str] = []
    seen: set[str] = set()
    for m in _ERA_YEAR.finditer(body):
        token = m.group(0)
        after = body[m.end() : m.end() + 24]
        if _YEAR_NOTE.match(after) or _MONTH_THEN_YEAR_NOTE.match(after):
            continue
        if token in seen:
            continue
        seen.add(token)
        missing.append(token)
    return missing


def format_annotation_gate_errors(
    detail: str,
    *,
    mother: str = "",
) -> List[str]:
    """Phase2 出口：地名漏标 + 纪年缺公元（可由环境变量关闭）。"""
    errs: List[str] = []
    if place_gate_enabled():
        # 仅拦「成稿出现且母本也出现过」的表内地名，减少 L3 新地名误伤
        mother_names = {p["name"] for p in places_in_text(mother)} if mother else None
        missing = missing_first_now_places(detail)
        if mother_names is not None:
            missing = [n for n in missing if n in mother_names]
        if missing:
            shown = "、".join(missing[:12])
            more = f" 等{len(missing)}处" if len(missing) > 12 else ""
            errs.append(
                f"地名漏标今地（对照表内、母本已出现）：{shown}{more}。"
                "首次出现须紧跟（今…）；表外不猜。"
            )
    if era_year_gate_enabled():
        years = missing_era_year_notes(detail)
        if years:
            shown = "、".join(years[:10])
            more = f" 等{len(years)}处" if len(years) > 10 else ""
            errs.append(
                f"纪年缺公元并注：{shown}{more}。"
                "须写成「汉二年（前205年）」或「贞观三年（公元629年）」形式。"
            )
    return errs


_CN_YEAR = {
    "元": 1,
    "正": 1,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
    "十三": 13,
    "十四": 14,
    "十五": 15,
}


def _parse_cn_year_ord(token: str) -> Optional[int]:
    t = str(token or "").strip()
    if t in _CN_YEAR:
        return _CN_YEAR[t]
    if re.fullmatch(r"十[一二三四五六七八九]", t):
        return 10 + _CN_YEAR[t[1]]
    if re.fullmatch(r"[二三四五六七八九]十[一二三四五六七八九]?", t):
        tens = _CN_YEAR[t[0]] * 10
        return tens + (_CN_YEAR[t[2]] if len(t) == 3 else 0)
    return None


def era_token_to_ce_note(token: str) -> Optional[str]:
    """已知可换算的显式纪年 → （前N年）/（公元N年）；拿不准返回 None。"""
    t = str(token or "").strip()
    m = re.fullmatch(r"汉(.+)年", t)
    if m:
        n = _parse_cn_year_ord(m.group(1))
        if n is not None and 1 <= n <= 15:
            # 汉元年＝前206；汉n年＝前(207−n)
            return f"（前{207 - n}年）"
    m = re.fullmatch(r"秦二世(.+)年", t)
    if m:
        n = _parse_cn_year_ord(m.group(1))
        if n is not None and 1 <= n <= 3:
            # 秦二世元年＝前209
            return f"（前{210 - n}年）"
    return None


def _now_gloss(now: str) -> str:
    s = str(now or "").strip()
    if not s:
        return ""
    if s.startswith("（") and "今" in s:
        return s
    if s.startswith("(") and "今" in s:
        return s
    if s.startswith("今"):
        return f"（{s}）"
    return f"（今{s}）"


def apply_annotation_autofix(
    detail: str,
    *,
    mother: str = "",
) -> tuple[str, List[str]]:
    """程序补注漏标今地 / 缺公元纪年（对照表与可换算纪年）；不改情节措辞。"""
    body = str(detail or "")
    changes: List[str] = []
    if place_gate_enabled():
        mother_names = {p["name"] for p in places_in_text(mother)} if mother else None
        gaz = {str(r["name"]): str(r.get("now") or "") for r in load_gazetteer()}
        # 每次只补「门禁认定的第一处漏标」位置，禁止 body.find 误打到（今…）内部
        for _ in range(40):
            missing = missing_first_now_places(body)
            if mother_names is not None:
                missing = [n for n in missing if n in mother_names]
            if not missing:
                break
            name = missing[0]
            gloss = _now_gloss(gaz.get(name, ""))
            if not gloss:
                break
            insert_at = _first_missing_place_end(body, name)
            if insert_at is None:
                break
            # 已紧跟今地则跳过（防御）
            after = body[insert_at : insert_at + 8]
            if after.startswith("（今") or after.startswith("(今"):
                break
            body = body[:insert_at] + gloss + body[insert_at:]
            changes.append(f"地名补注{name}")
    if era_year_gate_enabled():
        pending = missing_era_year_notes(body)
        for token in reversed(pending):
            note = era_token_to_ce_note(token)
            if not note:
                continue
            for m in reversed(list(_ERA_YEAR.finditer(body))):
                if m.group(0) != token:
                    continue
                after = body[m.end() : m.end() + 24]
                if _YEAR_NOTE.match(after):
                    continue
                body = body[: m.end()] + note + body[m.end() :]
                changes.append(f"纪年并注{token}")
                break
    return body, changes


def _first_missing_place_end(body: str, name: str) -> Optional[int]:
    """与 missing_first_now_places 同一套扫描，返回该漏标地名首次应插入今地的下标。"""
    from lib.place_now import _TITLE_SUFFIX, _inside_now_paren, load_gazetteer

    occupied: List[tuple[int, int]] = []
    for row in load_gazetteer():
        n = str(row.get("name") or "")
        if len(n) < 2:
            continue
        start = 0
        while True:
            idx = body.find(n, start)
            if idx < 0:
                break
            if any(a <= idx < b for a, b in occupied):
                start = idx + len(n)
                continue
            if _inside_now_paren(body, idx):
                start = idx + len(n)
                continue
            rest = body[idx + len(n) :]
            if _TITLE_SUFFIX.match(rest):
                start = idx + len(n)
                continue
            occupied.append((idx, idx + len(n)))
            if n != name:
                break
            after = rest[:32]
            if after.startswith("（今") or after.startswith("(今"):
                break
            if re.match(r"^[\u4e00-\u9fff·・]{0,16}[（(]今", after):
                break
            return idx + len(n)
            break
    return None
