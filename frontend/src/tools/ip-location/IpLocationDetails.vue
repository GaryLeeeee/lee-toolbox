<script setup lang="ts">
import CopyTextButton from '../../shared/components/CopyTextButton.vue'
import type { IpLocation } from './ip'

defineProps<{ location: IpLocation }>()
</script>

<template>
  <div class="ip-details">
    <div class="ip-address">
      <div class="ip-address-value">
        <span class="ip-version">{{ location.version }}</span>
        <code>{{ location.ip }}</code>
      </div>
      <CopyTextButton :text="location.ip" :aria-label="'复制 ' + location.version + ' 地址'">复制 IP</CopyTextButton>
    </div>
    <dl class="ip-fields">
      <div><dt>国家或地区</dt><dd>{{ location.country || '暂无数据' }}</dd></div>
      <div><dt>省份或州</dt><dd>{{ location.region || '暂无数据' }}</dd></div>
      <div><dt>城市</dt><dd>{{ location.city || '暂无数据' }}</dd></div>
    </dl>
  </div>
</template>

<style scoped>
.ip-details { display: grid; gap: 14px; }
.ip-address {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--green-light);
}
.ip-address-value { display: grid; flex: 1; gap: 2px; min-width: 0; }
.ip-version { color: var(--green); font-size: 12px; font-weight: 600; }
.ip-address code {
  min-width: 0;
  color: var(--green-dark);
  font: 500 16px/1.5 var(--editor-font);
  overflow-wrap: anywhere;
}
.ip-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0; }
.ip-fields dt { color: #57695e; font-size: 12px; }
.ip-fields dd { margin: 5px 0 0; color: var(--text); overflow-wrap: anywhere; }
</style>
