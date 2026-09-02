"""从 LLM 回复中提取内容并落盘。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


_PATH_PATTERNS: tuple[tuple[str, str], ...] = (
    ("plan", r"计划路径:\s*(\S+)"),
    ("output", r"产出路径:\s*(\S+)"),
    ("markdown", r"分块正文路径:\s*(\S+)"),
    ("skeleton", r"skeleton 产出路径:\s*(\S+)"),
    ("blocks", r"blocks 产出路径:\s*(\S+)"),
    ("primary_subjects", r"primary_subjects 产出路径:\s*(\S+)"),
    ("protagonists", r"protagonists 产出路径:\s*(\S+)"),
    ("markdown_append", r"审计落盘路径:\s*(\S+)"),
    ("markdown_append", r"参考资料路径:\s*(\S+)"),
)


def parse_paths_from_prompt(message: str) -> Dict[str, Path]:
    found: Dict[str, Path] = {}
    for key, pattern in _PATH_PATTERNS:
        match = re.search(pattern, message)
        if match:
            found[key] = Path(match.group(1).strip())
    return found


def _strip_code_fence(text: str, lang: str | None = None) -> str:
    if lang:
        pattern = rf"```{re.escape(lang)}\s*(.*?)```"
    else:
        pattern = r"```(?:json|markdown|md)?\s*(.*?)```"
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


def extract_markdown(text: str) -> str:
    fenced = _strip_code_fence(text, "markdown")
    if fenced != text.strip():
        return fenced
    fenced = _strip_code_fence(text, "md")
    if fenced != text.strip():
        return fenced
    return text.strip()


def extract_json_objects(text: str) -> List[Any]:
    objects: List[Any] = []
    for block in re.findall(r"```json\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE):
        try:
            objects.append(json.loads(block.strip()))
        except json.JSONDecodeError:
            continue

    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            objects.append(json.loads(stripped))
        except json.JSONDecodeError:
            pass

    start = stripped.find("{")
    while start >= 0:
        depth = 0
        for idx in range(start, len(stripped)):
            ch = stripped[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : idx + 1]
                    try:
                        objects.append(json.loads(candidate))
                    except json.JSONDecodeError:
                        pass
                    break
        start = stripped.find("{", start + 1)

    return objects


def protagonists_payload_errors(obj: Any, *, work: str = "", vol: str = "") -> List[str]:
    """Step1a 主轴人物清单最低结构。"""
    if not isinstance(obj, dict):
        return ["须为 JSON 对象"]
    errors: List[str] = []
    protagonists = obj.get("protagonists")
    if not isinstance(protagonists, list) or not protagonists:
        errors.append("protagonists 须为非空数组")
    else:
        for item in protagonists[:8]:
            if not isinstance(item, dict):
                errors.append("protagonists 每项须为对象")
                break
            for key in ("name", "category", "rationale"):
                if not (item.get(key) or "").strip():
                    errors.append(f"protagonists 缺少 {key}")
                    break
    if obj.get("blocks") or obj.get("entries"):
        errors.append("protagonists 禁止含 blocks/entries")
    return errors


def blocks_payload_errors(obj: Any, *, expected_total: int = 0) -> List[str]:
    """Step1 blocks 草稿最低结构要求。"""
    if not isinstance(obj, dict):
        return ["须为 JSON 对象"]
    errors: List[str] = []
    total = obj.get("total_paragraphs")
    if not isinstance(total, int) or total <= 0:
        errors.append("total_paragraphs 须为正整数")
    elif expected_total and total != expected_total:
        errors.append(f"total_paragraphs={total} ≠ 段落索引 {expected_total}")
    blocks = obj.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        errors.append("blocks 须为非空数组")
    else:
        for item in blocks[:5]:
            if not isinstance(item, dict):
                errors.append("blocks 每项须为对象")
                break
            for key in ("name", "category", "paragraph_from", "paragraph_to"):
                if key not in item:
                    errors.append(f"blocks 缺少 {key}")
                    break
    if obj.get("entries"):
        errors.append("blocks 草稿禁止含 entries")
    if obj.get("segment_attribution"):
        errors.append("blocks 草稿禁止含 segment_attribution")
    return errors


def primary_subjects_payload_errors(obj: Any, *, expected_total: int = 0) -> List[str]:
    """Step1b-α 逐段主语最低结构。"""
    if not isinstance(obj, dict):
        return ["须为 JSON 对象"]
    errors: List[str] = []
    total = obj.get("total_paragraphs")
    if not isinstance(total, int) or total <= 0:
        errors.append("total_paragraphs 须为正整数")
    elif expected_total and total != expected_total:
        errors.append(f"total_paragraphs={total} ≠ 段落索引 {expected_total}")
    paragraphs = obj.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        errors.append("paragraphs 须为非空数组")
    else:
        if expected_total and len(paragraphs) != expected_total:
            errors.append(f"paragraphs 段数 {len(paragraphs)} ≠ {expected_total}")
        for item in paragraphs[:5]:
            if not isinstance(item, dict):
                errors.append("paragraphs 每项须为对象")
                break
            if not isinstance(item.get("paragraph"), int):
                errors.append("paragraphs 缺少 paragraph")
                break
            if not (item.get("primary_subject") or "").strip():
                errors.append("paragraphs 缺少 primary_subject")
                break
    if obj.get("blocks") or obj.get("entries"):
        errors.append("primary_subjects 禁止含 blocks/entries")
    return errors


def skeleton_payload_errors(obj: Any) -> List[str]:
    """Step1 skeleton 最低结构要求；不满足则禁止落盘。"""
    if not isinstance(obj, dict):
        return ["须为 JSON 对象"]
    errors: List[str] = []
    for key in ("volume", "source_file", "total_paragraphs", "segment_attribution", "entries"):
        if key not in obj:
            errors.append(f"缺少 {key}")
    total = obj.get("total_paragraphs")
    if "total_paragraphs" in obj and not isinstance(total, int):
        errors.append("total_paragraphs 须为整数")
    attr = obj.get("segment_attribution")
    if "segment_attribution" in obj:
        if not isinstance(attr, list):
            errors.append("segment_attribution 须为数组")
        elif total and isinstance(total, int) and len(attr) != total:
            errors.append(f"segment_attribution 行数 {len(attr)} ≠ total_paragraphs {total}")
        else:
            for row in attr[:3]:
                if not isinstance(row, dict):
                    errors.append("segment_attribution 每行须为对象")
                    break
                if row.get("attribution") and not row.get("owners"):
                    errors.append("segment_attribution 禁止 attribution 字段，须用 owners[]")
                    break
                if "owners" not in row and "entry" in row:
                    errors.append("segment_attribution 须用 owners[]，禁止 entry 字段")
                    break
                if row.get("owners") and not isinstance(row.get("owners"), list):
                    errors.append("owners 须为数组")
                    break
    entries = obj.get("entries")
    if "entries" in obj:
        if not isinstance(entries, list):
            errors.append("entries 须为数组")
        elif not entries:
            errors.append("entries 为空")
        else:
            for ent in entries[:3]:
                if not isinstance(ent, dict):
                    errors.append("entries 每项须为对象")
                    break
                if "史略ID" not in ent or "史略名称" not in ent:
                    errors.append("entries 须含 史略ID、史略名称 等正式字段")
                    break
    return errors


def extract_translate_payload(message: str, text: str) -> Optional[Dict[str, Any]]:
    """翻译编排器：模型返回 Markdown 正文时包装为 JSON。"""
    entry_m = re.search(r"史略ID:\s*(\S+)", message)
    if not entry_m:
        return None
    entry_id = entry_m.group(1).strip()
    body = re.sub(
        r"\n*TRANSLATE_(?:DONE|MOTHER_DRAFT_DONE)\s+\S+.*$",
        "",
        text.strip(),
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    # 引入 / 结尾：短文可直接包装（JSON 已由 extract_best_json 优先处理）
    is_intro = "前置引入" in message and "篇末结尾" not in message
    is_ending = "篇末结尾" in message or (
        "结尾" in message and "前置引入" in message and "终稿装配" in message
    )
    if is_intro and 40 <= len(body) <= 400 and "{" not in body[:20]:
        return {"史略ID": entry_id, "前置引入": body}
    if is_ending and 40 <= len(body) <= 500 and "{" not in body[:20]:
        # 兼容旧「总结」字段名
        return {"史略ID": entry_id, "结尾": body}
    if len(body) < 200:
        return None
    is_phase2 = "Phase2" in message or "补全成稿" in message
    is_phase1 = (
        ("historiography-translate Phase1" in message or "MOTHER_DRAFT" in message.upper())
        and not is_phase2
    )
    if is_phase2:
        return {"史略ID": entry_id, "翻译详情": body}
    if is_phase1:
        if "*参考著作*" in body:
            body = body.split("*参考著作*")[0].strip()
        elif "参考著作" in body:
            body = re.split(r"\*?参考著作", body)[0].strip()
        return {"史略ID": entry_id, "母本顺译": body}
    if "historiography-translate job" in message:
        return {"史略ID": entry_id, "翻译详情": body}
    return None


def _extract_wrapped_plan(obj: Dict[str, Any]) -> Dict[str, Any] | None:
    """从 翻译详情 等 wrapper 字段解析内嵌 plan，取清单最长的一份。"""
    best: Dict[str, Any] | None = None
    best_len = 0
    for key in ("翻译详情", "content", "result", "output"):
        raw = str(obj.get(key) or "").strip()
        if not raw:
            continue
        if "```" in raw:
            raw = _strip_code_fence(raw, "json")
        inner_objects = extract_json_objects(raw)
        if not inner_objects and raw.startswith("{"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    inner_objects = [parsed]
            except json.JSONDecodeError:
                inner_objects = []
        for inner in inner_objects:
            if not isinstance(inner, dict):
                continue
            cl = inner.get("母本逐句清单")
            if not isinstance(cl, list) or not cl:
                continue
            if len(cl) > best_len:
                best = inner
                best_len = len(cl)
    return best


def _plan_checklist_len(plan: Dict[str, Any]) -> int:
    cl = plan.get("母本逐句清单")
    return len(cl) if isinstance(cl, list) else 0


def unwrap_plan_payload(obj: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 偶将 plan 包在「翻译详情」的 ```json 字符串里，拆出真正 plan 对象。

    若 wrapper 内嵌 plan 的清单不少于顶层（或存在 wrapper），以内嵌为准；
    并合并内嵌的 外部补全/参考著作 等（避免顶层空数组覆盖优质内嵌 plan）。
    """
    inner = _extract_wrapped_plan(obj)
    top_len = _plan_checklist_len(obj)
    has_wrapper = any(str(obj.get(k) or "").strip() for k in ("翻译详情", "content", "result", "output"))

    if inner:
        inner_len = _plan_checklist_len(inner)
        use_inner_checklist = inner_len > top_len or (has_wrapper and inner_len >= top_len)
        merged = dict(obj)
        if use_inner_checklist:
            merged["母本逐句清单"] = inner["母本逐句清单"]
        for k in (
            "外部补全",
            "参考著作",
            "写作结构",
            "索引补充处理",
            "风险提示",
            "史略ID",
            "史略名称",
            "母本著作",
        ):
            inner_val = inner.get(k)
            top_val = merged.get(k)
            if inner_val is None:
                continue
            if k in ("外部补全", "参考著作", "索引补充处理") and isinstance(inner_val, list):
                if not top_val:
                    merged[k] = inner_val
                continue
            if k in ("写作结构", "风险提示") and inner_val and not top_val:
                merged[k] = inner_val
                continue
            if k in ("史略ID", "史略名称", "母本著作") and inner_val and not top_val:
                merged[k] = inner_val
        for k in ("翻译详情", "content", "result", "output"):
            merged.pop(k, None)
        return merged

    cleaned = dict(obj)
    for k in ("翻译详情", "content", "result", "output"):
        cleaned.pop(k, None)
    return cleaned


