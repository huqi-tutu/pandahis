#!/usr/bin/env node
/**
 * 批量：生图 → 上传 COS → 更新 historical_unit.card_image_url
 * 断点续跑：.tmp/unit-portrait/batch-progress.json
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import crypto from 'node:crypto'
import { createRequire } from 'node:module'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const PROJECT_NODE = path.resolve(__dirname, '..', '..', 'project', 'node_modules')
const COS = require(path.join(PROJECT_NODE, 'cos-nodejs-sdk-v5'))
const mysql = require(path.join(PROJECT_NODE, 'mysql2', 'promise'))
const ROOT = path.resolve(__dirname, '..')
const OUT_DIR = path.join(ROOT, '.tmp', 'unit-portrait')
const PROGRESS_FILE = path.join(OUT_DIR, 'batch-progress.json')
const LOCK_FILE = path.join(OUT_DIR, 'batch.lock')
const LOG_FILE = path.join(OUT_DIR, 'batch.log')
const COS_PREFIX = 'histomap/unit-portrait'

function acquireLock() {
  if (fs.existsSync(LOCK_FILE)) {
    const pid = Number(fs.readFileSync(LOCK_FILE, 'utf8').trim())
    try {
      process.kill(pid, 0)
      throw new Error(`Another batch is running (pid ${pid}). Stop it first.`)
    } catch (e) {
      if (e.code !== 'ESRCH' && !String(e.message || e).includes('Another batch')) throw e
      fs.unlinkSync(LOCK_FILE)
    }
  }
  fs.writeFileSync(LOCK_FILE, String(process.pid), 'utf8')
}

function releaseLock() {
  try {
    if (fs.existsSync(LOCK_FILE)) fs.unlinkSync(LOCK_FILE)
  } catch {
    /* ignore */
  }
}

