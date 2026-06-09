const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const db = cloud.database()
const PAGE_SIZE = 100

async function fetchAll(collectionName) {
  const { total } = await db.collection(collectionName).count()
  if (!total) return []

  const pages = Math.ceil(total / PAGE_SIZE)
  const tasks = []
  for (let i = 0; i < pages; i++) {
    tasks.push(
      db.collection(collectionName)
        .skip(i * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .get()
    )
  }
  const results = await Promise.all(tasks)
  return results.flatMap(r => r.data)
}

exports.main = async () => {
  try {
    const [dynasties, emperors] = await Promise.all([
      fetchAll('atlas_dynasties'),
      fetchAll('atlas_emperors'),
    ])

    if (!dynasties.length || !emperors.length) {
      return {
        code: 1,
        message: '云数据库为空，请先运行 seedHomeMatrixData 导入数据',
        data: null,
      }
    }

    return {
      code: 0,
      message: 'ok',
      data: { dynasties, emperors },
      meta: {
        dynastyCount: dynasties.length,
        emperorCount: emperors.length,
        fetchedAt: Date.now(),
      },
    }
  } catch (err) {
    console.error('[getHomeMatrixData]', err)
    return {
      code: -1,
      message: err.message || '获取首页数据失败',
      data: null,
    }
  }
}
