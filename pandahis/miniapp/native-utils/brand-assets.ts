/** 品牌与分享配图（COS 公网 URL，避免打进小程序主包） */

/** 小程序正式品牌名（导航、关于、分享、海报等用户可见文案 SSOT） */
export const APP_DISPLAY_NAME = '时络历史'

const COS_ROOT = 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap'

/** 邀请好友分享卡片封面（线上 COS） */
export const INVITE_SHARE_COVER_URL = `${COS_ROOT}/share/invite-cover.jpg?v=2026080623`

/** 邀请页上卡纹理背景（线上 COS，不打进主包） */
export const INVITE_HERO_CARD_BG_URL = `${COS_ROOT}/invite/hero-card-bg.png?v=202608081540`

/** 品牌 logo（登录 / 关于等）：时络历史 · Chronos Thread */
export const BRAND_LOGO_URL = `${COS_ROOT}/brand/shiluo.png?v=202608081027`

/** 朗读浮层旋转封面 logo */
export const NARRATION_COVER_LOGO_URL = `${COS_ROOT}/brand/narration-cover.png?v=202608081207`

/** @deprecated 与 BRAND_LOGO_URL 相同，保留别名兼容旧引用 */
export const ABOUT_BRAND_LOGO_URL = BRAND_LOGO_URL
