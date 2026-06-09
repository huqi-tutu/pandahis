export function stripHtml(html: string): string {
  if (!html) return ''
  return String(html).replace(/<[^>]+>/g, '')
}

/** 搜索高亮 HTML（后端 <em>）→ rich-text 可用片段 */
export function highlightEmToRich(html: string): string {
  if (!html) return ''
  return String(html)
    .replace(/<em>/gi, '<span style="color:#4A3F3F;font-weight:700">')
    .replace(/<\/em>/gi, '</span>')
}

/** 路径展示：与参考稿一致使用 ` > ` 分隔 */
export function formatSearchPath(pathText: string): string {
  if (!pathText) return ''
  return pathText.replace(/\s*›\s*/g, ' > ')
}

/** PRD V1.1 王朝层横轴顺序 */
export const PRD_CATEGORY_KEYS = ['junji', 'shichen', 'dianzhi', 'shilue', 'minlu'] as const

export function categoryLabel(key: string): string {
  switch (key) {
    case 'junji':
      return '君纪'
    case 'shichen':
      return '士臣'
    case 'minlu':
      return '民录'
    case 'dianzhi':
      return '典制'
    case 'shilue':
      return '事略'
    default:
      return key || ''
  }
}