def _is_plan_decision_object(obj: Dict[str, Any]) -> bool:
    """长文决策包：可无母本逐句清单，但须有外部补全/参考著作/索引处理等决策字段。"""
    if not isinstance(obj, dict):
        return False
    if isinstance(obj.get("母本逐句清单"), list) and obj.get("母本逐句清单"):
        return True
    if "母本顺译" in obj or "翻译详情" in obj:
        return False
    has_decision = (
        "外部补全" in obj
        or "参考著作" in obj
        or "索引补充处理" in obj
        or "写作结构" in obj
    )
    return bool(has_decision and (obj.get("史略ID") or obj.get("史略名称") or has_decision))


def extract_plan_json(text: str) -> Optional[Dict[str, Any]]:
    objects = [o for o in extract_json_objects(text) if isinstance(o, dict)]
    if not objects:
        return None

    unwrapped = [unwrap_plan_payload(o) for o in objects]

    # 1) 优先：带非空外部补全的决策包（长文主路径）
    with_ext = [
        o
        for o in unwrapped
        if isinstance(o.get("外部补全"), list) and len(o.get("外部补全") or []) > 0
    ]
    if with_ext:
        return max(with_ext, key=lambda o: len(o.get("外部补全") or []))

    # 2) 短文/旧路径：带母本逐句清单
    with_cl = [
        o
        for o in unwrapped
        if isinstance(o.get("母本逐句清单"), list) and o.get("母本逐句清单")
    ]
    if with_cl:
        return max(with_cl, key=lambda o: len(o.get("母本逐句清单") or []))

    # 3) 决策壳（外部补全可能为空数组，仍须落盘供 verify/重试读到结构）
    for o in unwrapped:
        if _is_plan_decision_object(o):
            return o
    return None


