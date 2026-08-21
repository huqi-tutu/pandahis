import os
import sys
import time
from pathlib import Path

ROOT = Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")
os.environ["HISTOGRAPH_ROOT"] = str(ROOT)
sys.path.insert(0, str(ROOT / "tools/openclaw-historiography"))
sys.path.insert(0, str(ROOT / "tools/openclaw-historiography/historiography-translate"))

from llm.config import ensure_deepseek_v4_pro  # noqa: E402 — also loads .env
print(f"provider={ensure_deepseek_v4_pro()}", flush=True)
print(f"has_key={bool(os.environ.get('DEEPSEEK_API_KEY'))}", flush=True)
print(
    f"DEDUPE={os.environ.get('TRANSLATE_EXTERNAL_DEDUPE','1')} "
    f"LLM={os.environ.get('TRANSLATE_EXTERNAL_DEDUPE_LLM','1')}",
    flush=True,
)

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
# force regen
if plan_file.is_file():
    plan_file.unlink()
    print(f"removed existing {plan_file.name}", flush=True)
llm_dump = plan_file.with_suffix(".llm.json")
if llm_dump.is_file():
    llm_dump.unlink()

print(f"plan_file={plan_file}", flush=True)
print(
    f"recalled blocks={len(recalled.get('blocks') or [])}",
    flush=True,
)

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
    same_volish = [x for x in adopt if "高祖本纪" in str(x.get("出处") or "")]
    print(
        f"SUMMARY M={len(plan.get('母本逐句清单') or [])} ext={len(ext)} "
        f"adopt={len(adopt)} demoted={len(demoted)} adopt_with_高祖本纪={len(same_volish)}",
        flush=True,
    )
    print(f"DEDUPE_META {plan.get('_外部补全判重')}", flush=True)
    for x in adopt:
        print(
            f"ADOPT [{x.get('补全类型')}] {str(x.get('主题') or '')[:70]} | "
            f"{str(x.get('出处') or '')[:45]} | 锚点={x.get('母本锚点')} | 判重={x.get('_判重','')}",
            flush=True,
        )
else:
    print("LOAD_FAIL", load_errs, flush=True)
print(f"exit={'0' if ok else '1'}", flush=True)
sys.exit(0 if ok else 1)
