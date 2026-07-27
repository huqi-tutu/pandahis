import { hasToken, request } from '../../native-utils/api'

/** 最近一年阅读足迹热力图：7 行（周一~周日）× 52 列（周），最近一周在最左 */

const WEEK_COUNT = 52
const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日']

/** 苔绿 #7D8A6A：1–30 篇等比渐变，30 篇达到最深色 */
const TEA_GREEN = { r: 125, g: 138, b: 106 }
const HEAT_MAX_COUNT = 30
const HEAT_ALPHA_MIN = 0.12
const HEAT_ALPHA_RANGE = 0.88

function heatCellColor(count: number): string {
  if (count <= 0) return ''
  const ratio = Math.min(count, HEAT_MAX_COUNT) / HEAT_MAX_COUNT
  const a = HEAT_ALPHA_MIN + ratio * HEAT_ALPHA_RANGE
  const mix = (c: number) => Math.round(c * a + 255 * (1 - a))
  return `rgb(${mix(TEA_GREEN.r)}, ${mix(TEA_GREEN.g)}, ${mix(TEA_GREEN.b)})`
}

const HEATMAP_ICONS = {
  A: '/配图/icons/a.png',
  B: '/配图/icons/b.png',
  C: '/配图/icons/c.png',
  D: '/配图/icons/d.png',
} as const

type ReadingTier = keyof typeof HEATMAP_ICONS

function readingTier(count: number): ReadingTier {
  if (count === 0) return 'D'
  if (count <= 5) return 'C'
  if (count <= 15) return 'B'
  return 'A'
}

function buildSelected(dateStr: string, count: number) {
  const tier = readingTier(count)
  return {
    label: detailLabel(dateStr),
    count,
    icon: HEATMAP_ICONS[tier],
    sub: count === 0 ? '一篇没读还有脸看' : `这一天读过 ${count} 篇`,
  }
}

type HeatCell = {
  date: string
  count: number
  color: string
  future: boolean
}

type HeatWeek = {
  monthLabel: string
  cells: HeatCell[]
}

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

function fmtDate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

/** 周一为一周的第一天：周一=0 … 周日=6 */
function mondayIndex(d: Date): number {
  return (d.getDay() + 6) % 7
}

function detailLabel(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number)
  const day = new Date(y, m - 1, d)
  return `${m}月${d}日 星期${WEEKDAY_LABELS[mondayIndex(day)]}`
}

function buildWeeks(countByDate: Record<string, number>): HeatWeek[] {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const currentMonday = new Date(today)
  currentMonday.setDate(today.getDate() - mondayIndex(today))

  const weeks: HeatWeek[] = []
  for (let w = 0; w < WEEK_COUNT; w++) {
    const monday = new Date(currentMonday)
    monday.setDate(currentMonday.getDate() - w * 7)
    const cells: HeatCell[] = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(monday)
      d.setDate(monday.getDate() + i)
      const dateStr = fmtDate(d)
      const future = d.getTime() > today.getTime()
      const count = future ? 0 : countByDate[dateStr] || 0
      cells.push({
        date: dateStr,
        count,
        color: heatCellColor(count),
        future,
      })
    }
    weeks.push({ monthLabel: '', cells })
  }

  // 月份标签：标在每个月的第一周（从右往左扫 = 时间从旧到新，首次进入该月的那列）
  let prevMonth = -1
  for (let w = weeks.length - 1; w >= 0; w--) {
    const month = Number(weeks[w].cells[0].date.split('-')[1])
    if (month !== prevMonth) {
      weeks[w].monthLabel = `${month}月`
      prevMonth = month
    }
  }
  return weeks
}

Component({
  data: {
    weekdayLabels: WEEKDAY_LABELS,
    weeks: [] as HeatWeek[],
    selectedDate: '',
    selected: null as null | { label: string; count: number; icon: string; sub: string },
  },
  lifetimes: {
    attached() {
      this.refresh()
    },
  },
  pageLifetimes: {
    show() {
      this.refresh()
    },
  },
  methods: {
    async refresh() {
      let countByDate: Record<string, number> = {}
      if (hasToken()) {
        try {
          const res = await request<{ from: string; to: string; days: { date: string; count: number }[] }>(
            '/footprints/reading-heatmap',
            { auth: true, softAuth: true }
          )
          for (const d of res.data.days || []) {
            countByDate[d.date] = d.count
          }
        } catch {
          countByDate = {}
        }
      }
      const weeks = buildWeeks(countByDate)
      const todayStr = fmtDate(new Date())
      const selectedDate = this.data.selectedDate || todayStr
      const selectedCount = countByDate[selectedDate] || 0
      this.setData({
        weeks,
        selectedDate,
        selected: buildSelected(selectedDate, selectedCount),
      })
    },
    onCellTap(e: WechatMiniprogram.BaseEvent) {
      const ds = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset
      const date = ds.date as string
      if (!date) return
      const count = Number(ds.count) || 0
      this.setData({
        selectedDate: date,
        selected: buildSelected(date, count),
      })
    },
  },
})
