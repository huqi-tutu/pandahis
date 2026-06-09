# -*- coding: utf-8 -*-
import json

with open('/Users/rachelcheng/.openclaw-autoclaw/skills/historiography-compose/产出/史记_卷001_史略记录.json', 'r') as f:
    data = json.load(f)

# Read source text file for 舜 related paragraphs
with open('/Users/rachelcheng/.openclaw-autoclaw/skills/historiography-index/源文/史记_卷001.txt', 'r') as f:
    source_text = f.read()

# Extract paragraphs P20-P39 (inclusive) for 舜
lines = source_text.strip().split('\n')
shun_paras = []
capture = False
for line in lines:
    line = line.strip()
    if not line:
        if capture:
            shun_paras.append('')
        continue
    if line.startswith('[P20]') or line.startswith('[P21]') or line.startswith('[P22]'):
        capture = True
    if capture:
        shun_paras.append(line)
    if line.startswith('[P39]'):
        # Add until we hit the next paragraph marker after P39 content
        pass
    if capture and line.startswith('[P40]'):
        break

# Actually, let's just reconstruct from known paragraphs
# Read all lines and filter for P20-P39
all_paras = {}
current_para = None
current_text = []
for line in lines:
    line = line.strip()
    if not line:
        continue
    # Check if line starts a new paragraph
    import re
    m = re.match(r'^\[P(\d+)\](.*)', line)
    if m:
        if current_para is not None:
            all_paras[current_para] = '\n'.join(current_text).strip()
        current_para = int(m.group(1))
        current_text = [line]
    else:
        if current_para is not None:
            current_text.append(line)
if current_para is not None:
    all_paras[current_para] = '\n'.join(current_text).strip()

# Build shun source from P20-P39
shun_para_nums = list(range(20, 40))  # P20 through P39
shun_source_parts = []
for pn in shun_para_nums:
    if pn in all_paras:
        shun_source_parts.append(all_paras[pn])
shun_source = '\n\n'.join(shun_source_parts)

# Also extract P18-P20+P36 for 四岳
siyue_source_parts = []
for pn in [18, 19, 20, 36]:
    if pn in all_paras:
        siyue_source_parts.append(all_paras[pn])
siyue_source = '\n\n'.join(siyue_source_parts)

fixed = 0
for r in data['records']:
    if r['史略名称'] == '舜' and '详见源文' in r['史料原文']:
        r['史料原文'] = shun_source
        fixed += 1
        print(f'已修复 舜 的史料原文 ({len(shun_source)}字)')
    if r['史略名称'] == '四岳' and '详见源文' in r['史料原文']:
        r['史料原文'] = siyue_source
        fixed += 1
        print(f'已修复 四岳 的史料原文 ({len(siyue_source)}字)')

with open('/Users/rachelcheng/.openclaw-autoclaw/skills/historiography-compose/产出/史记_卷001_史略记录.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f'共修复 {fixed} 条记录')
print('文件已保存')
