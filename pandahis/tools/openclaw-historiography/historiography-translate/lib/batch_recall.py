"""分批成稿：recalled 只保留本批母本元数据（原文以 plan M 清单为准）。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from lib.m_anchor import mother_para_ids_for_batch


def batch_recalled_meta(recalled: Dict[str, Any], batch_items: List[Dict[str, Any]]) -> str:
    """
    分批成稿不注入全书 paragraphs / 补充 block。
    母本原文 authoritative 来源 = plan 母本逐句清单（M + 原文摘句）。
    """
    para_ids = sorted(mother_para_ids_for_batch(batch_items))
    sid0 = batch_items[0].get("编号") if batch_items else "?"
    sid1 = batch_items[-1].get("编号") if batch_items else "?"
    supplement = sum(
        1 for b in (recalled.get("blocks") or []) if b.get("role") == "补充"
    )
    payload: Dict[str, Any] = {
        "史略ID": recalled.get("史略ID"),
        "史略名称": recalled.get("史略名称"),
        "母本著作": recalled.get("母本著作"),
        "本批M范围": f"{sid0}–{sid1}",
        "本批母本段落域": [f"P{pid}" for pid in para_ids],
        "说明": (
            "本批顺译仅以 plan「母本逐句清单」中各 M 的「原文摘句」为母本依据；"
            "禁止翻译清单外母本句。"
            + (
                "本条目含索引补充著作：成稿时主动写入他书材料（经母本去重门禁后），"
                "每条须《书名·卷篇》，挂母本句后回主线；母本已有详述的不重复补。"
                if supplement
                else "他书补充在成稿时主动检索写入，须《书名·卷篇》，挂母本句后回主线；母本已有详述的不重复补。"
            )
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
