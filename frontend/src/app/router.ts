import { createRouter, createWebHistory, type RouteComponent } from 'vue-router'
import { tools } from '../registry/tools'
import { markRecent } from '../shared/preferences'
const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', name: 'home', component: () => import('../pages/HomePage.vue'), meta: { title: '工作台' } },
    { path: '/tasks', name: 'tasks', component: () => import('../pages/TasksPage.vue'), meta: { title: '任务中心' } },
    ...tools.map(tool => ({ path: tool.route, name: tool.id, component: tool.component as () => Promise<RouteComponent>, meta: { title: tool.name, toolId: tool.id } })),
    { path: '/:pathMatch(.*)*', component: () => import('../pages/NotFound.vue'), meta: { title: '页面未找到' } },
  ],
})
router.afterEach(to => {
  document.title = `${String(to.meta.title || '日常工具箱')} · Lee Toolbox`
  if (typeof to.meta.toolId === 'string') markRecent(to.meta.toolId)
})
export default router
