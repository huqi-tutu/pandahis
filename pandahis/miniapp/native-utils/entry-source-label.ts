/** 数据来源：API entrySource → 展示文案 */
export function formatEntrySourceLabel(value?: string | null): string {
  const v = String(value || '').trim().toLowerCase()
  if (v === 'supplement') return '模型补全'
  if (v === 'extract') return '历史著作标注'
  return ''
}
