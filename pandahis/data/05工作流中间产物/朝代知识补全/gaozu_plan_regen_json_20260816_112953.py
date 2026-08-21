import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")
os.environ["HISTOGRAPH_ROOT"] = str(ROOT)
# Prefer non-thinking; ensure room for output
os.environ.setdefault("DEEPSEEK_THINKING", "disabled")
os.environ.setdefault("DEEPSEEK_MAX_TOKENS", "16000")
sys.path.insert(0, str(ROOT / "tools/openclaw-historiography"))
sys.path.insert(0, str(ROOT / "tools/openclaw-historiography/historiography-translate"))

from llm.config import ensure_deepseek_v4_pro
from llm.deepseek_provider import run_deepseek_turn
from llm.artifacts import extract_plan_json

from lib.recall import recall_entry
from lib.openclaw import build_source_plan_prompt, recalled_summary
from lib.plan_skeleton import build_plan_skeleton, merge_llm_plan_decisions
from lib.work_artifacts import plan_path, save_plan, load_plan, verify_plan

print(f"provider={ensure_deepseek_v4_pro()}", flush=True)
entry_id = "GLBL_00085"
work_dir = ROOT / "data/05工作流中间产物/翻译"
print(f"START {time.strftime('%Y-%m-%dT%H:%M:%S%z')}", flush=True)

t0 = time.time()
recalled = recall_entry(entry_id)
entry_name = str(recalled.get("史略名称") or "汉高祖")
plan_file = plan_path(entry_id, entry_name, work_dir)
raw_file = plan_file.with_suffix(".llm.raw.txt")
skeleton = build_plan_skeleton(recalled)

ok = False
last_errors: list[str] = []
for attempt in range(3):
    feedback = ""
    if attempt:
        feedback = (
            "上次输出无效：" + (last_errors[0] if last_errors else "外部补全缺失") + "\n"
            "必须输出完整 JSON 对象，且「外部补全」为非空数组（建议 ≥12 条候选，其中 ≥8 条采用:true）。\n"
            "禁止只输出史略ID；禁止母本同一卷《史记·高祖本纪》作外部补全。"
        )
    prompt = build_source_plan_prompt(
        entry_id,
        recalled,
        recalled_summary(recalled),
        plan_file,
        retry_feedback=feedback,
    )
    print(f"🧭 LLM attempt {attempt} prompt_chars={len(prompt)}", flush=True)
    result = run_deepseek_turn(
        prompt,
        session_id=f"{entry_id}-plan-json-{int(t0)}-a{attempt}",
        timeout_sec=900,
        artifact_paths={"plan": plan_file},
        response_format={"type": "json_object"},
        max_attempts=2,
    )
    content = str(result.get("result") or "")
    raw_file.write_text(content, encoding="utf-8")
    print(
        f"   raw_len={len(content)} model={result.get('model')} written={result.get('written_artifacts')}",
        flush=True,
    )
    print(f"   raw_head={content[:200]!r}", flush=True)

    llm_plan = extract_plan_json(content) or {}
    if not isinstance(llm_plan, dict):
        llm_plan = {}
    # dump parsed
    plan_file.with_suffix(".llm.json").write_text(
        json.dumps(llm_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    n_ext = len(llm_plan.get("外部补全") or []) if isinstance(llm_plan.get("外部补全"), list) else -1
    print(f"   parsed 外部补全={n_ext} keys={list(llm_plan)[:12]}", flush=True)

    merged = merge_llm_plan_decisions(skeleton, llm_plan)
    save_plan(plan_file, merged, recalled, external_dedupe_llm=True)
    ok, last_errors = verify_plan(entry_id, recalled, plan_file)
    if ok:
        print(f"✅ plan ok on attempt {attempt}", flush=True)
        break
    print(f"⚠️ not ok: {last_errors[0] if last_errors else '?'}", flush=True)

elapsed = time.time() - t0
print(f"DONE ok={ok} elapsed={elapsed:.1f}s", flush=True)
if last_errors:
    print("ERRORS:", "; ".join(last_errors[:8]), flush=True)

ok_load, plan, _ = load_plan(plan_file)
if ok_load:
    ext = plan.get("外部补全") or []
    adopt = [x for x in ext if isinstance(x, dict) and x.get("采用") is True]
    demoted = [x for x in ext if isinstance(x, dict) and str(x.get("_判重") or "").endswith("demote")]
    same = [x for x in adopt if "高祖本纪" in str(x.get("出处") or "")]
    print(
        f"SUMMARY M={len(plan.get('母本逐句清单') or [])} ext={len(ext)} adopt={len(adopt)} "
        f"demoted={len(demoted)} adopt_高祖本纪={len(same)} meta={plan.get('_外部补全判重')}",
        flush=True,
    )
    for x in adopt:
        print(
            f"ADOPT [{x.get('补全类型')}] {str(x.get('主题') or '')[:70]} | "
            f"{str(x.get('出处') or '')[:45]} | 锚={x.get('母本锚点')} | {x.get('_判重','')}",
            flush=True,
        )
print(f"exit={'0' if ok else '1'}", flush=True)
sys.exit(0 if ok else 1)
