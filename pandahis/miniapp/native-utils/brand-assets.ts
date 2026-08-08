/** 品牌与分享配图（COS 公网 URL，避免打进小程序主包） */

const COS_ROOT = 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap'

/** 邀请好友分享卡片封面（线上 COS） */
export const INVITE_SHARE_COVER_URL = `${COS_ROOT}/share/invite-cover.jpg?v=2026080623`

/** 品牌 logo（登录 / 关于等）：时络历史 · Chronos Thread */
export const BRAND_LOGO_URL = `${COS_ROOT}/brand/shiluo.png?v=202608081027`

/** @deprecated 与 BRAND_LOGO_URL 相同，保留别名兼容旧引用 */
export const ABOUT_BRAND_LOGO_URL = BRAND_LOGO_URL
