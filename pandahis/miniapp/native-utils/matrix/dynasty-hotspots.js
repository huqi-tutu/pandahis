/** P01 总览地图热区（与原型 v3 一致，路径改为小程序页） */
const HOTSPOTS = [
  { id: 'huaxia-qin', name: '秦', box: { x: 7.3, y: 61.4, w: 2.4, h: 2.5 } },
  { id: 'huaxia-western-han', name: '西汉', box: { x: 9.2, y: 55.2, w: 4.2, h: 7.4 } },
  { id: 'huaxia-eastern-han', name: '东汉', box: { x: 13.0, y: 54.4, w: 4.8, h: 5.6 } },
  { id: 'huaxia-tang', name: '唐', box: { x: 18.8, y: 55.0, w: 9.8, h: 8.8 } },
  { id: 'huaxia-song', name: '宋', box: { x: 43.5, y: 54.7, w: 8.8, h: 4.4 } },
  { id: 'huaxia-yuan', name: '元', box: { x: 52.6, y: 56.0, w: 8.4, h: 4.9 } },
  { id: 'huaxia-ming', name: '明', box: { x: 62.0, y: 58.0, w: 8.5, h: 4.7 } },
  { id: 'huaxia-qing', name: '清', box: { x: 74.0, y: 57.0, w: 11.8, h: 4.9 } },
  { id: 'central-asia-mongol', name: '蒙古帝国', box: { x: 47.4, y: 45.0, w: 13.2, h: 9.8 } },
  { id: 'arab-caliphate', name: '阿拉伯帝国', box: { x: 36.0, y: 33.2, w: 16.6, h: 7.8 } },
  { id: 'persian-achaemenid', name: '阿契美尼德波斯', box: { x: 22.4, y: 28.6, w: 10.6, h: 4.9 } },
  { id: 'persian-sassanid', name: '萨珊波斯', box: { x: 32.2, y: 32.4, w: 9.8, h: 5.7 } },
  { id: 'eu-roman-republic', name: '罗马共和国', box: { x: 23.2, y: 72.8, w: 9.4, h: 4.5 } },
  { id: 'eu-roman-empire', name: '罗马帝国', box: { x: 30.6, y: 74.3, w: 17.0, h: 7.2 } },
  { id: 'byzantine', name: '东罗马（拜占庭）', box: { x: 43.6, y: 73.5, w: 9.4, h: 6.6 } },
  { id: 'ottoman', name: '奥斯曼帝国', box: { x: 57.6, y: 73.0, w: 14.8, h: 7.8 } },
  { id: 'japan-yamato', name: '大和时代', box: { x: 7.6, y: 7.9, w: 9.0, h: 4.8 } },
  { id: 'korea-silla', name: '新罗', box: { x: 44.4, y: 6.5, w: 8.5, h: 4.4 } },
  { id: 'india-mughal', name: '莫卧儿帝国', box: { x: 73.8, y: 25.4, w: 9.0, h: 5.2 } },
  { id: 'america-aztec', name: '阿兹特克', box: { x: 72.5, y: 5.6, w: 8.0, h: 4.2 } },
  { id: 'andes-inca', name: '印加', box: { x: 73.2, y: 13.2, w: 6.8, h: 4.7 } }
]

module.exports = { HOTSPOTS }
