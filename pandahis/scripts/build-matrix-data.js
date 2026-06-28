#!/usr/bin/env node
/**
 * 首页矩阵数据构建
 *
 * 展示条目以 小程序/数据/王朝表.json、帝王表.json 为准（与 home-matrix 一致）
 * 字段值从 data/政权.json、data/帝王.json 同步更新（新 ID、dynastyId 等）
 *
 * 用法：node scripts/build-matrix-data.js
 */
const fs = require('fs')
const path = require('path')

const ROOT = path.join(__dirname, '..')
const REGIME_SRC = path.join(ROOT, 'data', '政权.json')
const EMPEROR_SRC = path.join(ROOT, 'data', '帝王.json')
const MANIFEST_DYNASTY = path.join(ROOT, '小程序', '数据', '王朝表.json')
const MANIFEST_EMPEROR = path.join(ROOT, '小程序', '数据', '帝王表.json')

const OUTPUTS = [
  {
    dynasty: path.join(ROOT, 'miniapp', 'native-utils', 'matrix', 'dynasty-data.js'),
    emperor: path.join(ROOT, 'miniapp', 'native-utils', 'matrix', 'emperor-data.js'),
  },
  {
    dynasty: path.join(ROOT, '小程序', 'data', 'dynasty-data.js'),
    emperor: path.join(ROOT, '小程序', 'data', 'emperor-data.js'),
  },
]

function readJsonArray(file) {
  const text = fs.readFileSync(file, 'utf8').trim()
  if (!text) return []
  return JSON.parse(text)
}

/** 王朝表 / 帝王表：NDJSON 或 JSON 数组 */
function readManifest(file) {
  const text = fs.readFileSync(file, 'utf8').trim()
  if (!text) return []
  try {
    const parsed = JSON.parse(text)
    return Array.isArray(parsed) ? parsed : [parsed]
  } catch (e) {
    return text
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(Boolean)
      .map((line, i) => {
        try {
          return JSON.parse(line)
        } catch (err) {
          throw new Error(`${path.basename(file)} 第 ${i + 1} 行 JSON 解析失败：${err.message}`)
        }
      })
  }
}

function pick(row, ...keys) {
  for (const k of keys) {
    if (row[k] != null && row[k] !== '') return row[k]
  }
  return ''
}

function normalizeTag(raw) {
  if (raw == null || raw === '' || raw === '-') return ''
  return String(raw).trim()
}

function normYear(s) {
  return String(s || '').trim().replace(/^约/, '')
}

function regimeKey(r) {
  return `${String(r.name || '').trim()}|${String(r.civilization || '').trim()}|${normYear(r.start)}`
}

function emperorKey(e) {
  const regime = e.dynasty2 || e.dynasty || ''
  return `${String(e.name || '').trim()}|${String(regime).trim()}|${normYear(e.start)}`
}

function mapRegimeFromJson(row) {
  const id = pick(row, '政权ID', 'id', 'ID')
  const name = pick(row, '政权', 'name')
  const dynasty = pick(row, '朝代', 'dynasty')
  const out = {
    id,
    name,
    dynasty,
    dynastyId: pick(row, '朝代ID', 'dynastyId'),
    dynasty_zy: pick(row, 'dynasty_zy'),
    dynasty2: name,
    civilization: pick(row, '文明', 'civilization'),
    civilizationId: pick(row, '文明ID', 'civilizationId'),
    start: pick(row, '开始时间', 'start'),
    end: pick(row, '结束时间', 'end'),
  }
  const tag = normalizeTag(pick(row, '标签', 'tag'))
  if (tag) out.tag = tag
  return out
}

function mapRegimeFromManifest(row) {
  const legacyId = pick(row, 'ID', 'id')
  const name = pick(row, '政权', 'name')
  const dynasty = pick(row, '朝代', 'dynasty', '政权')
  const out = {
    id: legacyId,
    legacyId,
    name,
    dynasty,
    dynasty_zy: pick(row, 'dynasty_zy'),
    dynasty2: pick(row, 'dynasty2', '政权', '朝代', 'dynasty'),
    civilization: pick(row, '文明', 'civilization'),
    start: pick(row, '开始时间', 'start'),
    end: pick(row, '结束时间', 'end'),
  }
  const tag = normalizeTag(pick(row, '标签', 'tag'))
  if (tag) out.tag = tag
  return out
}

function mapEmperorFromJson(row) {
  const id = pick(row, '帝王ID', 'id', '历史盒子 ID', '历史盒子ID')
  const out = {
    id,
    name: pick(row, '帝王名称', '帝王', 'name'),
    dynasty: pick(row, '朝代', 'dynasty'),
    dynastyId: pick(row, '朝代ID', 'dynastyId'),
    dynasty2: pick(row, '政权', 'dynasty2'),
    regimeId: pick(row, '政权ID', 'regimeId'),
    civilization: pick(row, '文明', 'civilization'),
    civilizationId: pick(row, '文明ID', 'civilizationId'),
    originalName: pick(row, '帝王原名', 'originalName'),
    temple: pick(row, '庙号', 'temple'),
    era: pick(row, '年号', 'era'),
    start: pick(row, '即位时间', 'start'),
    end: pick(row, '退位时间', 'end'),
    years: pick(row, '在位时长', 'years'),
    importance: pick(row, '重要性评级', 'importance'),
  }
  const tag = normalizeTag(pick(row, '标签', 'tag'))
  if (tag) out.tag = tag
  return out
}

