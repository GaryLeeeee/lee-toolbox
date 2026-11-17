export const MILLISECONDS_PER_DAY = 86_400_000

// A civil date is represented at UTC midnight so arithmetic does not depend on DST.
export function parseCalendarDate(value: string): Date {
  const iso = value.trim()
  if (/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const date = new Date(`${iso}T00:00:00Z`)
    if (Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === iso) return date
  }
  throw new Error('请输入有效的公历日期。')
}
