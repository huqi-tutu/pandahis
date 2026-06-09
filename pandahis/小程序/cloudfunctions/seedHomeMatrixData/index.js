const cloud = require('wx-server-sdk')

let dynasties = []
let emperors = []
try {
  dynasties = require('./seed/dynasties.json')
  emperors = require('./seed/emperors.json')
} catch (err) {
  console.error('[seedHomeMatrixData] 读取 seed 失败', err)
}

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const db = cloud.database()

const COL_DYNASTIES = 'atlas_dynasties'
const COL_EMPERORS = 'atlas_emperors'
const BATCH = 20

function docId(raw, index, prefix) {
  const id = raw && raw.id ? String(raw.id).trim() : ''
  if (id) return id
  return `${prefix}_${index}`
}

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

async function upsertBatch(collectionName, rows, prefix) {
  let ok = 0
  const errors = []

  for (let i = 0; i < rows.length; i += BATCH) {
    const slice = rows.slice(i, i + BATCH)
    const results = await Promise.allSettled(slice.map((row, j) => {
      const _id = docId(row, i + j, prefix)
      const payload = Object.assign({}, row, { id: row.id || _id })
      return db.collection(collectionName).doc(_id).set({ data: payload })
    }))

    results.forEach((r, idx) => {
      if (r.status === 'fulfilled') {
        ok += 1
      } else {
        errors.push({
          index: i + idx,
          id: docId(slice[idx], i + idx, prefix),
          message: (r.reason && r.reason.message) || String(r.reason),
        })
      }
    })
  }

  return { ok, errors }
}

async function countCollection(name) {
  const { total } = await db.collection(name).count()
  return total || 0
}

exports.main = async (event) => {
  const clear = !!(event && event.clear)
  const clearOnly = !!(event && event.clearOnly)

  if (!clearOnly && (!dynasties.length || !emperors.length)) {
    return {
      code: 1,
      message: 'seed 文件为空或未随云函数部署。请本地运行 node scripts/build-cloud-seed-json.js 后，重新「上传并部署：云端安装依赖」',
      data: {
        seedLocal: { dynasties: dynasties.length, emperors: emperors.length },
      },
    }
  }

  try {
    let cleared = { dynasties: 0, emperors: 0 }
    if (clear || clearOnly) {
      cleared.dynasties = await clearCollection(COL_DYNASTIES)
      cleared.emperors = await clearCollection(COL_EMPERORS)
    }

    if (clearOnly) {
      return {
        code: 0,
        message: 'cleared only',
        data: {
          cleared,
          remaining: {
            dynasties: await countCollection(COL_DYNASTIES),
            emperors: await countCollection(COL_EMPERORS),
          },
          clearedAt: Date.now(),
        },
      }
    }

    const dynastyResult = await upsertBatch(COL_DYNASTIES, dynasties, 'dyn')
    const emperorResult = await upsertBatch(COL_EMPERORS, emperors, 'emp')

    const remaining = {
      dynasties: await countCollection(COL_DYNASTIES),
      emperors: await countCollection(COL_EMPERORS),
    }

    const hasError = dynastyResult.errors.length || emperorResult.errors.length
    const success = remaining.dynasties > 0 && remaining.emperors > 0

    return {
      code: success ? 0 : -1,
      message: success
        ? 'seed ok'
        : '写入失败或云库仍为空，请查看 errors 并重试（勿先用 clearOnly）',
      data: {
        cleared,
        seedSource: { dynasties: dynasties.length, emperors: emperors.length },
        written: {
          dynasties: dynastyResult.ok,
          emperors: emperorResult.ok,
        },
        remaining,
        errors: {
          dynasties: dynastyResult.errors.slice(0, 5),
          emperors: emperorResult.errors.slice(0, 5),
        },
        hasMoreErrors: dynastyResult.errors.length + emperorResult.errors.length > 5,
        seededAt: Date.now(),
      },
    }
  } catch (err) {
    console.error('[seedHomeMatrixData]', err)
    return {
      code: -1,
      message: err.message || '导入失败',
      data: {
        remaining: {
          dynasties: await countCollection(COL_DYNASTIES).catch(() => 0),
          emperors: await countCollection(COL_EMPERORS).catch(() => 0),
        },
      },
    }
  }
}
