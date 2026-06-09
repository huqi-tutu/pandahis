#!/usr/bin/env node
/**
 * 从 数据/*.json 生成云函数 seed（可选，首页已改回本地写死）
 */
const fs = require('fs')
const path = require('path')
const { loadMatrixRecords } = require('./parse-matrix-json.js')

const outDir = path.join(__dirname, '..', 'cloudfunctions/seedHomeMatrixData/seed')
const { dynasties, emperors } = loadMatrixRecords()

fs.mkdirSync(outDir, { recursive: true })
fs.writeFileSync(path.join(outDir, 'dynasties.json'), JSON.stringify(dynasties, null, 0))
fs.writeFileSync(path.join(outDir, 'emperors.json'), JSON.stringify(emperors, null, 0))

const empWithTag = emperors.filter(e => e.tag).length
console.log(`已写入 seed：王朝 ${dynasties.length} 条，帝王 ${emperors.length} 条（含 tag ${empWithTag} 条）`)
