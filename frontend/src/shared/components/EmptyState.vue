<script setup lang="ts">
import { Inbox } from 'lucide-vue-next'
defineProps<{ title: string; description: string; small?: boolean }>()
</script>
<template><div class="empty-state" :class="{ small }"><div class="empty-icon"><slot name="icon"><Inbox :size="25" :stroke-width="1.5" /></slot></div><h3>{{ title }}</h3><p>{{ description }}</p><slot /></div></template>
