<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { AlertCircle, ArrowLeft, ArrowRight, Check, ChevronRight, ClipboardPaste, Download, ExternalLink, Film, Image, Images, Info, Link2, ListTodo, LoaderCircle, Sparkles, X } from 'lucide-vue-next'
import type { XhsAsset, XhsNote } from '../../shared/types'
import { api, errorMessage } from '../../shared/api'
import { duration } from '../../shared/format'
import { notify, refreshTasks, state } from '../../shared/state'

const router = useRouter()
const text = ref('')
const note = ref<XhsNote | null>(null)
const parsedText = ref('')
const selectedIds = ref<string[]>([])
const resolving = ref(false)
const creating = ref(false)
const error = ref('')
const failedPreviews = ref(new Set<string>())
const labels = { image: '图片', video: '视频' }
const icons = { image: Image, video: Film }
const watermarkLabels = { none: '源文件无平台水印', present: '有平台水印', unknown: '水印状态未确认' }
const stale = computed(() => note.value !== null && text.value.trim() !== parsedText.value)
const canResolve = computed(() => !!text.value.trim() && !resolving.value && !creating.value)
function unavailableReason(asset: XhsAsset) {
  if (!asset.available) return asset.unavailable_reason || '暂时无法获取可导出的资源。'
  return ''
}
const available = computed(() => (note.value?.assets ?? []).filter(asset => !unavailableReason(asset)))
watch(available, assets => { selectedIds.value = selectedIds.value.filter(id => assets.some(asset => asset.id === id)) })
const selected = computed(() => available.value.filter(asset => selectedIds.value.includes(asset.id)))
const showWatermarkNote = computed(() => selected.value.some(asset => asset.kind === 'video' && asset.watermark_status !== 'none'))
const outputLabel = computed(() => selected.value.length > 1 ? 'ZIP · 批量打包' : selected.value[0]?.kind === 'video' ? 'MP4 视频' : '图片文件')
const counts = computed(() => (['image', 'video'] as const).map(kind => ({ kind, count: note.value?.assets.filter(asset => asset.kind === kind).length ?? 0 })))

async function resolve() {
  if (!canResolve.value) return
  error.value = ''; resolving.value = true; note.value = null; selectedIds.value = []; failedPreviews.value = new Set()
  const input = text.value.trim()
  try {
    const result = await api.resolveXhs(input)
    if (!result.assets.length) throw new Error('这篇笔记暂时没有可导出的图片或视频。')
    note.value = result; parsedText.value = input
  } catch (cause) { error.value = errorMessage(cause) }
  finally { resolving.value = false }
}
async function paste() {
  try { text.value = await navigator.clipboard.readText(); error.value = '' }
  catch { notify('无法读取剪贴板，请在输入框内手动粘贴。', 'error') }
}
function clear() { text.value = ''; note.value = null; selectedIds.value = []; error.value = '' }
function selectAll() { selectedIds.value = available.value.slice(0, 100).map(asset => asset.id) }
async function exportAssets() {
  if (!note.value || !selected.value.length || selected.value.length > 100 || stale.value || creating.value) return
  creating.value = true; error.value = ''
  try {
    const task = await api.exportXhs(parsedText.value, selected.value.map(asset => asset.id))
    await refreshTasks(); notify('导出任务已加入队列')
    await router.push({ path: '/tasks', query: { focus: task.id } })
  } catch (cause) { error.value = errorMessage(cause) }
  finally { creating.value = false }
}
</script>

