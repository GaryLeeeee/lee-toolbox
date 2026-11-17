import type { Component } from 'vue'
import { Download, Images, Film } from 'lucide-vue-next'

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
export const categories: ToolCategory[] = [{ id: 'media', name: '图片与影音', description: '保存图片和视频，让素材整理更省心。', icon: Film }]
export const tools: ToolDefinition[] = [{
  id: 'video-download', name: '视频下载',
  description: '粘贴抖音分享链接，解析视频信息，选择画质并保存到本地。',
  category: 'media', tags: ['抖音', '视频', '下载', '分享链接'],
  route: '/tools/video-download', execution: 'server', icon: Download,
  component: () => import('../tools/video-download/VideoDownload.vue'),
}, {
  id: 'xiaohongshu-export', name: '小红书导出',
  description: '解析小红书分享链接，选择图片或视频导出；Live 内容可拆分保存，暂不直接导出 Live Photo。',
  category: 'media', tags: ['小红书', '图片', '视频', 'MP4', '导出'],
  route: '/tools/xiaohongshu-export', execution: 'server', icon: Images,
  component: () => import('../tools/xiaohongshu-export/XiaohongshuExport.vue'),
}]
