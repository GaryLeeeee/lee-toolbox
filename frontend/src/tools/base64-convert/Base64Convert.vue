<script setup lang="ts">
import { ref, watch } from 'vue'
import { AlertCircle } from 'lucide-vue-next'
import BrowserToolPage from '../../shared/components/BrowserToolPage.vue'
import CopyTextButton from '../../shared/components/CopyTextButton.vue'
import { decodeBase64, encodeBase64 } from './base64'

const source = ref('')
const output = ref('')
const error = ref('')

watch(source, () => {
  output.value = ''
  error.value = ''
})

function convert(transform: (value: string) => string) {
  output.value = ''
  error.value = ''
  try {
    output.value = transform(source.value)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法转换这段文本。'
  }
}
</script>

<template>
  <BrowserToolPage tool-id="base64-convert">
    <section class="panel browser-tool-panel" aria-label="Base64 转换">
      <div class="browser-tool-grid">
        <label class="browser-field" for="base64-source">
          输入
          <textarea id="base64-source" v-model="source" class="browser-editor" spellcheck="false"
            placeholder="粘贴 UTF-8 文本或 Base64" :aria-invalid="!!error" />
        </label>
        <label class="browser-field" for="base64-result">
          转换结果
          <textarea id="base64-result" :value="output" class="browser-editor" readonly spellcheck="false"
            placeholder="编码或解码后的结果" />
        </label>
      </div>
      <div v-if="error" class="banner error" role="alert"><AlertCircle :size="17" /><span>{{ error }}</span></div>
      <div class="browser-actions">
        <button type="button" class="button button-primary" :disabled="!source" @click="convert(encodeBase64)">编码为 Base64</button>
        <button type="button" class="button button-light" :disabled="!source.trim()" @click="convert(decodeBase64)">解码为文本</button>
        <CopyTextButton :text="output">复制结果</CopyTextButton>
        <button type="button" class="button button-ghost" :disabled="!source" @click="source = ''">清空</button>
      </div>
      <p class="browser-hint">解码也支持 Base64URL，结果按 UTF-8 读取。</p>
    </section>
  </BrowserToolPage>
</template>
