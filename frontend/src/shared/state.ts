import { computed, reactive } from 'vue'
import { api, errorMessage } from './api'
import { isActive } from './format'
import type { Task, Health } from './types'

export const state = reactive({
  tasks: [] as Task[], tasksLoading: true, tasksError: '',
  health: null as Health | null, connection: 'checking' as 'checking' | 'online' | 'offline',
  toast: '' as string, toastKind: 'success' as 'success' | 'error',
})
export const activeTasks = computed(() => state.tasks.filter(task => isActive(task.status)))
export const completedTasks = computed(() => state.tasks.filter(task => task.status === 'completed'))
let taskFetching = false
let healthFetching = false
let toastTimer: number | undefined
export function notify(message: string, kind: 'success' | 'error' = 'success') {
  window.clearTimeout(toastTimer)
  state.toast = message; state.toastKind = kind
  toastTimer = window.setTimeout(() => { state.toast = '' }, 5000)
}
export async function refreshTasks() {
  if (taskFetching) return
  taskFetching = true
  try { state.tasks = (await api.tasks()).items; state.tasksError = '' }
  catch (error) { state.tasksError = errorMessage(error) }
  finally { taskFetching = false; state.tasksLoading = false }
}
export async function refreshHealth() {
  if (healthFetching) return
  healthFetching = true
  try { state.health = await api.health(); state.connection = 'online' }
  catch { state.connection = 'offline'; state.health = null }
  finally { healthFetching = false }
}
export function startPolling() {
  void refreshHealth(); void refreshTasks()
  const timer = window.setInterval(() => { if (!document.hidden) void refreshTasks() }, 2000)
  const healthTimer = window.setInterval(() => { if (!document.hidden) void refreshHealth() }, 20000)
  const visible = () => { if (!document.hidden) { void refreshTasks(); void refreshHealth() } }
  document.addEventListener('visibilitychange', visible)
  return () => {
    window.clearInterval(timer); window.clearInterval(healthTimer)
    document.removeEventListener('visibilitychange', visible)
  }
}
