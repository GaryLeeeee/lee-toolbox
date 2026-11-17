import { MILLISECONDS_PER_DAY, parseCalendarDate } from '../../shared/calendar'

export type DayUnit = 'days' | 'workdays'

const weekdayFormatter = new Intl.DateTimeFormat('zh-CN', { timeZone: 'UTC', weekday: 'long' })
const lunarFormatter = new Intl.DateTimeFormat('zh-CN-u-ca-chinese', {
  timeZone: 'UTC', numberingSystem: 'latn', year: 'numeric', month: 'long', day: 'numeric',
})
const lunarDays = [
  '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
  '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
  '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十',
]

export function todayInBeijing(): string {
  return new Date(Date.now() + 8 * 3_600_000).toISOString().slice(0, 10)
}

export function daysBetween(first: string, second: string): number {
  const difference = parseCalendarDate(second).getTime() - parseCalendarDate(first).getTime()
  return Math.abs(difference) / MILLISECONDS_PER_DAY
}

function isWorkday(day: number): boolean {
  // 1970-01-01 is Thursday. Normalize the remainder for dates before 1970.
  const weekday = ((day + 4) % 7 + 7) % 7
  return weekday >= 1 && weekday <= 5
}

function shiftWorkdays(day: number, offset: number): number {
  if (offset === 0) return day
  const step = Math.sign(offset)

  // Start on the first counted weekday, then skip whole work weeks.
  do { day += step } while (!isWorkday(day))
  const remaining = Math.abs(offset) - 1
  day += Math.floor(remaining / 5) * 7 * step
  let tail = remaining % 5
  while (tail > 0) {
    day += step
    if (isWorkday(day)) tail--
  }
  return day
}

function lunarDate(date: Date): string | null {
  if (lunarFormatter.resolvedOptions().calendar !== 'chinese') return null
  // Chinese calendars also emit yearName, which is missing from the TypeScript part registry.
  const parts: { type: string; value: string }[] = lunarFormatter.formatToParts(date)
  const year = parts.find(part => part.type === 'yearName')?.value
  const month = parts.find(part => part.type === 'month')?.value
  const day = Number(parts.find(part => part.type === 'day')?.value)
  const dayText = lunarDays[day - 1]
  if (!year || !month || !dayText) return null
  const animal = '鼠牛虎兔龙蛇马羊猴鸡狗猪'['子丑寅卯辰巳午未申酉戌亥'.indexOf(year.slice(-1))]
  return `${animal ?? year}年${month}${dayText}`
}

export function offsetDate(source: string, offset: number, unit: DayUnit) {
  if (!Number.isSafeInteger(offset)) throw new Error('请输入有效的整数天数。')
  const start = parseCalendarDate(source).getTime() / MILLISECONDS_PER_DAY
  const day = unit === 'workdays' ? shiftWorkdays(start, offset) : start + offset
  const date = new Date(day * MILLISECONDS_PER_DAY)
  const year = date.getUTCFullYear()
  if (!Number.isFinite(year) || year < 1 || year > 9999) throw new Error('推算结果超出公历 0001 至 9999 年范围。')
  return {
    date: date.toISOString().slice(0, 10),
    weekday: weekdayFormatter.format(date),
    lunar: lunarDate(date),
  }
}
