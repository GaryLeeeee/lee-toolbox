<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowRight, ArrowUpRight, Search, Star, X, LayoutGrid, Clock3, Download, CheckCheck, Layers3, Sparkles, RotateCcw, LoaderCircle } from 'lucide-vue-next'
import { tools, categories } from '../registry/tools'
import { favorites, recent, toggleFavorite } from '../shared/preferences'
import { state, activeTasks, completedTasks, refreshTasks } from '../shared/state'
import TaskRow from '../shared/components/TaskRow.vue'
import EmptyState from '../shared/components/EmptyState.vue'
const route = useRoute()
const query = ref('')
const category = computed(() => categories.find(item => item.id === route.query.category))
const view = computed(() => route.query.view || 'all')
const pageTitle = computed(() => category.value?.name || (view.value === 'favorites' ? '你的常用，随手可及' : view.value === 'recent' ? '接着上次，继续使用' : '你的日常工具箱'))
const pageDescription = computed(() => category.value ? category.value.description : view.value === 'favorites' ? '收藏喜欢的工具，下次更快找到。' : view.value === 'recent' ? '你最近打开过的工具，都在这里。' : '把重复的小事交给工具，把时间留给更重要的事。')
const filteredTools = computed(() => {
  let list = tools.filter(tool => !category.value || tool.category === category.value.id)
  if (view.value === 'favorites') list = list.filter(tool => favorites.value.includes(tool.id))
  if (view.value === 'recent') list = [...list.filter(tool => recent.value.includes(tool.id))].sort((a, b) => recent.value.indexOf(a.id) - recent.value.indexOf(b.id))
  const term = query.value.trim().toLowerCase()
  return list.filter(tool => !term || [tool.name, tool.description, ...tool.tags].join(' ').toLowerCase().includes(term))
})
const today = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }).format(new Date())
</script>

<template>
  <div class="home-page">
    <div class="page-heading home-heading"><div><div class="eyebrow"><span class="eyebrow-line" />YOUR EVERYDAY WORKSPACE</div><h1>{{ pageTitle }}</h1><p>{{ pageDescription }}</p></div><div class="today-badge"><span class="today-dot" />{{ today }}</div></div>
    <div class="overview-strip"><div><span class="overview-icon"><LayoutGrid :size="18" /></span><strong>{{ tools.length }}</strong><span>可用工具</span></div><span class="overview-divider" /><div><span class="overview-icon"><Download :size="18" /></span><strong>{{ activeTasks.length }}</strong><span>进行中任务</span></div><span class="overview-divider" /><div><span class="overview-icon"><CheckCheck :size="18" /></span><strong>{{ completedTasks.length }}</strong><span>已完成任务</span></div><span class="overview-caption">井井有条，轻松开始<ArrowUpRight :size="16" /></span></div>
    <section class="tools-section" aria-labelledby="tools-title">
      <div class="section-toolbar"><div class="section-title"><h2 id="tools-title">{{ category?.name || (view === 'favorites' ? '我的收藏' : view === 'recent' ? '最近使用' : '探索工具') }}</h2><span class="count-label">{{ filteredTools.length }}</span></div><div class="search-field"><Search :size="17" /><input v-model="query" type="search" aria-label="搜索工具" placeholder="搜索工具名称或关键词…" /><button v-if="query" class="icon-button" aria-label="清空搜索" @click="query = ''"><X :size="14" /></button><span v-else class="search-hint">搜索</span></div></div>
      <div v-if="filteredTools.length" class="tool-grid">
        <article v-for="tool in filteredTools" :key="tool.id" class="tool-card">
          <div class="tool-card-top"><div class="tool-icon"><component :is="tool.icon" :size="25" :stroke-width="1.8" /></div><button class="favorite-button" :class="{ selected: favorites.includes(tool.id) }" :aria-label="favorites.includes(tool.id) ? `取消收藏${tool.name}` : `收藏${tool.name}`" :aria-pressed="favorites.includes(tool.id)" @click="toggleFavorite(tool.id)"><Star :size="18" /></button></div>
          <RouterLink :to="tool.route" class="tool-title-link"><h3>{{ tool.name }}</h3><ArrowUpRight :size="19" /></RouterLink>
          <p class="tool-description">{{ tool.description }}</p>
          <div class="tool-tags"><span v-for="tag in tool.tags.slice(0, 1)" :key="tag">{{ tag }}</span><span>{{ categories.find(category => category.id === tool.category)?.name || tool.category }}</span></div>
          <div class="tool-card-bottom"><span class="tool-availability"><span />即开即用</span><RouterLink :to="tool.route">打开工具<ArrowRight :size="15" /></RouterLink></div>
        </article>
        <div v-if="view === 'all' && !query && !category" class="workspace-note"><div class="note-decoration"><Layers3 :size="29" :stroke-width="1.3" /><span /></div><div><span class="small-label">一个入口，更多可能</span><h3>工具各司其职，工作井井有条。</h3><p>在这里找到实用工具，集中查看处理任务。<br />用得顺手的，点亮星标留在收藏里。</p><span class="note-footer"><Sparkles :size="14" />为你的日常，一点点积累。</span></div></div>
      </div>
      <EmptyState v-else :title="query ? '没有找到匹配的工具' : view === 'favorites' ? '还没有收藏工具' : '还没有使用记录'" :description="query ? '试试“图片”“小红书”“抖音”或其他关键词。' : view === 'favorites' ? '在工具卡片上点亮星标，常用工具就会出现在这里。' : '打开一个工具后，可以在这里快速找到它。'"><template #icon><Search v-if="query" :size="25" /><Star v-else-if="view === 'favorites'" :size="25" /><Clock3 v-else :size="25" /></template><button v-if="query" class="button button-light button-small" @click="query = ''">清空搜索</button><RouterLink v-else class="button button-light button-small" to="/">浏览全部工具<ArrowRight :size="14" /></RouterLink></EmptyState>
    </section>
    <section class="recent-section" aria-labelledby="recent-tasks-title"><div class="section-toolbar"><div class="section-title"><h2 id="recent-tasks-title">最近任务</h2><span class="section-subtitle">每一步进展，都有迹可循</span></div><RouterLink class="text-link" to="/tasks">查看全部<ArrowRight :size="15" /></RouterLink></div>
      <div class="panel task-list"><div v-if="state.tasksLoading" class="loading-state"><LoaderCircle class="spin" :size="20" /><span>正在读取任务…</span></div><div v-else-if="state.tasksError" class="inline-error"><p>{{ state.tasksError }}</p><button class="button button-light button-small" @click="refreshTasks"><RotateCcw :size="14" />重新加载</button></div><template v-else-if="state.tasks.length"><TaskRow v-for="task in state.tasks.slice(0, 3)" :key="task.id" :task="task" compact /></template><EmptyState v-else title="还没有任务，从一个工具开始" description="选择工具、粘贴分享链接。任务进度会在这里实时显示。" small><RouterLink class="text-link" to="/tools/xiaohongshu-export">试试小红书导出<ArrowRight :size="15" /></RouterLink></EmptyState></div>
    </section>
  </div>
</template>
