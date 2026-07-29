"""人物关系补全：DeepSeek v4 Pro 调用、索引解析、prompt 与产出。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
OPENCLAW_ROOT = SKILL_ROOT.parent

if str(OPENCLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENCLAW_ROOT))

from paths_config import histograph_paths, validate_histograph_root  # noqa: E402

REQUIRED_MODEL = "deepseek-v4-pro"
PERSON_CATEGORIES = frozenset({"君王", "诸侯", "宗戚", "文臣", "武将", "宦官", "庶众"})
RELATION_CATEGORIES = ("家庭", "同僚", "师从", "外敌", "好友")
MAX_CATEGORY_LLM_ATTEMPTS = 3
CATEGORY_ID_PREFIX = {
    "家庭": "HD-FAM",
    "同僚": "HD-COL",
    "师从": "HD-MAS",
    "外敌": "HD-FOE",
    "好友": "HD-FRI",
}


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
    """固定使用 DeepSeek v4 Pro；返回 model label。"""
    load_env()
    os.environ["HIST_LLM_PROVIDER"] = "deepseek"
    os.environ["DEEPSEEK_MODEL"] = REQUIRED_MODEL
    from llm.config import deepseek_settings, get_provider_name, provider_label  # noqa: WPS433

    if get_provider_name() != "deepseek":
        raise RuntimeError("人物关系补全仅支持 HIST_LLM_PROVIDER=deepseek")
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


def read_text(path: Path, *, max_chars: int = 120_000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n…（截断）"
    return text


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


def is_person_entry(entry: dict[str, Any]) -> bool:
    return str(entry.get("史略分类", "")).strip() in PERSON_CATEGORIES


def load_grounding(entry: dict[str, Any], paths: dict[str, Path]) -> str:
    entry_id = str(entry.get("史略ID", "")).strip()
    name = str(entry.get("史略名称", "")).strip()
    chunks: list[str] = []

    # 04 单条译文
    trans_dir = paths["translate_output"]
    if trans_dir.is_dir():
        for fp in trans_dir.glob(f"{entry_id}_*.json"):
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
                detail = str(doc.get("翻译详情") or "").strip()
                if detail:
                    chunks.append(f"## 04史料翻译 · {fp.name}\n\n{detail}")
                    break
            except (OSError, json.JSONDecodeError):
                continue

    # 06 详情
    detail_dir = paths["dynasty_knowledge_details"]
    if detail_dir.is_dir():
        for fp in detail_dir.glob(f"{entry_id}_*.json"):
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
                detail = str(doc.get("翻译详情") or doc.get("详情") or "").strip()
                if detail:
                    chunks.append(f"## 06朝代知识详情 · {fp.name}\n\n{detail}")
                    break
            except (OSError, json.JSONDecodeError):
                continue

    meta = [
        f"史略ID: {entry_id}",
        f"史略名称: {name}",
        f"史略分类: {entry.get('史略分类', '')}",
        f"朝代: {entry.get('二级朝代坐标', '')} / {entry.get('三级政权坐标', '')}",
        f"简介: {entry.get('史略简介', '')}",
        f"史料出处: {entry.get('主要史料出处', '')}",
    ]
    if not chunks:
        blurb = str(entry.get("原文字句") or entry.get("史略简介") or "").strip()
        if blurb:
            chunks.append(f"## 索引摘要\n\n{blurb}")
    return "\n".join(meta) + "\n\n" + "\n\n".join(chunks)


def _category_rules(category: str) -> str:
    prefix = CATEGORY_ID_PREFIX.get(category, "HD-REL")
    return f"""本次**只整理「{category}」类别**的关系；不要输出其他类别。
- `关系类别` 必须全部为 **{category}**
- `关系ID` 前缀：**{prefix}**
- 无可靠史料的不写；有史料则**尽量写全**该类别下的关键人物，不设条数上限
- 同一 `关系类别` + `关系层级` + `关系节点标题` 只能一条；多面关系合并入 `关系简述`"""


def build_category_prompt(
    entry: dict[str, Any],
    grounding: str,
    paths: dict[str, Path],
    category: str,
) -> str:
    taxonomy = read_text(paths["root"] / "关系数据整理提示词.md")
    schema = read_text(SKILL_ROOT / "reference" / "schema.md")
    subject = str(entry.get("史略名称", "")).strip()
    if category not in RELATION_CATEGORIES:
        raise ValueError(f"invalid category: {category!r}")
    return f"""你是 pandahis 人物关系数据整理员。请为下列人物产出关系图谱 JSON。

