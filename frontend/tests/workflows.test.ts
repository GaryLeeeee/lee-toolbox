import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type RouteComponent } from 'vue-router'
import VideoDownload from '../src/tools/video-download/VideoDownload.vue'
import TaskRow from '../src/shared/components/TaskRow.vue'
import HomePage from '../src/pages/HomePage.vue'
import { tools } from '../src/registry/tools'
import { state } from '../src/shared/state'
import { favorites, recent } from '../src/shared/preferences'
import type { MediaInfo, Task } from '../src/shared/types'

const media: MediaInfo = {
  platform: 'douyin', id: 'video-1', title: '一段测试视频', author: '测试作者', cover_url: null,
  duration: 66.92, source_url: 'https://www.douyin.com/video/7444165186107297074',
  formats: [
    { id: 'hd', label: '720p · H.264', width: 720, height: 1280, codec: 'h264', bitrate: 1050807, size_bytes: 8790134 },
    { id: 'small', label: '540p · H.264', width: 576, height: 1024, codec: 'h264', bitrate: 700000, size_bytes: 5600000 },
  ],
}
function task(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1', tool_id: 'video-download', status: 'queued', title: '一段测试视频', author: '测试作者',
    source_text: 'https://v.douyin.com/example/', format_id: 'hd', format_label: '720p', progress: 0,
    downloaded_bytes: 0, total_bytes: null, speed_bps: null, file_name: null, file_size: null,
    file_available: false, error: null, created_at: '2026-11-16T00:00:00Z', updated_at: '2026-11-16T00:00:00Z',
    ...overrides,
  }
}
const wrappers: VueWrapper[] = []
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
function mockFetch(handler: (url: string, init: RequestInit) => Promise<Response> | Response) {
  const fetchMock = vi.fn((url: string, init: RequestInit = {}) => Promise.resolve(handler(url, init)))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
async function mountPage(component: typeof VideoDownload | typeof HomePage, path = '/tools/video-download') {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/', component: HomePage },
    ...tools.map(tool => ({ path: tool.route, component: tool.component as () => Promise<RouteComponent> })),
    { path: '/tasks', component: { template: '<div>任务中心</div>' } },
  ] })
  await router.push(path); await router.isReady()
  const wrapper = mount(component, { global: { plugins: [router] } })
  wrappers.push(wrapper)
  return { wrapper, router }
}
async function parseVideo(wrapper: VueWrapper) {
  await wrapper.get('textarea').setValue('复制这段文案 https://v.douyin.com/example/')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}
function buttonByText(wrapper: VueWrapper, text: string) {
  const button = wrapper.findAll('button').find(item => item.text().includes(text))
  if (!button) throw new Error(`Button not found: ${text}`)
  return button
}

beforeEach(() => {
  localStorage.clear(); favorites.value = []; recent.value = []
  state.tasks = []; state.tasksError = ''; state.tasksLoading = false; state.toast = ''
  state.connection = 'online'; state.health = { status: 'ok', worker_running: true, ffmpeg_available: true }
})
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); vi.unstubAllGlobals() })

describe('视频解析与下载', () => {
  it('显示解析信息，按用户选择的画质创建任务并转到任务中心', async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url === '/api/media/resolve') return json(media)
      if (url === '/api/tasks' && init.method === 'POST') return json(task({ id: 'created-task', format_id: 'small' }), 201)
      return json({ items: [task({ id: 'created-task' })] })
    })
    const { wrapper, router } = await mountPage(VideoDownload)
    await parseVideo(wrapper)
    expect(wrapper.text()).toContain('一段测试视频')
    expect(wrapper.text()).toContain('测试作者')
    expect(wrapper.findAll('input[type="radio"]')).toHaveLength(2)
    await wrapper.findAll('input[type="radio"]')[1]!.setValue(true)
    await buttonByText(wrapper, '开始下载').trigger('click')
    await flushPromises()
    const creation = fetchMock.mock.calls.find(([url, init]) => url === '/api/tasks' && init.method === 'POST')
    expect(JSON.parse(creation![1].body as string)).toEqual({ source_text: '复制这段文案 https://v.douyin.com/example/', format_id: 'small' })
    expect(router.currentRoute.value.path).toBe('/tasks')
    expect(router.currentRoute.value.query.focus).toBe('created-task')
    expect(state.toast).toBe('下载任务已加入队列')
  })

  it('编辑已解析的分享内容后禁止下载旧视频，要求重新解析', async () => {
    const fetchMock = mockFetch(() => json(media))
    const { wrapper } = await mountPage(VideoDownload)
    await parseVideo(wrapper)
    await wrapper.get('textarea').setValue('https://v.douyin.com/another-video/')
    const download = buttonByText(wrapper, '开始下载')
    expect((download.element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.text()).toContain('分享内容已修改，请重新解析后下载')
    await download.trigger('click')
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/tasks')).toHaveLength(0)
  })

  it('解析失败显示服务端原因，恢复输入和重试能力', async () => {
    mockFetch(() => json({ error: { code: 'UNAVAILABLE', message: '作品暂时不可访问，请检查分享链接。' } }, 422))
    const { wrapper } = await mountPage(VideoDownload)
    await parseVideo(wrapper)
    expect(wrapper.get('[role="alert"]').text()).toContain('作品暂时不可访问')
    expect((buttonByText(wrapper, '解析视频').element as HTMLButtonElement).disabled).toBe(false)
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).readOnly).toBe(false)
    expect(wrapper.findAll('input[type="radio"]')).toHaveLength(0)
  })
})

