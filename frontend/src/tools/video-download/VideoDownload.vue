<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, Check, ChevronRight, ClipboardPaste, Download, ExternalLink, FileVideo, Film, Info, Link2, ListTodo, LoaderCircle, ShieldCheck, Sparkles, X, AlertCircle } from 'lucide-vue-next'
import type { MediaInfo } from '../../shared/types'
import { api, errorMessage } from '../../shared/api'
import { bytes, duration } from '../../shared/format'
import { notify, refreshTasks, state } from '../../shared/state'
const router = useRouter()
const text = ref('')
const media = ref<MediaInfo | null>(null)
const parsedText = ref('')
const selectedFormat = ref('')
const resolving = ref(false)
const creating = ref(false)
const error = ref('')
const imageFailed = ref(false)
const selected = computed(() => media.value?.formats.find(format => format.id === selectedFormat.value))
const stale = computed(() => media.value !== null && text.value.trim() !== parsedText.value.trim())
const canResolve = computed(() => text.value.trim().length > 0 && !resolving.value && !creating.value)
async function resolve() {
  if (!canResolve.value) return
  error.value = ''; resolving.value = true; media.value = null; imageFailed.value = false
  const input = text.value.trim()
  try {
    const result = await api.resolve(input)
    if (!result.formats.length) throw new Error('这条作品暂时没有可下载的视频版本。')
    media.value = result; parsedText.value = input; selectedFormat.value = result.formats[0]!.id
  } catch (cause) { error.value = errorMessage(cause) }
  finally { resolving.value = false }
}
async function paste() {
  try { text.value = await navigator.clipboard.readText(); error.value = '' }
  catch { notify('无法读取剪贴板，请在输入框内手动粘贴。', 'error') }
}
function clear() { text.value = ''; media.value = null; error.value = ''; selectedFormat.value = '' }
async function download() {
  if (!media.value || !selected.value || stale.value || creating.value) return
  creating.value = true; error.value = ''
  try {
    const task = await api.createTask(parsedText.value, selectedFormat.value)
    await refreshTasks(); notify('下载任务已加入队列')
    await router.push({ path: '/tasks', query: { focus: task.id } })
  } catch (cause) { error.value = errorMessage(cause) }
  finally { creating.value = false }
}
</script>