<template>
  <div class="tool-page xhs-page">
    <RouterLink class="back-link" to="/"><ArrowLeft :size="15" />返回工具箱</RouterLink>
    <div class="page-heading tool-heading">
      <div class="heading-with-icon"><div class="tool-icon large"><Images :size="28" :stroke-width="1.7" /></div><div><div class="eyebrow small">图片与影音 <ChevronRight :size="11" /> 小红书</div><h1>小红书导出</h1><p>选好想保存的画面，把图片和视频带走。</p></div></div>
      <RouterLink class="button button-light" to="/tasks"><ListTodo :size="16" />查看任务</RouterLink>
    </div>
    <div class="banner warning xhs-live-notice" role="note"><Info :size="18" /><span>暂不支持直接导出 Live Photo，Live 内容可分别导出静态图片和 MP4 视频。</span></div>
    <div class="tool-layout"><div class="tool-main-column">
      <section class="panel input-panel" aria-labelledby="xhs-input-title">
        <div class="panel-heading"><div class="section-title"><span class="step-number">01</span><h2 id="xhs-input-title">粘贴分享内容</h2></div><span class="subtle-label">完整分享文案或链接 · 最多 5000 字符</span></div>
        <form @submit.prevent="resolve">
          <label class="sr-only" for="xhs-share-input">小红书分享文案或链接</label>
          <div class="share-textarea"><textarea id="xhs-share-input" v-model="text" :readonly="resolving || creating" maxlength="5000" rows="5" placeholder="将小红书的分享文案或链接粘贴到这里…&#10;&#10;例如：https://xhslink.cn/o/…" /><div class="textarea-actions"><span><Link2 :size="14" />自动识别笔记链接</span><span class="input-counter">{{ text.length }} / 5000</span><button v-if="text" type="button" class="text-button" :disabled="resolving || creating" @click="clear"><X :size="13" />清空</button><button v-else type="button" class="text-button" @click="paste"><ClipboardPaste :size="14" />粘贴</button></div></div>
          <div class="input-footer"><p><Images :size="15" />导出图片或 MP4 视频</p><button type="submit" class="button button-primary" :disabled="!canResolve"><LoaderCircle v-if="resolving" class="spin" :size="16" /><Sparkles v-else :size="16" />{{ resolving ? '正在解析…' : '解析笔记' }}<ArrowRight v-if="!resolving" :size="15" /></button></div>
        </form>
        <div v-if="error" class="banner error input-error" role="alert"><AlertCircle :size="18" /><span>{{ error }}</span></div>
        <div v-if="resolving" class="resolve-progress" role="status"><span class="loading-dots"><i /><i /><i /></span><div><strong>正在读取笔记中的素材</strong><p>检查图片和动态资源，解析完成后可选择导出内容。</p></div></div>
      </section>

      <section v-if="note" class="panel result-panel" aria-labelledby="xhs-result-title">
        <div class="panel-heading"><div class="section-title"><span class="step-number">02</span><h2 id="xhs-result-title">选择导出内容</h2></div><span class="resolved-tag"><Check :size="13" />解析成功</span></div>
        <div class="xhs-note-details"><span class="platform-badge">小红书笔记</span><h3>{{ note.title }}</h3><div><span>{{ note.author || '作者信息未提供' }}</span><a :href="note.source_url" target="_blank" rel="noopener noreferrer" class="text-link">查看原笔记<ExternalLink :size="13" /></a></div></div>
        <div class="xhs-type-counts" aria-label="素材类型统计"><span v-for="item in counts.filter(item => item.count)" :key="item.kind"><component :is="icons[item.kind]" :size="14" />{{ labels[item.kind] }} {{ item.count }}</span></div>
        <div v-for="(warning, index) in note.warnings" :key="index" class="banner warning xhs-warning" role="status"><Info :size="17" /><span>{{ warning }}</span></div>
        <div class="xhs-selection-toolbar"><span>已选 <strong>{{ selected.length }}</strong> / {{ available.length }} 项可用素材</span><div><button class="text-button" :disabled="creating || !available.length" @click="selectAll">全选可用</button><button class="text-button" :disabled="creating || !selectedIds.length" @click="selectedIds = []">清空选择</button></div></div>
        <p v-if="available.length > 100" class="xhs-selection-note">每个任务最多选择 100 项素材，请分批导出。</p>
        <div class="xhs-asset-grid">
          <label v-for="asset in note.assets" :key="asset.id" class="xhs-asset-card" :class="{ selected: selectedIds.includes(asset.id) && !unavailableReason(asset), unavailable: !!unavailableReason(asset) }">
            <div class="xhs-asset-preview"><img v-if="asset.preview_url && !failedPreviews.has(asset.id)" :src="asset.preview_url" :alt="asset.label" loading="lazy" @error="failedPreviews.add(asset.id)" /><component :is="icons[asset.kind]" v-else :size="32" :stroke-width="1.4" /><span class="xhs-asset-kind"><component :is="icons[asset.kind]" :size="12" />{{ labels[asset.kind] }}</span><input v-model="selectedIds" type="checkbox" :value="asset.id" :aria-label="`选择${asset.label}`" :disabled="creating || !!unavailableReason(asset) || (selected.length >= 100 && !selectedIds.includes(asset.id))" /></div>
            <div class="xhs-asset-info"><strong>{{ asset.label }}</strong><span v-if="asset.width && asset.height">{{ asset.width }} × {{ asset.height }}<template v-if="asset.duration"> · {{ duration(asset.duration) }}</template></span><span class="xhs-watermark-status" :class="{ caution: asset.watermark_status !== 'none' }">{{ watermarkLabels[asset.watermark_status] || watermarkLabels.unknown }}</span><p v-if="unavailableReason(asset)" class="xhs-unavailable-reason">{{ unavailableReason(asset) }}</p></div>
          </label>
        </div>
        <div v-if="!available.length" class="banner warning xhs-warning" role="status"><Info :size="17" /><span>暂时没有可导出的素材，请查看上方原因或尝试其他笔记。</span></div>
        <div v-if="stale" class="banner warning xhs-warning" role="status"><Info :size="17" /><span>分享内容已修改，请重新解析后导出。</span></div>
        <div v-if="showWatermarkNote" class="xhs-watermark-note" role="note"><Info :size="17" /><p>所选视频包含有平台水印或水印状态未确认的资源。导出会保留源文件中的水印。</p></div>
        <div class="download-footer"><div><span>{{ selected.length ? '导出格式' : '勾选想保存的素材' }}</span><strong v-if="selected.length">{{ outputLabel }}</strong></div><button class="button button-primary" :disabled="creating || !selected.length || stale" @click="exportAssets"><LoaderCircle v-if="creating" class="spin" :size="17" /><Download v-else :size="17" />{{ creating ? '正在创建任务…' : `导出${selected.length ? ` ${selected.length} 项` : '所选'}` }}</button></div>
      </section>
      <div v-else-if="!resolving" class="awaiting-preview"><Images :size="24" :stroke-width="1.3" /><div><strong>笔记里的画面，将在这里展开</strong><p>解析后预览素材，选择需要的图片或视频。</p></div></div>
    </div>
    <aside class="tool-aside">
      <section class="panel guide-panel"><div class="guide-title"><span class="guide-icon"><Info :size="17" /></span><h2>保存你的灵感</h2></div><ol class="guide-steps"><li><span>1</span><div><h3>复制笔记链接</h3><p>在小红书笔记的分享菜单中选择「复制链接」。</p></div></li><li><span>2</span><div><h3>预览并选择素材</h3><p>完整分享文案也能解析。Live 内容的静态图片和动态视频可分别勾选。</p></div></li><li><span>3</span><div><h3>在任务中心下载</h3><p>单张图片或单个 MP4 视频直接导出，多项素材打包为 ZIP。</p></div></li></ol></section>
      <div class="usage-note"><Info :size="18" /><h3>关于源文件水印</h3><p>优先获取无平台水印的源文件；仅有带水印或状态未确认的视频时，会在素材卡片上标明。导出保留原有画面与水印，不承诺所有视频均无水印。</p></div>
      <div v-if="state.connection === 'online' && !state.health?.ffmpeg_available" class="banner warning"><Info :size="17" /><span>缺少视频校验组件，视频暂时无法完成导出。请运行项目安装脚本补齐依赖。</span></div>
      <div v-if="state.connection === 'online' && !state.health?.worker_running" class="banner warning"><Info :size="17" /><span>任务处理器暂未运行。新任务可以加入队列，恢复后继续处理。</span></div>
    </aside></div>
  </div>
