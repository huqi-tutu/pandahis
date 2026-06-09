import type { Box, Civilization, SearchSuggest, TimeAxisRow, Unit } from './models'

export function yearLabel(year: number) {
  return year < 0 ? `前${Math.abs(year)}` : String(year)
}

export const CIVILIZATIONS: Civilization[] = [
  { id: 'huaxia', name: '华夏', colorVar: '--c-huaxia' },
  { id: 'chaoxian', name: '朝鲜', colorVar: '--c-chaoxian' },
  { id: 'japan', name: '日本', colorVar: '--c-japan' },
  { id: 'sea', name: '东南亚', colorVar: '--c-sea' },
  { id: 'india', name: '印度', colorVar: '--c-india' },
  { id: 'persia', name: '波斯两河', colorVar: '--c-persia' },
  { id: 'arab', name: '阿拉伯', colorVar: '--c-arab' },
  { id: 'egypt', name: '埃及', colorVar: '--c-egypt' },
  { id: 'eeu', name: '东欧', colorVar: '--c-eeu' },
  { id: 'medi', name: '地中海', colorVar: '--c-medi' },
  { id: 'weu', name: '西欧', colorVar: '--c-weu' },
  { id: 'wafrica', name: '西非', colorVar: '--c-wafrica' },
  { id: 'camer', name: '中美洲', colorVar: '--c-camer' },
  { id: 'andes', name: '安第斯', colorVar: '--c-andes' }
]

export const TIME_AXIS: TimeAxisRow[] = [
  { year: -221, label: yearLabel(-221), rowHeightPx: 48 },
  { year: -206, label: yearLabel(-206), rowHeightPx: 80 },
  { year: 9, label: yearLabel(9), rowHeightPx: 40 },
  { year: 25, label: yearLabel(25), rowHeightPx: 92 },
  { year: 220, label: yearLabel(220), rowHeightPx: 54 },
  { year: 265, label: yearLabel(265), rowHeightPx: 44 },
  { year: 420, label: yearLabel(420), rowHeightPx: 50 },
  { year: 581, label: yearLabel(581), rowHeightPx: 68 },
  { year: 618, label: yearLabel(618), rowHeightPx: 110 },
  { year: 960, label: yearLabel(960), rowHeightPx: 72 }
]

export const UNITS: Unit[] = [
  {
    id: 'huaxia_qinshihuang',
    name: '秦始皇',
    civilizationId: 'huaxia',
    crumbText: '华夏文明 · 中国 · 秦',
    startYear: -221,
    endYear: -206,
    durationYears: 15,
    summary: '完成六国统一，推行郡县制、书同文车同轨，奠定中国统一帝国的基本形态。',
  },
  {
    id: 'huaxia_song_shenzong',
    name: '宋神宗',
    civilizationId: 'huaxia',
    crumbText: '华夏文明 · 中国 · 宋',
    eraText: '年号 熙宁 · 元丰',
    startYear: 1067,
    endYear: 1085,
    durationYears: 18,
    summary:
      '宋神宗赵顼锐意变法图强，任用王安石推行新法；新旧党争撕裂朝野，乌台诗案更成为文字狱前奏，推动一代士大夫命运转折。',
  },
  {
    id: 'medi_rome_republic',
    name: '罗马共和',
    civilizationId: 'medi',
    crumbText: '地中海古典 · 罗马 · 共和',
    startYear: -509,
    endYear: -27,
    durationYears: 482,
    summary: '从元老院与公民大会的共治，到内战与独裁的循环，最终让共和国让位于帝制。',
  },
]

