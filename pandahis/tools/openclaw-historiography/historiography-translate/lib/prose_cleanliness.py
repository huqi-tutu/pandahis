"""成文洁净：禁止说书场身份、加工元叙述、市井称谓泄漏进读者正文。"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

# 说书场 / 对读者喊话（P0）
_STORYTELLER_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"诸位看官", "诸位看官"),
    (r"列位看官", "列位看官"),
    (r"各位听客", "各位听客"),
    (r"各位看官", "各位看官"),
    (r"今儿个?\s*咱", "今儿/咱"),
    (r"咱要讲的", "咱要讲的"),
    (r"咱们接着上回", "咱们接着上回"),
    (r"接着上回", "接着上回"),
    (r"上回讲到", "上回讲到"),
    (r"上一回讲到", "上一回讲到"),
    (r"咱们下回再说", "咱们下回再说"),
    (r"且听下回", "且听下回"),
    (r"您说邪门", "您说邪门"),
    (r"邪门不邪门", "邪门不邪门"),
    (r"给列位看官", "给列位看官"),
    (r"列位看官[，,]", "列位看官"),
)

# 加工/编排元叙述（P0）— 允许文末「参考著作」列表
_PROCESS_META_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"本篇以[《「].{0,40}为主线", "本篇以…为主线"),
    (r"本文以[《「].{0,40}为主线", "本文以…为主线"),
    (r"异同处参看", "异同处参看"),
    (r"一同出?参考", "一同参考"),
    (r"关键关节按时间线", "关键关节按时间线"),
    (r"专名[、，].{0,20}以母本为准", "以母本为准"),
    (r"胜负与因果以母本为准", "以母本为准"),
    (r"编辑已就位", "编辑已就位"),
    (r"结构账本", "结构账本"),
    (r"八大守恒", "八大守恒"),
    (r"Phase\s*2", "Phase2"),
    (r"说书体润色稿", "说书体润色稿"),
    (r"严格遵循结构", "严格遵循结构"),
)

# 市井/网络称谓（P0）
_VERNACULAR_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"这位爷", "这位爷"),
    (r"这位主儿?", "这位主儿"),
    (r"(?<![其父母])他娘(?![亲胎])", "他娘"),  # 粗滤；「他娘的」也拦
    (r"他爹人称", "他爹"),
    (r"这哥们", "这哥们"),
    (r"这波", "这波"),
    (r"忽悠住", "忽悠"),
    (r"开挂", "开挂"),
    (r"拿捏", "拿捏"),
)


def prose_cleanliness_enabled() -> bool:
    return (os.environ.get("TRANSLATE_PROSE_CLEANLINESS") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def detect_prose_cleanliness_errors(detail: str, *, label: str = "成稿") -> List[str]:
    """读者正文洁净硬拦。"""
    if not prose_cleanliness_enabled():
        return []
    body = (detail or "").split("参考著作")[0]
    if not body.strip():
        return []
    errs: List[str] = []
    for pat, name in _STORYTELLER_PATTERNS:
        if re.search(pat, body):
            errs.append(
                f"{label}：成文洁净·说书场身份（命中「{name}」）；"
                "须第三人称历史叙事，禁止对读者喊话/接上回"
            )
            break
    for pat, name in _PROCESS_META_PATTERNS:
        if re.search(pat, body):
            errs.append(
                f"{label}：成文洁净·加工元叙述（命中「{name}」）；"
                "禁止把编排说明写进读者正文（书目仅文末参考著作）"
            )
            break
    for pat, name in _VERNACULAR_PATTERNS:
        if re.search(pat, body):
            errs.append(
                f"{label}：成文洁净·市井称谓（命中「{name}」）；"
                "用人名/身份/武帝等历史称谓，禁止「这位爷」「他娘」类"
            )
            break
    # 去重保序
    seen = set()
    out: List[str] = []
    for e in errs:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def heal_prose_cleanliness(detail: str) -> Tuple[str, List[str]]:
    """静默剥离明显泄漏；无法安全改写的市井词仅删句级高危套话。"""
    if not detail:
        return detail, []
    text = detail
    changes: List[str] = []

    # 整段剥：提示词残骸 / 接上回套话段
    paras = re.split(r"\n\s*\n", text)
    kept: List[str] = []
    for p in paras:
        s = p.strip()
        if not s:
            continue
        if re.search(
            r"编辑已就位|结构账本|八大守恒|说书体润色稿|Phase\s*2|"
            r"各位听客|诸位看官|列位看官|咱们接着上回|上回讲到|上一回讲到|"
            r"咱们下回再说",
            s,
        ):
            # 若整段几乎全是套话则丢；若后半还有正文，剥开头套话
            stripped = re.sub(
                r"^(?:好的[，,]?\s*)?(?:编辑已就位[。．]?|"
                r"这是对第\d+/\d+章.*?(?:\n+|——\s*)|"
                r"好[，,]?\s*诸位看官[，,].*?[。！？]\s*|"
                r"各位听客[，,].*?[。！？]\s*|"
                r"列位看官[，,].*?[。！？]\s*)+",
                "",
                s,
                flags=re.S,
            ).strip("-\n 　")
            if not stripped or len(re.sub(r"\s+", "", stripped)) < 40:
                changes.append("剥除说书场/提示词段")
                continue
            if stripped != s:
                changes.append("剥除段首说书场/提示词套话")
                s = stripped
        kept.append(s)
    text = "\n\n".join(kept)

    # 句级剥加工说明
    def _strip_process_sentences(block: str) -> str:
        parts = re.split(r"(?<=[。！？])", block)
        out_p: List[str] = []
        for sent in parts:
            if re.search(
                r"本篇以|本文以|异同处参看|关键关节按时间线|"
                r"专名.{0,12}以母本为准|胜负与因果以母本为准|"
                r"一同出?参考《",
                sent,
            ):
                changes.append("剥除加工元叙述句")
                continue
            out_p.append(sent)
        return "".join(out_p)

    # 只处理参考著作前的正文
    ref = ""
    body = text
    for sep in ("\n\n参考著作\n", "\n参考著作\n", "\n\n参考著作", "\n参考著作"):
        if sep in text:
            body, _, rest = text.partition(sep)
            ref = sep.lstrip("\n") + rest
            break
    body2 = _strip_process_sentences(body)
    # 句内说书场喊话（不一定整段）
    body2, n_st = re.subn(
        r"[^。！？\n]{0,8}(?:诸位看官|列位看官|各位听客|各位看官)[^。！？\n]{0,40}[。！？]?",
        "",
        body2,
    )
    if n_st:
        changes.append("剥除句内看官喊话")
    body2, n_st2 = re.subn(
        r"(?:咱们下回再说|且听下回分解|上回讲到|上一回讲到|接着上回)[^。！？\n]{0,60}[。！？]?",
        "",
        body2,
    )
    if n_st2:
        changes.append("剥除上回/下回套话")
    # 残留提示词关键词整句
    body2, n_meta = re.subn(
        r"[^。！？\n]{0,6}(?:结构账本|八大守恒|Phase\s*2|编辑已就位)[^。！？\n]{0,80}[。！？]?",
        "",
        body2,
    )
    if n_meta:
        changes.append("剥除提示词残留句")
    # 市井词粗替换（安全同义）
    repls = (
        (r"这位爷", "此人"),
        (r"这位主儿", "此人"),
        (r"这位主", "此人"),
        (r"他娘更简单，叫", "其母人称"),
        (r"他娘便是", "其母是"),
        (r"他娘", "其母"),
        (r"他爹人称", "其父人称"),
        (r"他爹", "其父"),
    )
    for pat, rep in repls:
        if re.search(pat, body2):
            body2 = re.sub(pat, rep, body2)
            changes.append(f"市井称谓规范化（{pat}）")

    # 孤立 ---
    body2 = re.sub(r"\n---+\s*\n+", "\n\n", body2)
    body2 = body2.strip()
    if not ref:
        return body2, list(dict.fromkeys(changes))
    return f"{body2}\n\n{ref.lstrip()}", list(dict.fromkeys(changes))
