import type { MediaInfo, Task, Health, XhsNote } from './types'

export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message) }
}

export async function request<T>(path: string, options: RequestInit = {}, timeout = 20000): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(`/api${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
      signal: controller.signal,
    })
    let data: unknown
    try { data = await response.json() } catch { throw new ApiError('INVALID_RESPONSE', '服务返回了异常响应，请稍后重试。', response.status) }
    if (!response.ok) {
      const error = (data as { error?: { code?: string; message?: string } }).error
      throw new ApiError(error?.code ?? 'REQUEST_FAILED', error?.message ?? `请求失败（${response.status}），请稍后重试。`, response.status)
    }
    return data as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('TIMEOUT', '请求超时，请检查网络后重试。')
    throw new ApiError('NETWORK_ERROR', '暂时无法连接本地服务，请确认工具箱服务已启动。')
  } finally { window.clearTimeout(timer) }
}
const post = <T>(path: string, body?: unknown, timeout?: number) => request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }, timeout)
export const api = {
  health: () => request<Health>('/health', {}, 5000),
  tasks: () => request<{ items: Task[] }>('/tasks'),
  resolve: (text: string) => post<MediaInfo>('/media/resolve', { text }, 90000),
  createTask: (source_text: string, format_id: string) => post<Task>('/tasks', { source_text, format_id }),
  resolveXhs: (text: string) => post<XhsNote>('/xhs/resolve', { text }, 90000),
  exportXhs: (source_text: string, asset_ids: string[]) => post<Task>('/tasks', { tool_id: 'xiaohongshu-export', source_text, asset_ids }),
  cancel: (id: string) => post<Task>(`/tasks/${encodeURIComponent(id)}/cancel`),
  retry: (id: string) => post<Task>(`/tasks/${encodeURIComponent(id)}/retry`),
}
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : '操作未完成，请稍后重试。'