function writeProgress(progress) {
  const tmp = `${PROGRESS_FILE}.${process.pid}.tmp`
  fs.writeFileSync(tmp, JSON.stringify(progress, null, 2), 'utf8')
  fs.renameSync(tmp, PROGRESS_FILE)
}

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`
  fs.appendFileSync(LOG_FILE, line, 'utf8')
  console.log(msg)
}

function readJson(p, fallback) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'))
  } catch {
    return fallback
  }
}

function loadMcpEnv() {
  const paths = [
    path.join(ROOT, '.cursor', 'mcp.json'),
    path.join(process.env.USERPROFILE || '', '.cursor', 'mcp.json'),
  ]
  const env = {}
  for (const p of paths) {
    if (!fs.existsSync(p)) continue
    const j = JSON.parse(fs.readFileSync(p, 'utf8'))
    for (const srv of Object.values(j.mcpServers || {})) {
      Object.assign(env, srv.env || {})
    }
  }
  return env
}

function hash12(unitId) {
  return crypto.createHash('sha1').update(unitId, 'utf8').digest('hex').slice(0, 12)
}

function yearLabel(y) {
  return y < 0 ? `${Math.abs(y)} BCE` : `${y} CE`
}

function buildPrompt(row) {
  const name = row.name || 'historical figure'
  const dynasty = (row.dynasty_name || '').trim()
  const ruler = (row.ruler_name || '').trim()
  const era = (row.era_name || '').trim()
  const sy = row.start_year
  const ey = row.end_year
  let period = ''
  if (sy != null && ey != null) period = `, active circa ${yearLabel(sy)} to ${yearLabel(ey)}`
  const ctx = dynasty || era || 'ancient world history'
  const title = ruler && ruler !== name ? ruler : name
  return (
    `Scholarly portrait of ${title} (${ctx} historical figure)${period}. ` +
    'Historical atlas illustration style, warm parchment palette, half-body dignified pose, ' +
    'traditional ceremonial dress appropriate to era and culture, soft painterly brushwork, ' +
    'museum educational tone, no text, no watermark, no modern objects, square composition.'
  )
}

function stripV1(baseUrl) {
  return baseUrl.replace(/\/+$/, '').replace(/\/v1$/, '')
}

function mapAspectRatio() {
  return '1:1'
}

async function pollForImage(apiKey, baseUrl, resultUrl, timeoutMs = 300000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const res = await fetch(resultUrl, {
      headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    })
    const ct = res.headers.get('content-type') || ''
    if (ct.includes('image/')) return Buffer.from(await res.arrayBuffer())
    const json = await res.json()
    const outs = json?.data?.outputs
    if (Array.isArray(outs) && outs[0]) {
      const o = outs[0]
      if (typeof o === 'string' && o.startsWith('iVBOR')) return Buffer.from(o, 'base64')
      if (typeof o === 'string' && o.startsWith('http')) {
        const img = await fetch(o)
        return Buffer.from(await img.arrayBuffer())
      }
    }
    const b64 = json?.data?.[0]?.b64_json
    if (b64) return Buffer.from(b64, 'base64')
    const st = json?.data?.status || json?.status
    if (st && ['failed', 'error', 'canceled'].includes(String(st).toLowerCase())) {
      throw new Error(`gen failed: ${st}`)
    }
    await new Promise((r) => setTimeout(r, 800))
  }
  throw new Error('poll timeout')
}

async function generateImage({ text, outputPath, env }) {
  const baseUrl = env.OPENAI_BASE_URL || env.OPENAI_API_BASE || ''
  const apiKey = env.OPENAI_API_KEY || ''
  const model = env.OPENAI_IMAGE_MODEL || 'gpt-image-2'
  const url = `${stripV1(baseUrl)}/api/v3/openai/${encodeURIComponent(model)}/text-to-image`
  const res = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: text, aspect_ratio: mapAspectRatio(), output_format: 'png' }),
  })
  if (!res.ok) throw new Error(`gen HTTP ${res.status}: ${await res.text()}`)
  const json = await res.json()
  const b64 = json?.data?.[0]?.b64_json
  let buf
  if (b64) buf = Buffer.from(b64, 'base64')
  else {
    const imgUrl = json?.data?.[0]?.url || json?.url
    const resultUrl = json?.data?.urls?.get || json?.urls?.get
    if (imgUrl) {
      const imgRes = await fetch(imgUrl)
      buf = Buffer.from(await imgRes.arrayBuffer())
    } else if (resultUrl) buf = await pollForImage(apiKey, baseUrl, resultUrl)
    else throw new Error('no image in response')
  }
  fs.mkdirSync(path.dirname(outputPath), { recursive: true })
  fs.writeFileSync(outputPath, buf)
  return outputPath
}

function makeCos(env) {
  return new COS({ SecretId: env.COS_SECRET_ID, SecretKey: env.COS_SECRET_KEY })
}

async function uploadCos(cos, env, filePath, key) {
  const Bucket = env.COS_BUCKET
  const Region = env.COS_REGION
  const base = (env.COS_BASE_URL || '').replace(/\/+$/, '')
  await cos.putObject({
    Bucket,
    Region,
    Key: key,
    Body: fs.createReadStream(filePath),
    ContentType: 'image/png',
  })
  return `${base}/${key.replace(/^\/+/, '')}`
}

async function fetchPendingUnits(conn) {
  const [rows] = await conn.execute(
    `SELECT id, name, ruler_name, dynasty_name, era_name, start_year, end_year, civilization_l1_id
     FROM historical_unit WHERE status=1
     AND (card_image_url IS NULL OR TRIM(card_image_url)='' OR card_image_url NOT LIKE 'http%')
     ORDER BY civilization_l1_id, start_year`
  )
  return rows
}

async function syncDoneFromDb(conn, progress) {
  const [rows] = await conn.execute(
    `SELECT id, name, card_image_url FROM historical_unit
     WHERE status=1 AND card_image_url LIKE 'http%'`
  )
  for (const r of rows) {
    progress.done[r.id] = {
      url: r.card_image_url,
      name: r.name,
      at: progress.done[r.id]?.at || 'db-sync',
    }
    delete progress.failed[r.id]
  }
  writeProgress(progress)
}

async function main() {
  acquireLock()
  const env = loadMcpEnv()
  const delayMs = Number(process.env.PORTRAIT_BATCH_DELAY_MS || 2000)
  const limit = process.env.PORTRAIT_BATCH_LIMIT ? Number(process.env.PORTRAIT_BATCH_LIMIT) : null

  fs.mkdirSync(OUT_DIR, { recursive: true })
  const progress = readJson(PROGRESS_FILE, { done: {}, failed: {} })

  const conn = await mysql.createConnection({
    host: env.MYSQL_HOST || '49.235.165.220',
    port: Number(env.MYSQL_PORT || 3306),
    user: env.MYSQL_USER || 'histomap',
    password: env.MYSQL_PASS || env.MYSQL_PASSWORD || 'change-me',
    database: env.MYSQL_DB || 'histomap',
    charset: 'utf8mb4',
  })

  const cos = makeCos(env)
  await syncDoneFromDb(conn, progress)
  let units = await fetchPendingUnits(conn)
  if (limit) units = units.slice(0, limit)

  log(`pending=${units.length} already_done=${Object.keys(progress.done).length}`)

  let processed = 0
  for (const row of units) {
    const unitId = row.id
    if (progress.done[unitId]) continue

    const h = hash12(unitId)
    const localPath = path.join(OUT_DIR, `${h}.png`)
    const cosKey = `${COS_PREFIX}/${h}.png`
    const prompt = buildPrompt(row)

    const maxAttempts = 3
    let ok = false
    for (let attempt = 1; attempt <= maxAttempts && !ok; attempt++) {
      try {
        log(`[${processed + 1}/${units.length}] ${row.name} attempt ${attempt}/${maxAttempts}`)
        if (attempt > 1 && fs.existsSync(localPath)) fs.unlinkSync(localPath)
        if (!fs.existsSync(localPath)) {
          await generateImage({ text: prompt, outputPath: localPath, env })
        }
        const url = await uploadCos(cos, env, localPath, cosKey)
        await conn.execute('UPDATE historical_unit SET card_image_url=? WHERE id=?', [url, unitId])
        progress.done[unitId] = { url, name: row.name, at: new Date().toISOString() }
        delete progress.failed[unitId]
        writeProgress(progress)
        processed++
        ok = true
        await new Promise((r) => setTimeout(r, delayMs))
      } catch (e) {
        if (fs.existsSync(localPath)) {
          try {
            fs.unlinkSync(localPath)
          } catch {
            /* ignore */
          }
        }
        if (attempt === maxAttempts) {
          progress.failed[unitId] = { error: String(e.message || e), name: row.name, at: new Date().toISOString() }
          writeProgress(progress)
          log(`FAIL ${row.name}: ${e.message || e}`)
          await new Promise((r) => setTimeout(r, 5000))
        } else {
          log(`retry ${row.name}: ${e.message || e}`)
          await new Promise((r) => setTimeout(r, 4000))
        }
      }
    }
  }

  await conn.end()
  log(`finished processed=${processed} total_done=${Object.keys(progress.done).length}`)
  releaseLock()
}

main().catch((e) => {
  log(`fatal: ${e.stack || e}`)
  releaseLock()
  process.exit(1)
})
