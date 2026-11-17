import type { Component } from 'vue'
import { Binary, Braces, CalendarDays, Clock3, Code2, Diff, Download, Film, Images, Sparkles } from 'lucide-vue-next'

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
export const categories: ToolCategory[] = [{
  id: 'media', name: '图片与影音', description: '保存图片和视频，让素材整理更省心。', icon: Film,
}, {
  id: 'developer', name: '开发工具', description: '在浏览器中处理 JSON、时间戳、Base64 和文本。', icon: Code2,
}, {
  id: 'life', name: '生活工具', description: '计算日期，按生日查询星座与四象。', icon: CalendarDays,
}]
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
}, {
  id: 'json-format', name: 'JSON 格式化',
  description: '实时校验、格式化或压缩 JSON，保留原有字段顺序和数字精度。',
  category: 'developer', tags: ['JSON', '校验', '格式化', '压缩'],
  route: '/tools/json-format', execution: 'browser', icon: Braces,
  component: () => import('../tools/json-format/JsonFormat.vue'),
}, {
  id: 'timestamp-convert', name: '时间戳转换',
  description: '将秒级或毫秒级 Unix 时间戳与北京时间、UTC 日期互转。',
  category: 'developer', tags: ['时间戳', 'Unix', 'UTC', '日期'],
  route: '/tools/timestamp-convert', execution: 'browser', icon: Clock3,
  component: () => import('../tools/timestamp-convert/TimestampConvert.vue'),
}, {
  id: 'base64-convert', name: 'Base64 互转',
  description: '在 UTF-8 文本和 Base64 之间转换，支持中文和 Emoji。',
  category: 'developer', tags: ['Base64', 'Base64URL', '编码', '解码'],
  route: '/tools/base64-convert', execution: 'browser', icon: Binary,
  component: () => import('../tools/base64-convert/Base64Convert.vue'),
}, {
  id: 'text-diff', name: '文本差异对比',
  description: '逐行比较两段文本，标出新增、删除及对应行号。',
  category: 'developer', tags: ['文本', 'Diff', '差异', '对比'],
  route: '/tools/text-diff', execution: 'browser', icon: Diff,
  component: () => import('../tools/text-diff/TextDiff.vue'),
}, {
  id: 'date-calculator', name: '日期计算器',
  description: '计算两个日期相差多少天，也可按天或工作日向前、向后推算。',
  category: 'life', tags: ['日期', '天数', '工作日', '星期', '农历'],
  route: '/tools/date-calculator', execution: 'browser', icon: CalendarDays,
  component: () => import('../tools/date-calculator/DateCalculator.vue'),
}, {
  id: 'zodiac-lookup', name: '星座与四象',
  description: '输入公历生日查询星座与四象，查看十二星座日期和分组。',
  category: 'life', tags: ['星座', '生日', '四象', '火象', '土象', '风象', '水象'],
  route: '/tools/zodiac-lookup', execution: 'browser', icon: Sparkles,
  component: () => import('../tools/zodiac-lookup/ZodiacLookup.vue'),
}]