function mapEmperorFromManifest(row) {
  const legacyId = pick(row, '历史盒子 ID', '历史盒子ID', 'id')
  const out = {
    id: legacyId,
    legacyId,
    name: pick(row, '帝王', '帝王名字', 'name'),
    dynasty: pick(row, '朝代', 'dynasty'),
    dynasty2: pick(row, '政权', 'dynasty2'),
    start: pick(row, '即位时间', 'start'),
    end: pick(row, '退位时间', 'end'),
    years: pick(row, '在位时长', 'years'),
    temple: pick(row, '庙号', 'temple'),
    era: pick(row, '年号', 'era'),
    importance: pick(row, '重要性评级', 'importance'),
    civilization: pick(row, '文明', 'civilization'),
  }
  const tag = normalizeTag(pick(row, '标签', 'tag'))
  if (tag) out.tag = tag
  return out
}

function mergeManifestRegimes(manifestRows, regimeRaw) {
  const full = regimeRaw.map(mapRegimeFromJson).filter(d => d.id && d.name)
  const byKey = new Map()
  full.forEach(r => {
    byKey.set(regimeKey(r), r)
  })

  return manifestRows.map(row => {
    const base = mapRegimeFromManifest(row)
    const hit = byKey.get(regimeKey(base))
    if (!hit) return base

    return {
      ...hit,
      legacyId: base.legacyId || base.id,
      name: base.name || hit.name,
      dynasty: base.dynasty || hit.dynasty,
      dynasty_zy: base.dynasty_zy !== '' ? base.dynasty_zy : hit.dynasty_zy,
      dynasty2: base.dynasty2 || hit.dynasty2 || base.name,
      civilization: base.civilization || hit.civilization,
      start: base.start || hit.start,
      end: base.end || hit.end,
      tag: base.tag || hit.tag,
    }
  }).filter(d => d.id && d.name)
}

function mergeManifestEmperors(manifestRows, emperorRaw) {
  const full = emperorRaw.map(mapEmperorFromJson).filter(e => e.id && e.name)
  const byKey = new Map()
  const byLegacy = new Map()
  full.forEach(e => {
    byKey.set(emperorKey(e), e)
    if (e.id) byLegacy.set(e.id, e)
  })

  return manifestRows.map(row => {
    const base = mapEmperorFromManifest(row)
    const hit = byKey.get(emperorKey(base)) || byLegacy.get(base.legacyId || base.id)
    if (!hit) return base

    return {
      ...hit,
      legacyId: base.legacyId || base.id,
      name: base.name || hit.name,
      dynasty: base.dynasty || hit.dynasty,
      dynasty2: base.dynasty2 || hit.dynasty2,
      start: base.start || hit.start,
      end: base.end || hit.end,
      years: base.years || hit.years,
      temple: base.temple || hit.temple,
      era: base.era || hit.era,
      importance: base.importance || hit.importance,
      civilization: base.civilization || hit.civilization,
      tag: base.tag || hit.tag,
    }
  }).filter(e => e.id && e.name)
}

function writeModule(file, rows) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, 'module.exports = ' + JSON.stringify(rows) + '\n', 'utf8')
}

function main() {
  const regimeRaw = readJsonArray(REGIME_SRC)
  const emperorRaw = readJsonArray(EMPEROR_SRC)
  const manifestDyn = readManifest(MANIFEST_DYNASTY)
  const manifestEmp = readManifest(MANIFEST_EMPEROR)

  const dynasties = mergeManifestRegimes(manifestDyn, regimeRaw)
  const emperors = mergeManifestEmperors(manifestEmp, emperorRaw)

  OUTPUTS.forEach(({ dynasty, emperor }) => {
    writeModule(dynasty, dynasties)
    writeModule(emperor, emperors)
  })

  const dynMatched = dynasties.filter(d => d.dynastyId).length
  const empMatched = emperors.filter(e => e.dynastyId || e.regimeId).length
  const empWithTag = emperors.filter(e => e.tag).length

  console.log(`已写入矩阵数据：政权 ${dynasties.length} 条，帝王 ${emperors.length} 条`)
  console.log(`  清单来源：王朝表 ${manifestDyn.length} 条，帝王表 ${manifestEmp.length} 条`)
  console.log(`  已从 JSON  enrich：政权 ${dynMatched}，帝王 ${empMatched}`)
  console.log(`  帝王含标签 ${empWithTag} 条`)
}

main()
