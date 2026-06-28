#!/usr/bin/env node
/**
 * 从 data/政权.json、data/帝王.json 生成本地 data/*.js（小程序写死数据源）
 * 推荐统一使用：node scripts/build-matrix-data.js
 * 用法：node scripts/build-local-matrix-data.js
 */
const fs = require('fs')
const path = require('path')
const { loadMatrixRecords } = require('./parse-matrix-json.js')

const root = path.join(__dirname, '..')
const { dynasties, emperors } = loadMatrixRecords()

function writeModule(file, rows) {
  const content = 'module.exports = ' + JSON.stringify(rows) + '\n'
  fs.writeFileSync(path.join(root, 'data', file), content, 'utf8')
}

writeModule('dynasty-data.js', dynasties)
writeModule('emperor-data.js', emperors)

const empWithTag = emperors.filter(e => e.tag).length
console.log(`已写入本地数据：王朝 ${dynasties.length} 条，帝王 ${emperors.length} 条（含 tag ${empWithTag} 条）`)
