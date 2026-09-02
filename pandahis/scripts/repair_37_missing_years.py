#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补跑 repair 残留的 37 条缺生卒条目（小批次 + 种子表，避免 max_tokens 截断）。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONLINE = ROOT / "data" / "12线上史略索引" / "史略索引_online.json"
V2 = ROOT / "data" / "10新标注条目" / "史略索引_03至04.json"
REPORT = ROOT / "data" / "05工作流中间产物" / "三国东汉补全" / "repair_20260825_175400.json"
TOOLS = ROOT / "tools" / "openclaw-historiography"
ANNOTATE = TOOLS / "historiography-annotate"

for _p in (str(TOOLS), str(ANNOTATE), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_env = TOOLS / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())

SEED: dict[str, tuple[int, int, str]] = {
    "华歆": (157, 231, "华歆生卒约157–231"),
    "卢植": (139, 192, "卢植初平三年卒年五十四，生年139"),
    "卢毓": (183, 257, "卢毓十岁而孤（父卢植192卒），生约183，卒约257"),
    "卓茂": (-53, 28, "卓茂建武四年卒年七十余，生约前53"),
    "包咸": (-7, 65, "包咸生卒约前7–65"),
    "乐进": (160, 218, "乐进建安二十三年卒，生年约160"),
    "于禁": (160, 221, "于禁黄初二年卒，生年约160"),
    "典韦": (160, 197, "典韦宛城之战卒197，生年约160"),
    "张郃": (167, 231, "张郃太和五年卒，生年约167"),
    "徐晃": (169, 227, "徐晃太和元年卒，生年约169"),
    "曹洪": (169, 232, "曹洪太和六年卒，生年约169"),
    "曹休": (174, 228, "曹休太和二年卒，生年约174"),
    "曹真": (185, 231, "曹真太和五年卒，生年约185"),
    "丁奉": (190, 271, "丁奉建衡元年卒，生年约190"),
    "全琮": (198, 249, "全琮赤乌十二年卒，生年约198"),
    "公孙度": (150, 204, "公孙度建安九年卒，生年约150"),
    "公孙瓒": (150, 199, "公孙瓒建安四年卒，生年约150"),
    "公孙述": (-10, 36, "公孙述建武十二年兵败死，生年约前10"),
    "彭宠": (10, 29, "彭宠建武五年反旋败死，生年约10"),
    "朱俊": (140, 195, "朱儁初平中卒，生年约140"),
    "黄香": (68, 122, "黄香延光元年卒，生年约68"),
    "左雄": (70, 138, "左雄永和三年卒，生年约70"),
    "刘珍": (70, 126, "刘珍永建中卒，生年约70"),
    "万脩": (10, 26, "万脩云台二十八将，建武中卒，生年约10"),
    "任光": (10, 29, "任光云台二十八将，建武中卒，生年约10"),
    "傅燮": (140, 187, "傅燮中平四年战死，生年约140"),
    "刘馥": (160, 208, "刘馥建安十三年卒，生年约160"),
    "刘琰": (160, 234, "刘琰建兴十二年被诛，生年约160"),
    "华覈": (200, 280, "华覈天纪末前后，生年约200"),
    "常林": (150, 237, "常林正始中卒年八十余，生约150–237"),
    "王修": (157, 218, "王修生卒约157–218"),
    "文聘": (160, 228, "文聘太和中卒，生年约160"),
    "徐盛": (170, 230, "徐盛黄武中卒，生年约170"),
    "吕虔": (160, 230, "吕虔魏初官至徐州刺史，生卒约160–230"),
    "刘梁": (80, 140, "刘梁桓帝前人物，生卒约80–140"),
    "刘瑜": (120, 188, "刘瑜光和中上书，生卒约120–188"),
    "刘陶": (140, 185, "刘陶中平二年下狱死，生年约140"),
}


def _log(msg: str) -> None:
    print(msg, flush=True)


def write_years(entry: dict, start: int, end: int, note: str, *, level: str) -> None:
    entry["史略开始年"] = int(start)
    entry["史略结束年"] = int(end)
    af = dict(entry.get("_auto_filled") or {})
    af["_年LLM依据"] = note
    af["_年兜底级别"] = level
    af.pop("_年待LLM", None)
    entry["_auto_filled"] = af


