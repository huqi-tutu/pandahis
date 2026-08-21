const { describe, it } = require('node:test')
const assert = require('node:assert/strict')
const { resolveCorrectionSourceNav } = require('../native-utils/correction.js')

describe('resolveCorrectionSourceNav', () => {
  it('routes dynasty_canvas to dynasty detail', () => {
    const nav = resolveCorrectionSourceNav({
      sourceType: 'dynasty_canvas',
      unitId: 'dyn_song',
      dynastyName: '北宋',
      boxId: 'box_1',
      boxTitle: '史略',
      sourceRefId: null,
    })
    assert.equal(nav.path, '/pages/dynasty-detail/index')
    assert.equal(nav.query.unitId, 'dyn_song')
  })

  it('routes box_detail_selection to box detail', () => {
    const nav = resolveCorrectionSourceNav({
      sourceType: 'box_detail_selection',
      boxId: 'box_1',
      boxTitle: '乌台诗案',
      unitId: null,
      sourceRefId: null,
      dynastyName: '',
    })
    assert.equal(nav.path, '/package-graph/pages/box-detail/index')
    assert.equal(nav.query.boxId, 'box_1')
  })

  it('routes critique with sourceRefId', () => {
    const nav = resolveCorrectionSourceNav({
      sourceType: 'critique_detail_selection',
      boxId: 'box_1',
      boxTitle: '乌台诗案',
      unitId: null,
      sourceRefId: 12,
      dynastyName: '',
    })
    assert.equal(nav.path, '/pages/critique-detail/index')
    assert.equal(nav.query.critiqueId, 12)
  })

  it('routes relic with sourceRefId', () => {
    const nav = resolveCorrectionSourceNav({
      sourceType: 'relic_detail_selection',
      boxId: 'box_1',
      boxTitle: '乌台诗案',
      unitId: null,
      sourceRefId: 9,
      dynastyName: '',
    })
    assert.equal(nav.path, '/pages/relic-detail/index')
    assert.equal(nav.query.relicId, 9)
  })

  it('routes relation_graph_selection to box detail', () => {
    const nav = resolveCorrectionSourceNav({
      sourceType: 'relation_graph_selection',
      boxId: 'box_1',
      boxTitle: '乌台诗案',
      unitId: null,
      sourceRefId: null,
      dynastyName: '',
    })
    assert.equal(nav.path, '/package-graph/pages/box-detail/index')
    assert.equal(nav.query.boxId, 'box_1')
  })

  it('routes box_original_selection to box detail original sheet', () => {
    const nav = resolveCorrectionSourceNav({
      sourceType: 'box_original_selection',
      boxId: 'box_1',
      boxTitle: '汉武帝',
      unitId: null,
      sourceRefId: null,
      dynastyName: '',
    })
    assert.equal(nav.path, '/package-graph/pages/box-detail/index')
    assert.equal(nav.query.boxId, 'box_1')
    assert.equal(nav.query.openOriginal, '1')
  })

  it('errors when critique sourceRefId missing', () => {
    const nav = resolveCorrectionSourceNav({
      sourceType: 'critique_detail_selection',
      boxId: 'box_1',
      boxTitle: '乌台诗案',
      unitId: null,
      sourceRefId: null,
      dynastyName: '',
    })
    assert.ok(nav.error)
  })
})
