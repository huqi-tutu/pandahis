#!/usr/bin/env python3
"""审计已有见证数据：哪些史略可补 1 条附加 F（最知名艺术创作）。"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OPENCLAW_ROOT = SCRIPT_DIR.parent.parent
if str(OPENCLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENCLAW_ROOT))

from paths_config import histograph_paths  # noqa: E402

import cw_lib  # noqa: E402

BATCH_SIZE = 25


def is_literary_extra(row: dict) -> bool:
    if row.get("附加文学见证") is True:
        return True
    reason = str(row.get("优先级判定理由") or "")
    if "附加名额" in reason or "附加文学" in reason or "F层文学" in reason:
        return True
    loc = str(row.get("现藏地点") or "")
    if loc.startswith("传世文本"):
        return True
    return False


def has_literary_extra(doc: dict) -> bool:
    return any(is_literary_extra(e) for e in (doc.get("entries") or []))


def load_candidates(root: Path) -> list[dict]:
    out: list[dict] = []
    for fp in sorted(root.glob("*_见证.json")):
        if "manifest" in fp.name:
            continue
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        entries = doc.get("entries") or []
        if not entries:
            continue
        if has_literary_extra(doc):
            continue
        out.append(
            {
                "file": fp.name,
                "史略ID": doc.get("史略ID"),
                "史略名称": doc.get("史略名称"),
                "史略分类": doc.get("史略分类"),
                "二级朝代坐标": doc.get("二级朝代坐标"),
                "entry_count": len(entries),
                "existing_titles": [
                    str(e.get("文物标题") or "") for e in entries[:3]
                ],
            }
        )
    return out


def extract_json_array(text: str) -> list:
    m = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else text.strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    return json.loads(raw)


def audit_batch(batch: list[dict]) -> list[dict]:
    lines = []
    for i, c in enumerate(batch, 1):
        titles = "；".join(c["existing_titles"]) or "（无）"
        lines.append(
            f"{i}. {c['史略ID']} | {c['史略名称']} | {c['史略分类']} | "
            f"{c['二级朝代坐标']} | 已有见证例：{titles}"
        )
    prompt = (
        "你是中国文史专家。下列史略已有实物类见证，但尚未收录「附加文学见证」（F层）。\n"
        "请逐条判断：是否存在学界公认、**专指该史略主体**（人物/事件/制度/论著）的"
        "**最知名、影响力最大**的后世艺术创作（诗、词、曲、赋、杂剧、章回小说等）。\n\n"
        "规则：\n"
        "- 每条最多推荐 1 个作品；格式「作者《作品名》」或「《作品名》」\n"
        "- 须比其它候选更 iconic；无合格者填 null\n"
        "- 主体本人的著作/作品不算（如屈原与《离骚》）\n"
        "- 正史论赞、史论著作不算（归评述）\n"
        "- **正史传记篇目不算**（如《史记·刺客列传》，归史料/08，非 F）\n"
        "- 散文引典（如孟子单句）除非为该人物唯一 iconic 见证，否则不荐\n"
        "- 须为距主体时代明显偏晚的后世艺术创作；同时代《诗经》等已在实物主名额时，"
        "应优先荐更晚名诗名剧\n"
        "- 仅泛化借典、无专指性的不算\n\n"
        + "\n".join(lines)
        + "\n\n只输出 JSON 数组，每项："
        '{"史略ID":"…","候选作品":"作者《…》"或null,"理由":"20字内"}'
    )
    text = cw_lib.call_llm(prompt, session_prefix="audit-lit-")
    return extract_json_array(text)


def main() -> None:
    paths = histograph_paths()
    witness_dir = paths["witness"]
    candidates = load_candidates(witness_dir)
    print(f"待审计（有见证、无附加F）：{len(candidates)} 条", flush=True)

    results: list[dict] = []
    eligible: list[dict] = []
    skipped: list[dict] = []

    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i : i + BATCH_SIZE]
        print(
            f"批次 {i // BATCH_SIZE + 1}/{(len(candidates) + BATCH_SIZE - 1) // BATCH_SIZE} "
            f"({len(batch)} 条)…",
            flush=True,
        )
        try:
            rows = audit_batch(batch)
        except Exception as exc:  # noqa: BLE001
            print(f"  批次失败: {exc}", flush=True)
            continue
        by_id = {str(r.get("史略ID") or ""): r for r in rows if isinstance(r, dict)}
        for c in batch:
            eid = c["史略ID"]
            row = by_id.get(eid, {})
            work = row.get("候选作品")
            if work in (None, "null", "", "无", "None"):
                skipped.append({**c, "候选作品": None, "理由": row.get("理由") or "无 iconic 名作"})
            else:
                item = {
                    **c,
                    "候选作品": str(work).strip(),
                    "理由": str(row.get("理由") or "").strip(),
                }
                eligible.append(item)
                results.append(item)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mid = witness_dir.parent / "05工作流中间产物" / "评述见证补全"
    mid.mkdir(parents=True, exist_ok=True)
    out_path = mid / f"附加文学见证审计_{stamp}.json"
    summary = {
        "audited_at": stamp,
        "total_with_witness_no_extra_f": len(candidates),
        "eligible_count": len(eligible),
        "skipped_count": len(skipped),
        "by_category": dict(Counter(e["史略分类"] for e in eligible)),
        "eligible": eligible,
        "skipped_sample": skipped[:50],
    }
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n可补附加 F：{len(eligible)} 条", flush=True)
    print(f"不宜补：{len(skipped)} 条", flush=True)
    print(f"报告：{out_path}", flush=True)
    for e in eligible[:20]:
        print(f"  {e['史略ID']} {e['史略名称']} → {e['候选作品']}")


if __name__ == "__main__":
    main()
