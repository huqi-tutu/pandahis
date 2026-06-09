const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const db = cloud.database()

const COL_DYNASTIES = 'atlas_dynasties'
const COL_EMPERORS = 'atlas_emperors'
const BATCH = 40

async function clearCollection(name) {
  const { total } = await db.collection(name).count()
  if (!total) return 0

  let removed = 0
  while (removed < total) {
    const { data } = await db.collection(name).limit(BATCH).get()
    if (!data.length) break
    await Promise.all(data.map(row => db.collection(name).doc(row._id).remove()))
    removed += data.length
  }
  return removed
}

exports.main = async () => {
  try {
    const [dynastyRemoved, emperorRemoved] = await Promise.all([
      clearCollection(COL_DYNASTIES),
      clearCollection(COL_EMPERORS),
    ])

    const [dynastyLeft, emperorLeft] = await Promise.all([
      db.collection(COL_DYNASTIES).count(),
      db.collection(COL_EMPERORS).count(),
    ])

    return {
      code: 0,
      message: 'ok',
      data: {
        removed: {
          dynasties: dynastyRemoved,
          emperors: emperorRemoved,
        },
        remaining: {
          dynasties: dynastyLeft.total,
          emperors: emperorLeft.total,
        },
        clearedAt: Date.now(),
      },
    }
  } catch (err) {
    console.error('[clearHomeMatrixData]', err)
    return {
      code: -1,
      message: err.message || '清空失败',
    }
  }
}
