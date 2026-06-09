// pages/emperor/emperor.js
Page({
  data: {
    emperors: [],
    civilizationName: '',
    loading: true
  },

  onLoad(options) {
    const civId = options.civilizationId || 'east_asia';
    const civName = options.civilizationName || '东亚文明';
    
    this.setData({ civilizationName: civName });
    this.loadEmperors(civId);
  },

  loadEmperors(civilizationId) {
    // 如果是东亚文明（中华文明），加载中国帝王列表
    if (civilizationId === 'east_asia') {
      this.setData({
        emperors: this.getChineseEmperors(),
        loading: false
      });
    } else {
      // 其他文明暂时显示提示
      this.setData({
        emperors: [],
        loading: false
      });
    }
  },

  getChineseEmperors() {
    // 内置代表性帝王数据（简化版）
    return [
      { id: 'xia_yu', name: '禹', dynasty: '夏', reign: '前 2070-前 2025', importance: 5, tags: ['治水', '夏朝开创者'] },
      { id: 'shang_tang', name: '汤', dynasty: '商', reign: '前 1600-前 1571', importance: 5, tags: ['商朝开创者'] },
      { id: 'zhou_wu_wang', name: '周武王', dynasty: '周', reign: '前 1046-前 1043', importance: 5, tags: ['周朝开创者'] },
      { id: 'qin_shi_huang', name: '秦始皇', dynasty: '秦', reign: '前 221-前 210', importance: 5, tags: ['大一统', '始皇帝'] },
      { id: 'han_liu_bang', name: '刘邦', dynasty: '汉', reign: '前 202-前 195', importance: 5, tags: ['汉朝开创者'] },
      { id: 'han_wu_di', name: '汉武帝', dynasty: '汉', reign: '前 141-前 87', importance: 5, tags: ['开疆拓土', '丝绸之路'] },
      { id: 'tang_li_shi_min', name: '李世民', dynasty: '唐', reign: '626-649', importance: 5, tags: ['贞观之治'] },
      { id: 'tang_wu_ze_tian', name: '武则天', dynasty: '唐', reign: '690-705', importance: 5, tags: ['唯一女皇帝'] },
      { id: 'song_zhao_kuang_yin', name: '赵匡胤', dynasty: '宋', reign: '960-976', importance: 5, tags: ['宋朝开创者'] },
      { id: 'yuan_hu_bi_lie', name: '忽必烈', dynasty: '元', reign: '1260-1294', importance: 5, tags: ['元朝开创者'] },
      { id: 'ming_zhu_yuan_zhang', name: '朱元璋', dynasty: '明', reign: '1368-1398', importance: 5, tags: ['明朝开创者'] },
      { id: 'ming_zhu_di', name: '朱棣', dynasty: '明', reign: '1402-1424', importance: 5, tags: ['永乐盛世', '郑和下西洋'] },
      { id: 'qing_kang_xi', name: '康熙', dynasty: '清', reign: '1661-1722', importance: 5, tags: ['康乾盛世'] },
      { id: 'qing_qian_long', name: '乾隆', dynasty: '清', reign: '1735-1796', importance: 5, tags: ['康乾盛世'] }
    ];
  },

  onEmperorTap(e) {
    const index = e.currentTarget.dataset.index;
    const emperor = this.data.emperors[index];
    wx.showModal({
      title: emperor.name,
      content: `${emperor.dynasty} ${emperor.reign}\n标签：${emperor.tags.join('、')}`,
      showCancel: false
    });
  }
})
