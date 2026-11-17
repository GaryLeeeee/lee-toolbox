import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { RouterView } from 'vue-router'
import router from '../src/app/router'

let wrapper: VueWrapper | undefined

async function open(path: string) {
  await router.push(path)
  await router.isReady()
  wrapper = mount(RouterView, { global: { plugins: [router] } })
  return wrapper
}

beforeEach(() => vi.spyOn(window, 'scrollTo').mockImplementation(() => {}))
afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
})

it('在首页分类显示四个开发工具，点击链接可进入对应页面', async () => {
  const page = await open('/?category=developer')
  expect(page.findAll('.tool-card h3').map(title => title.text())).toEqual([
    'JSON 格式化', '时间戳转换', 'Base64 互转', '文本差异对比',
  ])
  const link = page.get('a.tool-title-link[href="/tools/json-format"]')
  await router.push(link.attributes('href'))
  expect(page.get('h1').text()).toBe('JSON 格式化')
  expect(page.get('#json-source').exists()).toBe(true)
})

it('输入时实时校验和格式化 JSON，切换缩进或压缩立即生效', async () => {
  const page = await open('/tools/json-format')
  const input = page.get<HTMLTextAreaElement>('#json-source')
  const output = () => page.findAll('#json-result code').map(line => line.element.textContent).join('\n')
  const format = page.get('#json-output-format')
  await input.setValue(String.raw`{ "2": 9007199254740993, "1": [ [], "a \" b" ] }`)
  expect(output()).toContain('\n  "2": 9007199254740993,')
  expect(page.get('.json-key').text()).toBe('"2"')
  expect(page.get('.json-number').text()).toBe('9007199254740993')
  expect(page.get('.json-string').text()).toBe(String.raw`"a \" b"`)

  await format.setValue('4')
  expect(output()).toBe([
    '{', '    "2": 9007199254740993,', '    "1": [', '        [],', String.raw`        "a \" b"`, '    ]', '}',
  ].join('\n'))

  await format.setValue('0')
  expect(output()).toBe(String.raw`{"2":9007199254740993,"1":[[],"a \" b"]}`)
  expect(page.find('.json-fold').exists()).toBe(false)
  await input.setValue('{"a":1,}')
  expect(page.get('[role="alert"]').text()).toContain('JSON 格式无效')
  expect(output()).toBe('')
  await input.setValue(' { "a": 1 } ')
  expect(page.find('[role="alert"]').exists()).toBe(false)
  expect(output()).toBe('{"a":1}')
})

it('折叠对象和数组只收起对应行，复制仍返回完整 JSON', async () => {
  const page = await open('/tools/json-format')
  const viewer = page.get('#json-result')
  await page.get('#json-source').setValue('{"user":{"enabled":true,"note":"<img src=x>"},"scores":[12,null]}')
  const complete = viewer.findAll('code').map(line => line.element.textContent).join('\n')
  expect(viewer.get('.json-boolean').text()).toBe('true')
  expect(viewer.get('.json-null').text()).toBe('null')
  expect(viewer.find('img').exists()).toBe(false)

  await viewer.get('button[aria-label="折叠第 2 行的对象"]').trigger('click')
  expect(viewer.get('button[aria-label="展开第 2 行的对象"]').attributes('aria-expanded')).toBe('false')
  expect(viewer.find('.json-boolean').exists()).toBe(false)
  expect(viewer.get('.json-ellipsis').text()).toBe('… },')

  await viewer.get('button[aria-label="折叠第 6 行的数组"]').trigger('click')
  expect(viewer.find('.json-null').exists()).toBe(false)
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  try {
    await page.findAll('button').find(button => button.text() === '复制结果')!.trigger('click')
    expect(writeText).toHaveBeenCalledWith(complete)
  } finally {
    vi.unstubAllGlobals()
  }

  await viewer.get('button[aria-label="展开第 2 行的对象"]').trigger('click')
  expect(viewer.get('.json-boolean').text()).toBe('true')
  expect(viewer.find('.json-null').exists()).toBe(false)
})

