<script setup lang="ts">
import { ArrowLeft, SearchX } from 'lucide-vue-next'
import EmptyState from '../shared/components/EmptyState.vue'
</script>
<template><div class="panel not-found"><EmptyState title="这个页面暂时找不到" description="链接可能有误，回到工具箱看看吧。"><template #icon><SearchX :size="28" /></template><RouterLink class="button button-primary" to="/"><ArrowLeft :size="16" />返回工具箱</RouterLink></EmptyState></div></template>