# 硬性要求

1. **只输出一个 JSON 数组**，不要 markdown 说明、不要代码块外的文字。
2. 每条记录字段：`关联史略名称`、`关系ID`、`关系类别`、`关系层级`、`关系节点标题`、`上级连接线标题`、`关系简述`；层级 ≥ 二级时填 `所属一级关系` 等链字段（见 schema）。
3. `关联史略名称` 固定为 **{subject}**。
4. {_category_rules(category)}
5. 任意路径 **最多四级**；禁止五级与 `所属四级关系`。
6. 无可靠史料不编造；`关系简述` 1–2 句写依据要点。
7. 禁止 君臣/敌对 旧类别名（同僚·敌对 → `同僚`；外部阵营 → `外敌`）。

# 关系 taxonomy（SSOT）

{taxonomy}

# JSON 字段说明

{schema}

# 待整理人物

{grounding}

请直接输出「{category}」类别的 JSON 数组（若无任何可写条目，输出 `[]`）：
"""


def build_prompt(entry: dict[str, Any], grounding: str, paths: dict[str, Path]) -> str:
    """兼容 dry-run：拼接全部类别 prompt。"""
    parts = [
        build_category_prompt(entry, grounding, paths, cat) for cat in RELATION_CATEGORIES
    ]
    return "\n\n---\n\n".join(parts)


def normalize_records(records: list[dict[str, Any]], subject: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    counters = {k: 0 for k in CATEGORY_ID_PREFIX.values()}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        row = dict(rec)
        row["关联史略名称"] = subject
        cat = str(row.get("关系类别", "")).strip()
        if cat == "君臣":
            cat = "同僚"
        if cat == "敌对":
            cat = "外敌"
        row["关系类别"] = cat
        rid = str(row.get("关系ID", "")).strip()
        prefix = CATEGORY_ID_PREFIX.get(cat, "HD-REL")
        if not rid:
            counters[prefix] = counters.get(prefix, 0) + 1
            row["关系ID"] = f"{prefix}-{counters[prefix]:03d}"
        if not row.get("record_id"):
            row["record_id"] = f"rec{uuid.uuid4().hex[:12]}"
        out.append(row)
    return out


def reassign_relation_ids(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并多轮类别产出后，按类别重新顺序编号。"""
    counters = {prefix: 0 for prefix in CATEGORY_ID_PREFIX.values()}
    out: list[dict[str, Any]] = []
    for rec in records:
        row = dict(rec)
        cat = str(row.get("关系类别", "")).strip()
        prefix = CATEGORY_ID_PREFIX.get(cat, "HD-REL")
        counters[prefix] = counters.get(prefix, 0) + 1
        row["关系ID"] = f"{prefix}-{counters[prefix]:03d}"
        out.append(row)
    return out


def _looks_truncated(raw: str) -> bool:
    text = raw.strip()
    if not text or extract_json_array(text):
        return False
    if text.rstrip().endswith("]") or text.rstrip().endswith("```"):
        return False
    return "[" in text


def _retry_category_prompt(
    base_prompt: str,
    *,
    category: str,
    subject: str,
    last_raw: str,
    attempt: int,
) -> str:
    if not last_raw.strip():
        return base_prompt + f"\n\n【重试 {attempt}】上次 API 返回空响应，请重新输出完整的「{category}」JSON 数组。\n"
    if _looks_truncated(last_raw):
        tail = last_raw[-1800:]
        return (
            f"{base_prompt}\n\n"
            f"【重试 {attempt}】上次输出在传输中被截断（末尾不完整）。"
            f"请重新输出**完整**的「{category}」JSON 数组，可尽量详细，不要省略关键人物。\n"
            f"截断末尾片段（勿重复已完整输出的前半）：\n```\n{tail}\n```\n"
        )
    return base_prompt + f"\n\n【重试 {attempt}】上次 JSON 无法解析，请只输出合法 JSON 数组。\n"


def _compose_category_records(
    entry: dict[str, Any],
    subject: str,
    eid: str,
    grounding: str,
    paths: dict[str, Path],
    category: str,
) -> list[dict[str, Any]]:
    base_prompt = build_category_prompt(entry, grounding, paths, category)
    last_raw = ""
    for attempt in range(1, MAX_CATEGORY_LLM_ATTEMPTS + 1):
        prompt = (
            base_prompt
            if attempt == 1
            else _retry_category_prompt(
                base_prompt,
                category=category,
                subject=subject,
                last_raw=last_raw,
                attempt=attempt,
            )
        )
        last_raw = call_llm(prompt, session_prefix=f"rel-{eid}-{category}-a{attempt}-")
        log_artifact(paths, eid, f"response_{category}_a{attempt}", last_raw)
        batch = normalize_records(extract_json_array(last_raw), subject)
        batch = [r for r in batch if str(r.get("关系类别", "")).strip() == category]
        if batch:
            return batch
    print(f"    ⚠️ 类别 {category}：{MAX_CATEGORY_LLM_ATTEMPTS} 轮均无有效产出，跳过")
    return []


