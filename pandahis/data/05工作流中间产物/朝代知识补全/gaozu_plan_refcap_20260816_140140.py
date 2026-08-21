import os, sys, time, json
from pathlib import Path
ROOT = Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")
os.environ["HISTOGRAPH_ROOT"] = str(ROOT)
os.environ["TRANSLATE_EXTERNAL_MACRO"] = "1"
os.environ.setdefault("DEEPSEEK_THINKING", "disabled")
os.environ.setdefault("DEEPSEEK_MAX_TOKENS", "16000")
sys.path.insert(0, str(ROOT / "tools/openclaw-historiography"))
sys.path.insert(0, str(ROOT / "tools/openclaw-historiography/historiography-translate"))
from llm.config import ensure_deepseek_v4_pro
print(ensure_deepseek_v4_pro(), flush=True)
from lib.recall import recall_entry
from lib.runner import ensure_source_plan
from lib.work_artifacts import plan_path, load_plan
from lib.plan_postprocess import MAX_REFERENCE_WORKS

entry_id = "GLBL_00085"
work = ROOT / "data/05工作流中间产物/翻译"
t0 = time.time()
print(f"START {time.strftime('%Y-%m-%dT%H:%M:%S%z')}", flush=True)
print(f"MAX_REFERENCE_WORKS={MAX_REFERENCE_WORKS}", flush=True)
recalled = recall_entry(entry_id)
pf = plan_path(entry_id, "汉高祖", work)
for p in list(work.glob("GLBL_00085_汉高祖.plan*")):
    if p.is_file() and p.parent == work:
        p.unlink()
ok, errs = ensure_source_plan(
    entry_id, recalled, pf,
    session_id=f"{entry_id}-refcap-{int(t0)}",
    work_dir=work,
)
print(f"DONE ok={ok} elapsed={time.time()-t0:.1f}s", flush=True)
if errs:
    print("ERRORS", "; ".join(errs[:8]), flush=True)
ok_load, plan, _ = load_plan(pf)
if ok_load:
    ext = plan.get("外部补全") or []
    adopt = [x for x in ext if isinstance(x, dict) and x.get("采用") is True]
    false = [x for x in ext if isinstance(x, dict) and x.get("采用") is False]
    refs = plan.get("参考著作") or []
    books = sorted({str(x.get("出处") or "") for x in adopt if str(x.get("出处") or "").strip()})
    print(f"SUMMARY ext={len(ext)} adopt={len(adopt)} false={len(false)} refs={len(refs)} books={books}", flush=True)
    print(f"REFS {refs}", flush=True)
    print(f"DEDUPE {plan.get('_外部补全判重')}", flush=True)
    for x in adopt:
        print(
            f"ADOPT [{x.get('补全类型')}|{x.get('重要轴')}|{x.get('史料通道')}] "
            f"{str(x.get('主题'))[:70]} | {x.get('出处')} | 锚={x.get('母本锚点')}",
            flush=True,
        )
    for x in false[:10]:
        print(
            f"FALSE [{x.get('_判重') or x.get('重要轴')}] {str(x.get('主题'))[:50]} | "
            f"{str(x.get('理由'))[:80]}",
            flush=True,
        )
print(f"exit={'0' if ok else '1'}", flush=True)
sys.exit(0 if ok else 1)