it('打开即显示同一时刻，日期和秒级时间戳均没有小数', async () => {
  vi.spyOn(Date, 'now').mockReturnValue(1700000000123)
  const page = await open('/tools/timestamp-convert')
  const timestampForm = page.get('form[aria-labelledby="timestamp-to-date-title"]')
  const dateForm = page.get('form[aria-labelledby="date-to-timestamp-title"]')
  const timestampInput = page.get<HTMLInputElement>('#unix-timestamp')
  const dateInput = page.get<HTMLInputElement>('#date-time')
  expect(timestampInput.element.value).toBe('1700000000000')
  expect(dateInput.element.value).toBe('2023-11-15 06:13:20')
  expect(timestampForm.findAll('code').map(value => value.text())).toEqual([
    '2023-11-15 06:13:20', '2023-11-14 22:13:20',
  ])
  expect(dateForm.findAll('code').map(value => value.text())).toEqual(['1700000000', '1700000000000'])

  await page.get('#timestamp-unit').setValue('seconds')
  await timestampInput.setValue('0.5')
  await timestampForm.trigger('submit')
  expect(timestampForm.findAll('code').map(value => value.text())).toEqual([
    '1970-01-01 08:00:00', '1970-01-01 00:00:00',
  ])

  await page.get('#date-zone').setValue('utc')
  await dateInput.setValue('1969-12-31 23:59:59.999')
  await dateForm.trigger('submit')
  expect(dateForm.findAll('code').map(value => value.text())).toEqual(['-1', '-1'])

  await dateInput.setValue('2026-02-29 12:00:00')
  await dateForm.trigger('submit')
  expect(dateForm.get('[role="alert"]').text()).toContain('日期或时间无效')
  expect(dateForm.findAll('code')).toHaveLength(0)
})

it('两个填入当前时间按钮分别更新对应的输入和结果', async () => {
  const clock = vi.spyOn(Date, 'now').mockReturnValue(1700000000123)
  const page = await open('/tools/timestamp-convert')
  const timestampForm = page.get('form[aria-labelledby="timestamp-to-date-title"]')
  const dateForm = page.get('form[aria-labelledby="date-to-timestamp-title"]')
  const timestampInput = page.get<HTMLInputElement>('#unix-timestamp')
  const dateInput = page.get<HTMLInputElement>('#date-time')

  await page.get('#date-zone').setValue('utc')
  await dateInput.setValue('2000-01-01 00:00:00')
  await dateForm.trigger('submit')
  await page.get('#timestamp-unit').setValue('seconds')

  clock.mockReturnValue(1700000001123)
  await timestampForm.get('.browser-actions button[type="button"]').trigger('click')
  expect(timestampInput.element.value).toBe('1700000001')
  expect(dateInput.element.value).toBe('2000-01-01 00:00:00')
  expect(dateForm.findAll('code').map(value => value.text())).toEqual(['946684800', '946684800000'])

  clock.mockReturnValue(1700000002123)
  await dateForm.get('.browser-actions button[type="button"]').trigger('click')
  expect(dateInput.element.value).toBe('2023-11-14 22:13:22')
  expect(dateForm.findAll('code').map(value => value.text())).toEqual(['1700000002', '1700000002000'])
  expect(timestampInput.element.value).toBe('1700000001')
  expect(timestampForm.findAll('code').map(value => value.text())).toEqual([
    '2023-11-15 06:13:21', '2023-11-14 22:13:21',
  ])
})

it('顶部时间戳独立更新，复制的是当前显示的整数秒', async () => {
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] })
  vi.setSystemTime(1700000000123)
  const page = await open('/tools/timestamp-convert')
  const clock = page.get('section[aria-labelledby="timestamp-clock-title"]')
  expect(clock.get('code').text()).toBe('1700000000')

  await vi.advanceTimersByTimeAsync(1877)
  expect(clock.get('code').text()).toBe('1700000002')
  expect(page.get<HTMLInputElement>('#unix-timestamp').element.value).toBe('1700000000000')
  expect(page.get<HTMLInputElement>('#date-time').element.value).toBe('2023-11-15 06:13:20')

  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  try {
    await clock.get('button[aria-label="复制当前时间戳"]').trigger('click')
    expect(writeText).toHaveBeenCalledWith('1700000002')
  } finally {
    vi.unstubAllGlobals()
  }
})

it('Base64 可往返中文和 Emoji，拒绝非 UTF-8 字节', async () => {
  const page = await open('/tools/base64-convert')
  const input = page.get<HTMLTextAreaElement>('#base64-source')
  const output = page.get<HTMLTextAreaElement>('#base64-result')
  const encode = page.findAll('button').find(button => button.text() === '编码为 Base64')!
  const decode = page.findAll('button').find(button => button.text() === '解码为文本')!
  await input.setValue('中文😃\n')
  await encode.trigger('click')
  expect(output.element.value).toBe('5Lit5paH8J+Ygwo=')

  await input.setValue('5Lit5paH8J-Ygwo')
  await decode.trigger('click')
  expect(output.element.value).toBe('中文😃\n')

  await input.setValue('/w==')
  await decode.trigger('click')
  expect(page.get('[role="alert"]').text()).toContain('不是有效的 UTF-8')
  expect(output.element.value).toBe('')
})

