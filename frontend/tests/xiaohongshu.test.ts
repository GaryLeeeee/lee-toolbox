import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import XiaohongshuExport from '../src/tools/xiaohongshu-export/XiaohongshuExport.vue'
import TaskRow from '../src/shared/components/TaskRow.vue'
import TasksPage from '../src/pages/TasksPage.vue'
import HomePage from '../src/pages/HomePage.vue'
import { state } from '../src/shared/state'
import { tools } from '../src/registry/tools'
import type { Task, XhsAsset, XhsNote } from '../src/shared/types'

const asset = (overrides: Partial<XhsAsset> = {}): XhsAsset => ({
  id: 'image-1', kind: 'image', label: '图片 1', width: 2160, height: 2880,
  duration: null, available: true, unavailable_reason: null, preview_url: '/api/xhs/previews/image-token', watermark_status: 'none', ...overrides,
})
const note: XhsNote = {
  platform: 'xiaohongshu', id: 'note-1', title: '又 到 九 月 底', author: '测试作者',
  source_url: 'https://www.xiaohongshu.com/explore/note-1', warnings: [],
  assets: [
    asset(),
    asset({ id: 'video-1', kind: 'video', label: 'Live 图 1 · 动态视频', duration: 3, watermark_status: 'present' }),
    asset({ id: 'video-2', kind: 'video', label: 'Live 图 2 · 动态视频', available: false, unavailable_reason: '未获取到可下载的动态视频。', watermark_status: 'unknown' }),
    asset({ id: 'image-2', label: 'Live 图 2 · 静态原图' }),
  ],
}
const task = (overrides: Partial<Task> = {}): Task => ({
  id: 'xhs-task-1', tool_id: 'xiaohongshu-export', status: 'queued', title: '又 到 九 月 底', author: '测试作者',
  source_text: 'https://xhslink.cn/o/example', format_id: null, format_label: '', asset_ids: ['video-1'],
  asset_count: 1, finished_assets: 0, progress: 0, downloaded_bytes: 0, total_bytes: null, speed_bps: null,
  file_name: null, file_size: null, file_available: false, error: null,
  created_at: '2026-11-17T00:00:00Z', updated_at: '2026-11-17T00:00:00Z', ...overrides,
})
const wrappers: VueWrapper[] = []
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
function mockFetch(handler: (url: string, init: RequestInit) => Response) {
  const fetchMock = vi.fn((url: string, init: RequestInit = {}) => Promise.resolve(handler(url, init)))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
async function mountTool() {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/', component: HomePage }, { path: '/tools/xiaohongshu-export', component: XiaohongshuExport },
    { path: '/tasks', component: TasksPage },
  ] })
  await router.push('/tools/xiaohongshu-export'); await router.isReady()
  const wrapper = mount(XiaohongshuExport, { global: { plugins: [router] } })
  wrappers.push(wrapper)
  return { wrapper, router }
}
async function parseNote(wrapper: VueWrapper) {
  await wrapper.get('textarea').setValue('又 到 九 月 底 https://xhslink.cn/o/example')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}
function button(wrapper: VueWrapper, text: string) {
  const result = wrapper.findAll('button').find(item => item.text().includes(text))
  if (!result) throw new Error(`Button not found: ${text}`)
  return result
}
function checkbox(wrapper: VueWrapper, id: string) { return wrapper.get(`input[type="checkbox"][value="${id}"]`) }

beforeEach(() => {
  state.tasks = []; state.tasksError = ''; state.tasksLoading = false; state.toast = ''
  state.connection = 'online'; state.health = { status: 'ok', worker_running: true, ffmpeg_available: true }
})
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); vi.unstubAllGlobals() })