def extract_best_json(text: str) -> Optional[Any]:
    objects = extract_json_objects(text)
    if not objects:
        return None

    # Step1a protagonists 清单
    for obj in objects:
        if isinstance(obj, dict) and "protagonists" in obj and "blocks" not in obj:
            return obj

    # Step1b-α primary_subjects（逐段主语，无 blocks）
    for obj in objects:
        if isinstance(obj, dict) and isinstance(obj.get("paragraphs"), list) and "blocks" not in obj:
            if obj.get("paragraphs") and isinstance(obj["paragraphs"][0], dict):
                if "primary_subject" in obj["paragraphs"][0]:
                    return obj

    # Step1 blocks 草稿（仅 blocks，无 entries）
    for obj in objects:
        if isinstance(obj, dict) and "blocks" in obj and "entries" not in obj:
            return obj

    # Step1 skeleton：须同时含 segment_attribution + entries，禁止用尾部残缺片段
    for obj in objects:
        if isinstance(obj, dict) and "segment_attribution" in obj and "entries" in obj:
            return obj

    # 翻译正文 / 母本顺译
    for obj in objects:
        if isinstance(obj, dict) and ("母本顺译" in obj or "翻译详情" in obj):
            return obj

    # 引入 / 结尾 / 定向补段（仅短字段，无整篇正文）
    for obj in objects:
        if isinstance(obj, dict) and (
            "前置引入" in obj
            or "结尾" in obj
            or "总结" in obj
            or "插入段" in obj
        ):
            return obj

    # source plan：含清单或长文决策包（外部补全/参考著作等）
    plan = extract_plan_json(text)
    if plan is not None:
        return plan

    for obj in objects:
        if isinstance(obj, dict) and "母本逐句清单" in obj:
            return obj
    return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def persist_artifacts(
    message: str,
    response_text: str,
    *,
    artifact_paths: Optional[Dict[str, Path]] = None,
) -> List[str]:
    """根据提示词路径与显式 artifact_paths 落盘，返回已写入路径列表。"""
    merged: Dict[str, Path] = {**parse_paths_from_prompt(message)}
    if artifact_paths:
        merged.update({k: v for k, v in artifact_paths.items() if v})

    written: List[str] = []
    json_payload = extract_best_json(response_text)
    if json_payload is None:
        json_payload = extract_translate_payload(message, response_text)

    for key in ("plan", "output", "skeleton", "blocks", "primary_subjects", "protagonists"):
        path = merged.get(key)
        if path and json_payload is not None:
            payload = json_payload
            if key == "plan" and isinstance(payload, dict):
                payload = extract_plan_json(response_text) or unwrap_plan_payload(payload)
            if key == "skeleton":
                sk_errs = skeleton_payload_errors(payload)
                if sk_errs:
                    raise ValueError(
                        "LLM 未返回完整 skeleton JSON（禁止落盘残缺片段）："
                        + "；".join(sk_errs)
                    )
            elif key == "blocks":
                blk_errs = blocks_payload_errors(payload)
                if blk_errs:
                    raise ValueError(
                        "LLM 未返回合法 blocks 草稿："
                        + "；".join(blk_errs)
                    )
            elif key == "primary_subjects":
                ps_errs = primary_subjects_payload_errors(payload)
                if ps_errs:
                    raise ValueError(
                        "LLM 未返回合法 primary_subjects："
                        + "；".join(ps_errs)
                    )
            elif key == "protagonists":
                p_errs = protagonists_payload_errors(payload)
                if p_errs:
                    raise ValueError(
                        "LLM 未返回合法 protagonists 清单："
                        + "；".join(p_errs)
                    )
            write_json(path, payload)
            written.append(str(path))

    markdown_path = merged.get("markdown")
    if markdown_path:
        body = extract_markdown(response_text)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(body + ("\n" if body and not body.endswith("\n") else ""), encoding="utf-8")
        written.append(str(markdown_path))

    append_path = merged.get("markdown_append")
    if append_path:
        block = extract_markdown(response_text)
        append_path.parent.mkdir(parents=True, exist_ok=True)
        prefix = "\n\n" if append_path.exists() and append_path.stat().st_size else ""
        with append_path.open("a", encoding="utf-8") as handle:
            handle.write(prefix + block)
        written.append(str(append_path))

    return written
