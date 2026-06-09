const fs = require('fs')
const path = process.argv[2]
if (!path) {
  console.error('usage: node fix-scss-bom.js <file>')
  process.exit(1)
}
let s = fs.readFileSync(path, 'utf8')
if (s.charCodeAt(0) === 0xfeff) s = s.slice(1)
s = s.replace(/^@import\s+['"]\.\.\/\.\.\/styles\/atlas\.wxss['"];\s*\n+/, '')
if (!s.includes('.muted {')) {
  s = `/* home-matrix + home-overview (product 1:1) */\n\n.muted { color: #8A8A8A; }\n\n${s}`
}
fs.writeFileSync(path, s, 'utf8')
const head = fs.readFileSync(path).slice(0, 4)
console.log('bom_removed', head[0] !== 0xef, 'head', head.toString('hex'))
