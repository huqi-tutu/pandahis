#!/usr/bin/env python3
"""单卷 v2 标注：Step1a/1b 调 DeepSeek（ensure_annotate_model）→ gate → expand → check_format。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ORCH = ROOT / "tools" / "openclaw-historiography" / "historiography-orchestrator"
V2 = ROOT / "tools" / "openclaw-historiography" / "historiography-annotate-v2"
ANNOTATE = ROOT / "tools" / "openclaw-historiography" / "historiography-annotate"
OG = ROOT / "tools" / "openclaw-historiography"

for p in (str(OG), str(ORCH), str(ANNOTATE)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("HISTOGRAPH_ROOT", str(ROOT))
os.environ.setdefault("HIST_ANNOTATE_TRACK", "v2")
os.environ.setdefault("HIST_LLM_PROVIDER", "deepseek")


def _load_index(work: str, vol: str) -> dict:
    from paths_config import histograph_paths

    vol = vol.zfill(3)
    pi = histograph_paths()["paragraph_index"]
    for name in (f"{work}_{vol}.json", f"{work}_{vol.lstrip('0') or '0'}.json"):
        fp = pi / name
        if fp.is_file():
            return json.loads(fp.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"段落索引不存在: {work} vol {vol}")


def _write_json_from_llm(content: str, path: Path) -> bool:
    from llm.artifacts import extract_json_objects

    for obj in reversed(extract_json_objects(content)):
        if not isinstance(obj, dict):
            continue
        if "protagonists" in obj or "blocks" in obj:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return True
        if "paragraphs" in obj and isinstance(obj.get("paragraphs"), list):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return True
    return False


def _volume_display_name(index: dict, work: str, vol: str) -> str:
    src = (index.get("source_file") or "").strip()
    stem = Path(src).stem if src else f"{work}_{vol.zfill(3)}"
    prefix = f"{work}_{vol.zfill(3)}_"
    name = stem[len(prefix) :] if stem.startswith(prefix) else stem
    return re.sub(r"第[一二三四五六七八九十百零]+(?:章|节|卷)?$", "", name)


def run_step1a(work: str, vol: str, index: dict) -> dict:
    from lib.adapters.openclaw import build_protagonist_prompt, run_agent_turn
    from lib.protagonist_workflow import protagonists_path, protagonists_valid, normalize_protagonists_file, load_protagonists
    from llm.config import ensure_annotate_model, deepseek_settings

    ensure_annotate_model()
    print(f"Step1a 模型: {deepseek_settings()['model']}", flush=True)

    vol_name = _volume_display_name(index, work, vol)
    pp = protagonists_path(work, vol)
    prompt = build_protagonist_prompt(work, vol, index)
    extra = (
        f"\n\n---\n【v2.5 补充 — 卷《{vol_name}》】\n"
        "- 仅据卷名+史学常识，**禁止读段落正文**\n"
        "- 先判断卷型 **volume_arc**（写入 JSON）：\n"
        "  · **A 单人卷**：整卷 essentially 一人（例：项羽本纪、秦始皇本纪、**孔子世家**）→ narrative_mode=single\n"
        "  · **B 多人卷**：卷内多个叙事高峰（例：秦本纪、吴太伯世家、齐太公世家）→ narrative_mode=hezhuan，protagonists 2–5\n"
        "  · **C 合传**：卷名含合传或双主角并列（例：屈原贾生列传）→ narrative_mode=hezhuan，volume_subtype=liezhuan_hezhuan\n"
        "- **世家≠国君**：孔子世家主轴是孔子、分类用文臣；吴太伯世家是多个**诸侯**国君\n"
        "- 勿因卷名带「世家」就一律 hezhuan；孔子世家等须走 **A**\n"
        "- **禁止**「始祖贯卷→single」：鲁周公/齐太公/吴太伯 = **B hezhuan**；"
        "始祖退场后历代小君标世系链，**禁止**整卷机械归始祖一人\n"
        "- 管蔡等武王之弟 → category=**宗戚**（不是君王/诸侯）\n"
        "- **君王≠帝王表有名**：卫康叔/吴太伯/齐桓公/秦孝公等封国国君 → **诸侯**；"
        "仅天子/皇帝/霸王级本纪共主 → **君王**\n"
        "- 每人须写 category（八类之一），**禁止**缺省或默认填君王；"
        "rationale 须对照准入（见 prompt「史略分类 v4」）\n"
    )
    prompt += extra

    sid = f"v2-{work}-{vol.zfill(3)}-1a"
    res = run_agent_turn(
        prompt,
        session_id=sid,
        timeout_sec=300,
        artifact_paths={"protagonists": pp},
    )
    if not pp.exists():
        if not _write_json_from_llm(str(res.get("result") or ""), pp):
            diag = ROOT / "data/05工作流中间产物/标注-v2" / f"{work}_{vol.zfill(3)}_step1a_raw.txt"
            diag.parent.mkdir(parents=True, exist_ok=True)
            diag.write_text(str(res.get("result") or ""), encoding="utf-8")
            raise RuntimeError(f"Step1a 未落盘 protagonists.json，原始回复已存: {diag}")

    normalize_protagonists_file(work, vol)
    ok, msg = protagonists_valid(work, vol, index)
    if not ok:
        raise RuntimeError(f"Step1a identity_gate 失败:\n{msg}")
    print(f"✅ Step1a: {msg}", flush=True)
    return load_protagonists(work, vol) or {}


def run_step1b_mechanical(work: str, vol: str) -> None:
    expand = V2 / "scripts/v2_expand_to_skeleton.py"
    r = subprocess.run(
        [sys.executable, str(expand), "--work", work, "--vol", vol, "--mechanical"],
        env={**os.environ, "HIST_ANNOTATE_TRACK": "v2", "HISTOGRAPH_ROOT": str(ROOT)},
        capture_output=True,
        text=True,
    )
    print(r.stdout, end="", flush=True)
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr, flush=True)
    if r.returncode != 0:
        raise RuntimeError(f"Step1b 机械划块失败 ({r.returncode})")


def run_step1b_alpha(work: str, vol: str, index: dict) -> None:
    """Step1b-α：LLM 逐段 primary_subject → primary_subjects.json"""
    from lib.adapters.openclaw import run_agent_turn
    from lib.protagonist_workflow import format_manifest_for_prompt, load_protagonists
    from llm.config import ensure_annotate_model, deepseek_settings
    from paths_config import histograph_paths

    ensure_annotate_model()
    manifest = load_protagonists(work, vol)
    if not manifest:
        raise RuntimeError("Step1b-α 需要 protagonists.json")

    primary_out = histograph_paths()["annotate_work"] / f"{work}_{vol.zfill(3)}_primary_subjects.json"
    step1b_alpha_md = (V2 / "prompts/step1b_primary_subjects.md").read_text(encoding="utf-8")
    vol_name = _volume_display_name(index, work, vol)
    subtype = (manifest.get("volume_subtype") or "").strip()

    paras = []
    for row in index.get("paragraphs") or []:
        pid = int(row.get("id") or row.get("paragraph") or 0)
        txt = (row.get("text") or "").strip()
        paras.append(f"P{pid:02d}: {txt}")
    body = "\n".join(paras)

    prompt = f"""【historiography-annotate-v2 · Step1b-α 逐段叙事主语】
