"""评述 / 见证补全：DeepSeek v4 Pro、索引解析、prompt、落盘。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
OPENCLAW_ROOT = SKILL_ROOT.parent
REFERENCE = SKILL_ROOT / "reference"

if str(OPENCLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENCLAW_ROOT))

from paths_config import histograph_paths, validate_histograph_root  # noqa: E402
from llm.config import MODEL_PRO, ensure_deepseek_v4_pro as pin_deepseek_v4_pro  # noqa: E402

REQUIRED_MODEL = MODEL_PRO
Mode = Literal["commentary", "witness"]

STATUS_DONE = "done"
STATUS_EMPTY = "已处理·无可用"

HAN_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def count_han(text: str) -> int:
    return len(HAN_RE.findall(text or ""))


def clamp_han(text: str, max_han: int) -> str:
    """按汉字计数截断，避免 LLM 略超长导致 verify 失败。"""
    s = str(text or "").strip()
    while s and count_han(s) > max_han:
        s = s[:-1]
    return s


def load_env() -> None:
    env_file = OPENCLAW_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def ensure_deepseek_v4_pro() -> str:
    load_env()
    from llm.config import deepseek_settings, get_provider_name  # noqa: WPS433

    if get_provider_name() != "deepseek":
        raise RuntimeError("评述/见证补全仅支持 HIST_LLM_PROVIDER=deepseek")
    settings = deepseek_settings()
    if str(settings.get("api_key", "")).strip() == "":
        raise RuntimeError("请设置 DEEPSEEK_API_KEY（tools/openclaw-historiography/.env）")
    return pin_deepseek_v4_pro()


def call_llm(prompt: str, *, session_prefix: str, timeout_sec: int = 900) -> str:
    ensure_deepseek_v4_pro()
    from llm.provider import run_agent_turn  # noqa: WPS433

    sid = session_prefix + hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]
    res = run_agent_turn(
        prompt,
        session_id=sid,
        timeout_sec=timeout_sec,
        temperature=0.2,
    )
    return str(res.get("result") or "").strip()


def extract_json_array(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("["), text.rfind("]")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def load_index(index_path: Path | None = None) -> dict[str, Any]:
    paths = histograph_paths()
    p = index_path or paths["global_index"]
    return json.loads(p.read_text(encoding="utf-8"))


def _index_entries(doc: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [e for e in doc if isinstance(e, dict)]
    entries = doc.get("entries")
    if isinstance(entries, list):
        return entries
    for v in doc.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "史略ID" in v[0]:
            return v
    return []


def find_entry(
    *,
    entry_id: str | None = None,
    name: str | None = None,
    index_path: Path | None = None,
) -> dict[str, Any]:
    doc = load_index(index_path)
    entries = _index_entries(doc)
    if entry_id:
        for e in entries:
            if str(e.get("史略ID", "")).strip() == entry_id.strip():
                return e
        raise KeyError(f"索引中未找到 {entry_id}")
    if name:
        name = name.strip()
        matches = [e for e in entries if str(e.get("史略名称", "")).strip() == name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise KeyError(f"史略名称 {name!r} 在索引中有多条，请用 --id 指定 GLBL")
        raise KeyError(f"索引中未找到史略名称 {name!r}")
    raise ValueError("必须提供 entry_id 或 name")


def list_entries_by_dynasty(
    dynasty: str,
    *,
    index_path: Path | None = None,
) -> list[dict[str, Any]]:
    doc = load_index(index_path)
    out = []
    for e in _index_entries(doc):
        if str(e.get("二级朝代坐标") or "").strip() == dynasty.strip():
            out.append(e)
    return out


def safe_name(name: str) -> str:
    return re.sub(r"[/\\:\s]+", "_", (name or "").strip()) or "未命名"


def output_path(mode: Mode, entry: dict[str, Any], paths: dict[str, Path] | None = None) -> Path:
    paths = paths or histograph_paths()
    eid = str(entry.get("史略ID", "")).strip()
    name = safe_name(str(entry.get("史略名称", "")).strip())
    if mode == "commentary":
        return paths["commentary"] / f"{eid}_{name}_评述.json"
    return paths["witness"] / f"{eid}_{name}_见证.json"


def read_rule(mode: Mode) -> str:
    fp = REFERENCE / ("评述遴选规则.md" if mode == "commentary" else "见证遴选规则.md")
    return fp.read_text(encoding="utf-8")


def _primary_book_title(cited: str) -> str:
    """《史记·五帝本纪》→ 史记；无书名号则取 · 前。"""
    s = (cited or "").strip()
    m = re.search(r"《([^》]+)》", s)
    inner = m.group(1) if m else s
    inner = inner.strip()
    if "·" in inner:
        inner = inner.split("·", 1)[0].strip()
    if " " in inner:
        inner = inner.split(" ", 1)[0].strip()
    return inner


def extract_bibliography_from_detail_text(text: str) -> list[str]:
    """从翻译详情文末 *参考著作：* 抽取条目（保留书名号）。

    兼容两种写法：
    - 换行列表：`*参考著作：*\\n- 《史记》\\n- 《汉书》`
    - 同行连写：`*参考著作：《尚书·尧典》《韩非子·说疑》《竹书纪年》*`
    """
    if not text:
        return []
    m = re.search(
        r"\*{0,2}\s*参考著作\s*[:：]\s*\*{0,2}\s*(?P<body>.*?)(?:\n\n\n|\Z)",
        text,
        re.DOTALL,
    )
    if not m:
        return []
    body = m.group("body").strip()
    # 去掉收尾装饰星号（同行写法常把整段包在 *...* 里）
    body = re.sub(r"^\*+|\*+$", "", body).strip()
    # 优先按书名号切分（同行连写）
    books = re.findall(r"《[^》]+》", body)
    if books:
        return books
    items: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*・•]\s*", "", line).strip()
        line = re.sub(r"^\*+|\*+$", "", line).strip()
        if line:
            items.append(line)
    return items


def load_detail_bibliography(
    entry: dict[str, Any],
    paths: dict[str, Path] | None = None,
) -> list[str]:
    """合并 04 译文 + 06 详情 中的参考著作列表（去重保序）。"""
    paths = paths or histograph_paths()
    eid = str(entry.get("史略ID", "")).strip()
    name = safe_name(str(entry.get("史略名称", "")).strip())
    texts: list[str] = []

    trans_dir = paths["translate_output"]
    if trans_dir.is_dir():
        for fp in sorted(trans_dir.glob(f"{eid}_*.json")):
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
                t = str(doc.get("翻译详情") or "")
                if t:
                    texts.append(t)
            except (json.JSONDecodeError, OSError):
                continue

    detail_dir = paths.get("dynasty_knowledge_details")
    if detail_dir and detail_dir.is_dir():
        for fp in sorted(detail_dir.glob(f"{eid}_*.json")):
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
                t = str(doc.get("翻译详情") or "")
                if t:
                    texts.append(t)
            except (json.JSONDecodeError, OSError):
                continue
        # 亦试名称匹配
        alt = detail_dir / f"{eid}_{name}.json"
        if alt.is_file() and not any(str(alt) in str(p) for p in []):
            pass

    seen: set[str] = set()
    out: list[str] = []
    for text in texts:
        for item in extract_bibliography_from_detail_text(text):
            key = _primary_book_title(item) or item
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out


def bibliography_exclusion_set(bib_items: list[str]) -> set[str]:
    """主书名集合，用于判定评述著作是否撞车。"""
    return {_primary_book_title(x) for x in bib_items if _primary_book_title(x)}


# 二十四史论赞套语（可破主书名排除）
ZHENGSHI_LUNZAN_RE = re.compile(
    r"(太史公曰|赞曰|评曰|史臣曰|论曰|呜呼)"
)


def is_zhengshi_lunzan(row: dict[str, Any] | None = None, *, work: str = "", content: str = "", title: str = "") -> bool:
    """是否为正史史家论赞（太史公曰/赞曰/评曰/史臣曰/论曰等）。"""
    if row:
        work = str(row.get("评述著作") or work)
        content = str(row.get("评述内容") or content)
        title = str(row.get("评述标题") or title)
        author = str(row.get("评述人") or "")
    else:
        author = ""
    blob = f"{work}\n{content}\n{title}\n{author}"
    return bool(ZHENGSHI_LUNZAN_RE.search(blob))


def is_cited_in_bibliography(work: str, excluded_primaries: set[str]) -> bool:
    prim = _primary_book_title(work)
    return bool(prim) and prim in excluded_primaries


def filter_commentary_against_bibliography(
    items: list[dict[str, Any]],
    excluded_primaries: set[str],
) -> list[dict[str, Any]]:
    if not excluded_primaries:
        return items
    kept: list[dict[str, Any]] = []
    for row in items:
        work = str(row.get("评述著作") or "")
        if is_cited_in_bibliography(work, excluded_primaries) and not is_zhengshi_lunzan(row):
            continue
        kept.append(row)
    return kept


def build_prompt(
    mode: Mode,
    entry: dict[str, Any],
    *,
    extra_prompt: str = "",
) -> str:
    rules = read_rule(mode)
    eid = str(entry.get("史略ID", "")).strip()
    name = str(entry.get("史略名称", "")).strip()
    dynasty = str(entry.get("二级朝代坐标") or "").strip()
    category = str(entry.get("史略分类") or "").strip()
    if mode == "commentary":
        bib = load_detail_bibliography(entry)
        bib_block = (
            "\n".join(f"- {b}" for b in bib)
            if bib
            else "- （未找到详情参考著作列表；仍须避免复述正史叙事性共识）"
        )
        excl = sorted(bibliography_exclusion_set(bib))
        excl_line = "、".join(f"《{x}》" for x in excl) if excl else "（无）"
        task = (
            f"请为下列史略产出评述 JSON 数组。\n"
            f"- 史略ID: {eid}\n"
            f"- 史略名称: {name}\n"
            f"- 二级朝代坐标: {dynasty}\n"
            f"- 史略分类: {category}\n\n"
            "## 已用书目（详情参考文献）——禁止再作评述来源\n"
            f"{bib_block}\n\n"
            f"主书名排除集：{excl_line}\n"
            "凡评述著作主书名落在排除集内的条目一律不要输出。\n\n"
            "## 质量要求\n"
            "- 必须是**评价性**声音（褒贬/解释框架/立场挑战），禁止仅记录事迹或姓氏溯源的史料充评述。\n"
            "- **优先查找二十四史史家论赞**（太史公曰/赞曰/评曰/史臣曰/论曰/呜呼+史臣曰等）；"
            "有则可收 1 条；论赞可破「详情已列该书」的主书名排除，但不得用本纪叙事冒充论赞。\n"
            "- 必须是**差异化、多元化**观点；禁止同质化共识复读；禁止顾颉刚「层累说」万能片尾。\n"
            "- 教材级框架（层累疑古 / 禅让真假 / 信史vs神话）每文件最多 1 条，且不得放第 1 条。\n"
            "- 上古/传说条目：存在性质疑可作为高阶角度之一，但非必填。\n"
            "- **写作形式**：一段完整议论；古文原文自然嵌入；"
            "**禁止**「原文：…白话：…」或「译文：」分离结构。\n"
            "- 有正史论赞则**必须收 1 条**（通常 P01），此外最多再补 5 条其他评述（合计 ≤6）；"
            "无论赞则最多 5 条；若找不到互有张力的多元评述，输出 []。\n\n"
            "每条字段：评述ID、评述标题、史略ID、史略名称、评述人、评述著作、"
            "评述内容、评述简介、评述年代。\n"
            f"评述ID 形如 {eid}_P01；标题形如「{name}·角度」。"
        )
    else:
        is_dianzhi = category in ("典制", "dianzhi") or "制" in name
        dianzhi_hint = (
            "- 制度类：文物介绍必须写明物证所属朝代，以及距传说起源大约多少年"
            "（或写明「后世成型期物证，非起源期」）。\n"
            if is_dianzhi
            else ""
        )
        task = (
            f"请为下列史略产出见证 JSON 数组。\n"
            f"- 史略ID: {eid}\n"
            f"- 史略名称: {name}\n"
            f"- 二级朝代坐标: {dynasty}\n"
            f"- 史略分类: {category}\n\n"
            "## 质量要求\n"
            "- 见证力分层：A+本人造物 > A确证陵墓/出土 > B早期存在性（上古）"
            " > C专属空间 > D后世纪念 > F文学见证 > E软关联。\n"
            "- **附加 F 文学见证**：额外 0–1 条，不计入 1–5 主名额；"
            "取全史略最知名、影响力最大的艺术创作一条；字段 `附加文学见证: true`；"
            "- 附加 F 排 entries 末尾；`附加文学见证: true`；诗歌须引原文"
            "（≤8句全文，>8句引2–8句）；**介绍须全中文，禁止夹杂英文**。\n"
            "- **F 层（主名额内仍禁止多条诗词）**：后世诗、词、曲、赋、杂剧、小说等；"
            "证明文化记忆与艺术再现。本人著作/作品仍归 A+；学术论赞归 08 评述。\n"
            "- **E 层（现代纪念碑、纯传说软关联、「传为」陵墓）不得标 P0**；"
            "仅有 E 时优先输出 []（空结果勇气）。\n"
            "- 上古人物：确有的早期存在性物证（如陈侯因齐敦类）必须纳入。\n"
            "- 禁止同时代无关物；禁止用「唯一能找到」的现代纪念物充 P0。\n"
            "- 不限于博物馆；原器佚失可写拓本/著录。\n"
            f"{dianzhi_hint}"
            "- 无合格见证则输出 []。\n\n"
            "每条字段：文物ID、文物标题、史略ID、史略名称、现藏地点、文物介绍、"
            "文物图片、文物优先级、优先级判定理由。\n"
            f"文物ID 形如 {eid}_W01；文物图片必须 \"\"；P0–P4 不重复，降序。"
        )
    extra = ""
    if extra_prompt.strip():
        extra = f"\n\n## 本批次额外约束（必须遵守）\n{extra_prompt.strip()}\n"
    return (
        f"{rules}\n\n---\n\n## 本条任务\n\n{task}{extra}\n\n"
        "只输出一个 JSON 数组（可用 ```json 围栏）。不要输出信封或其他说明。"
    )



def normalize_commentary_entries(
    raw: list[dict[str, Any]],
    *,
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    eid = str(entry.get("史略ID", "")).strip()
    name = str(entry.get("史略名称", "")).strip()
    out: list[dict[str, Any]] = []
    for i, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "评述ID": f"{eid}_P{i:02d}",
                "评述标题": str(row.get("评述标题") or "").strip(),
                "史略ID": eid,
                "史略名称": name,
                "评述人": str(row.get("评述人") or "").strip(),
                "评述著作": str(row.get("评述著作") or "").strip(),
                "评述内容": str(row.get("评述内容") or "").strip(),
                "评述简介": str(row.get("评述简介") or "").strip(),
                "评述年代": str(row.get("评述年代") or "").strip(),
            }
        )
    return out


MAX_OTHER_COMMENTARY = 5  # 论赞之外最多再补
MAX_COMMENTARY_WITH_LUNZAN = 6  # 1 论赞 + 5 其他
MAX_COMMENTARY_ENTRIES = MAX_COMMENTARY_WITH_LUNZAN  # 总硬上限（兼容旧名）


def commentary_has_lunzan(items: list[dict[str, Any]]) -> bool:
    return any(is_zhengshi_lunzan(row) for row in items if isinstance(row, dict))


def split_lunzan_and_others(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lunzan: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        if is_zhengshi_lunzan(row):
            lunzan.append(row)
        else:
            others.append(row)
    return lunzan, others


def merge_lunzan_into_commentary(
    existing: list[dict[str, Any]],
    lunzan: dict[str, Any],
    *,
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """
    将 1 条正史论赞插入为 P01。
    规则：论赞必收；除此之外最多保留 5 条其他 → 合计 ≤6。
    不置换已有其他评述（仅当其他已超 5 时截断超额部分）。
    """
    items = [r for r in existing if isinstance(r, dict)]
    if commentary_has_lunzan(items):
        return normalize_commentary_entries(items, entry=entry), "skip_has_lunzan"

    _prev_lunzan, others = split_lunzan_and_others(items)
    truncated = len(others) > MAX_OTHER_COMMENTARY
    others = others[:MAX_OTHER_COMMENTARY]
    merged = [lunzan] + others
    action = "append_keep_others"
    if truncated:
        action += "_trim_others"
    return normalize_commentary_entries(merged, entry=entry), action


def normalize_witness_entries(
    raw: list[dict[str, Any]],
    *,
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    eid = str(entry.get("史略ID", "")).strip()
    name = str(entry.get("史略名称", "")).strip()
    # 按优先级排序
    pri_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
    rows = [r for r in raw if isinstance(r, dict)]
    rows.sort(key=lambda r: pri_rank.get(str(r.get("文物优先级") or "").strip().upper(), 99))
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        title = str(row.get("文物标题") or row.get("文物名称") or "").strip()
        intro = str(row.get("文物介绍") or row.get("详细介绍") or "").strip()
        pri = str(row.get("文物优先级") or "").strip().upper()
        if pri and not pri.startswith("P"):
            pri = f"P{pri}" if pri.isdigit() else pri
        out.append(
            {
                "文物ID": f"{eid}_W{i:02d}",
                "文物标题": title,
                "史略ID": eid,
                "史略名称": name,
                "现藏地点": str(row.get("现藏地点") or "").strip(),
                "文物介绍": intro,
                "文物图片": "",
                "文物优先级": pri,
                "优先级判定理由": str(row.get("优先级判定理由") or "").strip(),
                **(
                    {"附加文学见证": True}
                    if row.get("附加文学见证") is True
                    else {}
                ),
            }
        )
    return out


def build_envelope(
    mode: Mode,
    entry: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    status = STATUS_DONE if items else STATUS_EMPTY
    return {
        "schema_version": 1,
        "mode": mode,
        "史略ID": str(entry.get("史略ID", "")).strip(),
        "史略名称": str(entry.get("史略名称", "")).strip(),
        "史略分类": str(entry.get("史略分类") or "").strip(),
        "二级朝代坐标": str(entry.get("二级朝代坐标") or "").strip(),
        "status": status,
        "entry_count": len(items),
        "processed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": REQUIRED_MODEL,
        "entries": items,
    }


def write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_manifest(
    mode: Mode,
    entry: dict[str, Any],
    doc: dict[str, Any],
    out_file: Path,
    *,
    paths: dict[str, Path] | None = None,
) -> Path:
    paths = paths or histograph_paths()
    dynasty = str(entry.get("二级朝代坐标") or "未知").strip() or "未知"
    root = paths["commentary"] if mode == "commentary" else paths["witness"]
    label = "评述" if mode == "commentary" else "见证"
    mf_path = root / f"{dynasty}_{label}_manifest.json"
    if mf_path.is_file():
        mf = json.loads(mf_path.read_text(encoding="utf-8"))
    else:
        mf = {"dynasty": dynasty, "mode": mode, "completed": []}
    glbl = str(entry.get("史略ID", "")).strip()
    completed = [c for c in (mf.get("completed") or []) if c.get("glbl") != glbl]
    completed.append(
        {
            "glbl": glbl,
            "name": str(entry.get("史略名称", "")).strip(),
            "file": out_file.name,
            "status": doc.get("status"),
            "entry_count": doc.get("entry_count", 0),
            "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    mf["dynasty"] = dynasty
    mf["mode"] = mode
    mf["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mf["completed"] = completed
    write_json(mf_path, mf)
    return mf_path


def compose_one(
    mode: Mode,
    *,
    entry_id: str | None = None,
    name: str | None = None,
    index_path: Path | None = None,
    dry_run: bool = False,
    skip_verify: bool = False,
    revise: bool = True,
    extra_prompt: str = "",
) -> dict[str, Any]:
    validate_histograph_root()
    paths = histograph_paths()
    entry = find_entry(entry_id=entry_id, name=name, index_path=index_path)
    prompt = build_prompt(mode, entry, extra_prompt=extra_prompt)
    if dry_run:
        return {"dry_run": True, "prompt": prompt, "entry": entry}

    raw_text = call_llm(prompt, session_prefix=f"cw-{mode}-")
    raw_items = extract_json_array(raw_text)
    if mode == "commentary":
        items = normalize_commentary_entries(raw_items, entry=entry)
        excl = bibliography_exclusion_set(load_detail_bibliography(entry, paths))
        items = filter_commentary_against_bibliography(items, excl)
        # 过滤后重编号
        items = normalize_commentary_entries(items, entry=entry)
    else:
        items = normalize_witness_entries(raw_items, entry=entry)

    doc = build_envelope(mode, entry, items)
    out = output_path(mode, entry, paths)
    write_json(out, doc)

    from verify_cw import verify_file  # noqa: WPS433

    issues = verify_file(out, mode=mode, strict=True)
    critical = [i for i in issues if i["level"] == "CRITICAL"]
    if critical and revise:
        bib = load_detail_bibliography(entry, paths) if mode == "commentary" else []
        bib_hint = ""
        if mode == "commentary":
            bib_hint = (
                "\n已用书目排除（禁止再引用）：\n"
                + "\n".join(f"- {b}" for b in bib)
                + "\n必须输出差异化评价性观点；禁止翻译体「原文/白话」；"
                "禁止记录性史料充评述；禁止顾颉刚万能片尾。\n"
            )
        else:
            bib_hint = (
                "\n见证分层：A+造物>A确证陵墓>B早期存在性>C专属>D纪念>F文学见证>E软关联；"
                "E/F不得P0；仅有E则输出[]；制度类须写时间跨度；"
                "文学见证须写定本出处与后世观点。\n"
            )
        if extra_prompt.strip():
            bib_hint += f"\n本批次额外约束：\n{extra_prompt.strip()}\n"
        fix_prompt = (
            f"下列 JSON 未通过校验，请输出修正后的 **entries 数组**（仅数组）。\n"
            f"错误：{json.dumps(critical, ensure_ascii=False)}\n"
            f"{bib_hint}\n"
            f"当前文件内容：\n{json.dumps(doc, ensure_ascii=False, indent=2)}\n"
        )
        raw2 = call_llm(fix_prompt, session_prefix=f"cw-{mode}-rev-")
        raw_items2 = extract_json_array(raw2)
        if mode == "commentary":
            items = normalize_commentary_entries(raw_items2, entry=entry)
            excl = bibliography_exclusion_set(load_detail_bibliography(entry, paths))
            items = filter_commentary_against_bibliography(items, excl)
            items = normalize_commentary_entries(items, entry=entry)
        else:
            items = normalize_witness_entries(raw_items2, entry=entry)
        doc = build_envelope(mode, entry, items)
        write_json(out, doc)
        issues = verify_file(out, mode=mode, strict=True)
        critical = [i for i in issues if i["level"] == "CRITICAL"]

    if critical and not skip_verify:
        raise RuntimeError(
            f"verify 未通过 ({out.name}): "
            + "; ".join(i["msg"] for i in critical[:8])
        )

    mf = update_manifest(mode, entry, doc, out, paths=paths)
    return {
        "path": str(out),
        "manifest": str(mf),
        "status": doc["status"],
        "entry_count": doc["entry_count"],
        "issues": issues,
    }


def compose_dynasty(
    mode: Mode,
    dynasty: str,
    *,
    max_n: int = 1,
    index_path: Path | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    entries = list_entries_by_dynasty(dynasty, index_path=index_path)
    results = []
    for e in entries[: max(0, max_n)]:
        r = compose_one(
            mode,
            entry_id=str(e.get("史略ID")),
            index_path=index_path,
            dry_run=dry_run,
        )
        results.append(r)
        if dry_run:
            break
    return results
