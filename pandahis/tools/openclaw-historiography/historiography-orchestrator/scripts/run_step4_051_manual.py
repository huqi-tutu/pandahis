#!/usr/bin/env python3
"""手动重跑 02汉书 051 Step4：逼 LLM 写 7 条 _坐标主轴说明并通过 final 质检。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
_ROOT = ORCH.parent
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "historiography-annotate"))

env_file = _ROOT / ".env"
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

os.environ.setdefault(
    "HISTOGRAPH_ROOT",
    str(Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")),
)

from knowledge_provenance import stamp_provenance  # noqa: E402
from llm.artifacts import extract_json_objects  # noqa: E402
from llm.provider import run_agent_turn  # noqa: E402

from lib import db, gates  # noqa: E402
from scripts.reconcile_hanshu_pipeline import _prepare_step4_retry  # noqa: E402

WORK, VOL = "02汉书", "051"
FORBIDDEN_TEMPLATE = ("主要功业/仕宦事", "本卷以", "为最著")


def _build_spindle_prompt(entries: list) -> str:
    lines = [
        "你是《汉书》人物坐标考订员。",
        "本卷《樊郦滕灌傅靳周传》合传七位西汉开国武将，四级帝王坐标均已定为「汉高祖」。",
        "",
        "任务：仅为下列 7 人各写 1～2 句 `_坐标主轴说明`（≥30 字史实句），",
        "说明为何四级帝王取汉高祖（据从沛公起兵、楚汉战争、封侯、官至太尉/丞相/太仆等本传史实）。",
        "禁止模板句「本卷以…主要功业/仕宦事…为最著」。",
        "",
        "输出**单个** ```json 数组```，每项仅含：",
        '- `"史略ID"`（必须与下表完全一致）',
        '- `"_坐标主轴说明"`',
        "",
        "人物清单：",
    ]
    for e in entries:
        af = e.get("_auto_filled") or {}
        hint = (af.get("_坐标主轴待说明") or "").strip()
        lines.append(
            f"- {e.get('史略ID')} {e.get('史略名称')} | "
            f"四级={e.get('四级帝王坐标')} | "
            f"原文首句={str(e.get('原文字句') or '')[:40]}…"
        )
        if hint:
            lines.append(f"  提示：{hint[:120]}")
    lines.append("")
    lines.append("禁止输出完整 skeleton；只输出上述 JSON 数组。")
    return "\n".join(lines)


def _parse_spindle_array(content: str, expected_ids: set[str]) -> dict[str, str]:
    objects = extract_json_objects(content)
    items: list | None = None
    for obj in objects:
        if isinstance(obj, list) and obj:
            items = obj
            break
        if isinstance(obj, dict) and isinstance(obj.get("items"), list):
            items = obj["items"]
            break
    if not items:
        raise ValueError("LLM 未返回 JSON 数组（须含 史略ID + _坐标主轴说明）")

    out: dict[str, str] = {}
    for row in items:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("史略ID") or "").strip()
        text = str(row.get("_坐标主轴说明") or "").strip()
        if eid and text:
            out[eid] = text

    missing = expected_ids - set(out)
    if missing:
        raise ValueError(f"主轴说明缺条目: {sorted(missing)}")
    for eid, text in out.items():
        if len(text) < 8:
            raise ValueError(f"{eid} 主轴说明过短")
        if any(m in text for m in FORBIDDEN_TEMPLATE):
            raise ValueError(f"{eid} 含禁止模板句")
    return out


def _merge_spindle_rationales(sk_path: Path, rationales: dict[str, str]) -> None:
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    new_entries = []
    for entry in data.get("entries") or []:
        eid = entry.get("史略ID")
        if eid not in rationales:
            new_entries.append(entry)
            continue
        af = dict(entry.get("_auto_filled") or {})
        af = {**af, "_坐标主轴说明": rationales[eid]}
        needs = [n for n in (entry.get("_needs_llm") or []) if n != "_坐标主轴说明"]
        new_entry = {**entry, "_auto_filled": af}
        if needs:
            new_entry["_needs_llm"] = needs
        else:
            new_entry.pop("_needs_llm", None)
        new_entries.append(new_entry)
    data = {**data, "entries": new_entries}
    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    db.init_schema()
    sk = gates.skeleton_path(WORK, VOL)
    if not sk:
        print("❌ 未找到 skeleton")
        return 1

    stamp_provenance(
        sk,
        "1",
        source="llm",
        session_id="hist-02-051-s1a-851-c7908906",
    )
    print("✅ 已补 knowledge_provenance.step1.source=llm")

    db.mark_volume_steps_done(WORK, VOL, "3")
    db.reset_volume_step(WORK, VOL, "4")
    _prepare_step4_retry(sk)
    gates.step4_prepare(sk)
    print("✅ Step4 prepare + restore scratch")

    data = json.loads(sk.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    expected_ids = {e.get("史略ID") for e in entries}
    prompt = _build_spindle_prompt(entries)
    diag = Path(gates.paths()["annotate_work"]) / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    (diag / "step4_spindle_prompt_051.txt").write_text(prompt, encoding="utf-8")

    job = db.get_job(WORK, VOL, "4")
    job_id = job["id"] if job else 854
    session_id = f"hist-02-051-s4-{job_id}-manual-spindle"
    db.update_job(
        job_id,
        status="running",
        fail_count=0,
        session_id=session_id,
        started_at=db.utc_now(),
        detail="manual: LLM 专写 7 条 _坐标主轴说明",
    )
    print(f"▶ LLM 专写主轴说明 session={session_id}")

    rationales: dict[str, str] | None = None
    last_err = ""
    for attempt in range(1, 4):
        try:
            result = run_agent_turn(
                prompt,
                session_id=f"{session_id}-a{attempt}",
                timeout_sec=300,
            )
            content = str(result.get("result") or "")
            (diag / f"step4_spindle_response_051_a{attempt}.txt").write_text(
                content, encoding="utf-8"
            )
            rationales = _parse_spindle_array(content, expected_ids)
            print(f"✅ LLM 返回 {len(rationales)} 条主轴说明（attempt {attempt}）")
            break
        except Exception as exc:
            last_err = str(exc)
            print(f"⚠️ attempt {attempt} 失败: {last_err[:200]}")

    if not rationales:
        print(f"❌ LLM 主轴说明未通过: {last_err}")
        db.update_job(job_id, status="failed", detail=last_err[:1500])
        return 1

    _merge_spindle_rationales(sk, rationales)
    stamp_provenance(sk, "4", source="llm", session_id=session_id)
    print("✅ 已合并主轴说明并 stamp step4")

    ok, recon_msg = gates.step4_reconcile(sk)
    print("✅ reconcile" if ok else f"⚠️ reconcile: {recon_msg[-200:]}")

    ok, msg = gates.step4_finalize(sk)
    if not ok:
        gates.step4_restore_scratch(sk)
        print(f"❌ finalize 失败:\n{msg[-800:]}")
        db.update_job(job_id, status="failed", detail=msg[:1500])
        return 1
    print("✅ Step4 finalize")

    ok, errs = gates.verify_step4_final(sk)
    if not ok:
        gates.step4_restore_scratch(sk)
        print("❌ check_format final 未过:")
        for e in errs[:10]:
            print(f"  - {e[:200]}")
        db.update_job(job_id, status="failed", detail="\n".join(errs)[:1500])
        return 1

    db.update_job(
        job_id,
        status="done",
        finished_at=db.utc_now(),
        fail_count=0,
        detail="manual_step4_spindle_ok",
    )
    db.set_work_status(WORK, "running", blocked_reason=None)
    print("✅ 051 Step4 封板 + check_format final 通过")
    for e in json.loads(sk.read_text(encoding="utf-8")).get("entries") or []:
        af = e.get("_auto_filled") or {}
        print(f"  · {e.get('史略名称')}: {(af.get('_坐标主轴说明') or '')[:56]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
