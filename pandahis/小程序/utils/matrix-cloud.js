const { loadMatrixData } = require('../data/mock-home-matrix.js')
const cloudEnv = require('../config/cloud.env.js')

const ENV_PLACEHOLDER = 'YOUR_ENV_ID'

function isCloudReady() {
  return !!(wx.cloud && cloudEnv.envId && cloudEnv.envId !== ENV_PLACEHOLDER)
}

/**
 * 从云函数拉取王朝 / 帝王数据并注入矩阵引擎
 * @returns {Promise<{source:'cloud'|'local', meta?:object, error?:string}>}
 */
function fetchHomeMatrixData() {
  if (!isCloudReady()) {
    return Promise.resolve({ source: 'local', error: 'cloud_not_configured' })
  }

  return wx.cloud.callFunction({ name: 'getHomeMatrixData' })
    .then(res => {
      const result = res && res.result
      if (result && result.code === 0 && result.data) {
        const { dynasties, emperors } = result.data
        if (Array.isArray(dynasties) && Array.isArray(emperors) &&
            dynasties.length > 0 && emperors.length > 0) {
          loadMatrixData(dynasties, emperors)
          return { source: 'cloud', meta: result.meta }
        }
      }
      const msg = (result && result.message) || 'empty_cloud_data'
      console.warn('[matrix-cloud]', msg)
      return { source: 'local', error: msg }
    })
    .catch(err => {
      console.warn('[matrix-cloud] 拉取失败，使用本地数据', err)
      return { source: 'local', error: err.errMsg || err.message || 'cloud_call_failed' }
    })
}

module.exports = {
  isCloudReady,
  fetchHomeMatrixData,
}
