import { parseCalendarDate } from '../../shared/calendar'

export const elements = [
  { id: 'fire', name: '火象' },
  { id: 'earth', name: '土象' },
  { id: 'air', name: '风象' },
  { id: 'water', name: '水象' },
] as const

type Element = typeof elements[number]['id']

interface ZodiacSign {
  name: string
  symbol: string
  start: number
  end: number
  element: Element
}

// Fixed month/day ranges and elements from the Farmers' Almanac zodiac chart.
// https://www.farmersalmanac.com/what-is-your-zodiac-sign
export const signs: readonly ZodiacSign[] = [
  { name: '白羊座', symbol: '♈︎', start: 321, end: 419, element: 'fire' },
  { name: '金牛座', symbol: '♉︎', start: 420, end: 520, element: 'earth' },
  { name: '双子座', symbol: '♊︎', start: 521, end: 620, element: 'air' },
  { name: '巨蟹座', symbol: '♋︎', start: 621, end: 722, element: 'water' },
  { name: '狮子座', symbol: '♌︎', start: 723, end: 822, element: 'fire' },
  { name: '处女座', symbol: '♍︎', start: 823, end: 922, element: 'earth' },
  { name: '天秤座', symbol: '♎︎', start: 923, end: 1022, element: 'air' },
  { name: '天蝎座', symbol: '♏︎', start: 1023, end: 1121, element: 'water' },
  { name: '射手座', symbol: '♐︎', start: 1122, end: 1221, element: 'fire' },
  { name: '摩羯座', symbol: '♑︎', start: 1222, end: 119, element: 'earth' },
  { name: '水瓶座', symbol: '♒︎', start: 120, end: 218, element: 'air' },
  { name: '双鱼座', symbol: '♓︎', start: 219, end: 320, element: 'water' },
]

export const elementGroups = elements.map(element => ({
  ...element,
  signs: signs.filter(sign => sign.element === element.id),
}))

export function elementName(id: Element): string {
  return elements.find(element => element.id === id)!.name
}

export function signForBirthday(birthday: string): ZodiacSign {
  const date = parseCalendarDate(birthday)
  const monthDay = (date.getUTCMonth() + 1) * 100 + date.getUTCDate()
  const sign = signs.find(({ start, end }) => start <= end
    ? monthDay >= start && monthDay <= end
    : monthDay >= start || monthDay <= end)
  if (!sign) throw new Error('无法匹配星座日期。')
  return sign
}

function formatMonthDay(monthDay: number): string {
  return `${Math.floor(monthDay / 100)}月${monthDay % 100}日`
}

export function dateRange(sign: ZodiacSign): string {
  return `${formatMonthDay(sign.start)} – ${formatMonthDay(sign.end)}`
}
