#!/usr/bin/env python3
"""Step3 语义审计硬检：按卷解析审计 MD，校验六条声明与段落覆盖。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# 声明块 6 条（与 historiography-audit/reference/审计模板.md 一致）
DECLARATION_MARKERS = (
    "喊数",
    "段落覆盖",
    "原文引用",
    "密度",
    "人物归类",
    "合传主人公",
)

VOL_HEADER_RE = re.compile(
    r"^##\s*卷(?P<vol>\d{3})\s*(?:[：:]\s*(?P<name>[^\n]+))?\s*$",
    re.MULTILINE,
)

PARA_ROW_RE = re.compile(r"^\|\s*P(\d+)\s*\|", re.MULTILINE)
PARA_RANGE_BAD_RE = re.compile(r"\|\s*P\d+\s*[-–—]\s*P\d+\s*\|")

PASS_RE = re.compile(r"✅.*(?:修正后通过|通过)")
REJECT_RE = re.compile(r"❌\s*退回")


@dataclass
class VolumeAuditBlock:
    vol: str
    title: str
    text: str
    start: int
    end: int


def split_volume_blocks(audit_text: str) -> List[VolumeAuditBlock]:
    """按「## 卷NNN」切分审计 MD。"""
    matches = list(VOL_HEADER_RE.finditer(audit_text))
    if not matches:
        return []
    blocks: List[VolumeAuditBlock] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(audit_text)
        blocks.append(
            VolumeAuditBlock(
                vol=m.group("vol"),
                title=(m.group("name") or "").strip(),
                text=audit_text[m.start() : end],
                start=m.start(),
                end=end,
            )
        )
    return blocks


def select_block_for_volume(
    blocks: List[VolumeAuditBlock],
    vol: str,
    volume_name: str = "",
) -> Tuple[Optional[VolumeAuditBlock], List[str]]:
    """选取本卷审计块；同卷多块则取最后一块并告警。"""
    vol = vol.zfill(3)
    hits = [b for b in blocks if b.vol == vol]
    issues: List[str] = []
    if not hits:
        return None, [f"审计 MD 缺少本卷区块「## 卷{vol}：…」"]
    if len(hits) > 1:
        issues.append(f"审计 MD 中卷{vol} 出现 {len(hits)} 个区块，须合并为一块（取最后一块校验）")
    block = hits[-1]
    if volume_name and block.title and volume_name not in block.title and block.title not in volume_name:
        issues.append(
            f"卷{vol} 区块标题「{block.title}」与 skeleton.volume「{volume_name}」不一致"
        )
    return block, issues


def _has_section(block_text: str, heading: str) -> bool:
    pattern = re.compile(rf"^###\s*{re.escape(heading)}", re.MULTILINE)
    return bool(pattern.search(block_text))


def count_paragraph_rows(block_text: str) -> Tuple[int, List[int]]:
    nums = [int(m.group(1)) for m in PARA_ROW_RE.finditer(block_text)]
    return len(nums), sorted(set(nums))


def verify_volume_audit_block(
    block: VolumeAuditBlock,
    *,
    total_paragraphs: int,
    volume_name: str = "",
) -> Tuple[bool, List[str]]:
    """校验单卷审计块内容。"""
    errors: List[str] = []
    text = block.text

    if REJECT_RE.search(text):
        if not PASS_RE.search(text):
            errors.append("审计结论为「❌ 退回」，须修正 skeleton 后重跑 Step1–3")
        else:
            errors.append("同一卷块内同时出现「❌ 退回」与通过结论，须清理后只保留一种结论")

    if not PASS_RE.search(text):
        errors.append("本卷块缺少通过结论（须含「✅ …修正后通过」或「✅ …通过」）")

    if not _has_section(text, "准入过程"):
        errors.append("本卷块缺少「### 准入过程」（须在本卷块内，不可复用他卷）")

    if not _has_section(text, "段落覆盖清单"):
        errors.append("本卷块缺少「### 段落覆盖清单」")

    if PARA_RANGE_BAD_RE.search(text):
        errors.append("段落覆盖清单禁止使用范围压缩（如 P1-P5），须每段一行")

    row_count, para_nums = count_paragraph_rows(text)
    if row_count < total_paragraphs:
        errors.append(
            f"段落覆盖清单仅 {row_count} 行，少于 total_paragraphs={total_paragraphs}"
        )
    elif row_count > total_paragraphs + 2:
        errors.append(
            f"段落覆盖清单 {row_count} 行明显多于 total_paragraphs={total_paragraphs}，请核对"
        )

    missing_decl = [m for m in DECLARATION_MARKERS if m not in text]
    if missing_decl:
        errors.append(f"声明块缺项（{len(missing_decl)}/{len(DECLARATION_MARKERS)}）：{', '.join(missing_decl)}")

    if volume_name and volume_name not in text:
        errors.append(f"本卷块未提及卷名「{volume_name}」")

    return len(errors) == 0, errors


def strip_audit_blocks(audit_text: str, vols: set[str]) -> str:
    """移除指定卷的 ## 卷NNN 区块。"""
    matches = list(VOL_HEADER_RE.finditer(audit_text))
    if not matches:
        return audit_text
    keep: list[str] = []
    if matches[0].start() > 0:
        keep.append(audit_text[: matches[0].start()])
    for i, m in enumerate(matches):
        if m.group("vol") in vols:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(audit_text)
        keep.append(audit_text[m.start() : end])
    return "".join(keep).rstrip() + "\n"


def verify_semantic_audit(
    audit_text: str,
    *,
    work: str,
    vol: str,
    volume_name: str,
    total_paragraphs: int,
) -> Tuple[bool, str]:
    """
    完整 Step3 语义校验。
    返回 (ok, message)；失败时 message 含全部错误行。
    """
    _ = work
    blocks = split_volume_blocks(audit_text)
    if not blocks:
        return False, (
            "审计 MD 无任何「## 卷NNN：卷名」区块。"
            "禁止仅在全书末尾写一次准入过程/✅。"
        )

    block, select_issues = select_block_for_volume(blocks, vol, volume_name)
    all_errors = list(select_issues)
    if block is None:
        return False, "\n".join(f"  - {e}" for e in all_errors)

    ok, block_errors = verify_volume_audit_block(
        block,
        total_paragraphs=total_paragraphs,
        volume_name=volume_name,
    )
    all_errors.extend(block_errors)

    if all_errors:
        header = f"卷{vol.zfill(3)}「{volume_name}」语义审计未通过："
        return False, header + "\n" + "\n".join(f"  - {e}" for e in all_errors)

    return True, (
        f"卷{vol.zfill(3)}「{volume_name}」语义审计通过"
        f"（独立区块 + 准入过程 + 段落表 {total_paragraphs} 行 + 六条声明）"
    )
