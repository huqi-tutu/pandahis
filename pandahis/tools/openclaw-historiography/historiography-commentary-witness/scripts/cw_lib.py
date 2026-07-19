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

REQUIRED_MODEL = "deepseek-v4-pro"
Mode = Literal["commentary", "witness"]

STATUS_DONE = "done"
STATUS_EMPTY = "已处理·无可用"

HAN_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def count_han(text: str) -> int:
    return len(HAN_RE.findall(text or ""))


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
    os.environ["HIST_LLM_PROVIDER"] = "deepseek"
    os.environ["DEEPSEEK_MODEL"] = REQUIRED_MODEL
    from llm.config import deepseek_settings, get_provider_name, provider_label  # noqa: WPS433

    if get_provider_name() != "deepseek":
        raise RuntimeError("评述/见证补全仅支持 HIST_LLM_PROVIDER=deepseek")
    settings = deepseek_settings()
    if str(settings.get("api_key", "")).strip() == "":
        raise RuntimeError("请设置 DEEPSEEK_API_KEY（tools/openclaw-historiography/.env）")
    if str(settings.get("model", "")) != REQUIRED_MODEL:
        raise RuntimeError(f"模型必须为 {REQUIRED_MODEL}，当前为 {settings.get('model')!r}")
    return provider_label()


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


def find_entry(
    *,
    entry_id: str | None = None,
    name: str | None = None,
    index_path: Path | None = None,
) -> dict[str, Any]:
    doc = load_index(index_path)
    entries = doc.get("entries") or []
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
    for e in doc.get("entries") or []:
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


def build_prompt(mode: Mode, entry: dict[str, Any]) -> str:
    rules = read_rule(mode)
    eid = str(entry.get("史略ID", "")).strip()
    name = str(entry.get("史略名称", "")).strip()
    dynasty = str(entry.get("二级朝代坐标") or "").strip()
    category = str(entry.get("史略分类") or "").strip()
    if mode == "commentary":
        task = (
            f"请为下列史略产出评述 JSON 数组（找分歧；无可用则输出 []）。\n"
            f"- 史略ID: {eid}\n"
            f"- 史略名称: {name}\n"
            f"- 二级朝代坐标: {dynasty}\n"
            f"- 史略分类: {category}\n\n"
            "每条须含字段：评述ID、评述标题、史略ID、史略名称、评述人、评述著作、"
            "评述内容、评述简介、评述年代。\n"
            f"评述ID 形如 {eid}_P01 起编；评述标题形如「{name}·角度」。"
        )
    else:
        task = (
            f"请为下列史略产出见证文物 JSON 数组（四维度；无直接相关则输出 []）。\n"
            f"- 史略ID: {eid}\n"
            f"- 史略名称: {name}\n"
            f"- 二级朝代坐标: {dynasty}\n"
            f"- 史略分类: {category}\n\n"
            "每条须含字段：文物ID、文物标题、史略ID、史略名称、现藏地点、文物介绍、"
            "文物图片、文物优先级、优先级判定理由。\n"
            f"文物ID 形如 {eid}_W01 起编；文物图片必须为 \"\"；"
            "优先级 P0–P4 不重复，按优先级降序。"
        )
    return (
        f"{rules}\n\n---\n\n## 本条任务\n\n{task}\n\n"
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
) -> dict[str, Any]:
    validate_histograph_root()
    paths = histograph_paths()
    entry = find_entry(entry_id=entry_id, name=name, index_path=index_path)
    prompt = build_prompt(mode, entry)
    if dry_run:
        return {"dry_run": True, "prompt": prompt, "entry": entry}

    raw_text = call_llm(prompt, session_prefix=f"cw-{mode}-")
    raw_items = extract_json_array(raw_text)
    if mode == "commentary":
        items = normalize_commentary_entries(raw_items, entry=entry)
    else:
        items = normalize_witness_entries(raw_items, entry=entry)

    doc = build_envelope(mode, entry, items)
    out = output_path(mode, entry, paths)
    write_json(out, doc)

    from verify_cw import verify_file  # noqa: WPS433

    issues = verify_file(out, mode=mode, strict=True)
    critical = [i for i in issues if i["level"] == "CRITICAL"]
    if critical and revise:
        fix_prompt = (
            f"下列 JSON 未通过校验，请输出修正后的 **entries 数组**（仅数组）。\n"
            f"错误：{json.dumps(critical, ensure_ascii=False)}\n\n"
            f"当前文件内容：\n{json.dumps(doc, ensure_ascii=False, indent=2)}\n"
        )
        raw2 = call_llm(fix_prompt, session_prefix=f"cw-{mode}-rev-")
        raw_items2 = extract_json_array(raw2)
        if mode == "commentary":
            items = normalize_commentary_entries(raw_items2, entry=entry)
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
