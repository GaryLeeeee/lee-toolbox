<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowUpRight, Check, ChevronRight, Clock3, LayoutGrid, ListTodo, Menu, ShieldCheck, Star, X, AlertCircle } from 'lucide-vue-next'
import { categories, tools } from '../registry/tools'
import { favoriteCount } from '../shared/preferences'
import { activeTasks, refreshHealth, startPolling, state } from '../shared/state'
const route = useRoute()
const mobileOpen = ref(false)
const title = computed(() => route.meta.title || '工作台')
const isBrowserTool = computed(() => tools.some(tool => tool.id === route.meta.toolId && tool.execution === 'browser'))
let stop: (() => void) | undefined
onMounted(() => { stop = startPolling() })
onUnmounted(() => stop?.())
watch(() => route.fullPath, () => { mobileOpen.value = false })
const activeView = (value: string) => route.path === '/' && (route.query.view || 'all') === value && !route.query.category
const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') mobileOpen.value = false }
onMounted(() => document.addEventListener('keydown', escape))
onUnmounted(() => document.removeEventListener('keydown', escape))
</script>

<template>
  <a class="skip-link" href="#main-content">跳转到主要内容</a>
  <div class="app-shell">
    <button v-if="mobileOpen" class="sidebar-overlay" aria-label="关闭导航" @click="mobileOpen = false" />
    <aside class="sidebar" :class="{ 'is-open': mobileOpen }" aria-label="主要导航">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">L<span>•</span></span>
        <span class="brand-text">Lee Toolbox<span>让日常，简单一点</span></span>
      </RouterLink>
      <div class="sidebar-label">工作空间</div>
      <nav class="nav-list">
        <RouterLink to="/" :class="{ active: activeView('all') }"><LayoutGrid :size="18" /><span>全部工具</span><span class="nav-count">{{ tools.length }}</span></RouterLink>
        <RouterLink to="/?view=favorites" :class="{ active: activeView('favorites') }"><Star :size="18" /><span>我的收藏</span><span v-if="favoriteCount" class="nav-count">{{ favoriteCount }}</span></RouterLink>
        <RouterLink to="/?view=recent" :class="{ active: activeView('recent') }"><Clock3 :size="18" /><span>最近使用</span></RouterLink>
      </nav>
      <div class="sidebar-label category-label">工具分类</div>
      <nav class="nav-list">
        <RouterLink v-for="category in categories" :key="category.id" :to="{ path: '/', query: { category: category.id } }" :class="{ active: route.path === '/' && route.query.category === category.id }"><component :is="category.icon" :size="18" /><span>{{ category.name }}</span><span class="category-dot" /></RouterLink>
      </nav>
      <div class="sidebar-divider" />
      <nav class="nav-list">
        <RouterLink to="/tasks" :class="{ active: route.path === '/tasks' }"><ListTodo :size="18" /><span>任务中心</span><span v-if="activeTasks.length" class="nav-count task-count">{{ activeTasks.length }}</span></RouterLink>
      </nav>
      <div class="sidebar-bottom">
        <div class="local-note"><ShieldCheck :size="19" /><div><strong>你的本地工作空间</strong><p>文件保存在这台电脑上</p></div></div>
        <div class="sidebar-footer"><span>LEE TOOLBOX</span><span>v0.1.0</span></div>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="breadcrumbs"><button class="icon-button mobile-menu" aria-label="打开导航" :aria-expanded="mobileOpen" @click="mobileOpen = true"><Menu :size="21" /></button><span class="breadcrumb-root">工具箱</span><ChevronRight :size="14" /><strong>{{ title }}</strong></div>
        <div class="topbar-right">
          <button class="connection" :class="state.connection" :title="state.connection === 'offline' ? '点击重新检查连接' : '本地服务状态'" @click="refreshHealth"><span class="status-dot" />{{ state.connection === 'online' ? '本地服务已连接' : state.connection === 'offline' ? '本地服务未连接' : '正在连接服务' }}</button>
          <span class="topbar-divider" />
          <RouterLink to="/tasks" class="topbar-task" title="任务中心"><ListTodo :size="19" /><span>任务中心</span><span v-if="activeTasks.length" class="tiny-badge">{{ activeTasks.length }}</span></RouterLink>
          <span class="avatar" aria-label="本地用户">L</span>
        </div>
      </header>
      <main id="main-content" class="main-content">
        <div v-if="state.connection === 'offline' && !isBrowserTool" class="banner warning"><AlertCircle :size="18" /><span>本地服务暂时不可用，下载和任务功能需要服务连接。</span><button @click="refreshHealth">重新连接<ArrowUpRight :size="14" /></button></div>
        <RouterView />
      </main>
      <footer class="workspace-footer"><span>小工具，大帮手。</span><span>Made for your everyday workflow <span class="footer-dot">·</span> Lee Toolbox</span></footer>
    </div>
    <Transition name="toast"><div v-if="state.toast" class="toast" :class="state.toastKind" role="status"><Check v-if="state.toastKind === 'success'" :size="18" /><AlertCircle v-else :size="18" /><span>{{ state.toast }}</span><button class="icon-button" aria-label="关闭提示" @click="state.toast = ''"><X :size="15" /></button></div></Transition>
  </div>
</template>
