import type { Component } from 'vue'
import { Download, Film } from 'lucide-vue-next'

export interface ToolDefinition {
  id: string
  name: string
  description: string
  category: string
  tags: string[]
  route: string
  execution: 'browser' | 'server'
  icon: Component
  component: () => Promise<unknown>
}
export interface ToolCategory { id: string; name: string; description: string; icon: Component }
export const categories: ToolCategory[] = [{ id: 'media', name: '视频与音频', description: '处理视频与音频，让素材整理更省心。', icon: Film }]
export const tools: ToolDefinition[] = [{
  id: 'video-download', name: '视频下载',
  description: '粘贴抖音分享链接，解析视频信息，选择画质并保存到本地。',
  category: 'media', tags: ['抖音', '视频', '下载', '分享链接'],
  route: '/tools/video-download', execution: 'server', icon: Download,
  component: () => import('../tools/video-download/VideoDownload.vue'),
}]
