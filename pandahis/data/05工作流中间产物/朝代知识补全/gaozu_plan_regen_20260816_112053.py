import os
import sys
import time
from pathlib import Path

ROOT = Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")
os.environ["HISTOGRAPH_ROOT"] = str(ROOT)
sys.path.insert(0, str(ROOT / "tools/openclaw-historiography"))
sys.path.insert(0, str(ROOT / "tools/openclaw-historiography/historiography-translate"))

from llm.config import ensure_deepseek_v4_pro

print(f"provider={ensure_deepseek_v4_pro()}", flush=True)
print(f"has_key={bool(os.environ.get('DEEPSEEK_API_KEY'))}", flush=True)

from lib.recall import recall_entry
from lib.runner import ensure_source_plan
from lib.work_artifacts import plan_path, load_plan

entry_id = "GLBL_00085"
work_dir = ROOT / "data/05工作流中间产物/翻译"
print(f"START plan regen {time.strftime('%Y-%m-%dT%H:%M:%S%z')}", flush=True)

t0 = time.time()
recalled = recall_entry(entry_id)
entry_name = str(recalled.get("史略名称") or "汉高祖")
plan_file = plan_path(entry_id, entry_name, work_dir)
for p in (plan_file, plan_file.with_suffix(".llm.json")):
    if p.is_file():
        p.unlink()
        print(f"removed {p.name}", flush=True)

print(f"plan_file={plan_file}", flush=True)
print(f"recalled blocks={recalled.get('block_count')} paras={recalled.get('paragraph_count')}", flush=True)

ok, errs = ensure_source_plan(
    entry_id,
    recalled,
    plan_file,
    session_id=f"{entry_id}-plan-regen-{int(t0)}",
    work_dir=work_dir,
    use_llm=True,
)
elapsed = time.time() - t0
print(f"DONE ok={ok} elapsed={elapsed:.1f}s", flush=True)
if errs:
    print("ERRORS:", "; ".join(errs[:10]), flush=True)

ok_load, plan, load_errs = load_plan(plan_file)
if ok_load:
    ext = plan.get("外部补全") or []
    adopt = [x for x in ext if isinstance(x, dict) and x.get("采用") is True]
    demoted = [
        x for x in ext if isinstance(x, dict) and str(x.get("_判重") or "").endswith("demote")
    ]
    same_vol = [x for x in adopt if "高祖本纪" in str(x.get("出处") or "")]
    print(
        f"SUMMARY M={len(plan.get('母本逐句清单') or [])} ext={len(ext)} "
        f"adopt={len(adopt)} demoted={len(demoted)} adopt_高祖本纪={len(same_vol)}",
        flush=True,
    )
    print(f"DEDUPE_META {plan.get('_外部补全判重')}", flush=True)
    for x in adopt:
        print(
            f"ADOPT [{x.get('补全类型')}] {str(x.get('主题') or '')[:80]} | "
            f"{str(x.get('出处') or '')[:50]} | 锚点={x.get('母本锚点')} | 判重={x.get('_判重','')}",
            flush=True,
        )
    false_items = [x for x in ext if isinstance(x, dict) and x.get("采用") is False]
    for x in false_items[:12]:
        reason = str(x.get("理由") or "")[:80]
        print(
            f"FALSE [{x.get('补全类型')}] {str(x.get('主题') or '')[:60]} | "
            f"{str(x.get('出处') or '')[:40]} | {reason}",
            flush=True,
        )
else:
    print("LOAD_FAIL", load_errs, flush=True)
print(f"exit={'0' if ok else '1'}", flush=True)
sys.exit(0 if ok else 1)
