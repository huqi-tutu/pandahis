const fs = require('fs')
const path = require('path')

const dataDir = path.join(__dirname, '..', '数据')

function readRecords(name) {
  const p = path.join(dataDir, name)
  const text = fs.readFileSync(p, 'utf8').trim()
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
          throw new Error(`${name} 第 ${i + 1} 行 JSON 解析失败：${err.message}`)
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

function mapDynasty(row) {
  const id = pick(row, 'id', 'ID', 'Id')
  const dynasty = pick(row, 'dynasty', '朝代', '政权')
  const name = pick(row, 'name', '政权', '朝代', 'dynasty')
  const tag = normalizeTag(pick(row, 'tag', '标签'))
  const out = {
    id,
    name,
    dynasty,
    dynasty_zy: pick(row, 'dynasty_zy', 'dynasty_zy'),
    dynasty2: pick(row, 'dynasty2', '朝代', 'dynasty', '政权'),
    civilization: pick(row, 'civilization', '文明'),
    start: pick(row, 'start', '开始时间'),
    end: pick(row, 'end', '结束时间'),
  }
  if (tag) out.tag = tag
  return out
}

function mapEmperor(row) {
  const id = pick(row, 'id', '历史盒子 ID', '历史盒子ID')
  const tag = normalizeTag(pick(row, 'tag', '标签'))
  const out = {
    id,
    name: pick(row, 'name', '帝王', '帝王名字'),
    dynasty: pick(row, 'dynasty', '朝代'),
    dynasty2: pick(row, 'dynasty2', '政权'),
    start: pick(row, 'start', '即位时间'),
    end: pick(row, 'end', '退位时间'),
    years: pick(row, 'years', '在位时长'),
    temple: pick(row, 'temple', '庙号'),
    era: pick(row, 'era', '年号'),
    importance: pick(row, 'importance', '重要性评级'),
  }
  if (tag) out.tag = tag
  return out
}

function loadMatrixRecords() {
  const dynasties = readRecords('王朝表.json').map(mapDynasty).filter(d => d.id)
  const emperors = readRecords('帝王表.json').map(mapEmperor).filter(e => e.id)
  return { dynasties, emperors }
}

module.exports = {
  loadMatrixRecords,
  mapDynasty,
  mapEmperor,
}
