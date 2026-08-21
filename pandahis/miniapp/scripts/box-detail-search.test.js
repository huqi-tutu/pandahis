const { describe, it } = require('node:test')
const assert = require('node:assert/strict')
const {
  findKeywordMatches,
  splitSentenceSpans,
  buildExcerptAround,
  highlightExcerptSegs,
  searchDetailParagraphs,
  detailParaAnchorId,
} = require('../native-utils/box-detail-search.js')

describe('findKeywordMatches', () => {
  it('finds all non-overlapping hits', () => {
    assert.deepEqual(findKeywordMatches('甲乙甲乙甲', '甲乙'), [0, 2])
  })

  it('is case-insensitive for ascii', () => {
    assert.deepEqual(findKeywordMatches('AbCabc', 'abc'), [0, 3])
  })
})

describe('splitSentenceSpans', () => {
  it('keeps punctuation with previous sentence', () => {
    const spans = splitSentenceSpans('甲句。乙句！丙')
    assert.equal(spans.length, 3)
    assert.equal('甲句。乙句！丙'.slice(spans[0].start, spans[0].end), '甲句。')
    assert.equal('甲句。乙句！丙'.slice(spans[1].start, spans[1].end), '乙句！')
    assert.equal('甲句。乙句！丙'.slice(spans[2].start, spans[2].end), '丙')
  })
})

describe('buildExcerptAround', () => {
  it('takes one to two sentences around match', () => {
    const plain = '前文一句。命中关键词在此。后文一句。更后。'
    const start = plain.indexOf('关键词')
    const { excerpt } = buildExcerptAround(plain, start, '关键词'.length, 96)
    assert.match(excerpt, /命中关键词在此/)
    assert.ok(excerpt.length <= 98)
  })

  it('does not expand to three sentences', () => {
    const plain = '甲句。乙关键词。丙句。'
    const start = plain.indexOf('关键词')
    const { excerpt } = buildExcerptAround(plain, start, '关键词'.length, 96)
    assert.equal(excerpt.includes('甲句'), false)
    assert.match(excerpt, /乙关键词/)
    assert.match(excerpt, /丙句/)
  })

  it('truncates long sentence around match', () => {
    const plain = `${'前'.repeat(80)}关键词${'后'.repeat(80)}`
    const start = plain.indexOf('关键词')
    const { excerpt } = buildExcerptAround(plain, start, 3, 40)
    assert.ok(excerpt.includes('关键词'))
    assert.ok(excerpt.replace(/…/g, '').length <= 40)
  })
})

describe('highlightExcerptSegs', () => {
  it('marks keyword in excerpt', () => {
    const plain = '甲乙丙丁戊'
    const { excerpt, excerptStart } = buildExcerptAround(plain, 2, 1, 96)
    const segs = highlightExcerptSegs(plain, excerpt, excerptStart, '丙', 2)
    const hl = segs.filter((s) => s.hl).map((s) => s.text).join('')
    assert.equal(hl, '丙')
  })
})

describe('searchDetailParagraphs', () => {
  it('splits multiple hits in one paragraph into multiple rows', () => {
    const hits = searchDetailParagraphs(['一关键词。二关键词。'], '关键词')
    assert.equal(hits.length, 2)
    assert.equal(hits[0].paragraphIndex, 0)
    assert.equal(hits[1].hitIndex, 1)
  })

  it('caps result count', () => {
    const plain = Array.from({ length: 80 }, (_, i) => `第${i}次关键词。`).join('')
    const hits = searchDetailParagraphs([plain], '关键词', 96, 50)
    assert.equal(hits.length, 50)
  })

  it('returns empty for blank keyword', () => {
    assert.deepEqual(searchDetailParagraphs(['有字'], '  '), [])
  })
})

describe('detailParaAnchorId', () => {
  it('builds stable id', () => {
    assert.equal(detailParaAnchorId(3), 'detail-para-3')
  })
})