def output_path(paths: dict[str, Path], subject: str) -> Path:
    return paths["person_relations"] / f"{subject}关系表.json"


def write_output(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_verify(path: Path, *, strict: bool = True) -> tuple[bool, str]:
    script = SCRIPT_DIR / "verify_relations.py"
    cmd = [sys.executable, str(script)]
    if strict:
        cmd.append("--strict")
    cmd.append(str(path))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output


def log_artifact(paths: dict[str, Path], entry_id: str, kind: str, content: str) -> Path:
    log_dir = paths["person_relations_work"] / "logs" / entry_id
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fp = log_dir / f"{ts}_{kind}.txt"
    fp.write_text(content, encoding="utf-8")
    return fp


def compose_one(
    *,
    entry_id: str | None = None,
    name: str | None = None,
    index_path: Path | None = None,
    dry_run: bool = False,
    no_llm: bool = False,
    revise_on_fail: bool = True,
    sync_db: bool = False,
    sql_out: Path | None = None,
    mysql: dict[str, Any] | None = None,
) -> Path | None:
    validate_histograph_root()
    paths = histograph_paths()
    label = ensure_deepseek_v4_pro()
    entry = find_entry(entry_id=entry_id, name=name, index_path=index_path)
    if not is_person_entry(entry):
        raise RuntimeError(
            f"{entry.get('史略ID')} {entry.get('史略名称')} 非人物六类（{entry.get('史略分类')}），跳过关系补全"
        )
    subject = str(entry.get("史略名称", "")).strip()
    eid = str(entry.get("史略ID", "")).strip()
    grounding = load_grounding(entry, paths)
    prompt = build_prompt(entry, grounding, paths)
    out_path = output_path(paths, subject)

    print(f"LLM: {label}")
    print(f"人物: {eid} {subject} ({entry.get('史略分类')})")
    print(f"产出: {out_path}")

    if dry_run:
        log_artifact(paths, eid, "prompt", prompt)
        print(f"dry-run: prompt 已写入 logs（{len(prompt)} chars）")
        return None

    if no_llm:
        raise RuntimeError("--no-llm 不可用于 compose")

    all_records: list[dict[str, Any]] = []
    for category in RELATION_CATEGORIES:
        print(f"  → 类别 {category} …")
        cat_records = _compose_category_records(
            entry, subject, eid, grounding, paths, category
        )
        print(f"    {len(cat_records)} 条")
        all_records.extend(cat_records)

    records = reassign_relation_ids(all_records)
    if not records:
        raise RuntimeError("全部类别均无有效产出")

    write_output(out_path, records)
    ok, verify_out = run_verify(out_path, strict=True)
    print(verify_out)

    if ok:
        print(f"✅ verify 通过: {out_path}")
        if sync_db:
            import_json_file(out_path, entry_id=eid, index_path=index_path, sql_out=sql_out, mysql=mysql)
        return out_path

    if not revise_on_fail:
        raise RuntimeError(f"verify 失败:\n{verify_out}")

    fix_prompt = f"""下列人物关系 JSON 校验失败。请**只输出修正后的完整 JSON 数组**。

人物：{subject}

校验输出：
{verify_out}

当前 JSON：
{json.dumps(records, ensure_ascii=False, indent=2)}

规则 SSOT 摘要：关系类别仅 家庭/同僚/师从/外敌/好友；最多四级；禁止 所属四级关系 与五级。

请输出修正后的 JSON 数组：
"""
    raw2 = call_llm(fix_prompt, session_prefix=f"rel-fix-{eid}-")
    log_artifact(paths, eid, "response_revise", raw2)
    records2 = normalize_records(extract_json_array(raw2), subject)
    if not records2:
        raise RuntimeError(f"修订轮未返回有效 JSON\n{verify_out}")
    write_output(out_path, records2)
    ok2, verify_out2 = run_verify(out_path, strict=True)
    print(verify_out2)
    if not ok2:
        raise RuntimeError(f"修订后 verify 仍失败:\n{verify_out2}")
    print(f"✅ verify 通过（修订后）: {out_path}")
    if sync_db:
        import_json_file(out_path, entry_id=eid, index_path=index_path, sql_out=sql_out, mysql=mysql)
    return out_path


def _verify_and_maybe_revise(
    *,
    out_path: Path,
    records: list[dict[str, Any]],
    subject: str,
    eid: str,
    paths: dict[str, Path],
    revise_on_fail: bool,
) -> list[dict[str, Any]]:
    ok, verify_out = run_verify(out_path, strict=True)
    print(verify_out)
    if ok:
        print(f"✅ verify 通过: {out_path}")
        return records

    if not revise_on_fail:
        raise RuntimeError(f"verify 失败:\n{verify_out}")

    fix_prompt = f"""下列人物关系 JSON 校验失败。请**只输出修正后的完整 JSON 数组**。

人物：{subject}

校验输出：
{verify_out}

当前 JSON：
{json.dumps(records, ensure_ascii=False, indent=2)}

规则 SSOT 摘要：关系类别仅 家庭/同僚/师从/外敌/好友；最多四级；禁止 所属四级关系 与五级。

请输出修正后的 JSON 数组：
"""
    raw2 = call_llm(fix_prompt, session_prefix=f"rel-fix-{eid}-")
    log_artifact(paths, eid, "response_revise", raw2)
    records2 = normalize_records(extract_json_array(raw2), subject)
    if not records2:
        raise RuntimeError(f"修订轮未返回有效 JSON\n{verify_out}")
    write_output(out_path, records2)
    ok2, verify_out2 = run_verify(out_path, strict=True)
    print(verify_out2)
    if not ok2:
        raise RuntimeError(f"修订后 verify 仍失败:\n{verify_out2}")
    print(f"✅ verify 通过（修订后）: {out_path}")
    return records2


def backfill_category_one(
    *,
    category: str = "好友",
    entry_id: str | None = None,
    name: str | None = None,
    index_path: Path | None = None,
    revise_on_fail: bool = True,
    sync_db: bool = False,
    sql_out: Path | None = None,
    mysql: dict[str, Any] | None = None,
    skip_if_present: bool = False,
) -> Path | None:
    """在已有关系表上回溯补全单个类别（保留其他类别，重新编号）。"""
    if category not in RELATION_CATEGORIES:
        raise ValueError(f"invalid category: {category!r}")

    validate_histograph_root()
    paths = histograph_paths()
    label = ensure_deepseek_v4_pro()
    entry = find_entry(entry_id=entry_id, name=name, index_path=index_path)
    if not is_person_entry(entry):
        raise RuntimeError(
            f"{entry.get('史略ID')} {entry.get('史略名称')} 非人物六类（{entry.get('史略分类')}），跳过关系补全"
        )

    subject = str(entry.get("史略名称", "")).strip()
    eid = str(entry.get("史略ID", "")).strip()
    out_path = output_path(paths, subject)
    if not out_path.is_file():
        raise FileNotFoundError(f"尚无关系表，请先 compose-one: {out_path}")

    existing = json.loads(out_path.read_text(encoding="utf-8"))
    if not isinstance(existing, list):
        raise ValueError(f"invalid JSON: {out_path}")

    has_category = any(str(r.get("关系类别", "")).strip() == category for r in existing)
    if skip_if_present and has_category:
        print(f"⏭ {eid} {subject} 已有「{category}」，跳过")
        return out_path

    kept = [dict(r) for r in existing if str(r.get("关系类别", "")).strip() != category]
    grounding = load_grounding(entry, paths)

    print(f"LLM: {label}")
    print(f"回溯补全: {eid} {subject} → 类别 {category}")
    print(f"  保留其他类别 {len(kept)} 条")
    print(f"  → 类别 {category} …")
    cat_records = _compose_category_records(entry, subject, eid, grounding, paths, category)
    print(f"    新增 {len(cat_records)} 条")

    records = reassign_relation_ids(kept + cat_records)
    if not records:
        raise RuntimeError("合并后关系表为空")

    write_output(out_path, records)
    records = _verify_and_maybe_revise(
        out_path=out_path,
        records=records,
        subject=subject,
        eid=eid,
        paths=paths,
        revise_on_fail=revise_on_fail,
    )
    if sync_db:
        import_json_file(out_path, entry_id=eid, index_path=index_path, sql_out=sql_out, mysql=mysql)
    return out_path


def import_json_file(
    path: Path,
    *,
    entry_id: str | None = None,
    index_path: Path | None = None,
    sql_out: Path | None = None,
    mysql: dict[str, Any] | None = None,
) -> list[str]:
    """将 07 JSON 导入 box_graph_*（生成 SQL 或直写 MySQL）。"""
    from import_relations_lib import build_import_sql  # noqa: WPS433

    validate_histograph_root()
    paths = histograph_paths()
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError(f"empty or invalid JSON: {path}")

    subjects = {str(r.get("关联史略名称", "")).strip() for r in records}
    subjects.discard("")
    if len(subjects) != 1:
        raise ValueError(f"关联史略名称 must be single value in {path}")
    subject = next(iter(subjects))

    entry = find_entry(entry_id=entry_id, name=subject if not entry_id else None, index_path=index_path)
    if not is_person_entry(entry):
        raise RuntimeError(f"{subject} 非人物六类，不可导入关系")
    box_id = str(entry.get("史略ID", "")).strip()

    stmts = build_import_sql(box_id, subject, records)
    print(f"import: {path.name} → box_id={box_id} nodes={len(records)}+1 edges={len(records)}")

    if sql_out:
        sql_out.parent.mkdir(parents=True, exist_ok=True)
        sql_out.write_text("\n".join(stmts) + "\n", encoding="utf-8")
        print(f"SQL written: {sql_out}")

    if mysql:
        import pymysql  # noqa: WPS433

        conn = pymysql.connect(
            host=mysql["host"],
            port=int(mysql.get("port", 3306)),
            user=mysql["user"],
            password=mysql.get("password", ""),
            database=mysql["db"],
            charset="utf8mb4",
        )
        try:
            with conn.cursor() as cur:
                for stmt in stmts:
                    cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()
        print(f"MySQL applied: {mysql['host']}/{mysql['db']}")

    return stmts


def import_one(
    *,
    entry_id: str | None = None,
    name: str | None = None,
    file_path: Path | None = None,
    index_path: Path | None = None,
    sql_out: Path | None = None,
    mysql: dict[str, Any] | None = None,
) -> None:
    validate_histograph_root()
    paths = histograph_paths()
    if file_path:
        fp = file_path
    else:
        entry = find_entry(entry_id=entry_id, name=name, index_path=index_path)
        subject = str(entry.get("史略名称", "")).strip()
        fp = output_path(paths, subject)
    if not fp.is_file():
        raise FileNotFoundError(fp)
    ok, verify_out = run_verify(fp, strict=True)
    if not ok:
        raise RuntimeError(f"verify failed before import:\n{verify_out}")
    import_json_file(fp, entry_id=entry_id or str(entry.get("史略ID", "")).strip() or None, index_path=index_path, sql_out=sql_out, mysql=mysql)


def list_dynasty_persons(dynasty: str, index_path: Path | None = None) -> list[dict[str, Any]]:
    doc = load_index(index_path)
    dynasty = dynasty.strip()
    out: list[dict[str, Any]] = []
    for e in _index_entries(doc):
        if not is_person_entry(e):
            continue
        d2 = str(e.get("二级朝代坐标", "")).strip()
        d3 = str(e.get("三级政权坐标", "")).strip()
        if dynasty not in (d2, d3):
            continue
        out.append(e)
    out.sort(key=lambda x: str(x.get("史略ID", "")))
    return out


def compose_dynasty(
    dynasty: str,
    *,
    max_count: int = 1,
    index_path: Path | None = None,
    dry_run: bool = False,
) -> list[Path]:
    persons = list_dynasty_persons(dynasty, index_path)
    if not persons:
        raise RuntimeError(f"朝代 {dynasty!r} 下未找到人物六类条目")
    print(f"朝代 {dynasty}: {len(persons)} 位人物，本次最多 {max_count} 位")
    written: list[Path] = []
    manifest: list[dict[str, Any]] = []
    paths = histograph_paths()
    for e in persons[:max_count]:
        eid = str(e.get("史略ID", "")).strip()
        try:
            fp = compose_one(entry_id=eid, index_path=index_path, dry_run=dry_run)
            if fp:
                written.append(fp)
                manifest.append(
                    {
                        "glbl": eid,
                        "name": e.get("史略名称"),
                        "file": fp.name,
                        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    }
                )
        except Exception as exc:
            print(f"❌ {eid} {e.get('史略名称')}: {exc}")
            raise
    if manifest and not dry_run:
        mf = paths["person_relations"] / f"{dynasty}_关系补全_manifest.json"
        mf.write_text(
            json.dumps({"dynasty": dynasty, "completed": manifest}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"manifest: {mf}")
    return written
