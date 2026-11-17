<script setup lang="ts">
import { computed, ref } from 'vue'
import { AlertCircle } from 'lucide-vue-next'
import BrowserToolPage from '../../shared/components/BrowserToolPage.vue'
import CopyTextButton from '../../shared/components/CopyTextButton.vue'
import { replaceSeparators } from './separators'

const presets = [
  { label: '换行', value: '\n' },
  { label: '空格', value: ' ' },
  { label: '制表符（Tab）', value: '\t' },
  { label: '英文逗号（,）', value: ',' },
  { label: '中文逗号（，）', value: '，' },
  { label: '英文分号（;）', value: ';' },
  { label: '中文分号（；）', value: '；' },
  { label: '顿号（、）', value: '、' },
  { label: '竖线（|）', value: '|' },
  { label: '斜杠（/）', value: '/' },
]
const source = ref('')
const sourceChoices = ref(['\n'])
const targetChoice = ref(',')
const customSource = ref('')
const customTarget = ref('')
const skipEmpty = ref(false)
const deduplicate = ref(false)

const sourceSeparators = computed(() => sourceChoices.value.map(choice => choice === 'custom' ? customSource.value : choice))
const targetSeparator = computed(() => targetChoice.value === 'custom' ? customTarget.value : targetChoice.value)
const error = computed(() => {
  if (!source.value) return ''
  if (!sourceSeparators.value.length) return '请至少选择一种原分隔符。'
  if (sourceSeparators.value.includes('')) return '请输入自定义原分隔符。'
  if (targetChoice.value === 'custom' && !targetSeparator.value) return '请输入自定义目标分隔符。'
  return ''
})
const output = computed(() => {
  if (!source.value || error.value) return ''
  return replaceSeparators(source.value, sourceSeparators.value, targetSeparator.value, {
    skipEmpty: skipEmpty.value,
    deduplicate: deduplicate.value,
  })
})
</script>

<template>
  <BrowserToolPage tool-id="separator-replace">
    <section class="panel browser-tool-panel" aria-label="分隔符替换">
      <div class="separator-settings">
        <fieldset class="separator-sources">
          <legend>原分隔符 <span class="browser-hint">可多选</span></legend>
          <div class="separator-choices">
            <label v-for="preset in presets" :key="preset.value" class="separator-choice">
              <input v-model="sourceChoices" type="checkbox" :value="preset.value" />{{ preset.label }}
            </label>
            <label class="separator-choice">
              <input v-model="sourceChoices" type="checkbox" value="custom" />自定义
            </label>
          </div>
          <label v-if="sourceChoices.includes('custom')" class="browser-field custom-separator" for="separator-custom-source">
            自定义原分隔符
            <input id="separator-custom-source" v-model="customSource" class="browser-control" type="text"
              spellcheck="false" placeholder="例如 ||" />
          </label>
        </fieldset>
        <div>
          <label class="browser-field" for="separator-target">
            目标分隔符
            <select id="separator-target" v-model="targetChoice" class="browser-control">
              <option v-for="preset in presets" :key="preset.value" :value="preset.value">{{ preset.label }}</option>
              <option value="">无分隔符</option>
              <option value="custom">自定义</option>
            </select>
          </label>
          <label v-if="targetChoice === 'custom'" class="browser-field custom-separator" for="separator-custom-target">
            自定义目标分隔符
            <input id="separator-custom-target" v-model="customTarget" class="browser-control" type="text"
              spellcheck="false" placeholder="例如 →" />
          </label>
        </div>
      </div>
      <div class="separator-choices">
        <label class="browser-inline-field">
          <input id="separator-skip-empty" v-model="skipEmpty" type="checkbox" />跳过空项
        </label>
        <label class="browser-inline-field">
          <input id="separator-deduplicate" v-model="deduplicate" type="checkbox" />去除重复项
        </label>
      </div>
      <div class="browser-tool-grid">
        <label class="browser-field" for="separator-source">
          原始文本
          <textarea id="separator-source" v-model="source" class="browser-editor" spellcheck="false"
            placeholder="粘贴待替换的文本" />
        </label>
        <label class="browser-field" for="separator-result">
          替换结果
          <textarea id="separator-result" :value="output" class="browser-editor" readonly spellcheck="false"
            placeholder="结果会实时显示在这里" />
        </label>
      </div>
      <div v-if="error" class="banner error" role="alert"><AlertCircle :size="17" /><span>{{ error }}</span></div>
      <div class="browser-actions">
        <CopyTextButton :text="output">复制结果</CopyTextButton>
        <button type="button" class="button button-ghost button-small" :disabled="!source" @click="source = ''">清空</button>
      </div>
    </section>
  </BrowserToolPage>
</template>

<style scoped>
.separator-settings {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 18px;
}
.separator-sources { min-width: 0; margin: 0; padding: 0; border: 0; }
.separator-sources legend { margin-bottom: 8px; padding: 0; color: var(--text); font-weight: 500; }
.separator-sources legend span { margin-left: 4px; font-weight: 400; }
.separator-choices { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.separator-choice {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 9px;
  border: 1px solid var(--line);
  border-radius: 7px;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
}
.separator-choice:has(input:checked) { border-color: #b9cbbb; background: var(--green-light); }
.separator-choices input { margin: 0; accent-color: var(--green); }
.custom-separator { margin-top: 12px; }
@media (max-width: 730px) {
  .separator-settings { grid-template-columns: minmax(0, 1fr); }
}
</style>
