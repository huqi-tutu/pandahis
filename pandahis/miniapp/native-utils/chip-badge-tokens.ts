/** 史略胶囊 Badge：分类主题色 → 浅底 + 深字（仅用于标签，不用于胶囊底） */
export type ChipBadgeToken = {
  bg: string
  text: string
}

export const CHIP_BADGE_TOKENS: Record<string, ChipBadgeToken> = {
  junji: { bg: '#FAF1DD', text: '#B88932' },
  zongqi: { bg: '#F6EAEA', text: '#9A6666' },
  wenchen: { bg: '#F3EDE3', text: '#9A7A45' },
  wujiang: { bg: '#F4EADF', text: '#94643D' },
  shilue: { bg: '#EAF4F7', text: '#5E8A94' },
  dianzhi: { bg: '#E8EFEC', text: '#5E7A70' },
  lunzhu: { bg: '#F0EBF5', text: '#7A668F' },
  huanguan: { bg: '#F1ECF6', text: '#7D6F92' },
  shuzhong: { bg: '#FAF2EA', text: '#A88762' },
  fanzhu: { bg: '#E8EFEC', text: '#5E7A70' },
}

export function chipBadgeToken(categoryKey?: string): ChipBadgeToken {
  const key = String(categoryKey || '').trim()
  return CHIP_BADGE_TOKENS[key] || { bg: '#F2F0EC', text: '#7A756C' }
}
