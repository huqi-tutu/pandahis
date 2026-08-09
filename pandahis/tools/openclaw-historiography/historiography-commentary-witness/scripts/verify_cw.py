"""评述 / 见证 JSON verify 门禁。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from cw_lib import STATUS_DONE, STATUS_EMPTY, count_han  # noqa: E402

Mode = Literal["commentary", "witness"]

ID_P_FLEX = re.compile(r"^.+_P\d{2}$")
ID_W_FLEX = re.compile(r"^.+_W\d{2}$")
PRI_OK = frozenset({"P0", "P1", "P2", "P3", "P4"})

# 写作形式：翻译体断裂
TRANSLATION_MARKERS = re.compile(
    r"(原文\s*[:：]|白话\s*[:：]|译文\s*[:：]|今译\s*[:：]|意思是\s*[:：])"
)

# 教材级争议框架（正文语义；与评述标题角度词无关）
# 仅匹配五帝禅让/疑古专题 discourse，勿用宽泛词（如单字「篡位」）误伤春秋弑君叙事
FRAME_LAYERED = re.compile(r"(层累|古史辨|疑古辨伪|神话历史化|神话剥离|神话解构|造神)")
FRAME_SHANRANG = re.compile(r"(禅让真假|逼尧|囚尧|逼篡|舜逼|尧舜.*逼|禅让.*(伪|假)|疑古.*禅让)")
FRAME_MYTH_HIST = re.compile(r"(信史|传说符号|神话人物|是否真实)")

# 软关联 / 现代纪念（见证 P0 禁）
# 注意：勿用裸「1993年/2008年」——出土/入藏年代会误伤早期简牍等真物证
SOFT_P0 = re.compile(
    r"(纪念碑|纪念亭|新建|手植柏|"
    r"传为.{0,8}葬|"
    r"(?:19|20)\d{2}\s*年.{0,12}(?:立|建|修|落成|重建|揭幕)|"
    r"(?:立|建|修|落成|重建|揭幕).{0,12}(?:19|20)\d{2}\s*年)"
)
GU_MARKERS = re.compile(r"(顾颉刚|古史辨)")


def _issue(level: str, msg: str) -> dict[str, str]:
    return {"level": level, "msg": msg}


def _angle(title: str) -> str:
    if "·" not in title:
        return ""
    return title.split("·", 1)[-1].strip()


def _framework_hits(title: str, brief: str, body: str) -> set[str]:
    blob = f"{title}\n{brief}\n{body}"
    hits: set[str] = set()
    if FRAME_LAYERED.search(blob):
        hits.add("层累/疑古")
    if FRAME_SHANRANG.search(blob):
        hits.add("禅让真假")
    if FRAME_MYTH_HIST.search(blob) and FRAME_LAYERED.search(blob):
        # 信史vs神话常与层累叠用，已计入层累则不重复计第二框架
        pass
    elif re.search(r"(神话|传说).{0,6}(历史|信史)|(历史|信史).{0,6}(神话|传说)", blob):
        hits.add("信史vs神话")
    return hits


def verify_envelope(doc: dict[str, Any], mode: Mode) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if doc.get("schema_version") != 1:
        issues.append(_issue("CRITICAL", f"schema_version 须为 1，当前 {doc.get('schema_version')!r}"))
    if doc.get("mode") != mode:
        issues.append(_issue("CRITICAL", f"mode 须为 {mode!r}，当前 {doc.get('mode')!r}"))
    status = doc.get("status")
    if status not in (STATUS_DONE, STATUS_EMPTY):
        issues.append(_issue("CRITICAL", f"非法 status: {status!r}"))
    entries = doc.get("entries")
    if not isinstance(entries, list):
        issues.append(_issue("CRITICAL", "entries 须为数组"))
        return issues
    if doc.get("entry_count") != len(entries):
        issues.append(
            _issue(
                "CRITICAL",
                f"entry_count={doc.get('entry_count')} 与 entries 长度 {len(entries)} 不一致",
            )
        )
    if status == STATUS_EMPTY and len(entries) != 0:
        issues.append(_issue("CRITICAL", "status=已处理·无可用 时 entries 须为空"))
    if status == STATUS_DONE and len(entries) == 0:
        issues.append(_issue("CRITICAL", "status=done 时 entries 不可为空（应标 已处理·无可用）"))
    for key in ("史略ID", "史略名称"):
        if not str(doc.get(key) or "").strip():
            issues.append(_issue("CRITICAL", f"信封缺少 {key}"))
    return issues


def verify_commentary_entries(doc: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    eid = str(doc.get("史略ID") or "").strip()
    name = str(doc.get("史略名称") or "").strip()
    seen: set[str] = set()
    angles: list[str] = []
    framework_used: list[tuple[int, str]] = []
    gu_indices: list[int] = []
    existence_doubt = 0

    try:
        from cw_lib import (  # noqa: WPS433
            bibliography_exclusion_set,
            is_cited_in_bibliography,
            is_zhengshi_lunzan,
            load_detail_bibliography,
        )

        excl = bibliography_exclusion_set(
            load_detail_bibliography({"史略ID": eid, "史略名称": name})
        )
    except Exception:
        excl = set()

        def is_cited_in_bibliography(*_a: Any, **_k: Any) -> bool:  # type: ignore
            return False

        def is_zhengshi_lunzan(*_a: Any, **_k: Any) -> bool:  # type: ignore
            return False

    has_lunzan = False
    for i, row in enumerate(doc.get("entries") or [], start=1):
        prefix = f"[{i}]"
        if not isinstance(row, dict):
            issues.append(_issue("CRITICAL", f"{prefix} 条目非对象"))
            continue
        rid = str(row.get("评述ID") or "").strip()
        if not ID_P_FLEX.match(rid) or not rid.startswith(f"{eid}_P"):
            issues.append(_issue("CRITICAL", f"{prefix} 评述ID 非法: {rid!r}"))
        expect = f"{eid}_P{i:02d}"
        if rid != expect:
            issues.append(_issue("CRITICAL", f"{prefix} 评述ID 应为 {expect}，当前 {rid}"))
        if rid in seen:
            issues.append(_issue("CRITICAL", f"{prefix} 评述ID 重复: {rid}"))
        seen.add(rid)
        if str(row.get("史略ID") or "").strip() != eid:
            issues.append(_issue("CRITICAL", f"{prefix} 史略ID 与信封不一致"))
        if str(row.get("史略名称") or "").strip() != name:
            issues.append(_issue("CRITICAL", f"{prefix} 史略名称 与信封不一致"))
        title = str(row.get("评述标题") or "").strip()
        if "·" not in title:
            issues.append(_issue("CRITICAL", f"{prefix} 评述标题须含「·」: {title!r}"))
        else:
            angles.append(_angle(title))
        for k in ("评述人", "评述著作", "评述内容", "评述简介", "评述年代"):
            if not str(row.get(k) or "").strip():
                issues.append(_issue("CRITICAL", f"{prefix} 缺少 {k}"))
        work = str(row.get("评述著作") or "")
        if excl and is_cited_in_bibliography(work, excl) and not is_zhengshi_lunzan(row):
            issues.append(
                _issue(
                    "CRITICAL",
                    f"{prefix} 评述著作「{work}」已在详情参考著作中，不得再作评述"
                    "（正史论赞除外）",
                )
            )
        if is_zhengshi_lunzan(row):
            has_lunzan = True
        brief = str(row.get("评述简介") or "")
        bc = count_han(brief)
        if bc > 20:
            issues.append(
                _issue("WARN", f"{prefix} 评述简介汉字数 {bc} > 20（建议上限，不截断）")
            )
        if brief and not re.search(r"[。！？；」』\"'\)\]】]$", brief.strip()):
            issues.append(_issue("CRITICAL", f"{prefix} 评述简介句末不完整（疑似截断）"))
        body = str(row.get("评述内容") or "")
        hc = count_han(body)
        if hc < 50:
            issues.append(_issue("CRITICAL", f"{prefix} 评述内容汉字数 {hc} < 50"))
        elif hc > 200:
            issues.append(
                _issue("WARN", f"{prefix} 评述内容汉字数 {hc} > 200（建议上限，不截断）")
            )
        if body and not re.search(r"[。！？；」』\"'\)\]】]$", body.strip()):
            issues.append(_issue("CRITICAL", f"{prefix} 评述内容句末不完整（疑似截断）"))
        if TRANSLATION_MARKERS.search(body):
            issues.append(
                _issue(
                    "CRITICAL",
                    f"{prefix} 评述内容禁止「原文/白话/译文」分离结构，须写成嵌入原文的完整议论",
                )
            )
        if "《" not in work:
            issues.append(_issue("WARN", f"{prefix} 评述著作建议含书名号"))

        author = str(row.get("评述人") or "")
        if GU_MARKERS.search(author) or GU_MARKERS.search(work):
            gu_indices.append(i)
        hits = _framework_hits(title, brief, body)
        for h in hits:
            framework_used.append((i, h))
        if "层累/疑古" in hits or GU_MARKERS.search(author + work + body):
            existence_doubt += 1

    n = len(doc.get("entries") or [])
    lunzan_rows, other_rows = [], []
    try:
        from cw_lib import split_lunzan_and_others  # noqa: WPS433

        lunzan_rows, other_rows = split_lunzan_and_others(doc.get("entries") or [])
    except Exception:
        lunzan_rows, other_rows = ([], doc.get("entries") or [])

    if doc.get("status") == STATUS_DONE and n > 6:
        issues.append(_issue("CRITICAL", f"评述条数 {n} 超过硬上限 6（1论赞+5其他）"))
    if doc.get("status") == STATUS_DONE and len(lunzan_rows) == 0 and n > 5:
        issues.append(_issue("CRITICAL", f"无论赞时评述条数 {n} 超过上限 5"))
    if doc.get("status") == STATUS_DONE and len(lunzan_rows) >= 1 and len(other_rows) > 5:
        issues.append(
            _issue(
                "CRITICAL",
                f"论赞之外其他评述 {len(other_rows)} 条，超过上限 5",
            )
        )
    if doc.get("status") == STATUS_DONE and (n < 1 or n > 6):
        issues.append(_issue("WARN", f"评述条数 {n} 超出建议范围（有论赞≤6 / 无论赞≤5）"))
    if len(lunzan_rows) > 1:
        issues.append(_issue("WARN", f"正史论赞 {len(lunzan_rows)} 条，建议只保留 1 条"))
    if (
        doc.get("status") == STATUS_DONE
        and n >= 1
        and not has_lunzan
        and str(doc.get("史略分类") or "") in ("君王", "junji", "宗戚", "zongqi", "文臣", "wenchen", "武将", "wujiang")
    ):
        issues.append(
            _issue(
                "WARN",
                "人物类评述未含二十四史论赞（太史公曰/赞曰/评曰/史臣曰/论曰等）；"
                "若该史略见于正史纪传，建议补 1 条",
            )
        )
    if len(angles) >= 2 and len(set(angles)) < len(angles):
        issues.append(_issue("CRITICAL", "评述标题角度词重复，须差异化/多元化"))
    if n >= 3 and len(set(angles)) == 1:
        issues.append(_issue("CRITICAL", "多条评述角度完全相同，违反多元化门禁"))

    # 教材级框架：合计种类过多，或出现在第 1 条
    frame_kinds = {h for _, h in framework_used}
    if len(frame_kinds) > 1:
        issues.append(
            _issue(
                "WARN",
                f"教材级争议框架出现多种 {sorted(frame_kinds)}，建议每文件最多保留 1 种",
            )
        )
    for idx, h in framework_used:
        if idx == 1:
            issues.append(
                _issue(
                    "CRITICAL",
                    f"[1] 教材级争议框架「{h}」不得放在第 1 条评述",
                )
            )
    if existence_doubt >= 3:
        issues.append(
            _issue(
                "WARN",
                f"存在性质疑/疑古类条目偏多（{existence_doubt}），宜删减叠床架屋者",
            )
        )
    if len(gu_indices) >= 2:
        issues.append(
            _issue("CRITICAL", f"顾颉刚/古史辨出现 {len(gu_indices)} 次，同文件择一即可")
        )
    return issues


def is_literary_extra(row: dict[str, Any]) -> bool:
    if row.get("附加文学见证") is True:
        return True
    reason = str(row.get("优先级判定理由") or "")
    if "附加名额" in reason or "附加文学" in reason:
        return True
    loc = str(row.get("现藏地点") or "")
    if loc.startswith("传世文本"):
        return True
    return False


# 史书 / 正史篇目（不得作为见证，尤其不得作附加文学见证）
SHISHU_WITNESS = re.compile(
    r"(《[^》]*(史记|汉书|后汉书|三国志|左传|公羊|谷梁|国语|战国策|"
    r"竹书纪年|逸周书|吴越春秋|越绝书|东观汉记|汉纪|后汉纪|资治通鉴|通鉴)[^》]*》|"
    r"(史记|汉书|后汉书|资治通鉴).{0,8}(本纪|世家|列传|表|志)|"
    r"(本纪|世家|列传))"
)
# 诗词歌赋 / 文章名篇（F 层合格）
POETIC_WITNESS = re.compile(
    r"(诗|词|曲|赋|歌行|乐府|绝句|律诗|楚辞|诗经|离骚|颂|谣|古风|"
    r"咏史|怀古|五子之歌)"
)
ARTICLE_WITNESS = re.compile(
    r"(《[^》]+(论|记|说|序|议|辩|书)》|(过秦论|封建论|灵渠记|祠堂记|五蠹)|"
    r"(论|记|说|序|议)[》」]?$)"
)
# 明确不合格：戏曲小说、字书、史注疏（非文章名篇）
BANNED_LIT = re.compile(
    r"(杂剧|传奇|小说|话本|章回|戏曲|剧本|演义|评书|"
    r"说文解字|艺文志|索隐|正义|注疏|府志|县志|纪事本末)"
)


def is_shishu_witness_row(row: dict[str, Any]) -> bool:
    """史书篇目：标题指向正史纪传本文；文章名篇即使附载于《史记》也不算史书见证。"""
    title = str(row.get("文物标题") or "")
    loc = str(row.get("现藏地点") or "")
    intro = str(row.get("文物介绍") or "")
    # 出土简牍实物：馆藏机构定位，不算「史书文本见证」
    if re.search(r"(出土|竹简|简牍|清华简|睡虎地|里耶|岳麓)", title + loc) and not loc.startswith(
        "传世文本"
    ):
        return False
    # 标题已是诗词歌赋/文章名篇（如《过秦论》）→ 非史书见证
    # 但「《史记·秦始皇本纪》」这类标题仍算史书
    title_is_shishu_chapter = bool(
        re.search(
            r"(史记|汉书|后汉书|左传|国语|战国策|资治通鉴|通鉴).{0,12}(本纪|世家|列传|表|志)|"
            r"《(史记|汉书|后汉书|左传|国语|战国策|资治通鉴)[^》]*》",
            title,
        )
    )
    if title_is_shishu_chapter:
        return True
    if ARTICLE_WITNESS.search(title) or POETIC_WITNESS.search(title):
        return False
    blob = f"{title}\n{loc}\n{intro}"
    if loc.startswith("传世文本") and SHISHU_WITNESS.search(title):
        return True
    if SHISHU_WITNESS.search(title) and (
        loc.startswith("传世文本") or "点校本" in loc or "传世" in loc
    ):
        return True
    # 标题无史书名、仅地点写「见《史记》」的文章 → 不算
    if not SHISHU_WITNESS.search(title):
        return False
    return bool(SHISHU_WITNESS.search(blob))


def is_poetic_literary_row(row: dict[str, Any]) -> bool:
    """兼容旧名：诗词歌赋或文章名篇。"""
    return is_allowed_literary_row(row)


def is_allowed_literary_row(row: dict[str, Any]) -> bool:
    """F 层：诗词歌赋 + 文章；排除戏曲演义与字书等。"""
    title = str(row.get("文物标题") or "")
    intro = str(row.get("文物介绍") or "")
    blob = title + "\n" + intro
    if BANNED_LIT.search(title):
        return False
    if POETIC_WITNESS.search(blob) or ARTICLE_WITNESS.search(title) or ARTICLE_WITNESS.search(blob):
        return True
    return False


def verify_witness_entries(doc: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    eid = str(doc.get("史略ID") or "").strip()
    name = str(doc.get("史略名称") or "").strip()
    category = str(doc.get("史略分类") or "").strip()
    seen_id: set[str] = set()
    seen_pri: set[str] = set()
    soft_count = 0
    extra_count = 0
    for i, row in enumerate(doc.get("entries") or [], start=1):
        prefix = f"[{i}]"
        if not isinstance(row, dict):
            issues.append(_issue("CRITICAL", f"{prefix} 条目非对象"))
            continue
        rid = str(row.get("文物ID") or "").strip()
        expect = f"{eid}_W{i:02d}"
        if rid != expect:
            issues.append(_issue("CRITICAL", f"{prefix} 文物ID 应为 {expect}，当前 {rid}"))
        if rid in seen_id:
            issues.append(_issue("CRITICAL", f"{prefix} 文物ID 重复"))
        seen_id.add(rid)
        if str(row.get("史略ID") or "").strip() != eid:
            issues.append(_issue("CRITICAL", f"{prefix} 史略ID 与信封不一致"))
        if str(row.get("史略名称") or "").strip() != name:
            issues.append(_issue("CRITICAL", f"{prefix} 史略名称 与信封不一致"))
        for k in ("文物标题", "现藏地点", "文物介绍", "文物优先级", "优先级判定理由"):
            if not str(row.get(k) or "").strip():
                issues.append(_issue("CRITICAL", f"{prefix} 缺少 {k}"))
        img = row.get("文物图片")
        if img not in ("", None):
            issues.append(_issue("CRITICAL", f"{prefix} 文物图片须为空字符串，当前 {img!r}"))
        pri = str(row.get("文物优先级") or "").strip().upper()
        if pri not in PRI_OK:
            issues.append(_issue("CRITICAL", f"{prefix} 非法优先级: {pri!r}"))
        elif pri in seen_pri:
            if not (is_literary_extra(row) and pri == "P4"):
                issues.append(_issue("CRITICAL", f"{prefix} 优先级重复: {pri}"))
        seen_pri.add(pri)
        intro = str(row.get("文物介绍") or "")
        reason = str(row.get("优先级判定理由") or "")
        title = str(row.get("文物标题") or "")
        hc = count_han(intro)
        if hc < 100 or hc > 200:
            issues.append(_issue("CRITICAL", f"{prefix} 文物介绍汉字数 {hc} 不在 100–200"))
        rc = count_han(reason)
        if rc < 20 or rc > 80:
            issues.append(_issue("WARN", f"{prefix} 优先级判定理由汉字数 {rc} 建议 20–80"))
        loc = str(row.get("现藏地点") or "")
        if "·" not in loc:
            issues.append(_issue("WARN", f"{prefix} 现藏地点建议「国家·机构」格式"))

        if is_literary_extra(row):
            extra_count += 1
            if pri == "P0":
                issues.append(
                    _issue("CRITICAL", f"{prefix} 附加文学见证不得标 P0")
                )
            if is_shishu_witness_row(row):
                issues.append(
                    _issue(
                        "CRITICAL",
                        f"{prefix} 禁止史书篇目作见证（如史记本纪/世家/列传、汉书、左传、通鉴）",
                    )
                )
            elif not is_allowed_literary_row(row):
                issues.append(
                    _issue(
                        "CRITICAL",
                        f"{prefix} 附加文学见证仅限诗词歌赋或文章名篇（论/记/说/序等）；"
                        "禁止史书纪传、杂剧演义、字书条目",
                    )
                )
        elif is_shishu_witness_row(row):
            # 主名额也不允许纯传世史书文本冒充实物
            issues.append(
                _issue(
                    "CRITICAL",
                    f"{prefix} 禁止以传世史书文本充当见证（与史略正文重复）",
                )
            )

        soft_blob = f"{title}\n{intro}\n{reason}"
        is_soft = bool(SOFT_P0.search(soft_blob)) or ("证据力弱" in reason)
        if is_soft:
            soft_count += 1
            if pri == "P0":
                issues.append(
                    _issue(
                        "CRITICAL",
                        f"{prefix} 软关联/现代纪念/证据力弱 不得标为 P0（应空结果或至多低优先级）",
                    )
                )

        # 制度类：介绍中宜有时间锚点提示
        if category in ("典制", "dianzhi") or "制" in name:
            if not re.search(
                r"(距|晚于|早于|属于.{0,6}(朝|世纪|年代)|后世成型|起源期|约.{0,4}年)",
                intro,
            ):
                issues.append(
                    _issue(
                        "WARN",
                        f"{prefix} 制度类见证介绍建议写明物证朝代及与传说起源的时间跨度",
                    )
                )

    n = len(doc.get("entries") or [])
    physical = n - extra_count
    if extra_count > 1:
        issues.append(_issue("CRITICAL", f"附加文学见证最多 1 条，当前 {extra_count}"))
    if doc.get("status") == STATUS_DONE:
        if physical < 1 or physical > 5:
            issues.append(
                _issue("WARN", f"实物见证件数 {physical} 超出建议 1–5（附加 F {extra_count} 条不计入）")
            )
        if n > 6:
            issues.append(_issue("CRITICAL", f"总条目 {n} 超过上限 6（5 实物 + 1 附加 F）"))
    elif n > 0 and (physical > 5 or n > 6):
        issues.append(_issue("WARN", f"条目数 {n}（实物 {physical} + 附加 F {extra_count}）超限"))
    if soft_count >= 2:
        issues.append(
            _issue(
                "WARN",
                f"软关联类见证 {soft_count} 条，宜删减；仅 E 层时应优先 已处理·无可用",
            )
        )
    if soft_count == n and n >= 1 and doc.get("status") == STATUS_DONE:
        issues.append(
            _issue(
                "WARN",
                "全部见证疑似软关联：考虑改为 status=已处理·无可用",
            )
        )
    return issues


def verify_file(path: Path, *, mode: Mode, strict: bool = True) -> list[dict[str, str]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    issues = verify_envelope(doc, mode)
    if mode == "commentary":
        issues.extend(verify_commentary_entries(doc))
    else:
        issues.extend(verify_witness_entries(doc))
    if strict:
        pass
    return issues


def verify_dynasty_commentary(dynasty: str, *, commentary_dir: Path) -> list[dict[str, str]]:
    """朝代级配额：顾颉刚占比、角度词跨文件重复。"""
    issues: list[dict[str, str]] = []
    files = sorted(commentary_dir.glob("GLBL_*_评述.json"))
    docs: list[dict[str, Any]] = []
    for fp in files:
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if str(doc.get("二级朝代坐标") or "").strip() != dynasty.strip():
            continue
        if doc.get("status") == STATUS_EMPTY:
            continue
        docs.append(doc)
    if not docs:
        issues.append(_issue("INFO", f"朝代「{dynasty}」无已完成评述文件"))
        return issues

    gu_files = 0
    angle_map: dict[str, list[str]] = {}
    for doc in docs:
        eid = str(doc.get("史略ID") or "")
        name = str(doc.get("史略名称") or "")
        blob = json.dumps(doc.get("entries") or [], ensure_ascii=False)
        if GU_MARKERS.search(blob):
            gu_files += 1
        for row in doc.get("entries") or []:
            if not isinstance(row, dict):
                continue
            ang = _angle(str(row.get("评述标题") or ""))
            if ang:
                angle_map.setdefault(ang, []).append(f"{eid}:{name}")

    ratio = gu_files / len(docs)
    if ratio > 0.5:
        issues.append(
            _issue(
                "CRITICAL",
                f"朝代「{dynasty}」含顾颉刚/古史辨的文件 {gu_files}/{len(docs)}"
                f"（{ratio:.0%}）> 50%，须换方向重做超额条目",
            )
        )
    elif ratio > 0.35:
        issues.append(
            _issue(
                "WARN",
                f"朝代「{dynasty}」顾颉刚占比 {ratio:.0%}，接近 50% 上限",
            )
        )

    for ang, holders in sorted(angle_map.items(), key=lambda x: -len(x[1])):
        if len(holders) >= 3:
            issues.append(
                _issue(
                    "WARN",
                    f"角度词「{ang}」跨文件出现 {len(holders)} 次"
                    f"（如 {', '.join(holders[:4])}），疑同质化模板",
                )
            )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="校验评述/见证 JSON")
    parser.add_argument("file", type=Path, nargs="?")
    parser.add_argument("--mode", choices=["commentary", "witness"], default=None)
    parser.add_argument("--strict", action="store_true", default=True)
    parser.add_argument("--no-strict", action="store_true")
    parser.add_argument("--dynasty", default=None, help="朝代级评述配额检查")
    parser.add_argument(
        "--commentary-dir",
        type=Path,
        default=None,
        help="评述目录（配合 --dynasty）",
    )
    args = parser.parse_args()
    strict = not args.no_strict

    if args.dynasty:
        from paths_config import histograph_paths  # noqa: E402

        cdir = args.commentary_dir or histograph_paths()["commentary"]
        issues = verify_dynasty_commentary(args.dynasty, commentary_dir=cdir)
        for it in issues:
            print(f"{it['level']}: {it['msg']}")
        critical = [i for i in issues if i["level"] == "CRITICAL"]
        if critical:
            print(f"\n⛔ {len(critical)} CRITICAL")
            return 1
        print(f"\n✅ dynasty verify OK（{len(issues)} issues，0 CRITICAL）")
        return 0

    if not args.file or not args.mode:
        parser.error("单文件校验须提供 file 与 --mode；或使用 --dynasty")
    issues = verify_file(args.file, mode=args.mode, strict=strict)
    for it in issues:
        print(f"{it['level']}: {it['msg']}")
    critical = [i for i in issues if i["level"] == "CRITICAL"]
    if critical:
        print(f"\n⛔ {len(critical)} CRITICAL")
        return 1
    print(f"\n✅ verify OK（{len(issues)} issues，0 CRITICAL）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
