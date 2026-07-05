#!/usr/bin/env python3
"""复现 042 Step4：抓取 LLM 原始回复 + persist_artifacts 落盘结果。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
_ROOT = ORCH.parent
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(_ROOT))

# 加载 .env（与 run_batch_daemon 一致；overnight_run_hanshu 未做此步）
env_file = _ROOT / ".env"
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from lib.adapters.openclaw import build_step_prompt, expected_skeleton_path  # noqa: E402
from lib import gates  # noqa: E402
from lib.config import get_work_config  # noqa: E402
from llm.artifacts import extract_best_json, persist_artifacts  # noqa: E402
from llm.config import get_provider_name  # noqa: E402
from llm.provider import run_agent_turn  # noqa: E402

WORK, VOL = "02汉书", "042"


def main() -> int:
    print(f"provider={get_provider_name()}")
    print(f"DEEPSEEK_API_KEY set={bool(os.environ.get('DEEPSEEK_API_KEY'))}")

    idx = gates.load_paragraph_index(WORK, VOL)
    sk = gates.skeleton_path(WORK, VOL)
    if not sk:
        print("no skeleton")
        return 1

    gates.step4_prepare(sk)
    missing = gates.step4_missing_report(sk)
    base = build_step_prompt(WORK, VOL, "4", idx)
    prompt = base + "\n\n" + (missing or "")

    out_dir = Path(gates.paths()["annotate_work"]) / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "step4_prompt_042.txt").write_text(prompt, encoding="utf-8")
    print(f"prompt_len={len(prompt)} saved={out_dir / 'step4_prompt_042.txt'}")

    sk_path = expected_skeleton_path(WORK, VOL, idx)
    before = json.loads(sk_path.read_text(encoding="utf-8"))
    before_e1 = before["entries"][0].get("四级帝王坐标")

    print("calling LLM...")
    result = run_agent_turn(
        prompt,
        session_id="diag-042-step4",
        timeout_sec=120,
        artifact_paths={"skeleton": sk_path},
    )
    content = str(result.get("result") or "")
    written = result.get("written_artifacts") or []
    (out_dir / "step4_response_042.txt").write_text(content, encoding="utf-8")
    print(f"response_len={len(content)} written_artifacts={written}")

    parsed = extract_best_json(content)
    if parsed is None:
        print("extract_best_json: None")
    elif isinstance(parsed, dict):
        keys = list(parsed.keys())
        print(f"extract_best_json keys={keys}")
        if "entries" in parsed and "segment_attribution" not in parsed:
            print("ROOT: 仅 entries 片段，persist_artifacts 不会落盘 skeleton")
    else:
        print(f"extract_best_json type={type(parsed)}")

    try:
        w2 = persist_artifacts(prompt, content, artifact_paths={"skeleton": sk_path})
        print(f"persist_artifacts retry written={w2}")
    except ValueError as e:
        print(f"persist_artifacts ValueError: {e}")

    after = json.loads(sk_path.read_text(encoding="utf-8"))
    after_e1 = after["entries"][0].get("四级帝王坐标")
    print(f"四级帝王坐标 before={before_e1!r} after={after_e1!r}")
    print(f"response head:\n{content[:800]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
