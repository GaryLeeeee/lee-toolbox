<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { buildJsonPreview } from './json'

const props = defineProps<{ text: string }>()
const lines = computed(() => buildJsonPreview(props.text))
const folded = ref(new Set<number>())

watch(() => props.text, () => folded.value.clear())

const visibleLines = computed(() => {
  const preview = lines.value ?? []
  const visible: typeof preview = []
  for (let index = 0; index < preview.length; index++) {
    const line = preview[index]
    visible.push(line)
    if (line.fold && folded.value.has(line.index)) index = line.fold.end
  }
  return visible
})

function toggle(index: number) {
  if (folded.value.has(index)) folded.value.delete(index)
  else folded.value.add(index)
}
</script>

<template>
  <div id="json-result" class="json-result" role="region" aria-labelledby="json-result-label">
    <template v-if="lines === null">
      <textarea :value="text" class="browser-editor" readonly spellcheck="false" aria-label="JSON 结果纯文本" />
      <p class="browser-hint">结果较长，当前以纯文本显示。</p>
    </template>
    <div v-else class="browser-editor json-preview" :tabindex="text ? 0 : undefined">
      <span v-if="!text" class="json-placeholder">结果随输入自动更新</span>
      <div v-for="line in visibleLines" :key="line.index" class="json-preview-line">
        <span class="json-fold-gutter">
          <button v-if="line.fold" type="button" class="json-fold" :aria-expanded="!folded.has(line.index)"
            :aria-label="`${folded.has(line.index) ? '展开' : '折叠'}第 ${line.index + 1} 行的${line.fold.label}`"
            @click="toggle(line.index)">{{ folded.has(line.index) ? '+' : '−' }}</button>
        </span>
        <code><span v-for="(token, index) in line.tokens" :key="index" :class="`json-${token.kind}`">{{ token.text }}</span><span v-if="line.fold && folded.has(line.index)" class="json-ellipsis"> … {{ line.fold.closing }}</span></code>
      </div>
    </div>
  </div>
</template>

<style scoped>
.json-result { min-width: 0; }
.json-preview {
  height: 230px;
  overflow: auto;
  background: #f6f8f6;
  color: #54665a;
}
.json-preview-line { display: flex; align-items: center; min-width: max-content; }
.json-preview-line code { font: inherit; white-space: pre; }
.json-fold-gutter { flex: 0 0 24px; min-height: 1em; user-select: none; }
.json-fold {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 1px solid #bdd5c7;
  border-radius: 4px;
  background: #fff;
  color: var(--green);
  font: 600 13px/1 var(--editor-font);
}
.json-fold:hover { border-color: #84b099; background: #eaf4ed; }
.json-key { color: #822c91; font-weight: 600; }
.json-string { color: #246d3d; }
.json-number { color: #145f9b; }
.json-boolean, .json-null { color: #9a4a16; }
.json-ellipsis { color: #607264; }
.json-placeholder { color: #6d776e; }
@media (max-width: 540px) {
  .json-preview { height: 180px; }
  .json-fold { width: 21px; height: 21px; }
}
</style>
