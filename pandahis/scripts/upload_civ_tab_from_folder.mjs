#!/usr/bin/env node
/**
 * 批量上传 .tmp/civ-tab-import/{CODE}.png → COS histomap/civ-tab/{CODE}.png
 * 复用 portrait_batch_pipeline 的 MCP env 加载与 COS SDK。
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const PROJECT_NODE = path.resolve(__dirname, '..', '..', 'project', 'node_modules')
const COS = require(path.join(PROJECT_NODE, 'cos-nodejs-sdk-v5'))
const ROOT = path.resolve(__dirname, '..')
const STAGE_DIR = path.join(ROOT, '.tmp', 'civ-tab-import')
const MANIFEST = path.join(STAGE_DIR, 'manifest.json')
const UPLOAD_MANIFEST = path.join(STAGE_DIR, 'upload-manifest.json')
const COS_PREFIX = 'histomap/civ-tab'

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

async function main() {
  const env = loadMcpEnv()
  if (!env.COS_SECRET_ID || !env.COS_BUCKET) {
    console.error('Missing COS credentials in .cursor/mcp.json')
    process.exit(1)
  }
  if (!fs.existsSync(MANIFEST)) {
    console.error('Run: python scripts/stage_civ_tab_import.py')
    process.exit(1)
  }
  const items = JSON.parse(fs.readFileSync(MANIFEST, 'utf8'))
  const cos = makeCos(env)
  const results = []
  for (const item of items) {
    const local = path.join(STAGE_DIR, item.stagedFile)
    if (!fs.existsSync(local)) {
      console.error(`Missing staged file: ${local}`)
      process.exit(1)
    }
    const key = item.cosKey || `${COS_PREFIX}/${item.code}.png`
    const url = await uploadCos(cos, env, local, key)
    console.log(`Uploaded ${item.code} -> ${url}`)
    results.push({ ...item, url, uploadedAt: new Date().toISOString() })
  }
  fs.writeFileSync(UPLOAD_MANIFEST, JSON.stringify(results, null, 2), 'utf8')
  console.log(`Wrote ${UPLOAD_MANIFEST}`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
