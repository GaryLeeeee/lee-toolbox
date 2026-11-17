<script setup lang="ts">
import { computed } from 'vue'
import { ArrowLeft } from 'lucide-vue-next'
import { tools } from '../../registry/tools'

const props = defineProps<{ toolId: string }>()
const tool = computed(() => tools.find(item => item.id === props.toolId))
</script>

<template>
  <div class="tool-page browser-tool-page">
    <RouterLink class="back-link" to="/"><ArrowLeft :size="15" />返回工具箱</RouterLink>
    <div v-if="tool" class="page-heading tool-heading">
      <div class="heading-with-icon">
        <div class="tool-icon large"><component :is="tool.icon" :size="28" :stroke-width="1.7" /></div>
        <div><h1>{{ tool.name }}</h1><p>{{ tool.description }}</p></div>
      </div>
    </div>
    <slot />
  </div>
</template>

<style>
.browser-tool-page {
  --editor-font: ui-monospace, 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
}
.browser-tool-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  align-items: start;
}
.browser-tool-panel {
  display: grid;
  gap: 18px;
  min-width: 0;
  padding: 24px;
}
.browser-tool-panel .banner { margin: 0; }
.browser-actions, .browser-panel-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
}
.browser-panel-heading { justify-content: space-between; }
.browser-field {
  display: grid;
  align-content: start;
  gap: 8px;
  min-width: 0;
  color: var(--text);
  font-weight: 500;
}
.browser-inline-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #57695e;
  font-size: 13px;
}
.browser-control, .browser-editor {
  width: 100%;
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid #dce6df;
  border-radius: 7px;
  background: #fff;
  color: var(--text);
  font-weight: 400;
}
.browser-inline-field .browser-control { width: auto; }
.browser-control:focus-visible, .browser-editor:focus-visible {
  outline: 2px solid #88bda4;
  outline-offset: 2px;
}
.browser-editor {
  min-height: 230px;
  padding: 13px;
  resize: vertical;
  font-family: var(--editor-font);
  font-size: 13px;
  line-height: 1.65;
  tab-size: 4;
}
.browser-editor[readonly] { background: #f6f8f6; }
.browser-hint { color: #607264; font-size: 12px; line-height: 1.65; }
.browser-error-message { overflow-wrap: anywhere; }
@media (max-width: 940px) {
  .browser-tool-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 540px) {
  .browser-tool-panel { padding: 17px; }
  .browser-editor { min-height: 180px; font-size: 16px; }
  .browser-control { font-size: 16px; }
}
</style>
