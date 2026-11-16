<script setup lang="ts">
import { computed, ref } from 'vue'
import { Download, ArrowRight, CheckCheck, Clock3, ListTodo, LoaderCircle, RotateCcw, Search, X, AlertCircle } from 'lucide-vue-next'
import { activeTasks, completedTasks, refreshTasks, state } from '../shared/state'
import { isActive } from '../shared/format'
import TaskRow from '../shared/components/TaskRow.vue'
import EmptyState from '../shared/components/EmptyState.vue'
const selectedTab = ref('all')
const search = ref('')
const refreshing = ref(false)
const unfinished = computed(() => state.tasks.filter(task => ['failed', 'interrupted', 'cancelled'].includes(task.status)))
const tabs = computed(() => [
  { id: 'all', label: '全部任务', count: state.tasks.length },
  { id: 'active', label: '进行中', count: activeTasks.value.length },
  { id: 'completed', label: '已完成', count: completedTasks.value.length },
  { id: 'unfinished', label: '未完成', count: unfinished.value.length },
])
const visibleTasks = computed(() => state.tasks.filter(task => {
  const matchesTab = selectedTab.value === 'all' || (selectedTab.value === 'active' && isActive(task.status)) || (selectedTab.value === 'completed' && task.status === 'completed') || (selectedTab.value === 'unfinished' && ['failed', 'interrupted', 'cancelled'].includes(task.status))
  return matchesTab && [task.title, task.author].join(' ').toLowerCase().includes(search.value.trim().toLowerCase())
}))
async function refresh() { refreshing.value = true; await refreshTasks(); refreshing.value = false }
</script>

<template>
  <div class="tasks-page"><div class="page-heading"><div><div class="eyebrow"><span class="eyebrow-line" />KEEP TRACK OF EVERY STEP</div><h1>任务中心</h1><p>下载进度、处理结果和历史记录，一目了然。</p></div><RouterLink class="button button-primary" to="/tools/video-download"><Download :size="16" />新建下载</RouterLink></div>
    <div class="task-stats"><div class="stat-card"><span class="stat-icon neutral"><ListTodo :size="21" /></span><div><span>全部任务</span><strong>{{ state.tasks.length }}</strong></div></div><div class="stat-card"><span class="stat-icon green"><LoaderCircle v-if="activeTasks.length" class="spin" :size="21" /><Clock3 v-else :size="21" /></span><div><span>进行中</span><strong>{{ activeTasks.length }}</strong></div><span v-if="activeTasks.length" class="stat-live">实时更新</span></div><div class="stat-card"><span class="stat-icon green"><CheckCheck :size="21" /></span><div><span>已完成</span><strong>{{ completedTasks.length }}</strong></div></div></div>
    <section class="panel tasks-panel" aria-label="任务列表"><div class="task-list-toolbar"><div class="task-tabs" role="group" aria-label="按状态筛选任务"><button v-for="tab in tabs" :key="tab.id" :class="{ active: selectedTab === tab.id }" :aria-pressed="selectedTab === tab.id" @click="selectedTab = tab.id">{{ tab.label }}<span>{{ tab.count }}</span></button></div><button class="icon-button refresh-button" :disabled="refreshing" aria-label="刷新任务列表" @click="refresh"><RotateCcw :size="17" :class="{ spin: refreshing }" /></button></div><div v-if="state.tasks.length" class="tasks-search-row"><div class="search-field task-search"><Search :size="16" /><input v-model="search" type="search" placeholder="搜索任务名称或作者…" aria-label="搜索任务" /><button v-if="search" class="icon-button" aria-label="清空任务搜索" @click="search = ''"><X :size="14" /></button></div><span class="task-total">{{ visibleTasks.length }} 个任务<span v-if="activeTasks.length" class="live-caption"><span />自动更新</span></span></div>
      <div v-if="state.tasksLoading" class="loading-state"><LoaderCircle class="spin" :size="22" /><span>正在读取任务…</span></div><div v-else-if="state.tasksError" class="inline-error"><AlertCircle :size="25" /><h3>暂时无法读取任务</h3><p>{{ state.tasksError }}</p><button class="button button-light button-small" @click="refresh"><RotateCcw :size="14" />重新加载</button></div><div v-else-if="visibleTasks.length" class="task-list"><TaskRow v-for="task in visibleTasks" :key="task.id" :task="task" /></div><EmptyState v-else :title="search ? '没有找到匹配的任务' : state.tasks.length ? '这个分类下暂无任务' : '还没有任务'" :description="search ? '试试其他关键词，或清空搜索查看全部任务。' : state.tasks.length ? '切换其他状态查看任务记录。' : '创建一个视频下载任务，所有处理进度都会在这里显示。'"><template #icon><Search v-if="search" :size="26" /><ListTodo v-else :size="26" /></template><button v-if="search" class="button button-light button-small" @click="search = ''">清空搜索</button><button v-else-if="state.tasks.length" class="button button-light button-small" @click="selectedTab = 'all'">查看全部</button><RouterLink v-else class="button button-primary button-small" to="/tools/video-download">开始下载<ArrowRight :size="14" /></RouterLink></EmptyState>
    </section><p class="tasks-bottom-note"><Clock3 :size="14" />任务记录保存在本地。离开当前页面后，下载仍会继续。</p></div>
</template>
