#!/usr/bin/env python3
"""校验史料标注/翻译工作流是否仍指向项目内目录。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from paths_config import (  # noqa: E402
    DEFAULT_HISTOGRAPH_ROOT,
    ENV_ANNOTATE_TRACK,
    FORBIDDEN_ROOTS,
    get_annotate_track,
    histograph_paths,
    validate_histograph_root,
)

SKILLS_ROOT = ROOT
OPENCLAW_SKILLS = Path.home() / ".openclaw-autoclaw" / "skills"


def main() -> int:
    ok = True
    print("🔍 历史图谱工作流路径自检\n")

    try:
        root = validate_histograph_root()
        print(f"✅ HISTOGRAPH_ROOT → {root}")
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1

    p = histograph_paths()
    track = get_annotate_track()
    print(f"ℹ️  当前标注轨道: {track} ({ENV_ANNOTATE_TRACK})")
    checks = [
        ("原文", p["sources"]),
        ("标注索引", p["annotations"]),
        ("段落索引", p["paragraph_index"]),
        ("全局索引", p["global_index"].parent),
        ("翻译产出", p["translate_output"]),
        ("标注中间产物", p["annotate_work"]),
        ("翻译中间产物", p["translate_work"]),
        ("编排运行态", p["state_root"]),
    ]
    for label, path in checks:
        under_project = DEFAULT_HISTOGRAPH_ROOT.resolve() in path.resolve().parents or path.resolve() == DEFAULT_HISTOGRAPH_ROOT.resolve()
        flag = "✅" if under_project else "❌"
        print(f"{flag} {label}: {path}")
        if not under_project:
            ok = False

    legacy_state = DEFAULT_HISTOGRAPH_ROOT / ".historiography"
    if legacy_state.exists():
        print(
            f"\n⚠️  检测到旧运行态目录: {legacy_state}\n"
            "   新流程已迁至 data/05工作流中间产物/编排/；可手动迁移后删除旧目录。"
        )

    if OPENCLAW_SKILLS.exists():
        print(f"\nℹ️  OpenClaw 旧 skill 仍存在: {OPENCLAW_SKILLS}")
        print("   生产流程请勿再编辑该目录；以项目内 tools/openclaw-historiography 为准。")

    if SKILLS_ROOT.exists():
        print(f"\n✅ 项目工作流目录: {SKILLS_ROOT}")

    for forbidden in FORBIDDEN_ROOTS:
        if forbidden.exists() and root.resolve() == forbidden.resolve():
            print(f"❌ 数据根误指向禁止目录: {forbidden}")
            ok = False

    if not p["global_index"].is_file():
        print(f"\n⚠️  全局索引尚未生成: {p['global_index']}")

    print("\n建议环境变量（写入 shell profile 或 .env）：")
    print("  export HIST_LLM_PROVIDER=deepseek")
    print(f"  export HISTOGRAPH_ROOT={DEFAULT_HISTOGRAPH_ROOT}")
    print("  export HIST_ANNOTATE_TRACK=v2   # 新版标注时使用")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
