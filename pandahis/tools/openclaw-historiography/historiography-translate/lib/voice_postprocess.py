"""Phase3 风格润色后处理：参考著作程序化补回 + 格式自动修（报警可抽检）。"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.reference_works import (  # noqa: E402
    format_reference_section,
    merge_reference_works,
    parse_reference_section,
    strip_reference_section,
)

# 仅书目/格式类：应用程序修复，不应触发整稿回滚
_REF_SOFT_MARKERS = (
    "文末缺少「参考著作」",
    "参考著作须独立成段",
    "参考著作节书目未在正文引用",
)


def is_reference_only_failure(errors: List[str]) -> bool:
    if not errors:
        return False
    return all(any(m in e for m in _REF_SOFT_MARKERS) for e in errors)


def _alert(
    *,
    code: str,
    message: str,
    before: str = "",
    after: str = "",
    auto_fixed: bool = True,
) -> Dict[str, Any]:
    """格式层报警项：不硬拦，须落盘供抽检。"""
    return {
        "severity": "alert",
        "layer": "format",
        "code": code,
        "message": message,
        "auto_fixed": auto_fixed,
        "before_snippet": (before or "")[:240],
        "after_snippet": (after or "")[:240],
    }


def unwrap_nested_translate_detail(detail: str) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]]]:
    """若 LLM 把整段 JSON 写进「翻译详情」，拆出真正正文。

    兼容截断/未转义的伪 JSON：用 `"翻译详情": "` 定位后做字符串扫描。
    返回 (正文, 旁路字段, 报警)。
    """
    alerts: List[Dict[str, Any]] = []
    s = (detail or "").strip()
    if not (s.startswith("{") and "翻译详情" in s[:400]):
        return detail, {}, alerts

    extra: Dict[str, Any] = {}
    # 先去掉我们可能已追加在外壳上的参考著作，避免干扰扫描
    core = strip_reference_section(s).rstrip()
    m = re.search(r'"翻译详情"\s*:\s*"', core)
    if not m:
        # 尝试标准 JSON
        try:
            obj = json.loads(core)
            if isinstance(obj, dict) and obj.get("翻译详情"):
                inner = str(obj["翻译详情"])
                for k, v in obj.items():
                    if k != "翻译详情" and v not in (None, ""):
                        extra[k] = v
                alerts.append(
                    _alert(
                        code="voice_unwrap_nested_json",
                        message="拆出嵌套 JSON 中的翻译详情",
                        before=core[:80],
                        after=inner[:80],
                    )
                )
                return inner, extra, alerts
        except json.JSONDecodeError:
            pass
        return detail, {}, alerts

    start = m.end()
    chars: List[str] = []
    i = start
    while i < len(core):
        c = core[i]
        if c == "\\" and i + 1 < len(core):
            nxt = core[i + 1]
            esc = {
                "n": "\n",
                "r": "\r",
                "t": "\t",
                '"': '"',
                "\\": "\\",
                "/": "/",
            }
            chars.append(esc.get(nxt, nxt))
            i += 2
            continue
        if c == '"':
            break
        chars.append(c)
        i += 1
    inner = "".join(chars).strip()
    if not inner:
        return detail, {}, alerts

    # 外壳上的参考著作若有，留给后续 rebuild
    outer_refs = ""
    if "参考著作" in s and "参考著作" not in inner:
        outer_refs = "\n\n" + s[s.find("参考著作") :].strip()

    alerts.append(
        _alert(
            code="voice_unwrap_nested_json",
            message="拆出嵌套/截断 JSON 中的翻译详情正文",
            before=core[:100],
            after=inner[:100],
        )
    )
    return inner + outer_refs, extra, alerts


def autofix_voice_format(detail: str) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    """Phase3 格式层自动修：去 markdown 加粗、参考著作独立成段。

    返回 (新文, 短说明列表, 报警记录)。
    """
    fixes: List[str] = []
    alerts: List[Dict[str, Any]] = []
    out = detail
    if re.search(r"\*\*[^*]+\*\*", out):
        samples = re.findall(r"\*\*[^*]+\*\*", out)[:3]
        out2 = re.sub(r"\*\*([^*]+)\*\*", r"\1", out)
        if out2 != out:
            out = out2
            msg = "去掉 Markdown 加粗"
            fixes.append(msg)
            alerts.append(
                _alert(
                    code="voice_strip_markdown_bold",
                    message=msg,
                    before="；".join(samples),
                    after="；".join(re.sub(r"\*\*([^*]+)\*\*", r"\1", s) for s in samples),
                )
            )
    if "参考著作" in out and not re.search(r"\n\n参考著作\s*[:：]", out):
        m = re.search(r"\*?参考著作\s*[:：]\*?", out)
        if m:
            body, after = out[: m.start()].rstrip(), out[m.start() :]
            after2 = re.sub(r"^\*?参考著作\s*[:：]\*?", "参考著作：", after.lstrip())
            before_snip = out[max(0, m.start() - 40) : m.start() + 40]
            out = f"{body}\n\n{after2}"
            msg = "参考著作独立成段"
            fixes.append(msg)
            alerts.append(
                _alert(
                    code="voice_ref_section_spacing",
                    message=msg,
                    before=before_snip,
                    after=out[max(0, len(body) - 20) : len(body) + 40],
                )
            )
    return out, fixes, alerts


def ensure_voice_reference_section(
    styled_detail: str,
    phase2_detail: str,
    recalled: Dict[str, Any],
    plan: Dict[str, Any] | None = None,
) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Phase3 正文保留，参考著作程序重建。

    返回 (新详情, 修复说明, 报警记录)。
    """
    alerts: List[Dict[str, Any]] = []
    had_refs = "参考著作" in styled_detail
    old_refs = parse_reference_section(styled_detail) if had_refs else []
    body = strip_reference_section(styled_detail).rstrip()
    if not body:
        return styled_detail, "", alerts

    refs = merge_reference_works(recalled, body, plan)
    note = "由正文《》+索引重建参考著作"
    source = "body_and_index"
    if not refs:
        refs = parse_reference_section(phase2_detail)
        note = "沿用 Phase2 参考著作列表"
        source = "phase2"
    if not refs:
        mother = str(recalled.get("母本著作") or (plan or {}).get("母本著作") or "").strip()
        if mother:
            refs = [mother if mother.startswith("《") else f"《{mother}》"]
            note = "回退为母本著作一条"
            source = "mother_only"

    cleaned: List[str] = []
    dropped_placeholder: List[str] = []
    for r in refs:
        s = str(r).strip()
        if not s:
            continue
        if "相关卷" in s:
            dropped_placeholder.append(s)
            continue
        orig = s
        if re.fullmatch(r"《?0?\d*史记》?", s) or s in ("01史记", "《01史记》"):
            s = "《史记》"
        if not s.startswith("《"):
            s = f"《{s.strip('《》')}》"
        if s != orig and "史记" in orig:
            alerts.append(
                _alert(
                    code="voice_ref_normalize_shiji",
                    message=f"书目规范化: {orig} → {s}",
                    before=orig,
                    after=s,
                )
            )
        if s not in cleaned:
            cleaned.append(s)

    for p in dropped_placeholder:
        alerts.append(
            _alert(
                code="voice_ref_drop_placeholder",
                message=f"丢弃不合规占位书目: {p}",
                before=p,
                after="",
            )
        )

    if not cleaned:
        if not had_refs:
            alerts.append(
                _alert(
                    code="voice_ref_missing_unfixed",
                    message="文末缺少参考著作且未能自动补全",
                    auto_fixed=False,
                )
            )
        return styled_detail, "", alerts

    section = format_reference_section(cleaned)
    new_detail = f"{body}\n\n{section}"
    if not had_refs or set(old_refs) != set(cleaned):
        alerts.append(
            _alert(
                code="voice_ref_rebuild",
                message=note,
                before="；".join(old_refs) or "(无)",
                after="；".join(cleaned),
            )
        )
        alerts[-1]["source"] = source
    return new_detail, note, alerts


