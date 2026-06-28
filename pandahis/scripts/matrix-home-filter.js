/**
 * 首页矩阵展示用政权白名单逻辑。
 * 政权.json 含全量数据；首页只展示曾上线矩阵的条目（legacyId）+ 少量补列。
 */

/** 无 legacyId 但仍需上矩阵的政权 ID（布局依赖） */
const MATRIX_HOME_EXTRA_REGIME_IDS = new Set([
  'ZQ_HX_SANGUO_SANGUOWU', // 三国·吴
  'ZQ_HX_NANMING_NANMING', // 南明
])

/** JSON 脏数据 / 非首页条目，即使有 legacyId 也排除 */
const MATRIX_HOME_BLOCKED_REGIME_IDS = new Set([
  'ZQ_HX_CHUNQIU_ANXIDIGUOPATIYA', // 安息帝国：文明ID 与朝代错配
])

function isMatrixHomeRegime(record) {
  if (!record || !record.id || !record.name) return false
  if (MATRIX_HOME_BLOCKED_REGIME_IDS.has(record.id)) return false
  if (record.legacyId) return true
  if (MATRIX_HOME_EXTRA_REGIME_IDS.has(record.id)) return true
  return false
}

function filterMatrixHomeRegimes(records) {
  return (records || []).filter(isMatrixHomeRegime)
}

module.exports = {
  MATRIX_HOME_EXTRA_REGIME_IDS,
  MATRIX_HOME_BLOCKED_REGIME_IDS,
  isMatrixHomeRegime,
  filterMatrixHomeRegimes,
}
