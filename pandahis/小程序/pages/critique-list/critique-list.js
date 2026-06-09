const protoPage = require('../../behaviors/proto-page.js')

/**
 * 史略评述列表页
 * 仿小红书评论区样式，展示历代学者对某一史略/事件的评述
 * 支持：主评述 + 回复（嵌套评述）
 */

// Mock 评述数据：以"乌台诗案"为例
// 每条评述：头像、作者、时代、正文、来源、点赞数、回复列表
const MOCK_CRITIQUES = [
  {
    id: 1,
    avatar: '司',
    avatarBg: '#84572F',
    author: '司马光',
    era: '北宋 · 约1084年',
    text: '苏轼以诗获罪，非朝廷本意。御史中丞李定、舒亶等以文字罗织罪状，欲置之于死地。太皇太后曹氏病中闻之，泣曰："吾尝记仁宗策贤良归，喜曰：吾今日又为子孙得太平宰相两人。今以诗入罪，岂不伤天下之心乎？"',
    source: '《涑水记闻》',
    likes: 247,
    liked: false,
    replies: [
      {
        id: 101,
        avatar: '朱',
        avatarBg: '#92ADA4',
        author: '朱熹',
        era: '南宋 · 约1200年',
        text: '温公此言甚善。轼之狱，非为诗也，为党议也。变法新旧之争，以文字为刃，君子小人同陷其中。',
        source: '《朱子语类》卷一三一',
        likes: 89,
        liked: false,
        replyTo: '司马光',
      },
      {
        id: 102,
        avatar: '吕',
        avatarBg: '#D4B098',
        author: '吕中',
        era: '南宋 · 约1240年',
        text: '乌台之狱，实安石新法之弊也。新法之行，以理财为先，以任刑为急，故小人得以希进，而君子不容于朝。',
        source: '《宋大事记讲义》',
        likes: 34,
        liked: false,
        replyTo: '司马光',
      },
    ],
  },
  {
    id: 2,
    avatar: '苏',
    avatarBg: '#9ABCC8',
    author: '苏轼（自述）',
    era: '北宋 · 1079年',
    text: '是岁七月二十八日，御史台差人追臣。八月十八日赴台推勘。臣初到台，被吏卒诟辱，昼夜不得休息。臣平生未尝作诗讽刺，实不晓所谓讥讽朝廷是何等语。臣虽万死，不敢诬服。',
    source: '《杭州召还乞郡状》',
    likes: 512,
    liked: true,
    replies: [
      {
        id: 201,
        avatar: '林',
        avatarBg: '#A894B8',
        author: '林语堂',
        era: '民国 · 1947年',
        text: '苏东坡一生三次下狱，这是第一次，也是最戏剧性的一次。他的豁达是在这里真正开始的。在狱中他写下"与君世世为兄弟，更结来生未了因"，读之令人泪下。',
        source: '《苏东坡传》第九章',
        likes: 156,
        liked: false,
        replyTo: '苏轼（自述）',
      },
    ],
  },
  {
    id: 3,
    avatar: '钱',
    avatarBg: '#F1A805',
    author: '钱穆',
    era: '近代 · 1940年',
    text: '此案开宋代文字狱之先声。宋人重气节，然政争一起，文章也成罪状。此风一开，贻害至明清。然宋之所以为宋，正在其虽有过激，终能自反。苏轼贬黄州后，神宗终有怜才之意，此非明清所能及。',
    source: '《国史大纲》下编',
    likes: 178,
    liked: false,
    replies: [],
  },
  {
    id: 4,
    avatar: '余',
    avatarBg: '#7F9EB5',
    author: '余英时',
    era: '当代 · 2004年',
    text: '乌台诗案的意义不仅在于苏轼个人的遭遇，更在于它揭示了宋代士大夫政治文化的内在紧张。当政见分歧升级为道德审判，文字便从表达思想的工具变成了定罪的依据。这一转变对中国知识分子的自我认知产生了深远影响。',
    source: '《朱熹的历史世界》',
    likes: 93,
    liked: false,
    replies: [],
  },
]

Page({
  behaviors: [protoPage],

  data: {
    title: '乌台诗案',
    subtitle: '1079 · 北宋 · 事略',
    critiques: [],
    totalReplies: 0,
    expandedReplies: {},  // { [critiqueId]: true/false }
  },

  onLoad(options) {
    const title = options.title ? decodeURIComponent(options.title) : '乌台诗案'
    const subtitle = options.subtitle ? decodeURIComponent(options.subtitle) : '1079 · 北宋 · 事略'

    // 统计总回复数
    let totalReplies = 0
    const critiques = MOCK_CRITIQUES.map(c => {
      totalReplies += c.replies.length
      return {
        ...c,
        hasReplies: c.replies.length > 0,
        replies: c.replies,
      }
    })

    this.setData({ title, subtitle, critiques, totalReplies })
  },

  // 展开/收起回复
  toggleReplies(e) {
    const id = e.currentTarget.dataset.id
    const key = `expandedReplies.${id}`
    this.setData({ [key]: !this.data.expandedReplies[id] })
  },

  // 点赞
  onLike(e) {
    const { type, parentId, id } = e.currentTarget.dataset

    if (type === 'reply') {
      // 回复点赞
      const critiques = this.data.critiques.map(c => {
        if (c.id !== parentId) return c
        return {
          ...c,
          replies: c.replies.map(r => {
            if (r.id !== id) return r
            return {
              ...r,
              liked: !r.liked,
              likes: r.liked ? r.likes - 1 : r.likes + 1,
            }
          }),
        }
      })
      this.setData({ critiques })
    } else {
      // 主评述点赞
      const critiques = this.data.critiques.map(c => {
        if (c.id !== id) return c
        return {
          ...c,
          liked: !c.liked,
          likes: c.liked ? c.likes - 1 : c.likes + 1,
        }
      })
      this.setData({ critiques })
    }
  },

  // 点击评述卡片 → 跳转评述详情
  onCritiqueTap(e) {
    const { author } = e.currentTarget.dataset
    if (!author) return
    wx.navigateTo({
      url: `/pages/critique-detail/critique-detail?author=${encodeURIComponent(author)}`,
    })
  },
})
