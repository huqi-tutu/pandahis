const { loadMatrixData } = require('./mock-home-matrix.js')

/** 生产环境无云函数：直接使用本地 bundled 王朝/帝王数据 */
function fetchHomeMatrixData() {
  return Promise.resolve({ source: 'local' })
}

module.exports = {
  fetchHomeMatrixData,
  loadMatrixData,
}