def write_voice_alerts(
    path: Path,
    *,
    entry_id: str,
    alerts: List[Dict[str, Any]],
    extra: Dict[str, Any] | None = None,
) -> Path:
    """落盘 Phase3 格式报警/自动修复清单，供抽检。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "史略ID": entry_id,
        "stage": "phase3_voice",
        "severity": "alert",
        "updated_at": time.time(),
        "updated_iso": time.strftime("%Y-%m-%d %H:%M:%S"),
        "alert_count": len(alerts),
        "auto_fixed_count": sum(1 for a in alerts if a.get("auto_fixed")),
        "alerts": alerts,
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def print_voice_alerts(alerts: List[Dict[str, Any]]) -> None:
    """控制台报警（非硬拦）。"""
    if not alerts:
        return
    print(
        f"   🚨 Phase3 格式报警 {len(alerts)} 项（已自动修复="
        f"{sum(1 for a in alerts if a.get('auto_fixed'))}；不阻断，请抽检）",
        flush=True,
    )
    for a in alerts[:12]:
        flag = "已修" if a.get("auto_fixed") else "未修"
        print(f"   ⚠️ [{flag}] {a.get('code')}: {a.get('message')}", flush=True)
    if len(alerts) > 12:
        print(f"   ⚠️ …另有 {len(alerts) - 12} 项见报警文件", flush=True)
