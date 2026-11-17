<script setup lang="ts">
import { computed, ref } from 'vue'
import { AlertCircle } from 'lucide-vue-next'
import BrowserToolPage from '../../shared/components/BrowserToolPage.vue'
import CopyTextButton from '../../shared/components/CopyTextButton.vue'
import JsonPreview from './JsonPreview.vue'
import { formatJson } from './json'

const source = ref('')
const outputFormat = ref<0 | 2 | 4>(2)

const result = computed(() => {
  if (!source.value.trim()) return { output: '', error: '' }
  try {
    return { output: formatJson(source.value, outputFormat.value), error: '' }
  } catch (cause) {
    return { output: '', error: cause instanceof Error ? cause.message : '无法处理这段 JSON。' }
  }
})
</script>

<template>
  <BrowserToolPage tool-id="json-format">
    <section class="panel browser-tool-panel" aria-label="JSON 格式处理">
      <div class="browser-tool-grid">
        <label class="browser-field" for="json-source">
          输入 JSON
          <textarea id="json-source" v-model="source" class="browser-editor" spellcheck="false"
            placeholder='粘贴 JSON，例如 {"name":"Lee","items":[]}' :aria-invalid="!!result.error" />
        </label>
        <div class="browser-field">
          <span id="json-result-label">处理结果</span>
          <JsonPreview :text="result.output" />
        </div>
      </div>
      <div v-if="result.error" class="banner error browser-error-message" role="alert"><AlertCircle :size="17" /><span>{{ result.error }}</span></div>
      <div class="browser-actions">
        <label class="browser-inline-field" for="json-output-format">
          输出格式
          <select id="json-output-format" v-model="outputFormat" class="browser-control">
            <option :value="2">缩进 2 个空格</option>
            <option :value="4">缩进 4 个空格</option>
            <option :value="0">压缩</option>
          </select>
        </label>
        <CopyTextButton :text="result.output">复制结果</CopyTextButton>
        <button type="button" class="button button-ghost" :disabled="!source" @click="source = ''">清空</button>
      </div>
    </section>
  </BrowserToolPage>
</template>
