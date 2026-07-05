"""《汉书》合传机械划块自动修复：别名重试、卷级块界覆盖、同段双归属。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib import blocks_workflow, gates
from lib.config import ANNOTATE_DIR
from lib.config import paths as orch_paths
from lib.volume_manifest import (
    HEZHUAN_BIO_ALIASES,
    build_mechanical_blocks,
    build_mechanical_hezhuan_blocks,
    uses_mechanical_blocks,
)

# 机械划块失败时的确定性块界（name, category, start, end）
HANSHU_HEZHUAN_BLOCK_OVERRIDES: Dict[str, List[Tuple[str, str, int, int]]] = {
    "054": [
        ("刘长", "宗戚", 2, 7),
        ("刘安", "宗戚", 8, 13),
        ("刘赐", "宗戚", 14, 14),
        ("刘勃", "宗戚", 15, 15),
    ],
    "056": [
        ("石奋", "文臣", 2, 3),
        ("卫绾", "文臣", 4, 5),
        ("直不疑", "文臣", 6, 6),
        ("周仁", "文臣", 7, 8),
    ],
    "057": [
        ("刘参", "宗戚", 2, 2),
        ("梁孝王", "宗戚", 3, 4),
        ("刘揖", "宗戚", 5, 5),
        ("梁孝王", "宗戚", 6, 9),
    ],
    "084": [
        ("王吉", "文臣", 4, 10),
        ("贡禹", "文臣", 11, 16),
        ("龚胜", "文臣", 17, 19),
        ("龚舍", "文臣", 20, 20),
        ("龚胜", "文臣", 21, 21),
        ("鲍宣", "文臣", 22, 27),
    ],
    "087": [
        ("眭弘", "文臣", 2, 2),
        ("夏侯始昌", "文臣", 3, 3),
        ("夏侯胜", "文臣", 4, 8),
        ("京房", "文臣", 9, 14),
        ("翼奉", "文臣", 15, 22),
        ("李寻", "文臣", 23, 33),
    ],
    "088": [
        ("赵广汉", "文臣", 2, 6),
        ("尹翁归", "文臣", 7, 9),
        ("韩延寿", "文臣", 10, 15),
        ("张敞", "文臣", 16, 23),
        ("王尊", "文臣", 24, 31),
        ("王章", "文臣", 32, 33),
    ],
}

HANSHU_HEZHUAN_EXTRA_EXCLUDES: Dict[str, List[Tuple[int, int, str]]] = {
    "084": [
        (2, 3, "其他"),
    ],
    "088": [
        (34, 34, "其他"),
    ],
}

# 展开 skeleton 后同段双归属补丁
CO_BIO_PARAGRAPH_PATCHES: Dict[str, List[Dict[str, Any]]] = {
    "049": [
        {"paragraph": 7, "owners": ["萧何", "曹参"]},
    ],
    "051": [
        {"paragraph": 7, "owners": ["郦商", "夏侯婴"]},
        {"paragraph": 9, "owners": ["夏侯婴", "灌婴"]},
        {"paragraph": 12, "owners": ["灌婴", "傅宽"]},
        {"paragraph": 13, "owners": ["傅宽", "靳歙"]},
        {"paragraph": 14, "owners": ["靳歙", "周緤"]},
    ],
    "052": [
        {"paragraph": 2, "owners": ["张苍", "周昌"]},
        {"paragraph": 3, "owners": ["周昌", "赵尧"]},
        {"paragraph": 4, "owners": ["赵尧", "周昌"]},
        {"paragraph": 5, "owners": ["任敖", "张苍"]},
        {"paragraph": 6, "owners": ["张苍", "申屠嘉"]},
    ],
    "056": [
        {"paragraph": 8, "owners": ["周仁", "张欧"], "ensure_entry": "张欧"},
    ],
    "057": [
        {"paragraph": 2, "owners": ["梁孝王", "刘参", "刘揖"]},
        {"paragraph": 4, "owners": ["梁孝王", "刘参"]},
        {"paragraph": 5, "owners": ["刘揖", "梁孝王"]},
    ],
    "084": [
        {"paragraph": 17, "owners": ["龚胜", "龚舍"]},
        {"paragraph": 20, "owners": ["龚胜", "龚舍"]},
    ],
    "087": [
        {"paragraph": 3, "owners": ["眭弘", "夏侯始昌"]},
    ],
    "083": [
        {"paragraph": 15, "owners": ["薛广德", "平当"]},
    ],
}

CO_BIO_ENTRY_PARAGRAPH_PATCHES: Dict[str, Dict[str, List[Tuple[int, int]]]] = {
    "049": {
        "萧何": [(2, 7)],
        "曹参": [(7, 11)],
    },
    "051": {
        "郦商": [(6, 7)],
        "夏侯婴": [(7, 9)],
        "灌婴": [(9, 12)],
        "傅宽": [(12, 13)],
        "靳歙": [(13, 14)],
        "周緤": [(14, 14)],
    },
    "052": {
        "张苍": [(2, 2), (5, 6)],
        "周昌": [(2, 4)],
        "赵尧": [(3, 4)],
        "任敖": [(5, 5)],
        "申屠嘉": [(6, 7)],
    },
    "057": {
        "刘参": [(2, 2), (4, 4)],
        "梁孝王": [(2, 9)],
        "刘揖": [(2, 2), (5, 5)],
    },
    "084": {
        "王吉": [(4, 10)],
        "贡禹": [(11, 16)],
        "龚胜": [(17, 21)],
        "龚舍": [(17, 17), (20, 20)],
        "鲍宣": [(22, 27)],
    },
    "087": {
        "眭弘": [(2, 3)],
    },
    "083": {
        "薛广德": [(14, 15)],
        "平当": [(15, 17)],
    },
}

# 同姓藩王补录宗戚表（仅机械修复用，字段对齐 reference/宗戚.json）
_PRINCE_ZONGQI_STUBS: Dict[str, Dict[str, Any]] = {
    "刘长": {"宗戚名称": "刘长", "宗戚原名": "刘长", "宗戚类型": "同姓藩王", "册封之君": "汉高祖", "政权": "西汉", "受封时间": "-196", "卒年": "-174"},
    "刘安": {"宗戚名称": "刘安", "宗戚原名": "刘安", "宗戚类型": "同姓藩王", "册封之君": "汉文帝", "政权": "西汉", "受封时间": "-164", "卒年": "-122"},
    "刘赐": {"宗戚名称": "刘赐", "宗戚原名": "刘赐", "宗戚类型": "同姓藩王", "册封之君": "汉文帝", "政权": "西汉", "受封时间": "-153", "卒年": "-122"},
    "刘勃": {"宗戚名称": "刘勃", "宗戚原名": "刘勃", "宗戚类型": "同姓藩王", "册封之君": "汉文帝", "政权": "西汉", "受封时间": "-164", "卒年": "-154"},
    "刘参": {"宗戚名称": "刘参", "宗戚原名": "刘参", "宗戚类型": "同姓藩王", "册封之君": "汉文帝", "政权": "西汉", "受封时间": "-178", "卒年": "-161"},
    "刘揖": {"宗戚名称": "刘揖", "宗戚原名": "刘揖", "宗戚类型": "同姓藩王", "册封之君": "汉文帝", "政权": "西汉", "受封时间": "-178", "卒年": "-169"},
}


def _paragraph_text_map(index: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for row in index.get("paragraphs") or []:
        pid = int(row.get("id") or 0)
        if pid:
            out[pid] = (row.get("text") or "").strip()
    return out


def _manifest_from_override(vol: str) -> Optional[dict]:
    protagonists = _unique_override_protagonists(vol)
    if not protagonists:
        return None
    return {
        "narrative_mode": "hezhuan",
        "volume_type": "合传",
        "protagonists": protagonists,
        "_mechanical_override": True,
    }


def _unique_override_protagonists(vol: str) -> List[dict]:
    spec = HANSHU_HEZHUAN_BLOCK_OVERRIDES.get(vol.zfill(3)) or []
    protagonists: List[dict] = []
    seen: set[str] = set()
    for name, category, _s, _e in spec:
        if name in seen:
            continue
        protagonists.append({"name": name, "category": category})
        seen.add(name)
    return protagonists


def override_protagonist_keys(vol: str) -> List[Tuple[str, str]]:
    return [
        (item["name"], item["category"])
        for item in _unique_override_protagonists(vol)
    ]


def build_override_protagonists_manifest(
    vol: str,
    *,
    work: str = "02汉书",
    volume_name: str = "",
) -> Optional[dict]:
    protagonists = _unique_override_protagonists(vol)
    if not protagonists:
        return None

    rationale_map = {
        "刘参": "卷名所列文帝诸王之一，虽仅在卷首交代受封，但属合传明确主角，不应因篇幅短而排除。",
        "梁孝王": "《文三王传》叙事主体，卷中多段记其朝会、薨逝及梁国后续事件，应保留为主轴人物。",
        "刘揖": "卷名所列三王之一，且有独立段落记其好学、坠马而薨及国除，具完整故事弧，应独立立条。",
        "刘长": "卷级覆盖指定的诸侯王主轴人物，需与 blocks 一致保留。",
        "刘安": "卷级覆盖指定的诸侯王主轴人物，需与 blocks 一致保留。",
        "刘赐": "卷级覆盖指定的诸侯王主轴人物，需与 blocks 一致保留。",
        "刘勃": "卷级覆盖指定的诸侯王主轴人物，需与 blocks 一致保留。",
        "石奋": "卷级覆盖指定的合传主轴人物，需与 blocks 一致保留。",
        "卫绾": "卷级覆盖指定的合传主轴人物，需与 blocks 一致保留。",
        "直不疑": "卷级覆盖指定的合传主轴人物，需与 blocks 一致保留。",
        "周仁": "卷级覆盖指定的合传主轴人物，需与 blocks 一致保留。",
        "王吉": "卷名所列五人合传首位人物，昌邑中尉谏王、宣帝时上疏论政，属本卷明确主轴。",
        "贡禹": "卷名所列合传主角之一，元帝朝御史大夫，多上书言节俭、赋役与宗庙制度，属本卷明确主轴。",
        "龚胜": "卷名“两龚”之一，哀帝朝谏官，王莽征召不起绝食而死，具完整故事弧，应独立立条。",
        "龚舍": "卷名“两龚”之一，以名节著称，受征为谏大夫、太山太守后辞归，属本卷明确主轴。",
        "鲍宣": "卷名所列合传主角之一，哀帝朝谏大夫与司隶，七亡七死之论为本卷核心叙事之一。",
        "眭弘": "卷名“眭”指眭弘，因推灾异与昌邑、公孙病已之说而著名，属本卷明确主轴。",
        "夏侯始昌": "卷名“两夏侯”之一，武帝所重经师，亦为昌邑王太傅，属本卷明确主轴。",
        "夏侯胜": "卷名“两夏侯”之一，昭宣间名儒，废昌邑王、斥武帝庙乐与授经太后事迹完整，属本卷明确主轴。",
        "京房": "卷名“京”指京房，治易言灾异、创考功课吏法而死于党争，属本卷明确主轴。",
        "翼奉": "卷名“翼”指翼奉，以齐诗、阴阳灾异与徙都成周之议著称，属本卷明确主轴。",
        "李寻": "卷名“李”指李寻，哀帝时以洪范灾异、改元易号与外戚之议著称，属本卷明确主轴。",
        "赵广汉": "卷名“赵”指赵广汉，宣帝朝京兆尹，以发奸擿伏、威制豪强著称，属本卷明确主轴。",
        "尹翁归": "卷名“尹”指尹翁归，历东海太守、右扶风，以明察与廉平著称，属本卷明确主轴。",
        "韩延寿": "卷名“韩”指韩延寿，重礼教、善移风俗，终以左冯翊坐弃市，属本卷明确主轴。",
        "张敞": "卷名“张”指张敞，宣帝朝名吏，历胶东相、京兆尹、冀州刺史，属本卷明确主轴。",
        "王尊": "卷名“两王”之一，历益州刺史、东平相、京兆尹、东郡太守，以刚直敢断著称，属本卷明确主轴。",
        "王章": "卷名“两王”之一，成帝朝谏大夫、司隶校尉、京兆尹，以刚直敢言、为王凤所陷著称，属本卷明确主轴。",
    }
    return {
        "work": work,
        "vol": vol.zfill(3),
        "volume_name": volume_name,
        "volume_type_guess": "列传",
        "narrative_mode": "hezhuan",
        "skip_reason": None,
        "protagonists": [
            {
                "name": item["name"],
                "category": item["category"],
                "rationale": rationale_map.get(
                    item["name"], "卷级机械覆盖指定主轴人物，需与 blocks 保持一致。"
                ),
            }
            for item in protagonists
        ],
        "excluded_kinds_hint": ["卷首标题", "赞曰", "名册简传", "其他"],
        "_mechanical_override": True,
    }


def write_override_protagonists_manifest(
    work: str,
    vol: str,
    *,
    volume_name: str = "",
) -> Tuple[bool, str]:
    if not str(work).startswith("02汉书"):
        return False, "非汉书"

    from lib.protagonist_workflow import load_protagonists, protagonists_path

    existing = load_protagonists(work, vol) or {}
    manifest = build_override_protagonists_manifest(
        vol,
        work=work,
        volume_name=volume_name or str(existing.get("volume_name") or "").strip(),
    )
    if not manifest:
        return False, "无覆盖 manifest"

    path = protagonists_path(work, vol)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, f"覆盖主轴 {len(manifest['protagonists'])} 人"


def _blocks_from_override(
    vol: str, total: int, para_text: Optional[Dict[int, str]] = None
) -> Optional[dict]:
    spec = HANSHU_HEZHUAN_BLOCK_OVERRIDES.get(vol.zfill(3))
    if not spec:
        return None
    blocks = []
    for name, category, start, end in spec:
        blocks.append(
            {
                "name": name,
                "category": category,
                "paragraph_from": start,
                "paragraph_to": end,
            }
        )
    excludes: List[dict] = []
    if total >= 1:
        excludes.append(
            {"paragraph_from": 1, "paragraph_to": 1, "exclude_reason": "卷首标题"}
        )
    for start, end, reason in HANSHU_HEZHUAN_EXTRA_EXCLUDES.get(vol.zfill(3), []):
        excludes.append(
            {"paragraph_from": start, "paragraph_to": end, "exclude_reason": reason}
        )
    if para_text:
        from lib.volume_manifest import _commentary_exclude_reason, _detect_commentary_paragraphs

        for pid in _detect_commentary_paragraphs(para_text, total):
            if pid == 1:
                continue
            excludes.append(
                {
                    "paragraph_from": pid,
                    "paragraph_to": pid,
                    "exclude_reason": _commentary_exclude_reason(para_text.get(pid, "")),
                }
            )
    return {
        "volume": vol.zfill(3),
        "narrative_mode": "hezhuan",
        "total_paragraphs": total,
        "excludes": excludes,
        "blocks": blocks,
        "_source": "hanshu_hezhuan_autofix_override",
    }


def _try_hezhuan_with_aliases(
    manifest: dict, total: int, para_text: Dict[int, str]
) -> Optional[dict]:
    """用扩展别名重试机械划块。"""
    extra_aliases = dict(HEZHUAN_BIO_ALIASES)
    for p in manifest.get("protagonists") or []:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        aliases = list(extra_aliases.get(name, ()))
        if name not in aliases:
            aliases.append(name)
        for row in para_text.values():
            t = row.strip()
            if not t:
                continue
            m = re.match(r"^[\u4e00-\u9fff]{2,6}", t)
            if m and m.group(0) != name and name in t[:20]:
                head = m.group(0)
                if head not in aliases:
                    aliases.append(head)
        if aliases:
            extra_aliases[name] = tuple(aliases)
    try:
        return build_mechanical_hezhuan_blocks(
            manifest,
            total_paragraphs=total,
            para_text=para_text,
            bio_aliases=extra_aliases,
        )
    except (ValueError, TypeError):
        return None


def try_build_mechanical_blocks(
    work: str,
    vol: str,
    index: dict,
    manifest: dict,
) -> Tuple[Optional[dict], str]:
    """汉书合传：标准机械 → 别名重试 → 卷级覆盖。"""
    if not str(work).startswith("02汉书"):
        return None, "非汉书"
    if not manifest or not uses_mechanical_blocks(manifest):
        return None, "非机械划块模式"
    vol = vol.zfill(3)
    total = int(index.get("total") or 0)
    para_text = _paragraph_text_map(index)

    try:
        draft = build_mechanical_blocks(manifest, total_paragraphs=total, para_text=para_text)
        return draft, "标准机械划块"
    except ValueError as exc:
        first_err = str(exc)

    draft = _try_hezhuan_with_aliases(manifest, total, para_text)
    if draft:
        return draft, "别名重试机械划块"

    override_manifest = _manifest_from_override(vol)
    if override_manifest:
        draft = _blocks_from_override(vol, total, para_text)
        if draft:
            return draft, f"卷级覆盖划块({vol})"

    return None, first_err


def ensure_prince_zongqi(names: List[str]) -> List[str]:
    """补录同姓藩王到宗戚.json（两路径同步）。"""
    fixes: List[str] = []
    zq_paths = [
        ANNOTATE_DIR / "reference" / "宗戚.json",
        orch_paths()["data"] / "01历史坐标数据" / "宗戚.json",
    ]
    for path in zq_paths:
        if not path.is_file():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows: List[dict] = raw if isinstance(raw, list) else list(raw.get("宗戚") or [])
        existing = {(e.get("宗戚名称") or "").strip() for e in rows}
        changed = False
        for name in names:
            if name in existing or name not in _PRINCE_ZONGQI_STUBS:
                continue
            stub = dict(_PRINCE_ZONGQI_STUBS[name])
            stub.setdefault("政权ID", "ZQ_HX_XIHAN_XIHAN")
            stub.setdefault("朝代", "西汉")
            stub.setdefault("朝代ID", "CD_HX_XIHAN")
            stub.setdefault("文明", "华夏")
            stub.setdefault("文明ID", "HX")
            stub.setdefault("标签", "hanshu_hezhuan_autofix")
            rows.append(stub)
            existing.add(name)
            changed = True
            fixes.append(f"宗戚表+{name}")
        if changed:
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixes


def ensure_prince_emperors(names: List[str]) -> List[str]:
    """兼容旧名：同姓藩王改补录宗戚表。"""
    return ensure_prince_zongqi(names)


def apply_cobio_patches(work: str, vol: str, skeleton: dict) -> Tuple[bool, str]:
    """同段双归属：补 segment_attribution owners 与缺失 entry。"""
    vol = vol.zfill(3)
    patches = CO_BIO_PARAGRAPH_PATCHES.get(vol)
    entry_patches = CO_BIO_ENTRY_PARAGRAPH_PATCHES.get(vol) or {}
    if not patches and not entry_patches:
        return False, ""
    attr = list(skeleton.get("segment_attribution") or [])
    entries = list(skeleton.get("entries") or [])
    entry_names = {(e.get("史略名称") or "").strip() for e in entries}
    entry_categories = {
        (e.get("史略名称") or "").strip(): (e.get("史略分类") or "").strip()
        for e in entries
        if (e.get("史略名称") or "").strip()
    }
    fixes: List[str] = []

    def _owner_category(name: str, default: str = "文臣") -> str:
        if name in entry_categories:
            return entry_categories[name]
        for p in HANSHU_HEZHUAN_BLOCK_OVERRIDES.get(vol, ()):
            if p[0] == name:
                return p[1]
        return default

    def _refresh_entry_anchor_fields(entry: dict) -> None:
        paragraphs = entry.get("paragraphs") or []
        parts: List[str] = []
        for row in paragraphs:
            pf = row.get("paragraph_from")
            pt = row.get("paragraph_to")
            if not isinstance(pf, int) or not isinstance(pt, int):
                continue
            parts.append(f"[P{pf}]" if pf == pt else f"[P{pf}-P{pt}]")
        anchor = ",".join(parts)
        if anchor:
            entry["六级段落锚点"] = anchor
            volume = (
                (paragraphs[0].get("volume") if paragraphs else "")
                or skeleton.get("volume")
                or ""
            )
            plain = anchor.replace("[", "").replace("]", "")
            entry["原文出处"] = f"{volume}·{plain}" if volume else plain

    for patch in patches:
        pid = int(patch["paragraph"])
        owners = list(patch.get("owners") or [])
        owner_objs = []
        for oname in owners:
            owner_objs.append({"name": oname, "category": _owner_category(oname)})
        row = next((r for r in attr if r.get("paragraph") == pid), None)
        changed = False
        if row is None:
            row = {"paragraph": pid, "owners": owner_objs}
            attr.append(row)
            changed = True
        elif row.get("owners") != owner_objs:
            row = {**row, "owners": owner_objs}
            attr = [
                {**r, "owners": owner_objs} if r.get("paragraph") == pid else r for r in attr
            ]
            changed = True
        if changed:
            fixes.append(f"P{pid}双归属{'/'.join(owners)}")

        ensure_name = (patch.get("ensure_entry") or "").strip()
        if ensure_name and ensure_name not in entry_names:
            cat = _owner_category(ensure_name)
            entries.append({"史略名称": ensure_name, "史略分类": cat, "史略简介": ensure_name})
            entry_names.add(ensure_name)
            entry_categories[ensure_name] = cat
            fixes.append(f"补条目{ensure_name}")

    for entry in entries:
        name = (entry.get("史略名称") or "").strip()
        ranges = entry_patches.get(name)
        if not ranges:
            continue
        volume = (
            (entry.get("paragraphs") or [{}])[0].get("volume")
            or skeleton.get("volume")
            or ""
        )
        new_paragraphs = [
            {
                "volume": volume,
                "paragraph_from": pf,
                "paragraph_to": pt,
            }
            for pf, pt in ranges
        ]
        if entry.get("paragraphs") != new_paragraphs:
            entry["paragraphs"] = new_paragraphs
            _refresh_entry_anchor_fields(entry)
            fixes.append(
                f"{name}段落→"
                + ",".join(f"P{pf}" if pf == pt else f"P{pf}-P{pt}" for pf, pt in ranges)
            )

    if not fixes:
        return False, ""
    skeleton["segment_attribution"] = sorted(attr, key=lambda r: int(r.get("paragraph") or 0))
    skeleton["entries"] = entries
    return True, "; ".join(fixes)


def try_repair_hanshu_hezhuan_step1(
    work: str, vol: str, index: dict, manifest: Optional[dict] = None,
) -> Tuple[bool, str]:
    """Step1b 机械划块失败时自动修复并写 blocks。"""
    from lib.protagonist_workflow import load_protagonists

    if not str(work).startswith("02汉书"):
        return False, "非汉书"
    vol = vol.zfill(3)
    manifest = manifest or load_protagonists(work, vol)
    if not manifest:
        return False, "无 protagonists"

    draft, msg = try_build_mechanical_blocks(work, vol, index, manifest)
    if not draft:
        return False, msg

    manifest_msg = ""
    if msg.startswith("卷级覆盖划块"):
        ok_manifest, manifest_msg = write_override_protagonists_manifest(work, vol)
        if not ok_manifest:
            return False, manifest_msg

    # 补宗戚表（仅宗戚类覆盖卷）
    prince_names = [
        p[0]
        for p in HANSHU_HEZHUAN_BLOCK_OVERRIDES.get(vol, ())
        if p[1] == "宗戚"
    ]
    emperor_fixes = ensure_prince_emperors(prince_names)

    bp = blocks_workflow.blocks_path(work, vol)
    bp.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok, blk_msg = blocks_workflow.blocks_valid(bp, index)
    if not ok:
        bp.unlink(missing_ok=True)
        return False, f"自动 blocks 校验未过: {blk_msg}"

    detail = msg
    if manifest_msg:
        detail += " · " + manifest_msg
    if emperor_fixes:
        detail += " · " + ",".join(emperor_fixes)
    return True, detail


def try_repair_hanshu_hezhuan_expand(
    work: str, vol: str, index: dict,
) -> Tuple[bool, str]:
    """展开后应用同段双归属等补丁。"""
    sk = gates.skeleton_path(work, vol)
    if sk is None or not sk.exists():
        return False, "无 skeleton"
    data = json.loads(sk.read_text(encoding="utf-8"))
    ok, msg = apply_cobio_patches(work, vol, data)
    if not ok:
        return False, msg or "无补丁"
    sk.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, msg
