#!/usr/bin/env python3
"""
Step 4 完成后自动产出统计
读完整 JSON → 输出 {著作名}_标注统计.md

用法:
  python3 generate_stats.py <完整JSON路径> [--output 统计输出路径]
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

from lib_config import paths


def generate_stats(json_path: str, output_dir: str):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = data.get('entries', [])
    work_name = json_path.split('/')[-1].replace('_条目索引.json', '').replace('_条目索引_temp.json', '')

    # 按卷次分组
    vol_entries = defaultdict(list)
    for e in entries:
        eid = e.get('史略ID', '')
        # 从 SHIJI_001_01 提取卷号 001
        parts = eid.split('_')
        if len(parts) >= 2:
            vol_key = parts[1]  # "001", "002" ...
        else:
            vol_key = '???'
        vol_entries[vol_key].append(e)

    cats_order = ['君王', '士臣', '庶众', '宗戚']

    lines = []
    lines.append(f'# {work_name} 标注统计')
    lines.append(f'> 自动生成于 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'> 共 {len(entries)} 条，{len(vol_entries)} 卷')
    lines.append('')
    lines.append(f"| 卷次 | 卷名 | {' | '.join(cats_order)} | 合计 |")
    lines.append(f"|------|------|{'|'.join(['---' for _ in cats_order])}|------|")

    totals = Counter()

    for vol_key in sorted(vol_entries.keys()):
        entries_in_vol = vol_entries[vol_key]
        vol_name = entries_in_vol[0].get('paragraphs', [{}])[0].get('volume', '') if entries_in_vol else ''
        cat_counts = Counter(e.get('史略分类', '?') for e in entries_in_vol)
        total = len(entries_in_vol)

        cat_strs = [str(cat_counts.get(c, 0)) for c in cats_order]
        lines.append(f'| {int(vol_key):03d} | {vol_name} | {" | ".join(cat_strs)} | {total} |')

        for c in cats_order:
            totals[c] += cat_counts.get(c, 0)

    # 合计行
    total_all = sum(totals.values())
    total_strs = [str(totals.get(c, 0)) for c in cats_order]
    lines.append(f'| 合计 | — | {" | ".join(total_strs)} | {total_all} |')

    # 空卷检查
    zero_cats = [c for c in cats_order if totals.get(c, 0) == 0]
    lines.append('')
    if zero_cats:
        lines.append(f'⚠️ 以下分类全著作为 0：{", ".join(zero_cats)} — 确认是否漏标')
    else:
        lines.append('✅ 所有分类均有条目')

    # 写入
    out_path = os.path.join(output_dir, f'{work_name}_标注统计.md')
    os.makedirs(output_dir, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'✅ {work_name}: {len(entries)} 条 / {len(vol_entries)} 卷')
    for c in cats_order:
        if totals[c] > 0:
            print(f'   {c}: {totals[c]}')
    print(f'   输出: {out_path}')


def main():
    parser = argparse.ArgumentParser(description='从完整 JSON 生成标注统计')
    parser.add_argument('json_path', help='Step 4 产出的完整 JSON')
    parser.add_argument('--output', '-o', default=None, help='统计输出目录（默认 HISTOGRAPH_ROOT/data/03索引标注条目/标注统计）')
    args = parser.parse_args()

    if not os.path.exists(args.json_path):
        print(f'❌ 文件不存在: {args.json_path}')
        sys.exit(1)

    output_dir = args.output or str(paths()["stats"])
    generate_stats(args.json_path, output_dir)


if __name__ == '__main__':
    main()
