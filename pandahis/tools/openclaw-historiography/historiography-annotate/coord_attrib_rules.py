#!/usr/bin/env python3
"""人物二/三/四级坐标归属：大模型判定规则（文案 SSOT）。"""

from __future__ import annotations

# 写入 fill_fields._坐标规则、Step4 prompt、跨时期说明提示
PERSON_COORD_ATTRIB_RULE = (
    "由大模型判定四级帝王（须为帝王.json 标准名）；"
    "一～三级坐标由编排器据帝王表自动反推，不要求填写。"
    "不依赖本卷是否出现君王条目。"
    "士臣/庶众/宦官以其主要主政、仕宦、最高官职、历史功业所在帝王为准；"
    "宗戚：嫔妃/皇后/太后挂册封之君（丈夫），公主等挂生父；"
    "蕃祚挂主要对抗/交往之帝王。"
    "禁止将史略名称本人当作四级帝王。"
)

SPINDLE_RATIONALE_PROMPT_SUFFIX = (
    "请据主政/仕宦/最高官职/功业写 _auto_filled._坐标主轴说明 1～2 句；"
    "功绩难分主次时取更早帝王。"
)
