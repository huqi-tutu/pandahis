const { describe, it } = require('node:test')
const assert = require('node:assert/strict')
const { applyHighlightsToPlain, applyHighlightsToSegs } = require('../native-utils/note-highlight.js')
const { resolveNoteSourceNav, noteRemarkLabel, excerptText } = require('../native-utils/note.js')

describe('applyHighlightsToPlain', () => {
  it('marks selected sentence', () => {
    const segs = applyHighlightsToPlain('甲乙丙丁戊', [{ id: 7, selectedText: '乙丙' }])
    assert.deepEqual(
      segs.map((s) => ({ text: s.text, highlight: !!s.highlight, noteId: s.noteId || 0 })),
      [
        { text: '甲', highlight: false, noteId: 0 },
        { text: '乙丙', highlight: true, noteId: 7 },
        { text: '丁戊', highlight: false, noteId: 0 },
      ]
    )
  })

  it('keeps later overlapping note id', () => {
    const segs = applyHighlightsToPlain('ABCDEF', [
      { id: 1, selectedText: 'BCD' },
      { id: 2, selectedText: 'CDE' },
    ])
    const highlighted = segs.filter((s) => s.highlight)
    assert.ok(highlighted.some((s) => s.noteId === 2))
  })
})

describe('applyHighlightsToSegs', () => {
  it('preserves bold across highlight split', () => {
    const segs = applyHighlightsToSegs(
      [
        { text: '前', bold: false },
        { text: '加重', bold: true },
        { text: '后', bold: false },
      ],
      [{ id: 3, selectedText: '加重' }]
    )
    const mid = segs.find((s) => s.highlight)
    assert.equal(mid.text, '加重')
    assert.equal(mid.bold, true)
    assert.equal(mid.anchorId, 'note-hl-3')
  })
})

describe('note helpers', () => {
  it('shows 仅划线 when remark empty', () => {
    assert.equal(noteRemarkLabel(''), '仅划线')
    assert.equal(noteRemarkLabel('  记得  '), '记得')
  })

  it('excerpts long selected text', () => {
    assert.equal(excerptText('短句'), '短句')
    assert.equal(excerptText('一二三四五六七八九十'.repeat(10), 8).endsWith('…'), true)
  })

  it('routes box detail note back with noteId', () => {
    const nav = resolveNoteSourceNav({
      id: 9,
      sourceType: 'box_detail_selection',
      boxId: 'box_1',
      boxTitle: '乌台诗案',
      selectedText: '原文',
      sourceRefId: null,
    })
    assert.equal(nav.path, '/package-graph/pages/box-detail/index')
    assert.equal(nav.query.noteId, 9)
    assert.equal(nav.query.tab, 'content')
  })

  it('routes relation note to relations tab', () => {
    const nav = resolveNoteSourceNav({
      id: 4,
      sourceType: 'relation_graph_selection',
      boxId: 'box_1',
      boxTitle: '乌台诗案',
      selectedText: '苏轼',
      sourceRefId: null,
    })
    assert.equal(nav.query.tab, 'relations')
    assert.equal(nav.query.highlightName, '苏轼')
  })
})
