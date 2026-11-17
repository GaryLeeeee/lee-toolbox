import ipaddr from 'ipaddr.js'
import chineseRegions from './regions.zh-CN.json'

export type IpVersion = 'IPv4' | 'IPv6'
export type IpLookup = { ip: string } | { version: IpVersion }

export interface IpLocation {
  ip: string
  version: IpVersion
  country: string
  region: string
  city: string
}

type RegionNames = Record<string, Record<string, { division: string; name: string }>>
type CityNames = Record<string, Record<string, string | Record<string, string>>>

const regions: RegionNames = chineseRegions.names
const endpoint = 'https://api.ip.sb/geoip'
const currentEndpoints: Record<IpVersion, string> = {
  IPv4: 'https://api-ipv4.ip.sb/geoip',
  IPv6: 'https://api-ipv6.ip.sb/geoip',
}
const countryNames = new Intl.DisplayNames('zh-CN', { type: 'region', fallback: 'none' })

function parseIp(value: string) {
  if (value.length > 45 || !/^[a-f\d:.]+$/i.test(value)) return null
  if (!ipaddr.IPv4.isValidFourPartDecimal(value) && !ipaddr.IPv6.isValid(value)) return null
  return ipaddr.process(value)
}

function parsePublicIp(value: string): string {
  const address = parseIp(value.trim().replace(/^\[([^\]]+)\]$/, '$1'))
  if (!address) throw new Error('请输入有效的 IPv4 或 IPv6 地址。')
  if (address.range() !== 'unicast') throw new Error('该 IP 属于私网、保留地址或其他特殊地址，暂无公网归属地。')
  return address.toString()
}

function textField(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function placeKey(value: string): string {
  return value.normalize('NFKD').toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')
}

async function localizePlaces(countryCode: string, region: string, city: string) {
  const regionMatch = regions[countryCode]?.[placeKey(region)]
  const cities: CityNames | undefined = city
    ? (await import('./cities.zh-CN.json').catch(() => null))?.default.names
    : undefined
  const cityMatch = cities?.[countryCode]?.[placeKey(city)]
  const cityName = typeof cityMatch === 'string' ? cityMatch : cityMatch?.[regionMatch?.division ?? '']
  return { region: regionMatch?.name ?? region, city: cityName ?? city }
}

export async function fetchIpLocation(query: IpLookup, signal: AbortSignal): Promise<IpLocation> {
  const requestedIp = 'ip' in query ? parsePublicIp(query.ip) : ''
  const url = 'version' in query ? currentEndpoints[query.version] : endpoint + '/' + encodeURIComponent(requestedIp)
  let response: Response
  try {
    response = await fetch(url, { signal, cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer' })
  } catch {
    throw new Error('暂时无法连接 IP 查询服务，请重试。')
  }
  if (response.status === 429) throw new Error('查询次数过多，请稍后重试。')
  if (!response.ok) throw new Error('IP 查询服务暂时不可用，请重试。')

  const data = await response.json().catch(() => null) as Record<string, unknown> | null
  const address = parseIp(textField(data?.ip))
  const ip = address?.toString()
  const version = address?.kind() === 'ipv4' ? 'IPv4' : 'IPv6'
  const matchesQuery = 'version' in query ? version === query.version : ip === requestedIp
  if (!ip || !matchesQuery) throw new Error('IP 查询服务未返回有效结果。')

  const countryCode = textField(data?.country_code).toUpperCase()
  const country = /^[A-Z]{2}$/.test(countryCode) ? countryNames.of(countryCode) : undefined
  const places = await localizePlaces(countryCode, textField(data?.region), textField(data?.city))
  return {
    ip,
    version,
    country: country ?? textField(data?.country),
    ...places,
  }
}
