/** 史略条目来源：API entrySource → 展示文案 */
export function formatEntrySourceLabel(value?: string | null): string {
  const v = String(value || '').trim().toLowerCase()
  if (v === 'supplement') return '模型补全'
  if (v === 'extract') return '历史著作标注'
  return ''
}

/** 史略详情来源：API detailSource → 展示文案 */
export function formatDetailSourceLabel(value?: string | null): string {
  const v = String(value || '').trim().toLowerCase()
  if (v === 'compose') return '大模型撰写'
  if (v === 'translate') return '史料顺译'
  return ''
}
