<script setup lang="ts">
import { computed, ref } from 'vue'
import { Download, FileVideo, FileImage, FileArchive, Images, RotateCcw, X, LoaderCircle, Check, AlertCircle } from 'lucide-vue-next'
import type { Task } from '../types'
import { api, errorMessage } from '../api'
import { bytes, dateTime, isActive, canRetry, statusLabels } from '../format'
import { notify, refreshTasks } from '../state'
import { tools } from '../../registry/tools'
const props = defineProps<{ task: Task; compact?: boolean }>()
const busy = ref(false)
const active = computed(() => isActive(props.task.status))
const progress = computed(() => Math.min(100, Math.max(0, props.task.progress)))
const toolName = computed(() => tools.find(tool => tool.id === props.task.tool_id)?.name || props.task.tool_id)
const xhsTask = computed(() => props.task.tool_id === 'xiaohongshu-export')
const fileIcon = computed(() => props.task.file_name?.endsWith('.zip') ? FileArchive : /\.(jpe?g|png|webp|heic)$/i.test(props.task.file_name || '') ? FileImage : xhsTask.value && !props.task.file_name ? Images : FileVideo)
async function cancel() {
  busy.value = true
  try { await api.cancel(props.task.id); notify('任务已取消'); await refreshTasks() }
  catch (error) { notify(errorMessage(error), 'error') }
  finally { busy.value = false }
}
async function retry() {
  busy.value = true
  try { await api.retry(props.task.id); notify('已创建重试任务'); await refreshTasks() }
  catch (error) { notify(errorMessage(error), 'error') }
  finally { busy.value = false }
}
</script>

<template>
  <article class="task-row" :class="{ compact }">
    <div class="task-file-icon" :class="{ done: task.status === 'completed' }"><component :is="fileIcon" :size="22" /></div>
    <div class="task-main">
      <div class="task-title-line"><h3 :title="task.title">{{ task.title || (xhsTask ? '待解析笔记' : '待解析视频') }}</h3><span class="status-pill" :class="task.status"><LoaderCircle v-if="active" class="spin" :size="12" /><Check v-else-if="task.status === 'completed'" :size="12" /><AlertCircle v-else-if="task.status === 'failed' || task.status === 'interrupted'" :size="12" />{{ statusLabels[task.status] || task.status }}</span></div>
      <div class="task-meta"><span>{{ toolName }}</span><template v-if="task.author"><span>·</span><span>{{ task.author }}</span></template><span>·</span><span>{{ task.format_label || (xhsTask ? '所选素材' : '自动选择') }}</span><template v-if="xhsTask && task.asset_count"><span>·</span><span>{{ task.finished_assets || 0 }} / {{ task.asset_count }} 项</span></template><span v-if="task.file_size">·</span><span v-if="task.file_size">{{ bytes(task.file_size) }}</span><span class="task-date">{{ dateTime(task.created_at) }}</span></div>
      <div v-if="active" class="task-progress"><div class="progress-track" role="progressbar" :aria-valuenow="Math.round(progress)" aria-valuemin="0" aria-valuemax="100" :aria-label="`${task.title} 下载进度`"><span :style="{ width: `${progress}%` }" /></div><span>{{ Math.round(progress) }}%</span><span v-if="task.speed_bps && !compact" class="task-speed">{{ bytes(task.speed_bps) }}/s</span></div>
      <p v-if="task.error" class="task-error">{{ task.error.message }}</p>
      <p v-if="task.status === 'completed' && !task.file_available" class="task-missing">本地文件已被移动或删除</p>
    </div>
    <div class="task-actions">
      <a v-if="task.status === 'completed' && task.file_available" class="button button-small button-light" :href="`/api/tasks/${encodeURIComponent(task.id)}/file`" download :aria-label="`下载 ${task.title}`"><Download :size="15" /><span>下载文件</span></a>
      <button v-if="active" class="button button-small button-ghost" :disabled="busy" aria-label="取消任务" @click="cancel"><LoaderCircle v-if="busy" :size="15" class="spin" /><X v-else :size="15" /><span>取消</span></button>
      <button v-else-if="canRetry(task.status)" class="button button-small button-light" :disabled="busy" @click="retry"><LoaderCircle v-if="busy" :size="15" class="spin" /><RotateCcw v-else :size="15" /><span>重试</span></button>
    </div>
  </article>
</template>