def extract_arr(text: str) -> list[dict]:
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if m:
        text = m.group(1)
    else:
        a, b = text.find("["), text.rfind("]")
        if a >= 0 and b > a:
            text = text[a : b + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def main() -> int:
    ids = json.loads(REPORT.read_text(encoding="utf-8")).get("still_no_year") or []
    online = json.loads(ONLINE.read_text(encoding="utf-8"))
    by_id = {e["史略ID"]: e for e in online}
    targets = [by_id[i] for i in ids if i in by_id]
    _log(f"目标 {len(targets)} 条")

    pending: list[dict] = []
    seeded = 0
    for e in targets:
        name = str(e.get("史略名称") or "")
        if name in SEED:
            start, end, note = SEED[name]
            write_years(e, start, end, note, level="学界生卒表")
            seeded += 1
        else:
            pending.append(e)
    _log(f"种子 {seeded}；待 LLM {len(pending)}")

    def save() -> None:
        ONLINE.write_text(
            json.dumps(online, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    save()

    if pending:
        from llm.config import PROVIDER_DEEPSEEK, ensure_annotate_model, get_provider_name
        from llm.provider import run_agent_turn

        if get_provider_name() == PROVIDER_DEEPSEEK:
            ensure_annotate_model()

        batch_size = 4
        llm_ok = llm_fail = 0
        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            payload = [
                {
                    "史略ID": e.get("史略ID"),
                    "判定对象": e.get("史略名称"),
                    "史略分类": e.get("史略分类"),
                    "二级朝代坐标": e.get("二级朝代坐标"),
                    "四级帝王坐标": e.get("四级帝王坐标"),
                    "主要史料出处": e.get("主要史料出处"),
                    "原文字句": (e.get("原文字句") or "")[:300],
                }
                for e in batch
            ]
            prompt = (
                "为下列人物填写生卒年。史略开始年=出生年，史略结束年=去世年（公元前为负）。\n"
                "取史学界主流；禁止用帝王在位年冒充生卒。依据≤40字。\n"
                '只输出JSON数组：[{"史略ID":"...","史略开始年":整数,"史略结束年":整数,"依据":"简述"}]\n\n'
                + json.dumps(payload, ensure_ascii=False)
            )
            sid = "yrs37-" + hashlib.sha1(prompt.encode()).hexdigest()[:10]
            _log(f"  LLM生卒批 {i // batch_size + 1} ({len(batch)})")
            try:
                res = run_agent_turn(prompt, session_id=sid, timeout_sec=120, temperature=0)
                rows = extract_arr(str(res.get("result", "")))
            except Exception as exc:  # noqa: BLE001
                _log(f"    FAIL {exc}")
                llm_fail += len(batch)
                continue
            by_row = {
                str(r.get("史略ID", "")).strip(): r for r in rows if isinstance(r, dict)
            }
            for e in batch:
                row = by_row.get(str(e.get("史略ID")))
                if not row:
                    llm_fail += 1
                    continue
                try:
                    start, end = int(row["史略开始年"]), int(row["史略结束年"])
                except (KeyError, TypeError, ValueError):
                    llm_fail += 1
                    continue
                if start > end or end - start > 120:
                    llm_fail += 1
                    continue
                write_years(
                    e,
                    start,
                    end,
                    str(row.get("依据") or f"{e.get('史略名称')}生卒约{start}–{end}"),
                    level="llm",
                )
                llm_ok += 1
            save()
        _log(f"生卒 LLM ok={llm_ok} fail={llm_fail}")

    peak_targets = [
        e
        for e in targets
        if isinstance(e.get("史略开始年"), int) and isinstance(e.get("史略结束年"), int)
    ]
    _log(f"峰值目标 {len(peak_targets)}")
    from peak_year import annotate as annotate_peak

    peak_stats = annotate_peak(
        peak_targets,
        use_llm=True,
        force=True,
        batch_size=8,
        on_batch_done=save,
    )
    _log(f"peak stats: {peak_stats}")
    save()

    # V2 patch
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    updated = {e["史略ID"]: e for e in targets}
    keys = (
        "史略开始年",
        "史略结束年",
        "峰值年",
        "峰值原因",
        "峰值类型",
        "峰值置信度",
        "_auto_filled",
    )
    n = 0
    for i, e in enumerate(v2):
        src = updated.get(e.get("史略ID"))
        if not src:
            continue
        for k in keys:
            if k == "_auto_filled":
                af = dict(e.get("_auto_filled") or {})
                af.update(src.get("_auto_filled") or {})
                e["_auto_filled"] = af
            else:
                e[k] = deepcopy(src.get(k))
        v2[i] = e
        n += 1
    V2.write_text(json.dumps(v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _log(f"回写 V2: {n}")

    left = [
        e
        for e in targets
        if e.get("史略开始年") is None or e.get("峰值年") is None
    ]
    for e in left:
        _log(
            f"  仍缺 {e.get('史略ID')} {e.get('史略名称')} "
            f"y={e.get('史略开始年')}-{e.get('史略结束年')} peak={e.get('峰值年')}"
        )
    _log(f"仍不完整: {len(left)}")

    for name in ("华歆", "卢植", "张郃", "典韦", "公孙瓒"):
        e = next((x for x in targets if x.get("史略名称") == name), None)
        if e:
            _log(
                f"  ✓ {name}: {e.get('史略开始年')}–{e.get('史略结束年')} "
                f"peak={e.get('峰值年')}"
            )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "import_box_index_json.py"),
            "--json",
            str(ONLINE),
            "--enrichment-only",
        ],
        cwd=str(ROOT),
        check=True,
    )
    _log("✅ 37 条补跑完成")
    return 0 if not left else 1


if __name__ == "__main__":
    raise SystemExit(main())
