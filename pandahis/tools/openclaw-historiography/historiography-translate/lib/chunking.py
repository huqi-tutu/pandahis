"""长史略分块：按段落域切分 recalled，控制单次 LLM 输入/输出规模。"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.work_artifacts import artifact_stem, mother_sentence_count

CHUNK_SCHEMA = "historiography-translate/chunks/v1"

MAX_PARAS_PER_CHUNK = int(os.environ.get("TRANSLATE_CHUNK_MAX_PARAS", "12"))
MAX_CHARS_PER_CHUNK = int(os.environ.get("TRANSLATE_CHUNK_MAX_CHARS", "6000"))
MODE_MIN_PARAGRAPHS = int(os.environ.get("TRANSLATE_CHUNK_MODE_MIN_PARAS", "12"))
MODE_MIN_MOTHER_CHARS = int(os.environ.get("TRANSLATE_CHUNK_MODE_MIN_CHARS", "10000"))
MODE_MIN_MOTHER_SENTENCES = int(os.environ.get("TRANSLATE_CHUNK_MIN_SENTENCES", "70"))


@dataclass
class BlockUnit:
    block_index: int
    paragraph_from: int
    paragraph_to: int
    role: str
    paragraph_count: int
    char_count: int


@dataclass
class ChunkSpec:
    chunk_id: int
    chunk_total: int
    sentence_id_start: int
    paragraph_count: int
    mother_sentence_count: int
    char_count: int
    block_units: List[BlockUnit] = field(default_factory=list)
    status: str = "pending"
    plan_file: str = ""
    body_file: str = ""


def _sentence_count_in_text(text: str) -> int:
    return len(re.findall(r"[。！？\n]", text)) or (1 if text.strip() else 0)


def _block_char_count(block: Dict[str, Any]) -> int:
    return sum(len(p.get("text") or "") for p in block.get("paragraphs") or [])


def _slice_block(block: Dict[str, Any], para_from: int, para_to: int) -> Dict[str, Any]:
    paras = [
        p
        for p in block.get("paragraphs") or []
        if para_from <= int(p.get("id", 0)) <= para_to
    ]
    text = "\n".join(str(p.get("text") or "") for p in paras)
    return {
        **{k: v for k, v in block.items() if k not in ("paragraphs", "text")},
        "paragraph_from": para_from,
        "paragraph_to": para_to,
        "paragraph_count": len(paras),
        "paragraphs": paras,
        "text": text,
    }


def _iter_units(blocks: List[Dict[str, Any]]) -> List[BlockUnit]:
    units: List[BlockUnit] = []
    for bi, block in enumerate(blocks):
        pf = int(block.get("paragraph_from") or 1)
        pt = int(block.get("paragraph_to") or pf)
        pc = int(block.get("paragraph_count") or max(0, pt - pf + 1))
        role = str(block.get("role") or "")
        if pc <= MAX_PARAS_PER_CHUNK:
            units.append(
                BlockUnit(
                    block_index=bi,
                    paragraph_from=pf,
                    paragraph_to=pt,
                    role=role,
                    paragraph_count=pc,
                    char_count=_block_char_count(block),
                )
            )
            continue
        cursor = pf
        while cursor <= pt:
            end = min(cursor + MAX_PARAS_PER_CHUNK - 1, pt)
            sliced = _slice_block(block, cursor, end)
            units.append(
                BlockUnit(
                    block_index=bi,
                    paragraph_from=cursor,
                    paragraph_to=end,
                    role=role,
                    paragraph_count=int(sliced["paragraph_count"]),
                    char_count=_block_char_count(sliced),
                )
            )
            cursor = end + 1
    return units


def _pack_units(units: List[BlockUnit]) -> List[List[BlockUnit]]:
    if not units:
        return []
    packs: List[List[BlockUnit]] = []
    current: List[BlockUnit] = []
    cur_paras = 0
    cur_chars = 0

    def flush() -> None:
        nonlocal current, cur_paras, cur_chars
        if current:
            packs.append(current)
        current = []
        cur_paras = 0
        cur_chars = 0

    for unit in units:
        would_paras = cur_paras + unit.paragraph_count
        would_chars = cur_chars + unit.char_count
        overflow = current and (
            would_paras > MAX_PARAS_PER_CHUNK or would_chars > MAX_CHARS_PER_CHUNK
        )
        if overflow:
            flush()
        current.append(unit)
        cur_paras += unit.paragraph_count
        cur_chars += unit.char_count
    flush()
    return packs


def needs_chunked_mode(recalled: Dict[str, Any]) -> bool:
    from lib.mother_sentences import mother_sentence_count

    para_count = int(recalled.get("paragraph_count") or 0)
    if para_count >= MODE_MIN_PARAGRAPHS:
        return True
    if mother_sentence_count(recalled) >= MODE_MIN_MOTHER_SENTENCES:
        return True
    blocks = recalled.get("blocks") or []
    if any(int(b.get("paragraph_count") or 0) > MAX_PARAS_PER_CHUNK for b in blocks):
        return True
    mother_chars = sum(
        _block_char_count(b) for b in blocks if b.get("role") == "母本"
    )
    return mother_chars >= MODE_MIN_MOTHER_CHARS


def build_chunk_specs(recalled: Dict[str, Any]) -> List[ChunkSpec]:
    from lib.mother_sentences import extract_mother_sentences

    blocks = recalled.get("blocks") or []
    units = _iter_units(blocks)
    packs = _pack_units(units)
    if not packs:
        packs = [[]]

    specs: List[ChunkSpec] = []
    sentence_cursor = 1
    total = len(packs)
    for i, pack in enumerate(packs, start=1):
        para_count = sum(u.paragraph_count for u in pack)
        char_count = sum(u.char_count for u in pack)
        mother_sents = 0
        for u in pack:
            if u.role != "母本":
                continue
            block = blocks[u.block_index]
            sliced = _slice_block(block, u.paragraph_from, u.paragraph_to)
            mother_sents += len(
                extract_mother_sentences(
                    {
                        "blocks": [sliced],
                    }
                )
            )
        mother_sents = max(mother_sents, 1 if any(u.role == "母本" for u in pack) else 0)
        specs.append(
            ChunkSpec(
                chunk_id=i,
                chunk_total=total,
                sentence_id_start=sentence_cursor,
                paragraph_count=para_count,
                mother_sentence_count=mother_sents,
                char_count=char_count,
                block_units=pack,
            )
        )
        sentence_cursor += mother_sents
    return specs


def slice_recalled_for_chunk(
    recalled: Dict[str, Any], spec: ChunkSpec
) -> Dict[str, Any]:
    blocks = recalled.get("blocks") or []
    sliced_blocks: List[Dict[str, Any]] = []
    for unit in spec.block_units:
        orig = blocks[unit.block_index]
        sliced_blocks.append(
            _slice_block(orig, unit.paragraph_from, unit.paragraph_to)
        )
    para_count = sum(int(b.get("paragraph_count") or 0) for b in sliced_blocks)
    return {
        "史略ID": recalled.get("史略ID"),
        "史略名称": recalled.get("史略名称"),
        "母本著作": recalled.get("母本著作"),
        "block_count": len(sliced_blocks),
        "paragraph_count": para_count,
        "blocks": sliced_blocks,
        "_chunk": {
            "chunk_id": spec.chunk_id,
            "chunk_total": spec.chunk_total,
            "sentence_id_start": spec.sentence_id_start,
            "sentence_id_end": spec.sentence_id_start
            + max(spec.mother_sentence_count, 1)
            - 1,
        },
    }


def manifest_path(entry_id: str, entry_name: str, work_dir: Path) -> Path:
    return work_dir / f"{artifact_stem(entry_id, entry_name)}.chunks.json"


def chunk_plan_path(entry_id: str, entry_name: str, work_dir: Path, chunk_id: int) -> Path:
    stem = artifact_stem(entry_id, entry_name)
    return work_dir / f"{stem}.chunk-{chunk_id:02d}.plan.json"


def chunk_body_path(entry_id: str, entry_name: str, work_dir: Path, chunk_id: int) -> Path:
    stem = artifact_stem(entry_id, entry_name)
    return work_dir / f"{stem}.chunk-{chunk_id:02d}.md"


def chunk_timeout_sec(spec: ChunkSpec) -> int:
    base = int(os.environ.get("TRANSLATE_CHUNK_TIMEOUT_BASE", "600"))
    per_para = int(os.environ.get("TRANSLATE_CHUNK_TIMEOUT_PER_PARA", "25"))
    cap = int(os.environ.get("TRANSLATE_CHUNK_TIMEOUT_CAP", "1800"))
    return min(cap, base + spec.paragraph_count * per_para)


def specs_to_manifest_dict(
    recalled: Dict[str, Any], specs: List[ChunkSpec]
) -> Dict[str, Any]:
    return {
        "schema": CHUNK_SCHEMA,
        "史略ID": recalled.get("史略ID"),
        "史略名称": recalled.get("史略名称"),
        "paragraph_count": recalled.get("paragraph_count"),
        "mother_sentence_count": mother_sentence_count(recalled),
        "chunk_count": len(specs),
        "chunked": len(specs) > 1,
        "chunks": [
            {
                "chunk_id": s.chunk_id,
                "chunk_total": s.chunk_total,
                "sentence_id_start": s.sentence_id_start,
                "sentence_id_end": s.sentence_id_start
                + max(s.mother_sentence_count, 1)
                - 1,
                "paragraph_count": s.paragraph_count,
                "mother_sentence_count": s.mother_sentence_count,
                "char_count": s.char_count,
                "block_units": [
                    {
                        "block_index": u.block_index,
                        "paragraph_from": u.paragraph_from,
                        "paragraph_to": u.paragraph_to,
                        "role": u.role,
                        "paragraph_count": u.paragraph_count,
                    }
                    for u in s.block_units
                ],
                "status": s.status,
                "plan_file": s.plan_file,
                "body_file": s.body_file,
            }
            for s in specs
        ],
    }


def spec_from_dict(item: Dict[str, Any]) -> ChunkSpec:
    units = [
        BlockUnit(
            block_index=int(u["block_index"]),
            paragraph_from=int(u["paragraph_from"]),
            paragraph_to=int(u["paragraph_to"]),
            role=str(u.get("role") or ""),
            paragraph_count=int(u.get("paragraph_count") or 0),
            char_count=0,
        )
        for u in item.get("block_units") or []
    ]
    return ChunkSpec(
        chunk_id=int(item["chunk_id"]),
        chunk_total=int(item["chunk_total"]),
        sentence_id_start=int(item["sentence_id_start"]),
        paragraph_count=int(item.get("paragraph_count") or 0),
        mother_sentence_count=int(item.get("mother_sentence_count") or 1),
        char_count=int(item.get("char_count") or 0),
        block_units=units,
        status=str(item.get("status") or "pending"),
        plan_file=str(item.get("plan_file") or ""),
        body_file=str(item.get("body_file") or ""),
    )


def load_manifest(path: Path) -> Tuple[bool, Dict[str, Any], List[str]]:
    if not path.is_file():
        return False, {}, [f"缺少分块清单: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, {}, [f"分块清单 JSON 解析失败: {exc}"]
    return True, data, []


def save_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_manifest(
    recalled: Dict[str, Any],
    work_dir: Path,
    entry_name: str,
) -> Tuple[Dict[str, Any], List[ChunkSpec], bool]:
    """
    返回 (manifest, specs, rebuilt)。
    若已有清单且 paragraph_count 一致则复用（保留 chunk status）。
    """
    entry_id = str(recalled.get("史略ID") or "")
    path = manifest_path(entry_id, entry_name, work_dir)
    fresh_specs = build_chunk_specs(recalled)
    ok, existing, _ = load_manifest(path)
    if ok and existing.get("史略ID") == entry_id:
        if int(existing.get("paragraph_count") or 0) == int(
            recalled.get("paragraph_count") or 0
        ):
            specs = [spec_from_dict(c) for c in existing.get("chunks") or []]
            if len(specs) == len(fresh_specs):
                return existing, specs, False

    manifest = specs_to_manifest_dict(recalled, fresh_specs)
    for i, spec in enumerate(fresh_specs):
        manifest["chunks"][i]["plan_file"] = str(
            chunk_plan_path(entry_id, entry_name, work_dir, spec.chunk_id)
        )
        manifest["chunks"][i]["body_file"] = str(
            chunk_body_path(entry_id, entry_name, work_dir, spec.chunk_id)
        )
    save_manifest(path, manifest)
    return manifest, fresh_specs, True


def update_chunk_status(
    manifest: Dict[str, Any],
    chunk_id: int,
    status: str,
    manifest_path_file: Path,
) -> None:
    for c in manifest.get("chunks") or []:
        if int(c.get("chunk_id")) == chunk_id:
            c["status"] = status
            break
    save_manifest(manifest_path_file, manifest)


def read_previous_chunk_tail(
    entry_id: str,
    entry_name: str,
    work_dir: Path,
    chunk_id: int,
    *,
    max_chars: int | None = None,
) -> str:
    if chunk_id <= 1:
        return ""
    if max_chars is None:
        max_chars = int(os.environ.get("TRANSLATE_CHUNK_TAIL_CHARS", "1200"))
    prev = chunk_body_path(entry_id, entry_name, work_dir, chunk_id - 1)
    if not prev.is_file():
        return ""
    text = prev.read_text(encoding="utf-8").strip()
    text = re.split(r"\n\*参考著作", text, maxsplit=1)[0].strip()
    # 优先取末尾完整段落（最多 3 段），再截断到 max_chars
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    tail_paras: List[str] = []
    total = 0
    for p in reversed(paras[-3:]):
        if total + len(p) > max_chars and tail_paras:
            break
        tail_paras.insert(0, p)
        total += len(p)
    joined = "\n\n".join(tail_paras) if tail_paras else text
    return joined[-max_chars:] if len(joined) > max_chars else joined
