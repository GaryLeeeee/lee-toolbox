<script setup lang="ts">
import { Copy } from 'lucide-vue-next'
import { notify } from '../state'

const props = defineProps<{ text: string }>()

async function copy() {
  try {
    await navigator.clipboard.writeText(props.text)
    notify('已复制到剪贴板')
  } catch {
    notify('无法访问剪贴板，请选中结果后手动复制。', 'error')
  }
}
</script>

<template>
  <button type="button" class="button button-light button-small" :disabled="!text" @click="copy">
    <Copy :size="14" aria-hidden="true" /><slot>复制</slot>
  </button>
</template>
