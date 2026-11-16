import type { TaskStatus } from './types'
export const activeStatuses: TaskStatus[] = ['queued', 'resolving', 'downloading', 'verifying']
export const isActive = (status: TaskStatus) => activeStatuses.includes(status)
export const canRetry = (status: TaskStatus) => ['failed', 'cancelled', 'interrupted'].includes(status)
export const statusLabels: Record<TaskStatus, string> = {
  queued: '等待中', resolving: '解析中', downloading: '下载中', verifying: '校验中',
  completed: '已完成', failed: '失败', cancelled: '已取消', interrupted: '已中断',
}
export function bytes(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '大小待确认'
  if (value < 1024) return `${value} B`
  const unit = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 3)
  return `${(value / 1024 ** unit).toFixed(unit === 1 ? 0 : 1)} ${['B', 'KB', 'MB', 'GB'][unit]}`
}
export function duration(value: number) {
  if (!Number.isFinite(value)) return '—'
  const seconds = Math.round(value)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
export function dateTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date)
}
