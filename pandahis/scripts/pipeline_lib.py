#!/usr/bin/env python3
"""朝代史略流水线：进度计算、门禁校验、步骤编排 SSOT。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "openclaw-historiography"
DK_SCRIPTS = TOOLS / "historiography-dynasty-knowledge" / "scripts"
CW_SCRIPTS = TOOLS / "historiography-commentary-witness" / "scripts"
REL_SCRIPTS = TOOLS / "historiography-person-relations" / "scripts"
TRANSLATE_DIR = TOOLS / "historiography-translate"

sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(TRANSLATE_DIR))

from entry_source import infer_entry_source, SOURCE_SUPPLEMENT  # noqa: E402
from paths_config import histograph_paths  # noqa: E402

PERSON_TAG_EMPTY = "_人物标签留空"
PERSON_TAG_LOCK = "_人物标签人工锁定"
PERSON_CATEGORIES = frozenset({"君王", "诸侯", "宗戚", "文臣", "武将", "宦官", "庶众"})
# 朝代知识补全人物类（含蕃祚，与 dynasty_supplement 一致）
KNOWLEDGE_PERSON_CATEGORIES = ("君王", "诸侯", "宗戚", "宦官", "文臣", "武将", "蕃祚", "庶众")
KNOWLEDGE_NONPERSON_CATEGORIES = ("事略", "典制", "论著")
KNOWLEDGE_CATEGORIES = KNOWLEDGE_NONPERSON_CATEGORIES + KNOWLEDGE_PERSON_CATEGORIES
SERIAL_STEPS = ("S1", "S2", "S3", "S4", "S5", "S6")
PARALLEL_STEPS = ("P1", "P2")
KNOWLEDGE_STEPS = ("K1", "K2", "K3", "K4", "K5", "K6")
ALL_STEPS = SERIAL_STEPS + PARALLEL_STEPS + KNOWLEDGE_STEPS

STEP_LABELS = {
    "S1": "索引就绪",
    "S2": "详情就绪",
    "S3": "Enrichment",
    "S4": "线上索引",
    "S5": "线上详情",
    "S6": "串行 Gate",
    "P1": "评述+见证",
    "P2": "人物关系",
    "K1": "候选就绪",
    "K2": "人审批准",
    "K3": "fill索引",
    "K4": "compose详情",
    "K5": "merge全局",
    "K6": "线上同步",
}

STATUS_DONE = "done"
STATUS_RUNNING = "running"
STATUS_BLOCKED = "blocked"
STATUS_LOCKED = "locked"
STATUS_PENDING = "pending"


def person_tag_decided(entry: dict) -> bool:
    """有标签字符串，或已标记 intentional 留空 / 人工锁定，均视为 S3 完成。"""
    if str(entry.get("人物标签") or "").strip():
        return True
    auto = entry.get("_auto_filled") or {}
    return bool(auto.get(PERSON_TAG_EMPTY) or auto.get(PERSON_TAG_LOCK))


@dataclass
class DynastyConfig:
    name: str
    dynasty_id: str
    track: str  # supplement | extract | mixed
    sync_script: str | None = None
    cw_batch: str | None = None
    relations_batch: str | None = None
    peak_batch: str | None = None
    person_tag_batch: str | None = None


DYNASTY_CONFIGS: dict[str, DynastyConfig] = {
    "五帝": DynastyConfig("五帝", "CD_HX_WUDI", "supplement", cw_batch="batch_wudi.py"),
    "夏": DynastyConfig("夏", "CD_HX_XIA", "supplement", sync_script="sync_xia_dynasty_online.py", cw_batch="batch_xia.py"),
    "商": DynastyConfig("商", "CD_HX_SHANG", "supplement", cw_batch="batch_shang.py", relations_batch="batch_shang.py"),
    "西周": DynastyConfig("西周", "CD_HX_XIZHOU", "supplement", cw_batch="batch_xizhou.py", relations_batch="batch_xizhou.py"),
    "春秋": DynastyConfig("春秋", "CD_HX_CHUNQIU", "extract", cw_batch="batch_chunqiu.py", relations_batch="batch_chunqiu.py", peak_batch="batch_chunqiu_peak.py", person_tag_batch="batch_chunqiu_person_tag.py"),
    "战国": DynastyConfig("战国", "CD_HX_ZHANGUO", "mixed", sync_script="sync_zhanguo_dynasty_online.py", cw_batch="batch_zhanguo.py", relations_batch="batch_zhanguo_relations.py"),
    "秦": DynastyConfig("秦", "CD_HX_QIN", "supplement", cw_batch=None, relations_batch=None),
}

DEFAULT_DYNASTIES = tuple(DYNASTY_CONFIGS.keys())
PIPELINE_DIR = ROOT / "data" / "05工作流中间产物" / "pipeline"
KNOWLEDGE_WORK_DIR = ROOT / "data" / "05工作流中间产物" / "朝代知识补全"
KNOWLEDGE_ENTRIES_DIR = ROOT / "data" / "06朝代知识补全" / "索引条目"
PROGRESS_JSON = PIPELINE_DIR / "progress.json"
PROGRESS_MD = PIPELINE_DIR / "progress.md"


def dynasty_slug(name: str) -> str:
    return name.replace(" ", "_")


def knowledge_paths(dynasty: str) -> dict[str, Path]:
    slug = dynasty_slug(dynasty)
    return {
        "candidates": KNOWLEDGE_WORK_DIR / f"{slug}_候选清单.json",
        "approval": KNOWLEDGE_WORK_DIR / f"{slug}_人审批准.json",
        "entries_sdl": KNOWLEDGE_ENTRIES_DIR / f"{slug}_事略典制论著.json",
        "entries_renwu": KNOWLEDGE_ENTRIES_DIR / f"{slug}_人物.json",
    }


def _load_env() -> None:
    env = TOOLS / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def load_global_entries(index_path: Path | None = None) -> list[dict]:
    path = index_path or histograph_paths()["global_index"]
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return list(data.get("entries") or [])


def dynasty_entries(dynasty: str, entries: list[dict] | None = None) -> list[dict]:
    rows = entries if entries is not None else load_global_entries()
    return [e for e in rows if str(e.get("二级朝代坐标", "")).strip() == dynasty]


def supplement_ids_from_06() -> set[str]:
    ids: set[str] = set()
    idx_dir = ROOT / "data" / "06朝代知识补全" / "索引条目"
    for fp in idx_dir.glob("*.json"):
        if fp.name.startswith("旧"):
            continue
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            if str(e.get("史略来源", "")).strip() == SOURCE_SUPPLEMENT:
                eid = str(e.get("史略ID", "")).strip()
                if eid:
                    ids.add(eid)
    return ids


def ids06_all_for_dynasty(dynasty: str) -> set[str]:
    ids: set[str] = set()
    idx_dir = ROOT / "data" / "06朝代知识补全" / "索引条目"
    for fp in idx_dir.glob(f"{dynasty}_*.json"):
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            eid = str(e.get("史略ID", "")).strip()
            if eid:
                ids.add(eid)
    return ids


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


KNOWLEDGE_SKIP_AUDIT = frozenset({"rejected", "excluded", "已剔除", "已排除"})


def _candidate_row_active(row: dict[str, Any]) -> bool:
    status = str(row.get("审核状态", "")).strip().lower()
    if status in KNOWLEDGE_SKIP_AUDIT:
        return False
    if row.get("补全来源") == "name_rejected":
        return False
    return True


def knowledge_candidate_counts(dynasty: str) -> dict[str, int]:
    """候选清单各分类条数（跳过 rejected/excluded）。"""
    doc = _load_json(knowledge_paths(dynasty)["candidates"])
    if not doc:
        return {}
    out: dict[str, int] = {}
    for cat in KNOWLEDGE_CATEGORIES:
        rows = doc.get("candidates", {}).get(cat) or []
        active = [r for r in rows if isinstance(r, dict) and _candidate_row_active(r)]
        if active:
            out[cat] = len(active)
    return out


def knowledge_approved_names(dynasty: str) -> dict[str, set[str]] | None:
    """人审批准名称；None 表示尚无批准文件。"""
    doc = _load_json(knowledge_paths(dynasty)["approval"])
    if not doc:
        return None
    if str(doc.get("phase", "")).strip() != "candidates":
        return None
    items = doc.get("items") or {}
    out: dict[str, set[str]] = {}
    for cat in KNOWLEDGE_CATEGORIES:
        names = items.get(cat) or []
        if isinstance(names, list) and names:
            out[cat] = {str(n).strip() for n in names if str(n).strip()}
    return out or {}


def knowledge_filled_entries(dynasty: str) -> list[dict[str, Any]]:
    """06 索引条目中已 fill 的全部条目。"""
    paths = knowledge_paths(dynasty)
    rows: list[dict[str, Any]] = []
    for key in ("entries_sdl", "entries_renwu"):
        doc = _load_json(paths[key])
        if doc:
            rows.extend(doc.get("entries") or [])
    return rows


def knowledge_expected_total(dynasty: str) -> tuple[int, dict[str, int]]:
    """应补全条数：以候选清单为 SSOT（非增量批准子集）。"""
    by_cat = knowledge_candidate_counts(dynasty)
    return sum(by_cat.values()), by_cat


def knowledge_candidate_name_sets(dynasty: str) -> dict[str, set[str]]:
    doc = _load_json(knowledge_paths(dynasty)["candidates"])
    out: dict[str, set[str]] = {}
    if not doc:
        return out
    for cat in KNOWLEDGE_CATEGORIES:
        names = {
            str(r.get("名称", "")).strip()
            for r in (doc.get("candidates", {}).get(cat) or [])
            if isinstance(r, dict)
            and _candidate_row_active(r)
            and str(r.get("名称", "")).strip()
        }
        if names:
            out[cat] = names
    return out


def knowledge_presence_index(
    dynasty: str,
    global_rows: list[dict[str, Any]],
    filled_06: list[dict[str, Any]],
) -> set[tuple[str, str]]:
    """候选名在全局索引或 06 中已存在的 (分类, 名称) 集合。"""
    present: set[tuple[str, str]] = set()
    for e in global_rows:
        cat = str(e.get("史略分类", "")).strip()
        name = str(e.get("史略名称", "")).strip()
        if cat and name:
            present.add((cat, name))
    for e in filled_06:
        cat = str(e.get("史略分类", "")).strip()
        name = str(e.get("史略名称", "")).strip()
        if cat and name:
            present.add((cat, name))
    return present


def _gid_from_path(p: Path) -> str:
    parts = p.stem.split("_")
    if len(parts) >= 2 and parts[0] == "GLBL":
        return f"{parts[0]}_{parts[1]}"
    return ""


class PipelineAuditor:
    """扫描本地 + MySQL，计算各步覆盖率。"""

    def __init__(self) -> None:
        _load_env()
        paths = histograph_paths()
        self.paths = paths
        self.trans_dir = paths["translate_output"]
        self.detail06_dir = paths["dynasty_knowledge_details"]
        self.comm_dir = paths["commentary"]
        self.wit_dir = paths["witness"]
        self.rel_dir = paths["person_relations"]
        self.global_entries = load_global_entries()
        self.global_by_id = {e["史略ID"]: e for e in self.global_entries}
        self.supp_ids = supplement_ids_from_06()
        self._mysql: dict[str, dict] | None = None

    def _cw_status(self, eid: str, kind: str) -> str | None:
        d, sfx = (self.comm_dir, "_评述") if kind == "c" else (self.wit_dir, "_见证")
        fps = list(d.glob(f"{eid}_*{sfx}.json"))
        if not fps:
            return None
        return json.loads(fps[0].read_text(encoding="utf-8")).get("status")

    def _has_detail_local(self, e: dict) -> bool:
        eid = e["史略ID"]
        for d in (self.detail06_dir, self.trans_dir):
            fp = next(d.glob(f"{eid}_*.json"), None)
            if fp and fp.name.endswith("_评述.json"):
                continue
            if fp:
                doc = json.loads(fp.read_text(encoding="utf-8"))
                if str(doc.get("翻译详情", "")).strip():
                    return True
        return False

    def mysql_rows(self, dynasties: tuple[str, ...] | None = None) -> dict[str, dict]:
        if self._mysql is not None:
            return self._mysql
        dynasties = dynasties or DEFAULT_DYNASTIES
        import pymysql

        conn = pymysql.connect(
            host=os.environ.get("MYSQL_HOST", "49.235.165.220"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=os.environ.get("MYSQL_USER", "histomap_admin"),
            password=os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
            database=os.environ.get("MYSQL_DB", "histomap"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )
        out: dict[str, dict] = {}
        with conn.cursor() as c:
            c.execute(
                """
                SELECT b.id, b.dynasty_name, b.entry_source, b.status,
                       b.peak_year, b.priority_code, b.person_tag,
                       (COALESCE(NULLIF(TRIM(b.detail_md),''), NULLIF(TRIM(d.translate_detail),'')) IS NOT NULL) AS has_detail,
                       (SELECT COUNT(*) FROM box_critique c WHERE c.box_id=b.id) AS crit,
                       (SELECT COUNT(*) FROM box_relic r WHERE r.box_id=b.id) AS relic,
                       (SELECT COUNT(*) FROM box_graph_edge g WHERE g.box_id=b.id) AS edges
                FROM historical_box b
                LEFT JOIN historical_box_detail d ON d.box_id=b.id
                WHERE b.dynasty_name IN %s
                """,
                (dynasties,),
            )
            for row in c.fetchall():
                out[row["id"]] = row
        conn.close()
        self._mysql = out
        return out

    def knowledge_metrics(self, dynasty: str) -> dict[str, Any]:
        """朝代知识补全轨道 K1–K6（与 extract 线独立）。"""
        expected_total, expected_by_cat = knowledge_expected_total(dynasty)
        if expected_total == 0:
            na = {"status": STATUS_DONE, "count": "n/a", "blockers": []}
            return {
                "active": False,
                "expected_total": 0,
                "expected_by_cat": {},
                "filled_total": 0,
                "detail_total": 0,
                "merged_total": 0,
                "online_total": 0,
                "K1": na,
                "K2": na,
                "K3": na,
                "K4": na,
                "K5": na,
                "K6": na,
                "current_k_step": None,
                "blockers": [],
            }

        cand_counts = knowledge_candidate_counts(dynasty)
        cand_total = sum(cand_counts.values())
        cand_names_by_cat = knowledge_candidate_name_sets(dynasty)
        global_rows = dynasty_entries(dynasty, self.global_entries)
        filled = knowledge_filled_entries(dynasty)
        present = knowledge_presence_index(dynasty, global_rows, filled)
        filled_by_cat: dict[str, int] = {}
        for cat, names in cand_names_by_cat.items():
            filled_by_cat[cat] = sum(1 for n in names if (cat, n) in present)
        filled_ok = sum(filled_by_cat.values())

        global_by_name = {
            (str(e.get("史略分类", "")).strip(), str(e.get("史略名称", "")).strip()): e
            for e in global_rows
        }
        merged_entries = [
            global_by_name[key]
            for key in present
            if key in global_by_name and key[0] in cand_names_by_cat and key[1] in cand_names_by_cat.get(key[0], set())
        ]

        # K1 候选
        k1_blockers: list[str] = []
        if cand_total < expected_total:
            k1_blockers.append(f"候选清单不完整 {cand_total}/{expected_total}")
        k1 = {
            "status": STATUS_DONE if not k1_blockers else STATUS_BLOCKED,
            "count": f"{cand_total}/{expected_total}",
            "blockers": k1_blockers,
        }

        # K2 批准（已全部入库的可豁免；否则须有人审批准文件）
        approval_path = knowledge_paths(dynasty)["approval"]
        approved = knowledge_approved_names(dynasty)
        k2_blockers: list[str] = []
        if filled_ok < expected_total:
            if not approval_path.is_file():
                k2_blockers.append(f"缺少 {approval_path.name}")
            elif approved is None:
                k2_blockers.append("批准文件 phase 须为 candidates")
            else:
                ap_doc = _load_json(approval_path) or {}
                if not ap_doc.get("approved_at"):
                    k2_blockers.append("approved_at 未填写")
        k2 = {
            "status": STATUS_DONE if not k2_blockers else STATUS_BLOCKED,
            "count": f"{'yes' if not k2_blockers else 'no'}",
            "blockers": k2_blockers,
        }

        # K3 fill
        k3_missing: list[str] = []
        for cat, names in cand_names_by_cat.items():
            miss = len(names) - filled_by_cat.get(cat, 0)
            if miss:
                k3_missing.append(f"{cat} 缺 {miss}")
        k3 = {
            "status": STATUS_DONE if filled_ok >= expected_total else STATUS_BLOCKED,
            "count": f"{filled_ok}/{expected_total}",
            "blockers": k3_missing if filled_ok < expected_total else [],
        }

        # K4 compose — 已存在条目（全局或 06）须有本地详情
        entries_for_detail = merged_entries if merged_entries else [
            e for e in filled if (str(e.get("史略分类")), str(e.get("史略名称"))) in present
        ]
        detail_ok = sum(1 for e in entries_for_detail if self._has_detail_local(e))
        k4_blockers: list[str] = []
        if filled_ok < expected_total:
            k4_blockers.append(f"须先完成 K3（{filled_ok}/{expected_total}）")
        elif detail_ok < filled_ok:
            k4_blockers.append(f"缺 compose 详情 {filled_ok - detail_ok}/{filled_ok}")
        k4 = {
            "status": STATUS_DONE if not k4_blockers else STATUS_BLOCKED,
            "count": f"{detail_ok}/{expected_total}",
            "blockers": k4_blockers,
        }

        # K5 merge — 候选名均须出现在全局索引
        merged = filled_ok if len(merged_entries) >= filled_ok else len(merged_entries)
        k5_blockers: list[str] = []
        if merged < expected_total:
            k5_blockers.append(f"全局索引缺 {expected_total - merged} 条候选")
        k5 = {
            "status": STATUS_DONE if not k5_blockers else STATUS_BLOCKED,
            "count": f"{merged}/{expected_total}",
            "blockers": k5_blockers,
        }

        # K6 线上
        mysql = self.mysql_rows()
        online_idx = sum(1 for e in merged_entries if e["史略ID"] in mysql)
        online_detail = sum(1 for e in merged_entries if mysql.get(e["史略ID"], {}).get("has_detail"))
        k6_blockers: list[str] = []
        if merged < expected_total:
            k6_blockers.append(f"须先完成 K5 merge（{merged}/{expected_total}）")
        else:
            if online_idx < expected_total:
                k6_blockers.append(f"MySQL 缺索引 {expected_total - online_idx}/{expected_total}")
            if online_detail < expected_total:
                k6_blockers.append(f"MySQL 缺详情 {expected_total - online_detail}/{expected_total}")
        k6 = {
            "status": STATUS_DONE if not k6_blockers else STATUS_BLOCKED,
            "count": f"idx {online_idx}/{expected_total} detail {online_detail}/{expected_total}",
            "blockers": k6_blockers,
        }

        steps = {"K1": k1, "K2": k2, "K3": k3, "K4": k4, "K5": k5, "K6": k6}
        current_k = next((s for s in KNOWLEDGE_STEPS if steps[s]["status"] != STATUS_DONE), None)
        blockers = [b for s in KNOWLEDGE_STEPS for b in steps[s].get("blockers", [])]

        return {
            "active": True,
            "expected_total": expected_total,
            "expected_by_cat": expected_by_cat,
            "filled_total": filled_ok,
            "detail_total": detail_ok,
            "merged_total": merged,
            "online_total": online_detail,
            **steps,
            "current_k_step": current_k,
            "blockers": blockers,
        }

    def metrics(self, dynasty: str) -> dict[str, Any]:
        cfg = DYNASTY_CONFIGS[dynasty]
        rows = dynasty_entries(dynasty, self.global_entries)
        n = len(rows)
        persons = [e for e in rows if e.get("史略分类") in PERSON_CATEGORIES]
        mysql = self.mysql_rows()
        rel_names = {p.name.replace("关系表.json", "") for p in self.rel_dir.glob("*关系表.json")}

        ids06 = ids06_all_for_dynasty(dynasty)
        supp_in_global = [e for e in rows if infer_entry_source(e) == SOURCE_SUPPLEMENT]
        unm_merged = sorted(ids06 - set(self.global_by_id))

        if cfg.track == "extract":
            s1_ok = n
            s1_blockers: list[str] = []
        elif not unm_merged:
            s1_ok = n
            s1_blockers = []
        else:
            s1_ok = n
            s1_blockers = [f"06 未 merge {len(unm_merged)} 条: {', '.join(unm_merged[:3])}{'…' if len(unm_merged) > 3 else ''}"]

        # S2
        s2_ok = sum(1 for e in rows if self._has_detail_local(e))
        s2_blockers = [] if s2_ok == n else [f"缺本地详情 {n - s2_ok} 条"]

        expected_n = n + len(unm_merged) if unm_merged and cfg.track != "extract" else n

        # S3 — 峰值 + 优先级 + 人物标签（人物类）全部满足才算 done
        s3_peak = sum(1 for e in rows if mysql.get(e["史略ID"], {}).get("peak_year") is not None or e.get("峰值年") is not None)
        s3_pri = sum(1 for e in rows if mysql.get(e["史略ID"], {}).get("priority_code") or e.get("优先级"))
        s3_tag = sum(1 for e in persons if person_tag_decided(e))
        s3_tag_empty = sum(1 for e in persons if (e.get("_auto_filled") or {}).get(PERSON_TAG_EMPTY))
        s3_blockers = []
        if s3_peak < n:
            s3_blockers.append(f"缺峰值年 {n - s3_peak} 条")
        if s3_pri < n:
            s3_blockers.append(f"缺优先级 {n - s3_pri} 条")
        if persons and s3_tag < len(persons):
            s3_blockers.append(f"缺人物标签 {len(persons) - s3_tag}/{len(persons)}")
        s3_done = s3_peak >= n and s3_pri >= n and (not persons or s3_tag >= len(persons))

        # S4
        s4_ok = sum(1 for e in rows if e["史略ID"] in mysql)
        s4_blockers = [] if s4_ok == n else [f"MySQL 缺索引 {n - s4_ok} 条"]

        # S5
        s5_ok = sum(1 for e in rows if mysql.get(e["史略ID"], {}).get("has_detail"))
        s5_blockers = [] if s5_ok == n else [f"MySQL 缺详情 {n - s5_ok} 条"]

        # P1 local + mysql sync for done entries
        p1_local = sum(1 for e in rows if self._cw_status(e["史略ID"], "c") in ("done", "已处理·无可用") and self._cw_status(e["史略ID"], "w") in ("done", "已处理·无可用"))
        p1_db = 0
        for e in rows:
            st_c = self._cw_status(e["史略ID"], "c")
            st_w = self._cw_status(e["史略ID"], "w")
            m = mysql.get(e["史略ID"], {})
            c_ok = st_c == "已处理·无可用" or (st_c == "done" and m.get("crit", 0) > 0)
            w_ok = st_w == "已处理·无可用" or (st_w == "done" and m.get("relic", 0) > 0)
            if c_ok and w_ok and st_c and st_w:
                p1_db += 1
        p1_blockers = []
        if p1_local < n:
            p1_blockers.append(f"本地评述/见证未完成 {n - p1_local} 条")
        if p1_db < n:
            p1_blockers.append(f"MySQL 评述/见证未同步 {n - p1_db} 条")

        # P2
        p2_local = sum(1 for e in persons if e.get("史略名称") in rel_names)
        p2_db = sum(1 for e in persons if e.get("史略名称") in rel_names and mysql.get(e["史略ID"], {}).get("edges", 0) > 0)
        p2_blockers = []
        if persons:
            if p2_local < len(persons):
                p2_blockers.append(f"本地缺关系 {len(persons) - p2_local}/{len(persons)}")
            rel_with_file = [e for e in persons if e.get("史略名称") in rel_names]
            gap_db = len(rel_with_file) - p2_db
            if gap_db > 0:
                p2_blockers.append(f"本地有关系但 DB 无边 {gap_db} 条")

        def step(count_ok: int, total: int, blockers: list[str]) -> dict:
            if blockers:
                return {"status": STATUS_BLOCKED, "count": f"{count_ok}/{total}", "blockers": blockers}
            if total == 0:
                return {"status": STATUS_DONE, "count": "0/0", "blockers": []}
            if count_ok >= total:
                return {"status": STATUS_DONE, "count": f"{count_ok}/{total}", "blockers": []}
            return {"status": STATUS_PENDING, "count": f"{count_ok}/{total}", "blockers": [f"未完成 {total - count_ok} 条"]}

        s1 = step(n if not unm_merged else n, expected_n if unm_merged else n, s1_blockers)
        s2 = step(s2_ok, expected_n if unm_merged else n, s2_blockers)
        s3 = {
            "status": STATUS_DONE if s3_done else STATUS_BLOCKED,
            "count": f"peak {s3_peak}/{n} tag {s3_tag}/{len(persons) or 0} (留空{s3_tag_empty})",
            "blockers": s3_blockers,
        }
        s4 = step(s4_ok, n, s4_blockers)
        s5 = step(s5_ok, n, s5_blockers)

        serial_done = all(x["status"] == STATUS_DONE for x in (s1, s2, s3, s4, s5))
        s6 = {
            "status": STATUS_DONE if serial_done else STATUS_BLOCKED,
            "count": "pass" if serial_done else "fail",
            "blockers": [] if serial_done else ["S1–S5 未全部完成"],
        }

        p1_status = STATUS_LOCKED
        if serial_done:
            p1_status = STATUS_DONE if p1_local >= n and p1_db >= n else STATUS_BLOCKED
        p1 = {"status": p1_status, "count": f"local {p1_local}/{n} db {p1_db}/{n}", "blockers": p1_blockers if p1_status != STATUS_DONE else []}

        p2_status = STATUS_LOCKED
        if serial_done:
            p2_status = STATUS_DONE if (not persons or (p2_local >= len(persons) and p2_db >= len(persons))) else STATUS_BLOCKED
        p2 = {"status": p2_status, "count": f"local {p2_local}/{len(persons)} db {p2_db}/{len(persons)}", "blockers": p2_blockers if p2_status != STATUS_DONE else []}

        knowledge = self.knowledge_metrics(dynasty)
        steps_map = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6, "P1": p1, "P2": p2}
        for k in KNOWLEDGE_STEPS:
            steps_map[k] = knowledge[k]

        extract_done = serial_done and p1["status"] == STATUS_DONE and p2["status"] == STATUS_DONE
        knowledge_done = (not knowledge["active"]) or all(
            knowledge[k]["status"] == STATUS_DONE for k in KNOWLEDGE_STEPS
        )

        current = next((s for s in SERIAL_STEPS if steps_map[s]["status"] != STATUS_DONE), None)
        if current is None and p1["status"] != STATUS_DONE:
            current = "P1"
        elif current is None and p2["status"] not in (STATUS_DONE, STATUS_LOCKED):
            current = "P2"
        elif current is None and extract_done and knowledge["active"] and not knowledge_done:
            current = knowledge["current_k_step"] or "K3"
        elif current is None and extract_done and knowledge_done:
            current = "F1"
        elif current is None and extract_done and not knowledge["active"]:
            current = "F1"

        all_blockers = [b for s in ALL_STEPS for b in steps_map[s].get("blockers", [])]
        if knowledge["active"]:
            all_blockers.extend(knowledge.get("blockers") or [])

        return {
            "dynasty": dynasty,
            "track": cfg.track,
            "total": expected_n if unm_merged else n,
            "global_count": n,
            "persons": len(persons),
            "supplement_count": len(supp_in_global),
            "unmerged_06": unm_merged,
            "knowledge_expected": knowledge["expected_total"],
            "knowledge_filled": knowledge["filled_total"],
            "knowledge_active": knowledge["active"],
            "S1": s1,
            "S2": s2,
            "S3": s3,
            "S4": s4,
            "S5": s5,
            "S6": s6,
            "P1": p1,
            "P2": p2,
            "K1": knowledge["K1"],
            "K2": knowledge["K2"],
            "K3": knowledge["K3"],
            "K4": knowledge["K4"],
            "K5": knowledge["K5"],
            "K6": knowledge["K6"],
            "extract_complete": extract_done,
            "knowledge_complete": knowledge_done,
            "current_step": current or ("F1" if extract_done and knowledge_done else "S1"),
            "current_k_step": knowledge.get("current_k_step"),
            "blockers": all_blockers,
        }


def compute_all_progress(dynasties: tuple[str, ...] | None = None) -> dict[str, Any]:
    dynasties = dynasties or DEFAULT_DYNASTIES
    auditor = PipelineAuditor()
    report = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dynasties": {d: auditor.metrics(d) for d in dynasties},
    }
    return report


def save_progress(report: dict[str, Any]) -> Path:
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROGRESS_MD.write_text(render_progress_md(report), encoding="utf-8")
    return PROGRESS_JSON


def render_progress_md(report: dict[str, Any]) -> str:
    lines = [
        "# 朝代史略流水线进度",
        "",
        f"更新时间（UTC）：{report.get('updated_at', '')}",
        "",
        "> **F1** = extract 线（S1–P2）与知识补全线（K1–K6，若有候选）均完成。",
        "",
        "| 朝代 | extract条 | S6 | P1 | P2 | 知识补全 | K3fill | K5merge | 当前步 |",
        "|------|-----------|-----|-----|-----|----------|--------|---------|--------|",
    ]
    for name, m in report.get("dynasties", {}).items():
        def icon(status: str) -> str:
            return {"done": "✅", "blocked": "❌", "locked": "🔒", "running": "⏳", "pending": "⬜"}.get(status, "?")

        def cell(step: str) -> str:
            s = m[step]
            return f"{icon(s['status'])} {s['count']}"

        k_label = "—"
        if m.get("knowledge_active"):
            k_label = f"{m.get('knowledge_filled', 0)}/{m.get('knowledge_expected', 0)}"
        ext = m.get("global_count", m.get("total", 0))
        lines.append(
            f"| {name} | {ext} | {cell('S6')} | {cell('P1')} | {cell('P2')} | {k_label} | {cell('K3')} | {cell('K5')} | **{m.get('current_step')}** |"
        )
    lines.append("")
    lines.append("## 阻塞项")
    lines.append("")
    for name, m in report.get("dynasties", {}).items():
        blockers = m.get("blockers") or []
        if blockers:
            lines.append(f"### {name}（{m.get('current_step')}）")
            for b in blockers:
                lines.append(f"- {b}")
            lines.append("")
    return "\n".join(lines)


def gate_check(dynasty: str, step: str, report: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    if step not in ALL_STEPS:
        return False, [f"未知步骤 {step}"]
    if report is None:
        report = compute_all_progress((dynasty,))
    m = report["dynasties"][dynasty]
    if step in KNOWLEDGE_STEPS:
        ok = m[step]["status"] == STATUS_DONE
        return ok, [] if ok else m[step].get("blockers", [])
    if step in PARALLEL_STEPS and m["S6"]["status"] != STATUS_DONE:
        return False, ["S6 串行 Gate 未通过，不可运行并行步骤"]
    if step == "S6":
        ok = m["S6"]["status"] == STATUS_DONE
        return ok, m["S6"].get("blockers", [])
    idx = ALL_STEPS.index(step)
    if idx > 0:
        for prev in ALL_STEPS[:idx]:
            if prev in PARALLEL_STEPS:
                continue
            if prev == "S6":
                continue
            if m[prev]["status"] != STATUS_DONE:
                return False, [f"前置步骤 {prev}({STEP_LABELS[prev]}) 未完成"]
    ok = m[step]["status"] == STATUS_DONE
    return ok, [] if ok else m[step].get("blockers", [])


def next_runnable_step(dynasty: str, report: dict[str, Any] | None = None) -> str | None:
    if report is None:
        report = compute_all_progress((dynasty,))
    m = report["dynasties"][dynasty]
    for step in ("S1", "S2", "S3", "S4", "S5"):
        if m[step]["status"] != STATUS_DONE:
            return step
    if m["S6"]["status"] != STATUS_DONE:
        return "S6"
    return None


def _run_cmd(cmd: list[str], *, log_path: Path | None = None, background: bool = False) -> int:
    print(f"$ {' '.join(cmd)}")
    if background and log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n--- {datetime.now().isoformat()} ---\n")
            log.write(f"$ {' '.join(cmd)}\n")
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT))
        print(f"后台 PID={proc.pid}  log={log_path}")
        return 0
    proc = subprocess.run(cmd, cwd=str(ROOT))
    return proc.returncode


def sync_dynasty_details(dynasty: str, *, dry_run: bool = False) -> int:
    sys.path.insert(0, str(TRANSLATE_DIR))
    from lib.remote_sync import sync_translate_detail  # noqa: WPS433

    rows = dynasty_entries(dynasty)
    paths = histograph_paths()
    ok_n = 0
    for e in rows:
        eid = e["史略ID"]
        text = ""
        detail_source = "compose"
        for d, src in (
            (paths["translate_output_v2"], "translate"),
            (paths["dynasty_knowledge_details"], "compose"),
        ):
            fp = next(d.glob(f"{eid}_*.json"), None)
            if fp and not fp.name.endswith("_评述.json"):
                text = str(json.loads(fp.read_text(encoding="utf-8")).get("翻译详情", "")).strip()
                if text:
                    detail_source = src
                    break
        if not text:
            print(f"⚠️ 跳过无详情: {eid} {e.get('史略名称')}")
            continue
        if dry_run:
            ok_n += 1
            continue
        ok, msg = sync_translate_detail(
            eid, text, dry_run=False, detail_source=detail_source
        )
        if not ok:
            print(f"❌ {eid}: {msg}")
            return 1
        ok_n += 1
    print(f"✅ 详情同步 {ok_n}/{len(rows)}（来源: 11 + 06）")
    return 0


def run_step(
    dynasty: str,
    step: str,
    *,
    dry_run: bool = False,
    background: bool = False,
    force: bool = False,
) -> int:
    cfg = DYNASTY_CONFIGS.get(dynasty)
    if not cfg:
        print(f"未知朝代: {dynasty}")
        return 1

    report = compute_all_progress((dynasty,))
    if not force:
        if report["dynasties"][dynasty][step]["status"] == STATUS_DONE and step not in ("S6",):
            print(f"✅ {dynasty} {step} 已完成，跳过")
            return 0
        for prev in ALL_STEPS[: ALL_STEPS.index(step)]:
            if prev in PARALLEL_STEPS or prev == "S6":
                continue
            if report["dynasties"][dynasty][prev]["status"] != STATUS_DONE:
                print(f"❌ 前置步骤 {prev}({STEP_LABELS[prev]}) 未完成: {report['dynasties'][dynasty][prev].get('blockers', [])}")
                return 1
        if step in PARALLEL_STEPS and report["dynasties"][dynasty]["S6"]["status"] != STATUS_DONE:
            print(f"❌ S6 串行 Gate 未通过，不可运行 {step}")
            return 1

    log_dir = PIPELINE_DIR / "logs"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{dynasty}_{step}_{ts}.log"
    py = sys.executable

    if step == "S1":
        if cfg.sync_script:
            script = ROOT / "scripts" / cfg.sync_script
            if not script.is_file():
                print(f"❌ 缺少脚本 {script}")
                return 1
            return _run_cmd([py, str(script)], log_path=log_path, background=background)
        unm = report["dynasties"][dynasty].get("unmerged_06") or []
        if unm:
            print(f"❌ {dynasty} 有 {len(unm)} 条 06 索引未 merge，需先 append（暂无通用 sync 脚本）")
            print(f"   例: {', '.join(unm[:5])}")
            return 1
        print(f"✅ {dynasty} S1 索引已就绪")
        return 0

    if step == "S2":
        if cfg.track in ("supplement", "mixed"):
            cmd = [py, str(DK_SCRIPTS / "dynasty_supplement.py"), "--dynasty", dynasty, "--step", "compose-pending", "--background"]
            return _run_cmd(cmd, log_path=log_path, background=True)
        print(f"ℹ️ {dynasty} 为提取线，S2 依赖 translate 批跑；请确认 04 详情齐全")
        return 0 if report["dynasties"][dynasty]["S2"]["status"] == STATUS_DONE else 1

    if step == "S3":
        if cfg.peak_batch and report["dynasties"][dynasty]["S3"].get("blockers") and any("峰值" in b for b in report["dynasties"][dynasty]["S3"].get("blockers", [])):
            cmd = [py, str(ROOT / "scripts" / cfg.peak_batch)]
            return _run_cmd(cmd, log_path=log_path, background=background)
        if cfg.person_tag_batch:
            cmd = [py, str(ROOT / "scripts" / cfg.person_tag_batch)]
            return _run_cmd(cmd, log_path=log_path, background=background)
        cmd = [py, str(DK_SCRIPTS / "dynasty_supplement.py"), "--dynasty", dynasty, "--step", "enrich-all", "--background"]
        return _run_cmd(cmd, log_path=log_path, background=True)

    if step == "S4":
        if dry_run:
            print("[dry-run] import_box_index_json upsert")
            return 0
        cmd = [py, str(ROOT / "scripts" / "import_box_index_json.py"), "--json", str(histograph_paths()["global_index_online"])]
        return _run_cmd(cmd, log_path=log_path, background=background)

    if step == "S5":
        if cfg.sync_script and cfg.track != "extract":
            script = ROOT / "scripts" / cfg.sync_script
            return _run_cmd([py, str(script)], log_path=log_path, background=background)
        return sync_dynasty_details(dynasty, dry_run=dry_run)

    if step == "S6":
        ok, blockers = gate_check(dynasty, "S6", report)
        if ok:
            print(f"✅ {dynasty} 串行 Gate 通过")
            return 0
        print(f"❌ {dynasty} 串行 Gate 未通过:")
        for b in blockers:
            print(f"  - {b}")
        return 1

    if step == "P1":
        if not cfg.cw_batch:
            print(f"❌ {dynasty} 未配置 cw_batch 脚本")
            return 1
        batch = CW_SCRIPTS / cfg.cw_batch
        code = _run_cmd([py, str(batch)], log_path=log_path, background=background)
        if code != 0 or background:
            return code
        imp = [py, str(ROOT / "tools" / "openclaw-historiography" / "scripts" / "import_dynasty_components.py"), "--dynasties", dynasty, "--skip-relations"]
        return _run_cmd(imp, log_path=log_path)

    if step == "P2":
        if not cfg.relations_batch:
            print(f"ℹ️ {dynasty} 未配置 relations_batch，请手动跑 relations.py")
            return 0
        batch = REL_SCRIPTS / cfg.relations_batch
        code = _run_cmd([py, str(batch)], log_path=log_path, background=background)
        if code != 0 or background:
            return code
        imp = [py, str(ROOT / "tools" / "openclaw-historiography" / "scripts" / "import_dynasty_components.py"), "--dynasties", dynasty, "--skip-cw"]
        return _run_cmd(imp, log_path=log_path)

    return 1


def run_next(dynasty: str, **kwargs: Any) -> int:
    report = compute_all_progress((dynasty,))
    step = next_runnable_step(dynasty, report)
    if step is None:
        m = report["dynasties"][dynasty]
        if m["S6"]["status"] == STATUS_DONE:
            pending = [s for s in PARALLEL_STEPS if m[s]["status"] != STATUS_DONE]
            if not pending:
                print(f"✅ {dynasty} 全部步骤已完成")
                return 0
            print(f"ℹ️ {dynasty} 串行已完成，请运行: --parallel 或 --step {' / '.join(pending)}")
            return 0
        step = "S6"
    print(f"→ {dynasty} 下一步: {step} ({STEP_LABELS.get(step, step)})")
    return run_step(dynasty, step, **kwargs)


def run_through(dynasty: str, target: str, **kwargs: Any) -> int:
    if target not in SERIAL_STEPS:
        print(f"--through 仅支持 {SERIAL_STEPS}")
        return 1
    for step in SERIAL_STEPS:
        code = run_step(dynasty, step, **kwargs)
        if code != 0:
            return code
        if step == target:
            break
        report = compute_all_progress((dynasty,))
        if report["dynasties"][dynasty][step]["status"] == STATUS_DONE:
            continue
    save_progress(compute_all_progress())
    return 0


def run_parallel(dynasty: str, **kwargs: Any) -> int:
    report = compute_all_progress((dynasty,))
    ok, blockers = gate_check(dynasty, "P1", report)
    if report["dynasties"][dynasty]["S6"]["status"] != STATUS_DONE:
        print(f"❌ S6 未通过，不可并行: {blockers}")
        return 1
    codes = []
    for step in PARALLEL_STEPS:
        m = report["dynasties"][dynasty][step]
        if m["status"] == STATUS_DONE:
            print(f"⏭ {step} 已完成")
            continue
        codes.append(run_step(dynasty, step, background=True, **kwargs))
    save_progress(compute_all_progress())
    return max(codes) if codes else 0