著作: {work}  卷: {vol.zfill(3)}
卷名: {vol_name}
volume_subtype: {subtype}
段落数: {index['total']}（须全覆盖 1..{index['total']}，每段一行）
primary_subjects 产出路径: {primary_out}
须将 **primary_subjects JSON** 写入上述路径（回复中给出**单个** ```json 代码块）。
禁止输出 blocks / skeleton / segment_attribution / entries。

{format_manifest_for_prompt(manifest)}

=== 段落索引全文 ===
{body}

=== Step1b 专则（摘要）===
- 先判每段「主要在记述谁」，再由脚本合并 blocks
- 非 Top5 小君纯享国链 → exclude 世系链；**叙事段（季札聘国、弑僚等）不得误标世系链**
- 开传边界：incoming 从「是为 XX」/「王XX元年」起
- 太史公曰 / 论赞 / 评曰 → exclude（三国志评曰不建条目）

=== step1b_primary_subjects.md ===
{step1b_alpha_md}
"""

    print(f"Step1b-α 模型: {deepseek_settings()['model']} · prompt 约 {len(prompt)} 字", flush=True)
    sid = f"v2-{work}-{vol.zfill(3)}-1b-alpha"
    res = run_agent_turn(
        prompt,
        session_id=sid,
        timeout_sec=900,
        artifact_paths={"primary_subjects": primary_out},
    )
    if not primary_out.exists():
        if not _write_json_from_llm(str(res.get("result") or ""), primary_out):
            diag = ROOT / "data/05工作流中间产物/标注-v2" / f"{work}_{vol.zfill(3)}_step1b_alpha_raw.txt"
            diag.parent.mkdir(parents=True, exist_ok=True)
            diag.write_text(str(res.get("result") or ""), encoding="utf-8")
            raise RuntimeError(f"Step1b-α 未落盘 primary_subjects.json，原始回复已存: {diag}")

    primary = json.loads(primary_out.read_text(encoding="utf-8"))
    n_para = len(primary.get("paragraphs") or [])
    n_block = sum(1 for r in (primary.get("paragraphs") or []) if (r.get("disposition") or "block") == "block")
    n_ex = n_para - n_block
    print(f"✅ Step1b-α 落盘: {primary_out} · {n_para} 段 · block {n_block} / exclude {n_ex}", flush=True)


def run_step1b_beta(work: str, vol: str) -> None:
    """Step1b-β：primary_subjects + protagonists → blocks.json（脚本）"""
    agg = V2 / "scripts/v2_aggregate_blocks.py"
    r = subprocess.run(
        [sys.executable, str(agg), "--work", work, "--vol", vol],
        env={**os.environ, "HIST_ANNOTATE_TRACK": "v2", "HISTOGRAPH_ROOT": str(ROOT)},
        capture_output=True,
        text=True,
    )
    print(r.stdout, end="", flush=True)
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr, flush=True)
    if r.returncode != 0:
        raise RuntimeError(f"Step1b-β 聚合失败 ({r.returncode})")


def run_step1b(work: str, vol: str, index: dict, *, skip_alpha: bool = False) -> None:
    from lib.protagonist_workflow import load_protagonists
    from paths_config import histograph_paths

    manifest = load_protagonists(work, vol)
    if not manifest:
        raise RuntimeError("Step1b 需要 protagonists.json")

    mode = (manifest.get("narrative_mode") or "single").strip()
    if mode in ("single", "fanzuo"):
        print(f"Step1b 机械划块（narrative_mode={mode}，不调 LLM）", flush=True)
        run_step1b_mechanical(work, vol)
        return

    primary_out = histograph_paths()["annotate_work"] / f"{work}_{vol.zfill(3)}_primary_subjects.json"
    if skip_alpha:
        if not primary_out.is_file():
            raise RuntimeError(f"--skip-primary-subjects 但缺少 {primary_out}")
        print(f"Step1b-α 跳过，沿用 {primary_out}", flush=True)
    else:
        run_step1b_alpha(work, vol, index)

    run_step1b_beta(work, vol)


def run_gate_expand_check(work: str, vol: str, *, skip_expand: bool = False) -> None:
    from paths_config import histograph_paths

    env = {**os.environ, "HIST_ANNOTATE_TRACK": "v2", "HISTOGRAPH_ROOT": str(ROOT), "HIST_REPAIR": "1"}
    gate = V2 / "scripts/v2_blocks_gate.py"
    expand = V2 / "scripts/v2_expand_to_skeleton.py"
    chk = ANNOTATE / "check_format.py"

    r = subprocess.run([sys.executable, str(gate), "--work", work, "--vol", vol], env=env, capture_output=True, text=True)
    print(r.stdout, end="", flush=True)
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr, flush=True)
    if r.returncode != 0:
        raise RuntimeError(f"gate 失败 ({r.returncode})")

    if not skip_expand:
        r = subprocess.run([sys.executable, str(expand), "--work", work, "--vol", vol], env=env, capture_output=True, text=True)
        print(r.stdout, end="", flush=True)
        if r.stderr:
            print(r.stderr, end="", file=sys.stderr, flush=True)
        if r.returncode != 0:
            raise RuntimeError(f"expand 失败 ({r.returncode})")

    if work.startswith("02汉书"):
        from lib.hanshu_autofix import repair_skeleton_headers

        repaired, hdr_msg = repair_skeleton_headers(work, vol)
        if repaired:
            print(f"✅ {hdr_msg}\n", flush=True)

    sk = list(histograph_paths()["annotations"].glob(f"{work}_{vol.zfill(3)}_*_skeleton.json"))
    if not sk:
        raise RuntimeError("skeleton 未生成")
    r = subprocess.run(
        [sys.executable, str(chk), str(sk[0]), "--phase", "skeleton"],
        env=env,
        capture_output=True,
        text=True,
    )
    print(r.stdout, end="", flush=True)
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr, flush=True)
    if r.returncode != 0:
        raise RuntimeError("check_format skeleton 失败")

    pp = histograph_paths()["annotate_work"] / f"{work}_{vol.zfill(3)}_protagonists.json"
    if pp.is_file():
        import importlib.util

        hint_mod = V2 / "scripts/v2_volume_profile_hints.py"
        spec = importlib.util.spec_from_file_location("v2_profile_hints", hint_mod)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        manifest = json.loads(pp.read_text(encoding="utf-8"))
        skeleton = json.loads(sk[0].read_text(encoding="utf-8"))
        mod.print_profile_yellow_hints(manifest, skeleton)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="01史记")
    ap.add_argument("--vol", default="032")
    ap.add_argument("--skip-1a", action="store_true")
    ap.add_argument("--skip-1b", action="store_true")
    ap.add_argument("--skip-primary-subjects", action="store_true", help="hezhuan：跳过 Step1b-α，沿用已有 primary_subjects")
    ap.add_argument("--aggregate-only", action="store_true", help="hezhuan：只跑 Step1b-β 聚合 blocks")
    args = ap.parse_args()

    index = _load_index(args.work, args.vol)
    manifest = {}
    if not args.skip_1a:
        manifest = run_step1a(args.work, args.vol, index)
    if args.aggregate_only:
        run_step1b_beta(args.work, args.vol)
    elif not args.skip_1b:
        run_step1b(args.work, args.vol, index, skip_alpha=args.skip_primary_subjects)
    mode = (manifest.get("narrative_mode") or "").strip()
    if args.skip_1a and not mode:
        from lib.protagonist_workflow import load_protagonists
        import sys as _sys
        if str(ORCH) not in _sys.path:
            _sys.path.insert(0, str(ORCH))
        m = load_protagonists(args.work, args.vol) or {}
        mode = (m.get("narrative_mode") or "single").strip()
    skip_expand = mode in ("single", "fanzuo")
    run_gate_expand_check(args.work, args.vol, skip_expand=skip_expand)
    print("✅ v2 单卷 LLM 流水线完成", flush=True)


if __name__ == "__main__":
    main()
