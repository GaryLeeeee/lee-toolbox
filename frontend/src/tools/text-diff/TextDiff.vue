<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { AlertCircle, Check } from 'lucide-vue-next'
import BrowserToolPage from '../../shared/components/BrowserToolPage.vue'
import { compareText } from './compare'

const original = ref('')
const modified = ref('')
const result = ref<ReturnType<typeof compareText> | null>(null)
const error = ref('')
const onlyChanges = ref(false)
const showWhitespace = ref(false)

const hasChanges = computed(() => !!(result.value && (result.value.added || result.value.removed)))
const visibleRows = computed(() => (result.value?.rows ?? []).filter(row => !onlyChanges.value || row.kind !== 'unchanged'))
const markers = { added: '+', removed: '−', unchanged: '' }

watch([original, modified], () => {
  result.value = null
  error.value = ''
})

function compare() {
  result.value = null
  error.value = ''
  try {
    result.value = compareText(original.value, modified.value)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '文本对比失败。'
  }
}

function displayLine(line: string) {
  return showWhitespace.value ? line.replaceAll(' ', '·').replaceAll('\t', '⇥') : line
}

function clear() {
  original.value = ''
  modified.value = ''
}
</script>

<template>
  <BrowserToolPage tool-id="text-diff">
    <form class="panel browser-tool-panel" @submit.prevent="compare">
      <div class="browser-tool-grid">
        <label class="browser-field" for="original-text">
          原始文本
          <textarea id="original-text" v-model="original" class="browser-editor" spellcheck="false" placeholder="粘贴原始文本" />
        </label>
        <label class="browser-field" for="modified-text">
          修改后文本
          <textarea id="modified-text" v-model="modified" class="browser-editor" spellcheck="false" placeholder="粘贴修改后的文本" />
        </label>
      </div>
      <div v-if="error" class="banner error" role="alert"><AlertCircle :size="17" /><span>{{ error }}</span></div>
      <div class="browser-actions">
        <button type="submit" class="button button-primary" :disabled="!original && !modified">对比文本</button>
        <button type="button" class="button button-ghost" :disabled="!original && !modified" @click="clear">清空</button>
      </div>
    </form>

    <section v-if="result" class="panel browser-tool-panel diff-result" aria-labelledby="diff-result-title">
      <div class="browser-panel-heading">
        <h2 id="diff-result-title">对比结果</h2>
        <div v-if="hasChanges" class="diff-options">
          <label><input v-model="onlyChanges" type="checkbox" />只看差异</label>
          <label><input v-model="showWhitespace" type="checkbox" />显示空白字符</label>
        </div>
      </div>
      <p v-if="!hasChanges" class="diff-identical" role="status"><Check :size="16" />两段文本一致</p>
      <template v-else>
        <div class="diff-counts" role="status">
          <span class="added">新增 {{ result.added }} 行</span>
          <span class="removed">删除 {{ result.removed }} 行</span>
        </div>
        <div class="diff-scroll" tabindex="0" aria-label="逐行差异">
          <table class="diff-table">
            <thead><tr><th scope="col">原文</th><th scope="col">新文</th><th scope="col">文本</th></tr></thead>
            <tbody>
              <tr v-for="row in visibleRows" :key="`${row.before ?? ''}:${row.after ?? ''}`" :class="row.kind">
                <td>{{ row.before }}</td>
                <td>{{ row.after }}</td>
                <td>
                  <div class="diff-content">
                    <span class="diff-marker">{{ markers[row.kind] }}</span>
                    <span><code>{{ displayLine(row.text) }}</code><span v-if="row.kind !== 'unchanged' && !row.endsWithNewline" class="diff-no-newline">无行尾换行</span></span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </section>
  </BrowserToolPage>
</template>

<style scoped>
.diff-result { margin-top: 18px; }
.diff-options, .diff-counts { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; }
.diff-options label, .diff-identical { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
.diff-options input { margin: 0; accent-color: var(--green); }
.diff-identical { color: var(--green); }
.diff-counts span { border-radius: 4px; padding: 4px 7px; font-size: 12px; }
.added { background: #eaf6ed; color: #1d5f3c; }
.removed { background: #fdf0ed; color: #873f32; }
.diff-scroll { max-height: 480px; overflow: auto; border: 1px solid var(--line); border-radius: 7px; }
.diff-scroll:focus-visible { outline: 2px solid #88bda4; outline-offset: 2px; }
.diff-table { width: 100%; table-layout: fixed; border-collapse: collapse; font: 13px/1.6 var(--editor-font); }
.diff-table :is(th, td):nth-child(-n+2) { width: 46px; text-align: right; color: #607264; }
.diff-table :is(th, td) { padding: 5px 8px; vertical-align: top; text-align: left; }
.diff-table th { position: sticky; top: 0; background: #f4f7f4; font-size: 12px; font-weight: 600; }
.diff-table td { border-top: 1px solid #e7ece880; }
.diff-content { display: grid; grid-template-columns: 1em minmax(0, 1fr); gap: 4px; }
.diff-marker { user-select: none; }
.diff-content code { font: inherit; white-space: pre-wrap; overflow-wrap: anywhere; tab-size: 4; }
.diff-no-newline { margin-left: 8px; font: 11px/1.6 var(--editor-font); color: #57695e; }
@media (max-width: 540px) {
  .diff-table :is(th, td):nth-child(-n+2) { width: 39px; }
  .diff-table :is(th, td) { padding-left: 5px; padding-right: 5px; }
}
</style>
