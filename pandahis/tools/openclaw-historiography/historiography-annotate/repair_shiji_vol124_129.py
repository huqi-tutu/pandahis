#!/usr/bin/env python3
"""返工《史记》124–129：游侠/佞幸/滑稽/日者/龟策(skip)/货殖 合传段落分块。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from coordinate_index import build_emperor_index, ids_from_emperor  # noqa: E402
from emperor_resolve import build_emperor_info_index  # noqa: E402
from paths_config import get_histograph_root  # noqa: E402

ORCH = _ROOT / "historiography-orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

from lib import gates  # noqa: E402
from lib.blocks_workflow import blocks_path, expand_blocks_to_skeleton, volume_display_name  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402

WORK = "01史记"
DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"

BlockSpec = Tuple[str, str, int, int]
ExcludeSpec = Tuple[int, int, str]


def _emperor_coords(name: str) -> dict:
    eidx = build_emperor_info_index()
    info = eidx.get(name)
    if not info:
        raise KeyError(f"帝王表无: {name}")
    rec = {
        "emperor": name,
        "dynasty": info.get("dynasty", ""),
        "regime": info.get("regime", ""),
        "civilization": info.get("civilization", "华夏"),
        "dynasty_id": info.get("dynasty_id", ""),
        "regime_id": info.get("regime_id", ""),
        "civilization_id": info.get("civilization_id", "HX"),
        "id": info.get("id", ""),
    }
    out = {
        "四级帝王坐标": name,
        "三级政权坐标": info.get("regime", ""),
        "二级朝代坐标": info.get("dynasty", ""),
        "一级文明坐标": info.get("civilization", "华夏"),
    }
    out.update(ids_from_emperor(rec))
    return out


REPAIRS: Dict[str, dict] = {
    "124": {
        "blocks": [
            ("朱家", "庶众", 7, 7),
            ("剧孟", "庶众", 9, 9),
            ("郭解", "庶众", 11, 20),
        ],
        "excludes": [
            (1, 6, "其他"),
            (8, 8, "其他"),  # 田仲过渡，不单立传主
            (10, 10, "其他"),
            (21, 21, "其他"),
            (22, 22, "太史公曰"),
        ],
        "entry_meta": {
            "朱家": {
                "patron": "汉高祖",
                "start": -250,
                "end": -167,
                "axis": "朱家任侠藏活豪士，与高祖同时，主轴挂汉高祖。",
                "reason": "朱家传，P7",
            },
            "剧孟": {
                "patron": "汉武帝",
                "start": -200,
                "end": -127,
                "axis": "剧孟江淮任侠、吴楚反时条侯得之为助，主轴挂汉武帝。",
                "reason": "剧孟传，P9",
            },
            "郭解": {
                "patron": "汉武帝",
                "start": -180,
                "end": -116,
                "axis": "郭解轵人任侠至族诛，主轴挂汉武帝。",
                "reason": "郭解传，P11–20",
            },
        },
    },
    "125": {
        "blocks": [
            ("籍孺", "文臣", 1, 2),
            ("闳孺", "文臣", 3, 3),
            ("邓通", "文臣", 4, 7),
            ("韩嫣", "文臣", 9, 11),
            ("李延年", "宦官", 12, 14),
        ],
        "excludes": [
            (8, 8, "其他"),  # 周文仁
            (15, 15, "其他"),
            (16, 16, "太史公曰"),
        ],
        "entry_meta": {
            "籍孺": {
                "patron": "汉高祖",
                "start": -230,
                "end": -180,
                "axis": "籍孺高祖佞幸，与闳孺并述于开篇，主轴挂汉高祖。",
                "reason": "籍孺传，P1–2",
            },
            "闳孺": {
                "patron": "汉惠帝",
                "start": -210,
                "end": -160,
                "axis": "闳孺孝惠佞幸，化侍中冠饰，主轴挂汉惠帝。",
                "reason": "闳孺传，P3",
            },
            "邓通": {
                "patron": "汉文帝",
                "start": -210,
                "end": -157,
                "axis": "邓通文帝宠臣铸钱，景帝后贫死，主轴挂汉文帝。",
                "reason": "邓通传，P4–7",
            },
            "韩嫣": {
                "patron": "汉武帝",
                "start": -180,
                "end": -133,
                "axis": "韩嫣武帝幸臣，太后赐死，主轴挂汉武帝。",
                "reason": "韩嫣传，P9–11",
            },
            "李延年": {
                "patron": "汉武帝",
                "start": -110,
                "end": -91,
                "axis": "李延年协声律、妹幸李夫人，主轴挂汉武帝。",
                "reason": "李延年传，P12–14",
            },
        },
    },
    "126": {
        "blocks": [
            ("淳于髡", "庶众", 1, 6),
            ("优孟", "庶众", 8, 11),
            ("优旃", "庶众", 13, 17),
        ],
        "excludes": [
            (7, 7, "其他"),
            (12, 12, "其他"),
            (18, 18, "太史公曰"),
            (19, 39, "其他"),  # 褚先生补
        ],
        "entry_meta": {
            "淳于髡": {
                "patron": "齐威王",
                "start": -378,
                "end": -320,
                "axis": "淳于髡齐赘婿滑稽讽谏威王，主轴挂齐威王。",
                "reason": "淳于髡传，P1–6",
            },
            "优孟": {
                "patron": "楚庄王",
                "start": -613,
                "end": -591,
                "axis": "优孟楚优讽谏葬马、荐孙叔敖子，主轴挂楚庄王。",
                "reason": "优孟传，P8–11",
            },
            "优旃": {
                "patron": "秦始皇",
                "start": -246,
                "end": -210,
                "axis": "优旃秦倡侏儒讽秦二世，主轴挂秦始皇。",
                "reason": "优旃传，P13–17",
            },
        },
    },
    "127": {
        "blocks": [
            ("司马季主", "庶众", 3, 19),
        ],
        "excludes": [
            (1, 2, "其他"),
            (20, 24, "其他"),  # 宋忠贾谊结局、太史公曰、褚补
        ],
        "entry_meta": {
            "司马季主": {
                "patron": "汉武帝",
                "start": -180,
                "end": -120,
                "axis": "司马季主长安东市卜，与贾谊宋忠论道，主轴挂汉武帝。",
                "reason": "司马季主传，P3–19",
            },
        },
    },
    "129": {
        "blocks": [
            ("陶朱公", "庶众", 5, 7),
            ("子贡", "文臣", 8, 8),
            ("白圭", "庶众", 9, 10),
            ("猗顿", "庶众", 11, 11),
            ("巴寡妇清", "庶众", 12, 13),
            ("卓氏", "庶众", 36, 36),
        ],
        "excludes": [
            (1, 4, "其他"),
            (14, 35, "其他"),
            (37, 52, "其他"),
        ],
        "entry_meta": {
            "陶朱公": {
                "patron": "越王勾践",
                "start": -496,
                "end": -448,
                "axis": "范蠡佐勾践后化名陶朱公治产，主轴挂越王勾践。",
                "reason": "陶朱公（范蠡）传，P5–7",
            },
            "子贡": {
                "patron": "鲁定公",
                "start": -520,
                "end": -456,
                "axis": "子贡鬻财诸侯，与仲尼弟子传呼应，主轴挂鲁定公。",
                "reason": "子贡货殖段，P8",
            },
            "白圭": {
                "patron": "魏文侯",
                "start": -445,
                "end": -396,
                "axis": "白圭魏文侯时乐观时变，主轴挂魏文侯。",
                "reason": "白圭传，P9–10",
            },
            "猗顿": {
                "patron": "魏文侯",
                "start": -400,
                "end": -350,
                "axis": "猗顿用盬盐起富，主轴挂魏文侯朝。",
                "reason": "猗顿传，P11",
            },
            "巴寡妇清": {
                "patron": "秦始皇",
                "start": -246,
                "end": -210,
                "axis": "巴寡妇清守丹穴业，秦皇帝客之，主轴挂秦始皇。",
                "reason": "巴寡妇清传，P12–13",
            },
            "卓氏": {
                "patron": "秦始皇",
                "start": -220,
                "end": -150,
                "axis": "蜀卓氏赵人迁临邛铁冶，主轴挂秦始皇。",
                "reason": "卓氏传，P36",
            },
        },
    },
}


def _load_index(vol: str) -> dict:
    return json.loads((INDEX_DIR / f"{WORK}_{vol}.json").read_text(encoding="utf-8"))


def _write_protagonists(vol: str, blocks: List[BlockSpec], vol_name: str) -> None:
    seen: dict[str, str] = {}
    for name, cat, _, _ in blocks:
        if name not in seen:
            seen[name] = cat
    payload = {
        "work": WORK,
        "vol": vol,
        "volume_name": vol_name,
        "volume_type_guess": "列传",
        "protagonists": [
            {
                "name": n,
                "category": c,
                "rationale": f"《{vol_name}》叙事主轴：{n}（{c}）",
            }
            for n, c in seen.items()
        ],
        "excluded_kinds_hint": ["太史公曰", "世系链", "卷首标题", "其他"],
    }
    pp = protagonists_path(WORK, vol)
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_blocks(vol: str, blocks: List[BlockSpec], excludes: List[ExcludeSpec], total: int) -> None:
    payload = {
        "total_paragraphs": total,
        "excludes": [
            {"paragraph_from": a, "paragraph_to": b, "exclude_reason": r}
            for a, b, r in excludes
        ],
        "blocks": [
            {
                "name": n,
                "category": c,
                "paragraph_from": pf,
                "paragraph_to": pt,
            }
            for n, c, pf, pt in blocks
        ],
    }
    blocks_path(WORK, vol).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _patch_entries(sk: dict, vol: str, cfg: dict) -> None:
    vol_name = sk.get("volume", "")
    metas_raw = cfg["entry_meta"]
    for i, entry in enumerate(sk.get("entries") or []):
        name = entry.get("史略名称", "")
        cat = entry.get("史略分类", "")
        m = metas_raw.get(name) if isinstance(metas_raw, dict) else None
        if not m:
            continue
        pf = entry["paragraphs"][0]["paragraph_from"]
        pt = entry["paragraphs"][-1]["paragraph_to"]
        entry["史略开始年"] = m["start"]
        entry["史略结束年"] = m["end"]
        entry["优先级"] = "P0"
        entry["优先级判定理由"] = m["reason"]
        entry["五级细坐标"] = f"史记·卷{vol}·{cat}·{i + 1:02d}"
        entry["六级段落锚点"] = f"[P{pf}-P{pt}]"
        entry["原文出处"] = f"{vol_name}·P{pf}-P{pt}"
        entry["_needs_llm"] = []
        if cat == "君王":
            entry.update(_emperor_coords(name))
        elif m.get("patron"):
            entry.update(_emperor_coords(m["patron"]))
        af: dict = {}
        if m.get("axis"):
            af["_坐标主轴说明"] = m["axis"]
        if af:
            entry["_auto_filled"] = af


def repair_vol_skip_128() -> tuple[bool, str]:
    """128 龟策列传：全书约定不录人物史略，全卷 exclude。"""
    from lib.adapters.openclaw import expected_skeleton_path

    vol = "128"
    idx = _load_index(vol)
    total = int(idx["total"])
    vn = volume_display_name(WORK, vol, idx)
    reason = "无故事弧"
    vol_type = "非人物叙事"

    for p in (blocks_path(WORK, vol), protagonists_path(WORK, vol)):
        if p.exists():
            p.unlink()

    sk_path = gates.skeleton_path(WORK, vol)
    if sk_path is not None and sk_path.exists():
        sk_path.unlink()

    sk_path = expected_skeleton_path(WORK, vol, idx)
    sk = {
        "volume": vn,
        "source_file": (idx.get("source_file") or f"{WORK}_{vol}.txt").strip(),
        "total_paragraphs": total,
        "volume_type": vol_type,
        "segment_attribution": [
            {"paragraph": p, "owners": [], "exclude_reason": reason}
            for p in range(1, total + 1)
        ],
        "entries": [],
    }
    sk_path.parent.mkdir(parents=True, exist_ok=True)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, vol, sk_path)
    gates.step4_prepare(sk_path)
    gates.step4_shiji_person_fallback(sk_path, WORK, vol)
    ok_fin, fin_msg = gates.step4_finalize(sk_path)
    if not ok_fin:
        return False, f"卷128 finalize 失败: {fin_msg[-400:]}"

    for step in ("1", "2", "3", "4"):
        ok, msg = gates.verify_step(WORK, vol, step)
        if not ok:
            return False, f"卷128 Step{step} 未过: {msg[-400:]}"

    conn = connect()
    now = utc_now()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, WORK, vol, step),
        )
    conn.commit()
    return True, f"卷128 {vn} 已 skip（{reason}，0 条）"


def repair_vol(vol: str) -> tuple[bool, str]:
    if vol == "128":
        return repair_vol_skip_128()

    cfg = REPAIRS[vol]
    blocks: List[BlockSpec] = list(cfg["blocks"])
    excludes: List[ExcludeSpec] = list(cfg["excludes"])
    idx = _load_index(vol)
    total = int(idx["total"])
    vn = volume_display_name(WORK, vol, idx)

    _write_protagonists(vol, blocks, vn)
    _write_blocks(vol, blocks, excludes, total)

    sk_path = gates.skeleton_path(WORK, vol)
    if sk_path is not None and sk_path.exists():
        sk_path.unlink()

    sk_path = expand_blocks_to_skeleton(WORK, vol, idx)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    _patch_entries(sk, vol, cfg)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, vol, sk_path)
    gates.step4_prepare(sk_path)
    gates.step4_shiji_person_fallback(sk_path, WORK, vol)

    for step in ("1", "2", "3", "4"):
        ok, msg = gates.verify_step(WORK, vol, step)
        if not ok:
            return False, f"卷{vol} Step{step} 校验失败:\n{msg[-800:]}"
    gates.step4_finalize(sk_path)

    conn = connect()
    now = utc_now()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, WORK, vol, step),
        )
    conn.commit()
    return True, f"卷{vol} {vn} 返工完成（{len(sk.get('entries', []))} 条）"


def main() -> None:
    default = ["124", "125", "126", "127", "128", "129"]
    vols = sys.argv[1:] if len(sys.argv) > 1 else default
    failed = []
    for vol in vols:
        vol = vol.zfill(3)
        if vol != "128" and vol not in REPAIRS:
            print(f"跳过未知卷: {vol}")
            continue
        print(f"\n=== 返工 {WORK} 卷{vol} ===")
        try:
            ok, msg = repair_vol(vol)
            print("✅" if ok else "❌", msg)
            if not ok:
                failed.append(vol)
        except Exception as e:
            print(f"❌ 卷{vol} 异常: {e}")
            failed.append(vol)
    if failed:
        raise SystemExit(f"失败卷: {failed}")
    print("\n✅ 全部完成")


if __name__ == "__main__":
    main()
