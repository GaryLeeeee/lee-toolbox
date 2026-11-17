export type TimestampUnit = 'auto' | 'seconds' | 'milliseconds'

const ZONE_OFFSETS = { beijing: 8 * 60 * 60 * 1000, utc: 0 } as const
export type DateZone = keyof typeof ZONE_OFFSETS

function displayDate(milliseconds: number): string {
  const date = new Date(milliseconds)
  if (Number.isNaN(date.getTime())) throw new Error('时间戳超出可转换范围。')
  return date.toISOString().slice(0, -5).replace('T', ' ')
}

export function timestampToDates(source: string, requestedUnit: TimestampUnit) {
  const match = /^([+-]?)(\d{1,16})(?:\.(\d{1,3}))?$/.exec(source.trim())
  if (!match) throw new Error('请输入有效的时间戳，秒级时间戳最多带 3 位小数。')

  const [, sign, digits, fraction] = match
  const magnitude = BigInt(digits)
  const unit = requestedUnit === 'auto'
    ? (fraction === undefined && magnitude >= 10_000_000_000n ? 'milliseconds' : 'seconds')
    : requestedUnit
  if (unit === 'milliseconds' && fraction !== undefined) throw new Error('毫秒时间戳须为整数。')

  const absoluteMilliseconds = unit === 'seconds'
    ? magnitude * 1000n + BigInt(fraction?.padEnd(3, '0') ?? '0')
    : magnitude
  const milliseconds = Number(sign === '-' ? -absoluteMilliseconds : absoluteMilliseconds)
  return {
    unit,
    utc: displayDate(milliseconds),
    beijing: displayDate(milliseconds + ZONE_OFFSETS.beijing),
  }
}

export function dateToTimestamps(source: string, zone: DateZone) {
  const match = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$/.exec(source.trim())
  if (!match) throw new Error('请输入日期时间，例如 2026-01-01 12:30:00。')

  const [, day, time, second = '00', fraction = ''] = match
  const iso = `${day}T${time}:${second}.${fraction.padEnd(3, '0')}Z`
  const date = new Date(iso)
  if (Number.isNaN(date.getTime()) || date.toISOString() !== iso) {
    throw new Error('日期或时间无效，请检查年月日和时间。')
  }

  const milliseconds = date.getTime() - ZONE_OFFSETS[zone]
  return { seconds: String(Math.floor(milliseconds / 1000)), milliseconds: String(milliseconds) }
}