describe('任务操作', () => {
  it('一次点击即可取消进行中的任务，并刷新任务记录', async () => {
    const fetchMock = mockFetch((url) => url.endsWith('/cancel') ? json(task({ status: 'cancelled' })) : json({ items: [task({ status: 'cancelled' })] }))
    const wrapper = mount(TaskRow, { props: { task: task({ status: 'downloading', progress: 33 }) } }); wrappers.push(wrapper)
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('33')
    await buttonByText(wrapper, '取消').trigger('click'); await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith('/api/tasks/task-1/cancel', expect.objectContaining({ method: 'POST' }))
    expect(state.tasks[0]?.status).toBe('cancelled')
    expect(state.toast).toBe('任务已取消')
  })

  it('重试失败任务创建新任务，并保留旧记录', async () => {
    const failed = task({ status: 'failed', error: { code: 'NETWORK', message: '网络中断' } })
    const newTask = task({ id: 'task-2' })
    const fetchMock = mockFetch(url => url.endsWith('/retry') ? json(newTask, 201) : json({ items: [newTask, failed] }))
    const wrapper = mount(TaskRow, { props: { task: failed } }); wrappers.push(wrapper)
    await buttonByText(wrapper, '重试').trigger('click'); await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith('/api/tasks/task-1/retry', expect.objectContaining({ method: 'POST' }))
    expect(state.tasks.map(item => item.id)).toEqual(['task-2', 'task-1'])
    expect(state.toast).toBe('已创建重试任务')
  })

  it('取消请求失败时展示原因并恢复按钮，避免误报成功', async () => {
    mockFetch(() => json({ error: { code: 'TASK_CONFLICT', message: '任务已完成，无法取消。' } }, 409))
    const wrapper = mount(TaskRow, { props: { task: task({ status: 'downloading' }) } }); wrappers.push(wrapper)
    await buttonByText(wrapper, '取消').trigger('click'); await flushPromises()
    expect(state.toastKind).toBe('error')
    expect(state.toast).toBe('任务已完成，无法取消。')
    expect((buttonByText(wrapper, '取消').element as HTMLButtonElement).disabled).toBe(false)
  })
})

describe('工具箱目录', () => {
  it('根据注册表搜索工具，收藏后可在收藏视图找到且持久化', async () => {
    const { wrapper, router } = await mountPage(HomePage, '/')
    const search = wrapper.get('input[aria-label="搜索工具"]')
    await search.setValue('不存在的工具')
    expect(wrapper.text()).toContain('没有找到匹配的工具')
    expect(wrapper.findAll('.tool-card')).toHaveLength(0)
    await search.setValue('抖音')
    expect(wrapper.findAll('.tool-card')).toHaveLength(1)
    await wrapper.get('button[aria-label="收藏视频下载"]').trigger('click')
    expect(JSON.parse(localStorage.getItem('lee-toolbox:favorites')!)).toEqual(['video-download'])
    await router.push('/?view=favorites'); await flushPromises()
    expect(wrapper.text()).toContain('你的常用，随手可及')
    expect(wrapper.findAll('.tool-card')).toHaveLength(1)
    await wrapper.get('button[aria-label="取消收藏视频下载"]').trigger('click')
    expect(wrapper.findAll('.tool-card')).toHaveLength(0)
    await search.setValue('')
    expect(wrapper.text()).toContain('还没有收藏工具')
  })
})
