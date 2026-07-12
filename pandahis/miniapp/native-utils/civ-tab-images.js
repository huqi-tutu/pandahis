/** 文明 Tab 配图：统一 ASCII 路径，避免中文目录在开发者工具静态服务 500 */
const CIV_TAB_IMAGES = {
  huaxia: '/images/civ-tabs/01_huaxia.png',
  chaoxian: '/images/civ-tabs/02_chaoxian.png',
  japan: '/images/civ-tabs/03_japan.png',
  sea: '/images/civ-tabs/04_sea.png',
  centralasia: '/images/civ-tabs/05_centralasia.png',
  northasia: '/images/civ-tabs/06_northasia.png',
  southasia: '/images/civ-tabs/07_southasia.png',
  westasia: '/images/civ-tabs/08_westasia.png',
  southeu: '/images/civ-tabs/09_southeu.png',
  easteu: '/images/civ-tabs/10_easteu.png',
  westeu: '/images/civ-tabs/11_westeu.png',
  northeu: '/images/civ-tabs/12_northeu.png',
  northafrica: '/images/civ-tabs/13_northafrica.png',
  westafrica: '/images/civ-tabs/14_westafrica.png',
  eastafrica: '/images/civ-tabs/15_eastafrica.png',
  centralamerica: '/images/civ-tabs/16_centralamerica.png',
  northamerica: '/images/civ-tabs/17_northamerica.png',
  southamerica: '/images/civ-tabs/18_southamerica.png',
}

function civTabImage(id) {
  return CIV_TAB_IMAGES[id] || ''
}

module.exports = {
  CIV_TAB_IMAGES,
  civTabImage,
}
