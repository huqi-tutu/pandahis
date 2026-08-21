const test = require('node:test')
const assert = require('node:assert/strict')

function chunkTextForTts(text, maxLen = 450) {
  const normalized = String(text || '')
    .replace(/\r\n/g, '\n')
    .replace(/[#*_`>\[\]()]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!normalized) return []

  const parts = []
  let seg = ''
  for (const ch of normalized) {
    seg += ch
    if ('。！？；\n'.includes(ch)) {
      const t = seg.trim()
      if (t) parts.push(t)
      seg = ''
    }
  }
  const tail = seg.trim()
  if (tail) parts.push(tail)

  const out = []
  let buf = ''
  const flush = () => {
    if (buf.trim()) out.push(buf.trim())
    buf = ''
  }
  for (const part of parts) {
    if (part.length > maxLen) {
      flush()
      for (let i = 0; i < part.length; i += maxLen) {
        out.push(part.slice(i, i + maxLen))
      }
      continue
    }
    if (buf.length + part.length <= maxLen) {
      buf += part
    } else {
      flush()
      buf = part
    }
  }
  flush()
  return out
}

test('WechatSI mode uses 50-char chunks', () => {
  const text = '甲'.repeat(120) + '。'
  const parts = chunkTextForTts(text, 50)
  assert.ok(parts.length >= 3)
  for (const c of parts) {
    assert.ok(c.length <= 50, `chunk too long: ${c.length}`)
  }
})

test('backend mode uses 450-char chunks', () => {
  const long = '甲'.repeat(900) + '。'
  const chunks = chunkTextForTts(long, 450)
  assert.ok(chunks.length >= 2)
  for (const c of chunks) {
    assert.ok(c.length <= 450)
  }
})
