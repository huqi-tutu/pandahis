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
CATEGORY_ID_PREFIX = {
    "家庭": "HD-FAM",
    "同僚": "HD-COL",
    "师从": "HD-MAS",
    "外敌": "HD-FOE",
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


def build_prompt(entry: dict[str, Any], grounding: str, paths: dict[str, Path]) -> str:
    taxonomy = read_text(paths["root"] / "关系数据整理提示词.md")
    schema = read_text(SKILL_ROOT / "reference" / "schema.md")
    subject = str(entry.get("史略名称", "")).strip()
    return f"""你是 pandahis 人物关系数据整理员。请为下列人物产出关系图谱 JSON。

# 硬性要求

1. **只输出一个 JSON 数组**，不要 markdown 说明、不要代码块外的文字。
2. 每条记录字段：`关联史略名称`、`关系ID`、`关系类别`、`关系层级`、`关系节点标题`、`上级连接线标题`、`关系简述`；层级 ≥ 二级时填 `所属一级关系` 等链字段（见 schema）。
3. `关联史略名称` 固定为 **{subject}**。
4. `关系类别` 只能是：**家庭、同僚、师从、外敌**（禁止 君臣/敌对 旧名）。
5. 任意路径 **最多四级**；禁止五级与 `所属四级关系`。
6. 无可靠史料不编造；`关系简述` 1–2 句写依据要点。
7. `关系ID` 建议前缀：HD-FAM / HD-COL / HD-MAS / HD-FOE。
8. **禁止同类别重复节点**：同一 `关系类别` + `关系层级` + `关系节点标题` 只能出现**一条**记录。若同一人兼有君臣、政敌等多面关系，**合并为一条**，在 `关系简述` 中写清；不得因 `上级连接线标题` 不同而拆成两条。
9. **跨类别可并存**：同一人可同时出现在不同 `关系类别`（如家庭中为父亲、同僚中为君王），这是允许的。

# 关系 taxonomy（SSOT）

{taxonomy}

# JSON 字段说明

{schema}

# 待整理人物

{grounding}

请直接输出 JSON 数组：
"""


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

    raw = call_llm(prompt, session_prefix=f"rel-{eid}-")
    log_artifact(paths, eid, "response", raw)
    records = normalize_records(extract_json_array(raw), subject)
    if not records:
        raise RuntimeError("LLM 未返回有效 JSON 数组")

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

规则 SSOT 摘要：关系类别仅 家庭/同僚/师从/外敌；最多四级；禁止 所属四级关系 与五级。

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
    for e in doc.get("entries") or []:
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
