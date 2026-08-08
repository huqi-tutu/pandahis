const { describe, it } = require('node:test')
const assert = require('node:assert/strict')
const {
  toLocalDateKey,
  formatDateSectionLabel,
  formatClockTime,
  groupByDateKey,
  appendGroupedItems,
} = require('../native-utils/date-grouped-list.js')

describe('date-grouped-list', () => {
  it('formats section labels', () => {
    const now = new Date(2026, 7, 5, 12, 0, 0)
    assert.equal(formatDateSectionLabel('2026-08-05', now), '今天')
    assert.equal(formatDateSectionLabel('2026-08-04', now), '昨天')
    assert.equal(formatDateSectionLabel('2026-07-01', now), '7月1日')
    assert.equal(formatDateSectionLabel('2025-12-01', now), '2025年12月1日')
  })

  it('groups and merges by date', () => {
    const page1 = [
      { boxId: 'a', at: '2026-08-05T10:00:00+08:00' },
      { boxId: 'b', at: '2026-08-05T09:00:00+08:00' },
      { boxId: 'c', at: '2026-08-04T20:00:00+08:00' },
    ]
    const groups = groupByDateKey(page1, (x) => x.at)
    assert.equal(groups.length, 2)
    assert.equal(groups[0].items.length, 2)
    assert.equal(toLocalDateKey(page1[0].at), groups[0].dateKey)

    const page2 = [
      { boxId: 'd', at: '2026-08-04T08:00:00+08:00' },
      { boxId: 'e', at: '2026-08-03T08:00:00+08:00' },
    ]
    const merged = appendGroupedItems(groups, page2, (x) => x.at, (x) => x.boxId)
    assert.equal(merged.length, 3)
    assert.equal(merged[1].items.map((x) => x.boxId).join(','), 'c,d')
    assert.equal(formatClockTime('2026-08-05T10:05:00+08:00'), '10:05')
  })
})