<template>
  <div class="tool-page">
    <RouterLink class="back-link" to="/"><ArrowLeft :size="15" />返回工具箱</RouterLink>
    <div class="page-heading tool-heading"><div class="heading-with-icon"><div class="tool-icon large"><Download :size="28" :stroke-width="1.7" /></div><div><div class="eyebrow small">图片与影音 <ChevronRight :size="11" /> 抖音</div><h1>视频下载</h1><p>粘贴分享链接，把喜欢的视频保存到本地。</p></div></div><RouterLink class="button button-light" to="/tasks"><ListTodo :size="16" />查看任务</RouterLink></div>
    <div class="tool-layout"><div class="tool-main-column">
      <section class="panel input-panel" aria-labelledby="input-title"><div class="panel-heading"><div class="section-title"><span class="step-number">01</span><h2 id="input-title">粘贴分享内容</h2></div><span class="subtle-label">完整分享文案或链接 · 最多 5000 字符</span></div>
        <form @submit.prevent="resolve"><label class="sr-only" for="share-input">抖音分享文案或链接</label><div class="share-textarea"><textarea id="share-input" v-model="text" :readonly="resolving || creating" maxlength="5000" rows="6" placeholder="将抖音的分享文案或链接粘贴到这里…&#10;&#10;例如：https://v.douyin.com/…" /><div class="textarea-actions"><span><Link2 :size="14" />自动识别分享链接</span><span class="input-counter">{{ text.length }} / 5000</span><button v-if="text" type="button" class="text-button" :disabled="resolving || creating" @click="clear"><X :size="13" />清空</button><button v-else type="button" class="text-button" @click="paste"><ClipboardPaste :size="14" />粘贴</button></div></div><div class="input-footer"><p><ShieldCheck :size="15" />仅下载公开可访问的视频</p><button type="submit" class="button button-primary" :disabled="!canResolve"><LoaderCircle v-if="resolving" class="spin" :size="16" /><Sparkles v-else :size="16" />{{ resolving ? '正在解析…' : '解析视频' }}<ArrowRight v-if="!resolving" :size="15" /></button></div></form>
        <div v-if="error" class="banner error input-error" role="alert"><AlertCircle :size="18" /><span>{{ error }}</span></div>
        <div v-if="resolving" class="resolve-progress" role="status"><span class="loading-dots"><i /><i /><i /></span><div><strong>正在获取作品信息</strong><p>正在检查分享链接和可用画质，通常需要几秒钟。</p></div></div>
      </section>
      <section v-if="media" class="panel result-panel" aria-labelledby="result-title"><div class="panel-heading"><div class="section-title"><span class="step-number">02</span><h2 id="result-title">选择画质并下载</h2></div><span class="resolved-tag"><Check :size="13" />解析成功</span></div><div class="media-preview"><div class="media-cover"><img v-if="media.cover_url && !imageFailed" :src="media.cover_url" :alt="`${media.title} 视频封面`" referrerpolicy="no-referrer" @error="imageFailed = true" /><Film v-else :size="30" :stroke-width="1.3" /><span>{{ duration(media.duration) }}</span></div><div class="media-details"><span class="platform-badge">抖音视频</span><h3>{{ media.title }}</h3><p>{{ media.author || '作者信息未提供' }}</p><a :href="media.source_url" target="_blank" rel="noopener noreferrer" class="text-link">查看原作品<ExternalLink :size="13" /></a></div></div>
        <fieldset class="format-fieldset"><legend>下载画质<span>按可用版本提供</span></legend><div class="format-options"><label v-for="(format, index) in media.formats" :key="format.id" class="format-option" :class="{ selected: selectedFormat === format.id }"><input v-model="selectedFormat" type="radio" name="format" :value="format.id" :disabled="creating" /><span class="custom-radio"><span /></span><div><strong>{{ format.label }}<em v-if="index === 0">推荐</em></strong><span>{{ format.width }} × {{ format.height }}<span class="meta-separator">·</span>{{ format.codec.toUpperCase() }}<span class="meta-separator">·</span>{{ bytes(format.size_bytes) }}</span></div><Check v-if="selectedFormat === format.id" class="format-check" :size="17" /></label></div></fieldset>
        <div v-if="stale" class="banner warning" role="status"><Info :size="17" /><span>分享内容已修改，请重新解析后下载。</span></div><div class="download-footer"><div><span>预计文件大小</span><strong>{{ bytes(selected?.size_bytes) }}</strong></div><button class="button button-primary" :disabled="creating || !selectedFormat || stale" @click="download"><LoaderCircle v-if="creating" class="spin" :size="17" /><Download v-else :size="17" />{{ creating ? '正在创建任务…' : '开始下载' }}</button></div>
      </section>
      <div v-else-if="!resolving" class="awaiting-preview"><FileVideo :size="23" :stroke-width="1.3" /><div><strong>视频信息将在这里显示</strong><p>解析完成后，可预览作品信息并选择下载画质。</p></div></div>
    </div><aside class="tool-aside"><section class="panel guide-panel"><div class="guide-title"><span class="guide-icon"><Info :size="17" /></span><h2>三步，保存视频</h2></div><ol class="guide-steps"><li><span>1</span><div><h3>复制分享链接</h3><p>在抖音作品页面点击分享，选择「复制链接」。</p></div></li><li><span>2</span><div><h3>粘贴并解析</h3><p>完整分享文案也可以，工具会自动识别其中的链接。</p></div></li><li><span>3</span><div><h3>选择画质，开始下载</h3><p>在任务中心查看进度，完成后即可下载文件。</p></div></li></ol></section><div class="usage-note"><ShieldCheck :size="18" /><h3>关于下载版本</h3><p>获取平台提供的播放文件。作者嵌入画面的标记会保留，画质以实际可用版本为准。</p></div><div v-if="state.connection === 'online' && !state.health?.ffmpeg_available" class="banner warning"><Info :size="17" /><span>缺少视频校验组件。请在项目目录执行 ./scripts/setup.sh 补齐依赖，然后重启服务。</span></div><div v-if="state.connection === 'online' && !state.health?.worker_running" class="banner warning"><Info :size="17" /><span>任务处理器暂未运行。新任务可以加入队列，恢复后继续处理。</span></div></aside></div>
  </div>
</template>
