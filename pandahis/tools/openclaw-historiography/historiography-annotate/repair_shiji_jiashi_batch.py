#!/usr/bin/env python3
"""批量返工《史记》问题世家卷：047–049、034–041。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from lib.blocks_workflow import blocks_path, expand_blocks_to_skeleton  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402

WORK = "01史记"
DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"
ANNOT_DIR = DATA / "05工作流中间产物" / "标注"

# (name, category, p_from, p_to)
BlockSpec = tuple[str, str, int, int]
ExcludeSpec = tuple[int, int, str]


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
    "047": {
        "blocks": [("孔子", "士臣", 1, 106)],
        "excludes": [(107, 108, "太史公曰")],
        "entry_meta": [
            {
                "patron": "鲁定公",
                "start": -551,
                "end": -479,
                "axis": "孔子为鲁国人，周游列国主轴锚鲁定公；生卒取学界主流前551–前479。",
                "reason": "孔子世家主轴（士臣），共106段",
            }
        ],
    },
    "048": {
        "blocks": [("陈涉", "庶众", 2, 21)],
        "excludes": [(1, 1, "卷首标题"), (22, 28, "其他")],
        "entry_meta": [
            {
                "patron": "秦二世",
                "start": -209,
                "end": -196,
                "axis": "陈涉起义反秦，叙事主轴锚秦二世；活跃期含吴广等余绪前209–前196。",
                "reason": "陈涉世家主轴（庶众），共20段",
            }
        ],
    },
    "049": {
        "blocks": [
            ("薄太后", "宗戚", 4, 8),
            ("窦太后", "宗戚", 9, 15),
            ("王太后", "宗戚", 16, 28),
            ("卫子夫", "宗戚", 29, 44),
        ],
        "excludes": [(1, 3, "其他"), (45, 56, "其他")],
        "entry_meta": {
            "薄太后": {
                "patron": "汉文帝",
                "start": -203,
                "end": -155,
                "axis": "薄太后为文帝生母，叙事锚汉文帝朝。",
                "reason": "薄太后叙事，共5段",
            },
            "窦太后": {
                "patron": "汉景帝",
                "start": -205,
                "end": -135,
                "axis": "窦太后为景帝皇后、武帝祖母，叙事锚汉景帝朝。",
                "reason": "窦太后叙事，共7段",
            },
            "王太后": {
                "patron": "汉武帝",
                "start": -188,
                "end": -104,
                "axis": "王娡为武帝生母，栗姬、王儿姁诸妃并此块；锚汉武帝朝。",
                "reason": "王太后（王娡）及栗姬、王儿姁，共13段",
            },
            "卫子夫": {
                "patron": "汉武帝",
                "start": -139,
                "end": -91,
                "axis": "卫子夫为武帝皇后，叙事锚汉武帝朝。",
                "reason": "卫子夫及外戚专宠，共16段",
            },
        },
    },
    "034": {
        "blocks": [
            ("燕召公", "君王", 1, 29),
            ("燕昭王", "君王", 30, 34),
            ("燕惠王", "君王", 35, 39),
            ("燕王喜", "君王", 40, 43),
        ],
        "excludes": [(44, 44, "太史公曰")],
        "entry_meta": [
            {"patron": None, "start": -1044, "end": -864, "reason": "召公始祖贯卷，共29段"},
            {"patron": None, "start": -311, "end": -279, "reason": "燕昭王招贤复国，共5段"},
            {"patron": None, "start": -278, "end": -272, "reason": "燕惠王、武成王，共5段"},
            {"patron": None, "start": -255, "end": -222, "reason": "燕王喜末代，共4段"},
        ],
    },
    "037": {
        "blocks": [
            ("卫康叔", "君王", 1, 11),
            ("卫宣公", "君王", 12, 16),
            ("卫懿公", "君王", 17, 20),
            ("卫文公", "君王", 21, 35),
            ("卫灵公", "君王", 36, 40),
            ("卫出公", "君王", 41, 57),
        ],
        "excludes": [(58, 58, "太史公曰")],
        "entry_meta": [
            {"patron": None, "start": -1042, "end": -760, "reason": "卫康叔及早期，共11段"},
            {"patron": None, "start": -718, "end": -700, "reason": "卫宣公杀太子，共5段"},
            {"patron": None, "start": -699, "end": -660, "reason": "卫懿公好鹤亡国，共4段"},
            {"patron": None, "start": -659, "end": -600, "reason": "卫文公复国，共15段"},
            {"patron": None, "start": -543, "end": -493, "reason": "卫灵公与南子，共5段"},
            {"patron": None, "start": -492, "end": -456, "reason": "卫出公辄乱政，共17段"},
        ],
    },
    "038": {
        "blocks": [
            ("宋微子", "君王", 1, 39),
            ("宋襄公", "君王", 40, 44),
            ("宋昭公", "君王", 45, 57),
            ("宋景公", "君王", 58, 61),
            ("宋君偃", "君王", 62, 62),
        ],
        "excludes": [(63, 64, "太史公曰")],
        "entry_meta": [
            {"patron": None, "start": -1100, "end": -800, "reason": "微子始祖贯卷，共39段"},
            {"patron": None, "start": -650, "end": -637, "reason": "宋襄公泓水之战，共5段"},
            {"patron": None, "start": -636, "end": -520, "reason": "昭公文公乱政，共13段"},
            {"patron": None, "start": -516, "end": -451, "reason": "宋景公，共4段"},
            {"patron": None, "start": -328, "end": -286, "reason": "宋君偃称王，共1段"},
        ],
    },
    "039": {
        "blocks": [
            ("晋武公", "君王", 1, 23),
            ("晋献公", "君王", 24, 44),
            ("晋文公", "君王", 45, 102),
            ("晋景公", "君王", 103, 151),
            ("晋悼公", "君王", 152, 182),
        ],
        "excludes": [(183, 183, "太史公曰")],
        "entry_meta": [
            {"patron": None, "start": -678, "end": -678, "reason": "曲沃并晋，共23段"},
            {"patron": None, "start": -676, "end": -651, "reason": "晋献公灭国，共21段"},
            {"patron": None, "start": -636, "end": -628, "reason": "晋文公称霸，共58段"},
            {"patron": None, "start": -627, "end": -573, "reason": "襄灵景厉诸君，共49段"},
            {"patron": None, "start": -572, "end": -403, "reason": "悼公及三家分晋前夜，共31段"},
        ],
    },
    "040": {
        "blocks": [
            ("楚武王", "君王", 1, 19),
            ("楚成王", "君王", 20, 29),
            ("楚庄王", "君王", 30, 55),
            ("楚昭王", "君王", 56, 93),
            ("楚怀王", "君王", 94, 133),
        ],
        "excludes": [(134, 134, "太史公曰")],
        "entry_meta": [
            {"patron": None, "start": -741, "end": -690, "reason": "楚武王开拓，共19段"},
            {"patron": None, "start": -689, "end": -626, "reason": "楚成王，共10段"},
            {"patron": None, "start": -613, "end": -541, "reason": "楚庄王称霸，共26段"},
            {"patron": None, "start": -540, "end": -489, "reason": "平昭诸王，共38段"},
            {"patron": None, "start": -328, "end": -296, "reason": "楚怀王，共40段"},
        ],
    },
    "041": {
        "blocks": [("越王句践", "君王", 1, 35)],
        "excludes": [(36, 36, "太史公曰")],
        "entry_meta": [
            {"patron": None, "start": -496, "end": -379, "reason": "句践世家主轴，共35段"},
        ],
    },
    "059": {
        "blocks": [
            ("栗姬", "宗戚", 1, 9),
            ("程姬", "宗戚", 10, 18),
            ("贾夫人", "宗戚", 19, 26),
            ("唐姬", "宗戚", 27, 30),
            ("儿姁", "宗戚", 31, 45),
        ],
        "excludes": [(46, 47, "太史公曰")],
        "entry_meta": {
            "栗姬": {
                "patron": "汉景帝",
                "start": -176,
                "end": -150,
                "axis": "栗姬三子荣、德、阏于封王及宗族，锚汉景帝。",
                "reason": "栗姬宗支，共9段",
            },
            "程姬": {
                "patron": "汉景帝",
                "start": -155,
                "end": -108,
                "axis": "程姬三子馀、非、端封王叙事，锚汉景帝。",
                "reason": "程姬宗支，共9段",
            },
            "贾夫人": {
                "patron": "汉景帝",
                "start": -155,
                "end": -92,
                "axis": "贾夫人二子彭祖、胜封王叙事，锚汉景帝。",
                "reason": "贾夫人宗支，共8段",
            },
            "唐姬": {
                "patron": "汉景帝",
                "start": -155,
                "end": -128,
                "axis": "唐姬子长沙定王发一宗，锚汉景帝。",
                "reason": "唐姬宗支，共4段",
            },
            "儿姁": {
                "patron": "汉景帝",
                "start": -148,
                "end": -104,
                "axis": "王夫人儿姁四子及后裔封王，锚汉景帝。",
                "reason": "儿姁宗支，共15段",
            },
        },
    },
    "060": {
        "blocks": [
            ("齐王刘闳", "君王", 12, 13),
            ("齐王刘闳", "君王", 21, 21),
            ("齐王刘闳", "君王", 23, 23),
            ("燕王旦", "君王", 14, 15),
            ("燕王旦", "君王", 29, 34),
            ("广陵王刘胥", "君王", 16, 17),
            ("广陵王刘胥", "君王", 25, 28),
        ],
        "excludes": [
            (1, 11, "其他"),
            (18, 18, "太史公曰"),
            (19, 20, "其他"),
            (22, 22, "其他"),
            (24, 24, "其他"),
        ],
        "entry_meta": {
            "齐王刘闳": {
                "patron": "汉武帝",
                "start": -117,
                "end": -110,
                "axis": "齐王闳册命策与褚补事迹，锚汉武帝。",
                "reason": "齐王策+褚补，共5段",
            },
            "燕王旦": {
                "patron": "汉武帝",
                "start": -117,
                "end": -80,
                "axis": "燕王旦册命策与谋反，锚汉武帝。",
                "reason": "燕王策+褚补，共8段",
            },
            "广陵王刘胥": {
                "patron": "汉武帝",
                "start": -117,
                "end": -54,
                "axis": "广陵王胥册命策与后世，锚汉武帝。",
                "reason": "广陵王策+褚补，共6段",
            },
        },
    },
}


def _load_index(vol: str) -> dict:
    p = INDEX_DIR / f"{WORK}_{vol}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _write_protagonists(vol: str, blocks: List[BlockSpec], vol_name: str) -> None:
    seen: dict[str, str] = {}
    for name, cat, _, _ in blocks:
        if name not in seen:
            seen[name] = cat
    protagonists = [
        {
            "name": n,
            "category": c,
            "rationale": f"《{vol_name}》叙事主轴：{n}（{c}）",
        }
        for n, c in seen.items()
    ]
    payload = {
        "work": WORK,
        "vol": vol,
        "volume_name": vol_name,
        "volume_type_guess": "世家",
        "protagonists": protagonists,
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
    bp = blocks_path(WORK, vol)
    bp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _patch_entries(sk: dict, vol: str, cfg: dict) -> None:
    vol_name = sk.get("volume", "")
    metas_raw = cfg["entry_meta"]
    for i, entry in enumerate(sk.get("entries") or []):
        name = entry.get("史略名称", "")
        cat = entry.get("史略分类", "")
        if isinstance(metas_raw, dict):
            m = metas_raw.get(name)
        else:
            m = metas_raw[i] if i < len(metas_raw) else None
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
            coords = _emperor_coords(name)
            entry.update(coords)
        elif m.get("patron"):
            entry.update(_emperor_coords(m["patron"]))
        af: dict = {}
        if m.get("axis"):
            af["_坐标主轴说明"] = m["axis"]
        if af:
            entry["_auto_filled"] = af


def repair_vol(vol: str) -> tuple[bool, str]:
    cfg = REPAIRS[vol]
    blocks: List[BlockSpec] = list(cfg["blocks"])
    excludes: List[ExcludeSpec] = list(cfg["excludes"])
    idx = _load_index(vol)
    total = int(idx["total"])
    vol_name = idx.get("source_file", "").split("_")[-1].replace(".txt", "")
    # volume display from index path
    from lib.blocks_workflow import volume_display_name

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
    vols = sys.argv[1:] if len(sys.argv) > 1 else list(REPAIRS.keys())
    failed = []
    for vol in vols:
        vol = vol.zfill(3)
        if vol not in REPAIRS:
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
