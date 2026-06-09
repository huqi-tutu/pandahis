#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const mysql = require(path.join(__dirname, '..', '..', 'project', 'node_modules', 'mysql2', 'promise'))
const ROOT = path.resolve(__dirname, '..')

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

async function main() {
  const sqlFile = process.argv[2]
  if (!sqlFile) {
    console.error('Usage: node run_sql_migration.mjs <sql-file>')
    process.exit(1)
  }
  const env = loadMcpEnv()
  const sql = fs.readFileSync(sqlFile, 'utf8')
  const conn = await mysql.createConnection({
    host: env.MYSQL_HOST || '127.0.0.1',
    port: Number(env.MYSQL_PORT || 3306),
    user: env.MYSQL_USER,
    password: env.MYSQL_PASS || env.MYSQL_PASSWORD || '',
    database: env.MYSQL_DB,
    multipleStatements: true,
  })
  try {
    await conn.query(sql)
    const [rows] = await conn.query(
      'SELECT id, code, display_name, sort_order FROM civilization_l1 WHERE status=1 ORDER BY sort_order'
    )
    console.log('civilization_l1 count:', rows.length)
    console.table(rows)
  } finally {
    await conn.end()
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
