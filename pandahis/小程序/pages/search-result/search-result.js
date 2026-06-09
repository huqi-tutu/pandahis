const protoPage = require('../../behaviors/proto-page.js')

// 模拟搜索数据库
const MOCK_DB = [
  { id: '1', title: '乌台诗案',        cat: '事略', civ: 'huaxia', dynasty: '北宋', color: '#9B3E38',
    sub: '1079 · 华夏 · 北宋',     snippet: '苏轼因诗文涉嫌讥讽时政被捕，历经四月审讯，贬黄州...' },
  { id: '2', title: '王安石变法',      cat: '典制', civ: 'huaxia', dynasty: '北宋', color: '#84572F',
    sub: '1069—1076 · 华夏',       snippet: '熙宁变法以富国强兵为目标，推行青苗法、募役法等新法...' },
  { id: '3', title: '贞观之治',        cat: '君纪', civ: 'huaxia', dynasty: '唐',  color: '#F1A805',
    sub: '627—649 · 华夏 · 唐',   snippet: '唐太宗李世民励精图治，广纳谏言，轻徭薄赋...' },
  { id: '4', title: '文艺复兴',        cat: '事略', civ: 'medi',   dynasty: '意大利城邦', color: '#4A80D0',
    sub: '约14—17世纪 · 地中海',  snippet: '以人文主义为核心，在艺术、科学、文学领域掀起革命性浪潮...' },
  { id: '5', title: '唐太宗',          cat: '君纪', civ: 'huaxia', dynasty: '唐',  color: '#9B3E38',
    sub: '597—649 · 华夏',        snippet: '李世民，唐朝第二位皇帝，在位23年，史称贞观之治...' },
  { id: '6', title: '宋神宗熙宁变法',  cat: '典制', civ: 'huaxia', dynasty: '北宋', color: '#84572F',
    sub: '1069 · 华夏 · 北宋',    snippet: '宋神宗与王安石合力推行变法，试图改变积贫积弱局面...' },
  { id: '7', title: '蒙古西征',        cat: '事略', civ: 'eeu',   dynasty: '蒙古', color: '#8974B8',
    sub: '1218—1260 · 东欧',      snippet: '成吉思汗及继任者多次西征，建立横跨欧亚的庞大帝国...' },
  { id: '8', title: '苏轼',            cat: '士臣', civ: 'huaxia', dynasty: '北宋', color: '#C4764A',
    sub: '1037—1101 · 华夏',      snippet: '苏轼，字子瞻，北宋文学家、书法家、政治家，唐宋八大家之一...' },
]

Page({
  behaviors: [protoPage],

  data: {
    keyword: '',
    results: [],
    filteredResults: [],
    filterCats: ['全部', '君纪', '士臣', '典制', '事略', '民录'],
    filterIndex: 0,
  },

  onLoad(options) {
    const kw = options.keyword ? decodeURIComponent(options.keyword) : ''
    this.setData({ keyword: kw })
    this._doSearch(kw)
  },

  _doSearch(kw) {
    if (!kw) {
      this.setData({ results: MOCK_DB, filteredResults: MOCK_DB })
      return
    }
    const results = MOCK_DB.filter(item =>
      item.title.includes(kw) ||
      item.dynasty.includes(kw) ||
      item.snippet.includes(kw) ||
      item.cat.includes(kw)
    )
    this.setData({ results, filteredResults: results, filterIndex: 0 })
  },

  onFilter(e) {
    const i = Number(e.currentTarget.dataset.i)
    const cat = this.data.filterCats[i]
    const filtered = i === 0
      ? this.data.results
      : this.data.results.filter(r => r.cat === cat)
    this.setData({ filterIndex: i, filteredResults: filtered })
  },

  onResultTap(e) {
    const item = e.currentTarget.dataset.item
    wx.navigateTo({
      url: `/pages/box-detail/box-detail?title=${encodeURIComponent(item.title)}&civ=${item.civ}`
    })
  },

  goSearch() {
    wx.navigateBack()
  }
})
