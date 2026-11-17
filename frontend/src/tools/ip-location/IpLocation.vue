<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { AlertCircle, LoaderCircle, RefreshCw } from 'lucide-vue-next'
import BrowserToolPage from '../../shared/components/BrowserToolPage.vue'
import IpLocationDetails from './IpLocationDetails.vue'
import { fetchIpLocation, type IpLocation, type IpLookup, type IpVersion } from './ip'

interface LookupState {
  loading: boolean
  result: IpLocation | null
  error: string
}

const current = reactive<(LookupState & { version: IpVersion })[]>([
  { version: 'IPv4', loading: false, result: null, error: '' },
  { version: 'IPv6', loading: false, result: null, error: '' },
])
const manual = reactive<LookupState>({ loading: false, result: null, error: '' })
const input = ref('')
const requests = new Set<AbortController>()

const pendingVersions = computed(() => current.filter(state => state.loading).map(state => state.version))
const currentResults = computed(() => current.map(state => state.result).filter(result => result !== null))
const currentError = computed(() => current.find(state => state.error)?.error ?? '')

watch(input, () => {
  manual.result = null
  manual.error = ''
}, { flush: 'sync' })

async function lookup(state: LookupState, query: IpLookup) {
  if (state.loading) return
  state.loading = true
  state.result = null
  state.error = ''

  const controller = new AbortController()
  requests.add(controller)
  const timeout = window.setTimeout(() => controller.abort(), 8_000)
  try {
    state.result = await fetchIpLocation(query, controller.signal)
  } catch (error) {
    state.error = error instanceof Error ? error.message : 'IP 查询失败，请重试。'
  } finally {
    window.clearTimeout(timeout)
    requests.delete(controller)
    state.loading = false
  }
}

function refreshCurrent() {
  for (const state of current) void lookup(state, { version: state.version })
}

onMounted(refreshCurrent)
onUnmounted(() => requests.forEach(request => request.abort()))
</script>

<template>
  <BrowserToolPage tool-id="ip-location">
    <div class="browser-tool-grid">
      <section class="panel browser-tool-panel ip-panel" aria-labelledby="current-ip-title">
        <div class="browser-panel-heading">
          <h2 id="current-ip-title">当前公网 IP</h2>
          <button type="button" class="button button-light button-small" aria-label="刷新当前公网 IP"
            :disabled="pendingVersions.length > 0" @click="refreshCurrent">
            <RefreshCw :size="14" aria-hidden="true" />刷新
          </button>
        </div>
        <div v-if="currentResults.length" class="ip-current-results">
          <IpLocationDetails v-for="location in currentResults" :key="location.version" :location="location" />
        </div>
        <p v-if="pendingVersions.length" class="ip-loading browser-hint" role="status">
          <LoaderCircle :size="16" class="spin" aria-hidden="true" />正在查询 {{ pendingVersions.join(' 和 ') }}…
        </p>
        <div v-else-if="!currentResults.length && currentError" class="banner error" role="alert">
          <AlertCircle :size="17" aria-hidden="true" /><span>{{ currentError }}</span>
        </div>
      </section>

      <form class="panel browser-tool-panel ip-panel" aria-labelledby="ip-query-title" @submit.prevent="lookup(manual, { ip: input })">
        <h2 id="ip-query-title">查询其他 IP</h2>
        <div class="ip-query-controls">
          <label class="browser-field" for="ip-query-input">
            IP 地址
            <input id="ip-query-input" v-model="input" class="browser-control" type="text" spellcheck="false"
              autocomplete="off" autocapitalize="off" :disabled="manual.loading" placeholder="例如 8.8.8.8"
              :aria-describedby="manual.error ? 'ip-query-error' : undefined" />
          </label>
          <button type="submit" class="button button-primary" :disabled="!input.trim() || manual.loading">
            {{ manual.loading ? '查询中…' : '查询' }}
          </button>
        </div>
        <div v-if="manual.error" id="ip-query-error" class="banner error" role="alert">
          <AlertCircle :size="17" aria-hidden="true" /><span>{{ manual.error }}</span>
        </div>
        <IpLocationDetails v-else-if="manual.result" :location="manual.result" />
      </form>
    </div>
    <p class="browser-hint ip-source">
      归属地按公网出口估算。
      <a href="https://ip.sb/api/" target="_blank" rel="noreferrer">IP.SB 定位数据</a> ·
      <a href="https://download.geonames.org/export/dump/" target="_blank" rel="noreferrer">GeoNames 中文地名</a>
      （<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>）
    </p>
  </BrowserToolPage>
</template>

<style scoped>
.ip-panel h2 { font-size: 15px; }
.ip-loading { display: flex; align-items: center; gap: 7px; }
.ip-current-results { display: grid; gap: 16px; }
.ip-current-results > * + * { border-top: 1px solid var(--line); padding-top: 16px; }
.ip-query-controls { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 8px; }
.ip-query-controls button { min-height: 42px; }
.ip-source { margin-top: 12px; }
.ip-source a { color: var(--green); text-decoration: underline; text-underline-offset: 2px; }
</style>
