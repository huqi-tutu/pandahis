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
from llm.config import MODEL_PRO, ensure_deepseek_v4_pro as pin_deepseek_v4_pro  # noqa: E402

REQUIRED_MODEL = MODEL_PRO
PERSON_CATEGORIES = frozenset({"君王", "诸侯", "宗戚", "文臣", "武将", "宦官", "庶众"})
RELATION_CATEGORIES = ("家庭", "同僚", "敌对", "师徒", "好友")
MAX_CATEGORY_LLM_ATTEMPTS = 3
CATEGORY_ID_PREFIX = {
    "家庭": "HD-FAM",
    "同僚": "HD-COL",
    "敌对": "HD-FOE",
    "师徒": "HD-MAS",
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
    from llm.config import deepseek_settings, get_provider_name  # noqa: WPS433

    if get_provider_name() != "deepseek":
        raise RuntimeError("人物关系补全仅支持 HIST_LLM_PROVIDER=deepseek")
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

    # 11 新标注条目翻译（v2 译文 SSOT；不再读 04）
    trans_dir = paths.get("translate_output_v2") or paths["translate_output"]
    if trans_dir.is_dir():
        for fp in trans_dir.glob(f"{entry_id}_*.json"):
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
                detail = str(doc.get("翻译详情") or "").strip()
                if detail:
                    chunks.append(f"## 11新标注条目翻译 · {fp.name}\n\n{detail}")
                    break
            except (OSError, json.JSONDecodeError):
                continue

    # 06 详情（可选加厚，非门禁）
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
- 无可靠史料的不写；有史料时优先写**最重要、最紧密**的人物，**每个二级枢纽下直接人物不得超过 10 人**（不是写全朝所有出现过的人名）
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
2. 每条记录字段：`关联史略名称`、`关系ID`、`关系类别`、`关系层级`、`关系节点标题`、`上级连接线标题`、`关系简述`；二级分类枢纽须含 `节点类型":"二级分类"`；层级 ≥ 二级时填 `所属一级关系` 等链字段（见 schema）。
3. `关联史略名称` 固定为 **{subject}**。
4. {_category_rules(category)}
5. **仅依据下方 grounding**（11译文/06详情/索引）写关系；无依据不编造；不得凭通识补节点。
6. **所有类别**（含好友）须先写二级分类枢纽（`关系层级=一级`，`节点类型=二级分类`，`上级连接线标题=""`），再挂具体人物。好友一级名与二级枢纽名同为「好友」。**无具体人物的二级枢纽不要写**（不适用则整类输出 `[]`）。
7. **每个二级枢纽下直接人物（关系层级=二级）最多 10 人（硬上限）**；超过则只输出最重要、最紧密的 10 人。选取优先：至亲/核心君臣/关键战和政争主角 > 史料笔墨多者 > 已有独立史略者；禁止堆砌满朝文武、全体宗室。不满 10 不必凑数。
8. 展开深度：家庭·配偶支最多四级（配偶→子女→孙辈）；其余人物为叶节点。禁止曾孙、徒孙、兄弟姐妹之子女。生母不详时配偶节点标题用「不详」。
9. 同僚/敌对/师徒/好友：二级枢纽→人物的 `上级连接线标题` 必须为 `""`。家庭边标题**仅允许**白名单：父/母、祖/祖母、妻/妾/妃/夫、兄/弟/姐/妹（分不清用兄弟/姐妹）、子/女。**禁止**曾祖/外祖/孙/侄/婿等（祖父母仅上一代；孙辈只能挂在配偶→子女下用子/女）。配偶边标题**必须站在条目主人公视角**（如嫘祖→黄帝用「夫」，黄帝→嫘祖用「妻」）。
10. 互斥：家庭排斥同僚/好友/师徒；同僚排斥好友；敌对可与他类共现。禁止旧类别名：`君臣`→`同僚`；顶级`外敌`→`敌对`；`师从`→`师徒`。`关系简述` 1–2 句写依据要点（可追溯到 grounding）。
11. **节点资格**：叶子节点只写**具体人物**；家族/氏姓（鲍氏、高氏）可写。禁止国家/政权/方国（秦国、齐国）、少数民族/部族（犬戎、淮夷、三苗）、职衔空名（东周君、中山国君）、战役名。敌对外敌须写具体君主/将领；名失载则不写该节点。

# 关系 taxonomy（SSOT）

{taxonomy}

# JSON 字段说明

{schema}

# 待整理人物（grounding · 唯一事实源）

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
        elif cat == "外敌":
            cat = "敌对"
        elif cat == "师从":
            cat = "师徒"
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


def _index_person_names(index_path: Path | None = None) -> set[str]:
    try:
        doc = load_index(index_path)
    except Exception:
        return set()
    names: set[str] = set()
    for e in _index_entries(doc):
        if not is_person_entry(e):
            continue
        name = str(e.get("史略名称") or "").strip()
        if name:
            names.add(name)
    return names


def sanitize_and_reid(
    records: list[dict[str, Any]],
    subject: str,
    *,
    index_path: Path | None = None,
    index_names: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """确定性清洗（边标题/互斥/枢纽≤10）后重新编号。"""
    from sanitize_relations import sanitize_relation_records  # noqa: WPS433

    names = index_names if index_names is not None else _index_person_names(index_path)
    cleaned, notes = sanitize_relation_records(records, index_names=names)
    cleaned = normalize_records(cleaned, subject)
    cleaned = reassign_relation_ids(cleaned)
    return cleaned, notes


REVISE_RULES = """硬性修正规则（必须全部满足）：
1. 关系类别仅 家庭/同僚/敌对/师徒/好友；二级分类为枢纽（含好友）。
2. 每个二级枢纽下直接人物（关系层级=二级）**最多 10 人**；超出只保留最重要、最紧密的 10 人，删除其余及其子孙。
3. 家庭边标题白名单仅：父/母/祖/祖母/妻/妾/妃/夫/兄/弟/姐/妹/兄弟/姐妹/子/女；禁止曾祖/外祖/孙/侄等；旧称父亲→父、祖父→祖、儿子→子。标题「不详」允许同层多条（多配偶生母不明）；真人名同层同类别不得重复。
4. 非家庭人物边标题必须为 ""。
5. 互斥：家庭 > 同僚 > 好友；家庭亦排斥师徒。
6. 配偶支可至四级孙辈；禁止曾孙/五级。"""


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
    index_names = _index_person_names(index_path)
    if records:
        records, san_notes = sanitize_and_reid(
            records, subject, index_path=index_path, index_names=index_names
        )
        if san_notes:
            print("sanitize:")
            for n in san_notes[:40]:
                print(f"  - {n}")
            if len(san_notes) > 40:
                print(f"  …另有 {len(san_notes)-40} 条")
    else:
        print("ℹ️ 各类均无有效产出 → 空关系表")

    # 史料确无具名关系时允许空表 []，不强制挂点
    write_output(out_path, records)
    if not records:
        ok, verify_out = run_verify(out_path, strict=True)
        print(verify_out)
        print(f"✅ 空关系表已落盘（无内容可挂）: {out_path}")
        if sync_db:
            import_json_file(out_path, entry_id=eid, index_path=index_path, sql_out=sql_out, mysql=mysql)
        return out_path

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

{REVISE_RULES}

请输出修正后的 JSON 数组：
"""
    raw2 = call_llm(fix_prompt, session_prefix=f"rel-fix-{eid}-")
    log_artifact(paths, eid, "response_revise", raw2)
    records2 = normalize_records(extract_json_array(raw2), subject)
    if not records2:
        # 修订轮交空数组：视为确认无内容
        write_output(out_path, [])
        print(f"✅ 修订轮确认无内容 → 空关系表: {out_path}")
        if sync_db:
            import_json_file(out_path, entry_id=eid, index_path=index_path, sql_out=sql_out, mysql=mysql)
        return out_path
    records2, san_notes2 = sanitize_and_reid(
        records2, subject, index_path=index_path, index_names=index_names
    )
    if san_notes2:
        print("sanitize(after revise):")
        for n in san_notes2[:40]:
            print(f"  - {n}")
    write_output(out_path, records2)
    if not records2:
        ok2, verify_out2 = run_verify(out_path, strict=True)
        print(verify_out2)
        print(f"✅ 修订清洗后为空关系表: {out_path}")
        if sync_db:
            import_json_file(out_path, entry_id=eid, index_path=index_path, sql_out=sql_out, mysql=mysql)
        return out_path
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
    index_path: Path | None = None,
) -> list[dict[str, Any]]:
    index_names = _index_person_names(index_path)
    records, san_notes = sanitize_and_reid(
        records, subject, index_path=index_path, index_names=index_names
    )
    if san_notes:
        print("sanitize:")
        for n in san_notes[:40]:
            print(f"  - {n}")
    write_output(out_path, records)

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

{REVISE_RULES}

请输出修正后的 JSON 数组：
"""
    raw2 = call_llm(fix_prompt, session_prefix=f"rel-fix-{eid}-")
    log_artifact(paths, eid, "response_revise", raw2)
    records2 = normalize_records(extract_json_array(raw2), subject)
    if not records2:
        raise RuntimeError(f"修订轮未返回有效 JSON\n{verify_out}")
    records2, san_notes2 = sanitize_and_reid(
        records2, subject, index_path=index_path, index_names=index_names
    )
    if san_notes2:
        print("sanitize(after revise):")
        for n in san_notes2[:40]:
            print(f"  - {n}")
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
        index_path=index_path,
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
    if not isinstance(records, list):
        raise ValueError(f"invalid JSON: {path}")

    if records:
        subjects = {str(r.get("关联史略名称", "")).strip() for r in records}
        subjects.discard("")
        if len(subjects) != 1:
            raise ValueError(f"关联史略名称 must be single value in {path}")
        subject = next(iter(subjects))
    else:
        subject = path.stem.replace("关系表", "").strip()
        if not subject:
            raise ValueError(f"cannot infer subject from empty file: {path}")

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


def write_dynasty_manifest(
    dynasty: str,
    *,
    index_path: Path | None = None,
) -> Path:
    """扫描已产出关系表，增量写入 {朝代}_关系补全_manifest.json。"""
    paths = histograph_paths()
    persons = list_dynasty_persons(dynasty, index_path)
    rel_dir = paths["person_relations"]
    manifest: list[dict[str, Any]] = []
    for e in persons:
        name = str(e.get("史略名称", "")).strip()
        fp = rel_dir / f"{name}关系表.json"
        if not fp.exists():
            continue
        recs = json.loads(fp.read_text(encoding="utf-8"))
        manifest.append(
            {
                "glbl": str(e.get("史略ID", "")).strip(),
                "name": name,
                "file": fp.name,
                "count": len(recs),
                "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        )
    mf = rel_dir / f"{dynasty}_关系补全_manifest.json"
    mf.write_text(
        json.dumps({"dynasty": dynasty, "completed": manifest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return mf


def compose_dynasty(
    dynasty: str,
    *,
    max_count: int = 1,
    index_path: Path | None = None,
    dry_run: bool = False,
    fail_fast: bool = False,
) -> list[Path]:
    persons = list_dynasty_persons(dynasty, index_path)
    if not persons:
        raise RuntimeError(f"朝代 {dynasty!r} 下未找到人物六类条目")
    print(f"朝代 {dynasty}: {len(persons)} 位人物，本次最多 {max_count} 位")
    written: list[Path] = []
    for e in persons[:max_count]:
        eid = str(e.get("史略ID", "")).strip()
        name = str(e.get("史略名称", "")).strip()
        try:
            fp = compose_one(entry_id=eid, index_path=index_path, dry_run=dry_run)
            if fp:
                written.append(fp)
                print(f"✅ {eid} {name}")
        except Exception as exc:
            print(f"❌ {eid} {name}: {exc}")
            if fail_fast:
                raise
        if not dry_run:
            write_dynasty_manifest(dynasty, index_path=index_path)
    if not dry_run:
        mf = write_dynasty_manifest(dynasty, index_path=index_path)
        print(f"manifest: {mf} ({len(written)} 新增)")
    return written