</template>

<style scoped>
.xhs-note-details h3 { margin: 12px 0 10px; font-size: 18px; line-height: 1.6; overflow-wrap: anywhere; }
.xhs-live-notice { margin-bottom: 22px; align-items: flex-start; }
.xhs-live-notice > svg { margin-top: 2px; flex-shrink: 0; }
.xhs-note-details > div { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px; color: #68786e; font-size: 13px; }
.xhs-type-counts { display: flex; flex-wrap: wrap; gap: 9px; margin: 19px 0 23px; }
.xhs-type-counts > span { display: flex; gap: 6px; align-items: center; font-size: 12px; color: #587362; padding: 7px 10px; background: #f2f6f3; border-radius: 6px; }
.xhs-warning { margin: 14px 0; align-items: flex-start; }
.xhs-warning > span { min-width: 0; flex: 1; overflow-wrap: anywhere; }
.xhs-warning > svg { margin-top: 2px; }
.xhs-selection-toolbar { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; align-items: center; border-top: 1px solid var(--line); padding: 20px 0 16px; color: #68786e; font-size: 12px; }
.xhs-selection-toolbar strong { color: var(--green); }
.xhs-selection-toolbar > div { display: flex; gap: 15px; }
.xhs-selection-note { font-size: 12px; color: #68786e; margin-bottom: 15px; }
.xhs-asset-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; }
.xhs-asset-card { display: block; min-width: 0; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; cursor: pointer; background: #fff; transition: border-color .15s, box-shadow .15s; }
.xhs-asset-card.selected { border-color: #6c9a80; box-shadow: 0 0 0 1px #6c9a80; }
.xhs-asset-card.unavailable { cursor: default; background: #fafbf9; }
.xhs-asset-preview { position: relative; display: flex; align-items: center; justify-content: center; aspect-ratio: 4/5; background: #edf1ed; color: #92a798; }
.xhs-asset-preview > img { width: 100%; height: 100%; object-fit: contain; }
.xhs-asset-preview > input { position: absolute; right: 9px; top: 9px; width: 20px; height: 20px; margin: 0; accent-color: var(--green); cursor: pointer; }
.xhs-asset-preview > input:disabled { cursor: not-allowed; }
.xhs-asset-kind { position: absolute; display: flex; align-items: center; gap: 4px; bottom: 8px; left: 8px; padding: 4px 7px; border-radius: 5px; background: #243d32dc; color: #fff; font-size: 12px; }
.xhs-asset-info { display: flex; flex-direction: column; gap: 6px; padding: 12px 11px 13px; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.xhs-asset-info strong { font-size: 13px; font-weight: 600; color: #385442; }
.xhs-asset-info > span { color: #68786e; }
.xhs-unavailable-reason { color: #8b6639; }
.xhs-asset-info .xhs-watermark-status { color: var(--green); }
.xhs-asset-info .xhs-watermark-status.caution { color: #8b6639; }
.xhs-watermark-note { display: flex; align-items: flex-start; gap: 10px; margin-top: 20px; padding: 13px; border-radius: 8px; background: #f8f3e9; color: #8b6639; font-size: 12px; line-height: 1.8; }
.xhs-watermark-note svg { margin-top: 2px; flex-shrink: 0; }
.xhs-page .download-footer { gap: 16px; }
.xhs-page .download-footer > div { align-items: flex-start; flex-direction: column; gap: 5px; }
.xhs-page .download-footer strong { font-size: 12px; line-height: 1.7; }
@media (max-width: 1240px) and (min-width: 1011px) { .xhs-asset-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
@media (max-width: 600px) { .xhs-asset-grid { grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; } }
@media (max-width: 380px) { .xhs-asset-grid { gap: 9px; } .xhs-asset-info { padding: 10px 8px; } .xhs-page .download-footer { align-items: stretch; flex-direction: column; } }
</style>