describe('小红书导出', () => {
  it('注册独立工具，解析后按用户明确选择的稳定资源 ID 创建任务', async () => {
    expect(tools.find(tool => tool.id === 'xiaohongshu-export')?.route).toBe('/tools/xiaohongshu-export')
    const fetchMock = mockFetch((url, init) => {
      if (url === '/api/xhs/resolve') return json(note)
      if (url === '/api/tasks' && init.method === 'POST') return json(task(), 201)
      return json({ items: [task()] })
    })
    const { wrapper, router } = await mountTool()
    await parseNote(wrapper)
    expect(wrapper.text()).toContain('又 到 九 月 底')
    expect(wrapper.get('.xhs-selection-toolbar').text()).toContain('已选 0 / 3 项可用素材')
    expect((button(wrapper, '导出所选').element as HTMLButtonElement).disabled).toBe(true)
    await checkbox(wrapper, 'video-1').setValue(true)
    expect(wrapper.get('.download-footer').text()).toContain('MP4 视频')
    expect(wrapper.get('.xhs-watermark-note').text()).toContain('导出会保留源文件中的水印')
    await button(wrapper, '导出 1 项').trigger('click'); await flushPromises()
    const creation = fetchMock.mock.calls.find(([url, init]) => url === '/api/tasks' && init.method === 'POST')
    expect(JSON.parse(creation![1].body as string)).toEqual({
      tool_id: 'xiaohongshu-export', source_text: '又 到 九 月 底 https://xhslink.cn/o/example', asset_ids: ['video-1'],
    })
    expect(router.currentRoute.value.path).toBe('/tasks')
    expect(router.currentRoute.value.query.focus).toBe('xhs-task-1')
  })

  it('带水印动态视频允许主动选择，静态图片独立选择，全选排除缺失资源', async () => {
    mockFetch(() => json(note))
    const { wrapper } = await mountTool(); await parseNote(wrapper)
    expect((checkbox(wrapper, 'video-2').element as HTMLInputElement).disabled).toBe(true)
    expect((checkbox(wrapper, 'video-1').element as HTMLInputElement).disabled).toBe(false)
    expect((checkbox(wrapper, 'video-1').element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.text()).toContain('有平台水印')
    expect((checkbox(wrapper, 'image-2').element as HTMLInputElement).checked).toBe(false)
    await button(wrapper, '全选可用').trigger('click')
    expect(wrapper.get('.xhs-selection-toolbar').text()).toContain('已选 3 / 3')
    expect((checkbox(wrapper, 'video-2').element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.get('.download-footer').text()).toContain('ZIP · 批量打包')
    await button(wrapper, '清空选择').trigger('click')
    expect((button(wrapper, '导出所选').element as HTMLButtonElement).disabled).toBe(true)
  })

  it('解析前后均声明暂不直接导出 Live Photo，图片和视频不依赖配对组件', async () => {
    mockFetch(() => json(note))
    const { wrapper } = await mountTool()
    expect(wrapper.get('.xhs-live-notice').text()).toContain('暂不支持直接导出 Live Photo')
    await parseNote(wrapper)
    expect(wrapper.get('.xhs-live-notice').text()).toContain('分别导出静态图片和 MP4 视频')
    expect(wrapper.get('.xhs-type-counts').text()).toBe('图片 2视频 2')
    expect((checkbox(wrapper, 'video-1').element as HTMLInputElement).disabled).toBe(false)
    await checkbox(wrapper, 'image-1').setValue(true)
    expect((button(wrapper, '导出 1 项').element as HTMLButtonElement).disabled).toBe(false)
    expect(wrapper.get('.download-footer').text()).toContain('图片文件')
    expect(wrapper.text()).not.toContain('JPG + MOV')
    expect(wrapper.text()).not.toContain('Xcode')
  })

  it('编辑分享内容后禁止使用旧解析结果导出', async () => {
    const fetchMock = mockFetch(() => json(note))
    const { wrapper } = await mountTool(); await parseNote(wrapper)
    await checkbox(wrapper, 'image-1').setValue(true)
    await wrapper.get('textarea').setValue('https://xhslink.cn/o/other')
    expect(wrapper.text()).toContain('分享内容已修改，请重新解析后导出')
    const exportButton = button(wrapper, '导出 1 项')
    expect((exportButton.element as HTMLButtonElement).disabled).toBe(true)
    await exportButton.trigger('click')
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/tasks')).toHaveLength(0)
  })

  it('未知水印状态的视频明确提示，已确认无水印视频不显示混淆提醒', async () => {
    mockFetch(() => json({ ...note, assets: [
      asset({ id: 'video-clean', kind: 'video', label: '视频 1', watermark_status: 'none' }),
      asset({ id: 'video-unknown', kind: 'video', label: '视频 2', watermark_status: 'unknown' }),
    ] }))
    const { wrapper } = await mountTool(); await parseNote(wrapper)
    expect(wrapper.findAll('.xhs-watermark-status').map(item => item.text())).toEqual(['源文件无平台水印', '水印状态未确认'])
    await checkbox(wrapper, 'video-clean').setValue(true)
    expect(wrapper.find('.xhs-watermark-note').exists()).toBe(false)
    await checkbox(wrapper, 'video-unknown').setValue(true)
    expect(wrapper.get('.xhs-watermark-note').text()).toContain('水印状态未确认')
    await checkbox(wrapper, 'video-unknown').setValue(false)
    expect(wrapper.find('.xhs-watermark-note').exists()).toBe(false)
  })

  it('解析或创建失败后展示服务端原因，恢复按钮并保留已选素材', async () => {
    mockFetch(() => json({ error: { code: 'NOTE_UNAVAILABLE', message: '笔记暂时无法访问，请检查链接。' } }, 422))
    const { wrapper } = await mountTool(); await parseNote(wrapper)
    expect(wrapper.get('[role="alert"]').text()).toContain('笔记暂时无法访问')
    expect((button(wrapper, '解析笔记').element as HTMLButtonElement).disabled).toBe(false)
    mockFetch(url => url === '/api/xhs/resolve' ? json(note) : json({ error: { code: 'QUEUE_FULL', message: '任务队列已满。' } }, 429))
    await parseNote(wrapper); await checkbox(wrapper, 'image-1').setValue(true)
    await button(wrapper, '导出 1 项').trigger('click'); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('任务队列已满')
    expect((button(wrapper, '导出 1 项').element as HTMLButtonElement).disabled).toBe(false)
    expect((checkbox(wrapper, 'image-1').element as HTMLInputElement).checked).toBe(true)
  })

  it('全部不可用时禁用导出并解释原因，预览失败不影响可用性判断', async () => {
    mockFetch(() => json({ ...note, assets: [note.assets[2]] }))
    const { wrapper } = await mountTool(); await parseNote(wrapper)
    expect(wrapper.text()).toContain('暂时没有可导出的素材')
    expect((button(wrapper, '全选可用').element as HTMLButtonElement).disabled).toBe(true)
    expect((button(wrapper, '导出所选').element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.get('.xhs-asset-preview img').trigger('error')
    expect(wrapper.find('.xhs-asset-preview img').exists()).toBe(false)
    expect((checkbox(wrapper, 'video-2').element as HTMLInputElement).disabled).toBe(true)
  })

  it('最多选择 100 项，清空后可重新选择', async () => {
    mockFetch(() => json({ ...note, assets: Array.from({ length: 101 }, (_, index) => asset({ id: `image-${index}`, label: `图片 ${index + 1}` })) }))
    const { wrapper } = await mountTool(); await parseNote(wrapper)
    await button(wrapper, '全选可用').trigger('click')
    expect(wrapper.get('.xhs-selection-toolbar').text()).toContain('已选 100 / 101')
    expect((checkbox(wrapper, 'image-100').element as HTMLInputElement).disabled).toBe(true)
    await checkbox(wrapper, 'image-0').setValue(false)
    expect((checkbox(wrapper, 'image-100').element as HTMLInputElement).disabled).toBe(false)
  })

  it('任务卡展示工具与资源进度，完成后可下载 ZIP', async () => {
    const wrapper = mount(TaskRow, { props: { task: task({ status: 'downloading', asset_count: 3, finished_assets: 1, progress: 40 }) } }); wrappers.push(wrapper)
    expect(wrapper.text()).toContain('小红书导出')
    expect(wrapper.text()).toContain('1 / 3 项')
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('40')
    await wrapper.setProps({ task: task({ status: 'completed', file_name: 'note.zip', file_available: true, asset_count: 3, finished_assets: 3 }) })
    expect(wrapper.get('a[download]').attributes('href')).toBe('/api/tasks/xhs-task-1/file')
    expect(wrapper.text()).toContain('3 / 3 项')
  })
})