it('文本对比保留空白差异、行号和末尾换行，并可筛掉相同行', async () => {
  const page = await open('/tools/text-diff')
  await page.get('#original-text').setValue('相同\n改动 \n结尾')
  await page.get('#modified-text').setValue('相同\n改动\n结尾\n')
  await page.get('form').trigger('submit')
  expect(page.get('.diff-counts').text()).toContain('新增 2 行')
  expect(page.get('.diff-counts').text()).toContain('删除 2 行')
  expect(page.findAll('tbody tr')).toHaveLength(5)

  const [onlyChanges, whitespace] = page.findAll('input[type="checkbox"]')
  await onlyChanges.setValue(true)
  await whitespace.setValue(true)
  expect(page.findAll('tbody tr')).toHaveLength(4)
  expect(page.get('tr.removed code').text()).toBe('改动·')
  expect(page.get('.diff-no-newline').text()).toBe('无行尾换行')
  const removedLine = page.get('tr.removed').findAll('td').slice(0, 2).map(cell => cell.text())
  expect(removedLine).toEqual(['2', ''])
})

it('生活工具分类显示日期计算器和星座查询入口', async () => {
  const page = await open('/?category=life')
  expect(page.findAll('.tool-card h3').map(title => title.text())).toEqual(['日期计算器', '星座与四象'])
})

it('日期计算默认用北京时间的今天，能计算日期差并显示推算日期的星期和农历', async () => {
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-11-16T16:05:00Z'))
  const page = await open('/tools/date-calculator')
  const difference = page.get('form[aria-labelledby="date-difference-title"]')
  const projection = page.get('form[aria-labelledby="date-projection-title"]')
  const start = page.get<HTMLInputElement>('#date-difference-first')
  const end = page.get('#date-difference-second')
  expect(start.element.value).toBe('2026-11-17')
  expect(page.get<HTMLInputElement>('#date-projection-base').element.value).toBe('2026-11-17')

  await end.setValue('2025-01-21')
  await difference.trigger('submit')
  expect(difference.get('[role="status"] strong').text()).toBe('665')

  await start.setValue('2024-02-28')
  await end.setValue('2024-03-01')
  await difference.trigger('submit')
  expect(difference.get('[role="status"] strong').text()).toBe('2')

  await page.get('#date-projection-direction').setValue('-1')
  await page.get('#date-projection-amount').setValue('90')
  await projection.trigger('submit')
  expect(projection.get('time').attributes('datetime')).toBe('2026-08-19')
  expect(projection.get('[role="status"]').text()).toContain('星期三')
  expect(projection.get('[role="status"]').text()).toContain('马年七月初七')
})

it('按工作日推算时能向前和向后跨过周末', async () => {
  const page = await open('/tools/date-calculator')
  const projection = page.get('form[aria-labelledby="date-projection-title"]')
  await page.get('#date-projection-base').setValue('2026-11-22')
  await page.get('#date-projection-unit').setValue('workdays')
  await page.get('#date-projection-amount').setValue('6')
  await projection.trigger('submit')
  expect(projection.get('time').text()).toBe('2026-11-30')

  await page.get('#date-projection-direction').setValue('-1')
  await page.get('#date-projection-amount').setValue('1')
  await projection.trigger('submit')
  expect(projection.get('time').text()).toBe('2026-11-20')

  await page.get('#date-projection-amount').setValue('-1')
  await projection.trigger('submit')
  expect(projection.get('[role="alert"]').text()).toContain('大于或等于 0 的整数天数')
  expect(projection.find('time').exists()).toBe(false)
})

it('星座查询处理跨年边界和闰日，并展示十二星座与四象分组', async () => {
  const page = await open('/tools/zodiac-lookup')
  const birthday = page.get('#zodiac-birthday')
  expect(page.findAll('.zodiac-table tbody tr')).toHaveLength(12)
  expect(page.findAll('.zodiac-elements dd').map(group => group.text())).toEqual([
    '白羊座、狮子座、射手座', '金牛座、处女座、摩羯座', '双子座、天秤座、水瓶座', '巨蟹座、天蝎座、双鱼座',
  ])

  for (const date of ['1999-12-22', '2000-01-19']) {
    await birthday.setValue(date)
    expect(page.get('.zodiac-result h3').text()).toBe('摩羯座')
    expect(page.get('.zodiac-result .element-badge').text()).toBe('土象')
    expect(page.get('.zodiac-match').text()).toContain('12月22日 – 1月19日')
  }

  await birthday.setValue('2000-01-20')
  expect(page.get('.zodiac-result h3').text()).toBe('水瓶座')
  await birthday.setValue('2000-02-29')
  expect(page.get('.zodiac-result h3').text()).toBe('双鱼座')
  expect(page.get('.zodiac-result .element-badge').text()).toBe('水象')
})
