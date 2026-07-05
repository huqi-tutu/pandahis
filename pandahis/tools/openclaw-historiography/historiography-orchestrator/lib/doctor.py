"""编排器环境自检。"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.config import PROVIDER_DEEPSEEK, get_provider_name, provider_label  # noqa: E402

from lib.adapters.openclaw import default_state_dir, orch_resolve_agent_id, run_agent_turn  # noqa: E402
from lib.config import load_catalog  # noqa: E402


def _config_agents() -> list[str]:
    cfg_path = Path(default_state_dir()) / "openclaw.json"
    if not cfg_path.exists():
        return []
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return [a.get("id", "") for a in data.get("agents", {}).get("list", [])]


def run_doctor() -> int:
    provider = get_provider_name()
    ok = True
    agent = orch_resolve_agent_id(
        load_catalog().get("works", {}).get("01A尚书", {}).get("openclaw_agent", "hist-worker")
    )

    print("🔧 historiography-orchestrator doctor\n")
    print(f"   LLM provider: {provider_label(provider)}")

    try:
        from pypinyin import lazy_pinyin  # noqa: F401

        print("   ✅ pypinyin 已安装（Step4 坐标 ID）")
    except ImportError:
        print("   ❌ 缺少 pypinyin：python3 -m pip install pypinyin")
        ok = False

    if provider == PROVIDER_DEEPSEEK:
        from llm.config import deepseek_settings

        if not deepseek_settings()["api_key"]:
            print("   ❌ 未设置 DEEPSEEK_API_KEY")
            ok = False
        else:
            print("   ✅ DeepSeek API key 已配置")
    else:
        configured = _config_agents()
        if agent in configured:
            print(f"   ✅ openclaw.json 已配置 agent: {agent}")
        else:
            print(f"   ❌ openclaw.json 未找到 agent: {agent}")
            print(f"      已配置: {', '.join(configured) or '(无)'}")
            print("      修改配置后需重启 AutoClaw / Gateway")
            ok = False

        print(
            "\n   ℹ️  飞书 agents_list 只显示 main，不能用来判断 hist-worker 是否存在。"
        )

    if not ok:
        return 1

    print(f"\n   ⏳ 探测 {provider_label(provider)}（约 30s）…")
    try:
        result = run_agent_turn(
            "doctor ping：只回复 OK",
            agent_id=agent,
            session_id=f"hist-doctor-{uuid.uuid4().hex[:8]}",
            timeout_sec=45,
        )
        snippet = str(result.get("result") or result.get("raw", ""))[:120]
        print(f"   ✅ provider 可达: {snippet}")
        return 0
    except Exception as exc:
        print(f"   ❌ provider 调用失败:\n      {exc}")
        if provider != PROVIDER_DEEPSEEK:
            print("      请确认 AutoClaw 已启动；若刚改 openclaw.json 请重启 Gateway")
        return 1