export const BOXES: Box[] = [
  {
    id: 'box_wutai_1079',
    unitId: 'huaxia_song_shenzong',
    title: '乌台诗案',
    categoryKey: 'shilue',
    year: 1079,
    importanceLevel: 5,
    detail: [
      '苏轼是个倒霉孩子。他写诗的时候，绝没想到一首小诗能把自己送进监狱。',
      '元丰二年，时任湖州知州的他，照例给皇帝写了份谢恩表。文章里夹了几句牢骚，结果被御史台的人盯上。',
      '他们翻箱倒柜，从苏轼旧作里挑出一百多首“有问题”的诗，一条条批注送到神宗面前……',
    ],
    critiques: [
      {
        author: '朱熹',
        eraText: '南宋 · 1200',
        content: '轼之狱，非为诗也，为党议也。变法新旧之争，以文字为刃，君子小人同陷其中。',
        source: '《朱子语类》卷一三一',
      },
      {
        author: '钱穆',
        eraText: '近代 · 1940',
        content: '此案开宋代文字狱之先声。政争一起，文章也成罪状，此风一开，贻害至明清。',
        source: '《国史大纲》下编',
      },
      {
        author: '林语堂',
        eraText: '民国 · 1947',
        content: '苏东坡一生三次下狱，这是第一次，也是最戏剧性的一次。他的豁达是在这里真正开始的。',
        source: '《苏东坡传》第九章',
      },
    ],
    relics: [
      { name: '黄州寒食帖', description: '被贬黄州第三年寒食节所写。天下第三行书，笔意苍茫郁结。', museum: '台北故宫博物院' },
      { name: '赤壁赋卷', description: '亲笔行书，完整保留《前赤壁赋》全文，纸色古朴。', museum: '台北故宫博物院' },
      { name: '东坡铭端砚', description: '黄州时期随身之物，背面刻有亲书铭文，端溪老坑石料。', museum: '北京故宫博物院' },
    ],
    graph: {
      center: 'event_wutai',
      nodes: [
        { key: 'event_wutai', name: '乌台诗案', kind: 'event' },
        { key: 'person_sushi', name: '苏轼', kind: 'person' },
        { key: 'org_yushitai', name: '御史台', kind: 'org' },
        { key: 'person_zhangdun', name: '章惇', kind: 'person' },
        { key: 'place_huangzhou', name: '黄州', kind: 'place' },
        { key: 'work_hanshitie', name: '寒食帖', kind: 'work', badge: '(名作)' },
      ],
      edges: [
        { from: 'event_wutai', to: 'person_sushi', label: '主角' },
        { from: 'event_wutai', to: 'org_yushitai', label: '审判' },
        { from: 'event_wutai', to: 'person_zhangdun', label: '新党' },
        { from: 'event_wutai', to: 'place_huangzhou', label: '贬黄州' },
        { from: 'event_wutai', to: 'work_hanshitie', label: '写下' },
      ],
    },
  },
  {
    id: 'box_dengji_1067',
    unitId: 'huaxia_song_shenzong',
    title: '登基',
    categoryKey: 'junji',
    year: 1067,
    importanceLevel: 4,
    detail: ['少年天子登基，理想与现实在宫墙内开始碰撞。'],
    critiques: [],
    relics: [],
    graph: { center: 'event_dengji', nodes: [{ key: 'event_dengji', name: '登基', kind: 'event' }], edges: [] },
  },
  {
    id: 'box_qingmiaofa_1069',
    unitId: 'huaxia_song_shenzong',
    title: '青苗法',
    categoryKey: 'dianzhi',
    year: 1069,
    importanceLevel: 4,
    detail: ['新法之一：由官府发放低息贷款救济青黄不接，同时改变地方权力结构。'],
    critiques: [],
    relics: [],
    graph: { center: 'event_qingmiao', nodes: [{ key: 'event_qingmiao', name: '青苗法', kind: 'event' }], edges: [] },
  },
]

export const SEARCH_SUGGEST: SearchSuggest = {
  hot: [
    { keyword: '王安石变法', hot: true },
    { keyword: '唐玄宗', hot: false },
    { keyword: '奥斯曼帝国', hot: false },
    { keyword: '文艺复兴', hot: true },
    { keyword: '玛雅', hot: false },
    { keyword: '乌台诗案', hot: false },
    { keyword: '郑和下西洋', hot: false },
  ],
  history: ['苏轼', '明朝 · 万历', '大航海时代', '贞观之治'],
}

export function getUnit(unitId: string) {
  return UNITS.find((u) => u.id === unitId) ?? null
}

export function getBox(boxId: string) {
  return BOXES.find((b) => b.id === boxId) ?? null
}

export function listBoxesByUnit(unitId: string) {
  return BOXES.filter((b) => b.unitId === unitId)
}

export function searchAll(q: string) {
  const qq = q.trim()
  if (!qq) return []

  const hitsBoxes = BOXES.filter((b) => b.title.includes(qq)).map((b) => ({
    type: 'box' as const,
    id: b.id,
    title: b.title,
    pathText: `华夏 › 宋神宗 › ${b.categoryKey}`,
    desc: b.detail.join(''),
  }))

  const hitsUnits = UNITS.filter((u) => u.name.includes(qq)).map((u) => ({
    type: 'unit' as const,
    id: u.id,
    title: u.name,
    pathText: `${u.crumbText.replaceAll(' · ', ' › ')}`,
    desc: u.summary,
  }))

  return [...hitsBoxes, ...hitsUnits]
}

