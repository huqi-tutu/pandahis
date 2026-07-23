import { hasToken, request } from '../../native-utils/api'

/** 最近一年阅读足迹热力图：7 行（周一~周日）× 52 列（周），最近一周在最左 */

const WEEK_COUNT = 52
const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日']

/** 苔绿 #7D8A6A：1–10 篇十档色阶，在白色卡片底上预混为不透明色 */
const TEA_GREEN = { r: 125, g: 138, b: 106 }
const LEVEL_COLORS = Array.from({ length: 10 }, (_, i) => {
  const a = 0.12 + (i * 0.88) / 9
  const mix = (c: number) => Math.round(c * a + 255 * (1 - a))
  return `rgb(${mix(TEA_GREEN.r)}, ${mix(TEA_GREEN.g)}, ${mix(TEA_GREEN.b)})`
})

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
      const level = Math.min(count, 10)
      cells.push({
        date: dateStr,
        count,
        color: level > 0 ? LEVEL_COLORS[level - 1] : '',
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
    selected: null as null | { label: string; count: number },
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
      const todayCount = countByDate[todayStr] || 0
      this.setData({
        weeks,
        selectedDate: todayStr,
        selected: { label: detailLabel(todayStr), count: todayCount },
      })
    },
    onCellTap(e: WechatMiniprogram.BaseEvent) {
      const ds = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset
      const date = ds.date as string
      if (!date || ds.future) return
      const count = Number(ds.count) || 0
      this.setData({
        selectedDate: date,
        selected: { label: detailLabel(date), count },
      })
    },
  },
})
