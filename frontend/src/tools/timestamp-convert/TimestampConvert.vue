<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { AlertCircle } from 'lucide-vue-next'
import BrowserToolPage from '../../shared/components/BrowserToolPage.vue'
import CopyTextButton from '../../shared/components/CopyTextButton.vue'
import { dateToTimestamps, timestampToDates, type DateZone, type TimestampUnit } from './timestamp'

const initialSeconds = Math.floor(Date.now() / 1000)
const currentSeconds = ref(initialSeconds)
let clockTimer: number | undefined

const timestamp = ref('')
const timestampUnit = ref<TimestampUnit>('milliseconds')
const dates = ref<ReturnType<typeof timestampToDates> | null>(null)
const timestampError = ref('')
const date = ref('')
const zone = ref<DateZone>('beijing')
const timestamps = ref<ReturnType<typeof dateToTimestamps> | null>(null)
const dateError = ref('')

watch([timestamp, timestampUnit], () => {
  dates.value = null
  timestampError.value = ''
}, { flush: 'sync' })

watch([date, zone], () => {
  timestamps.value = null
  dateError.value = ''
}, { flush: 'sync' })

function convertTimestamp() {
  dates.value = null
  timestampError.value = ''
  try {
    dates.value = timestampToDates(timestamp.value, timestampUnit.value)
  } catch (cause) {
    timestampError.value = cause instanceof Error ? cause.message : '时间戳转换失败。'
  }
}

function convertDate() {
  timestamps.value = null
  dateError.value = ''
  try {
    timestamps.value = dateToTimestamps(date.value, zone.value)
  } catch (cause) {
    dateError.value = cause instanceof Error ? cause.message : '日期转换失败。'
  }
}

function fillTimestamp(seconds = Math.floor(Date.now() / 1000)) {
  timestamp.value = String(timestampUnit.value === 'milliseconds' ? seconds * 1000 : seconds)
  convertTimestamp()
}

function fillDate(seconds = Math.floor(Date.now() / 1000)) {
  date.value = timestampToDates(String(seconds), 'seconds')[zone.value]
  convertDate()
}

function updateClock() {
  const now = Date.now()
  const seconds = Math.floor(now / 1000)
  currentSeconds.value = seconds
  clockTimer = window.setTimeout(updateClock, (seconds + 1) * 1000 - now)
}

fillTimestamp(initialSeconds)
fillDate(initialSeconds)
onMounted(updateClock)
onUnmounted(() => window.clearTimeout(clockTimer))
</script>

<template>
  <BrowserToolPage tool-id="timestamp-convert">
    <section class="panel timestamp-clock" aria-labelledby="timestamp-clock-title">
      <div>
        <h2 id="timestamp-clock-title">当前 Unix 时间戳（秒）</h2>
        <code>{{ currentSeconds }}</code>
      </div>
      <CopyTextButton :text="String(currentSeconds)" aria-label="复制当前时间戳" />
    </section>

    <div class="browser-tool-grid">
      <form class="panel browser-tool-panel" aria-labelledby="timestamp-to-date-title" @submit.prevent="convertTimestamp">
        <h2 id="timestamp-to-date-title">时间戳转日期</h2>
        <label class="browser-field" for="unix-timestamp">
          Unix 时间戳
          <input id="unix-timestamp" v-model="timestamp" class="browser-control" type="text" spellcheck="false"
            placeholder="1700000000" :aria-invalid="!!timestampError" />
        </label>
        <label class="browser-inline-field" for="timestamp-unit">
          输入单位
          <select id="timestamp-unit" v-model="timestampUnit" class="browser-control">
            <option value="auto">自动识别</option>
            <option value="seconds">秒</option>
            <option value="milliseconds">毫秒</option>
          </select>
        </label>
        <p v-if="timestampUnit === 'auto'" class="browser-hint">自动识别时，绝对值为 11 位及以上的整数按毫秒处理。</p>
        <div v-if="timestampError" class="banner error" role="alert"><AlertCircle :size="17" /><span>{{ timestampError }}</span></div>
        <div class="browser-actions">
          <button type="submit" class="button button-primary" :disabled="!timestamp.trim()">转换为日期</button>
          <button type="button" class="button button-light" aria-label="填入当前时间戳" @click="fillTimestamp()">填入当前时间</button>
        </div>
        <div v-if="dates" class="timestamp-result" aria-live="polite">
          <p class="browser-hint">按{{ dates.unit === 'seconds' ? '秒' : '毫秒' }}转换</p>
          <dl class="timestamp-values">
            <div>
              <dt>北京时间（UTC+08:00）</dt>
              <dd><code>{{ dates.beijing }}</code><CopyTextButton :text="dates.beijing" aria-label="复制北京时间" /></dd>
            </div>
            <div>
              <dt>UTC</dt>
              <dd><code>{{ dates.utc }}</code><CopyTextButton :text="dates.utc" aria-label="复制 UTC 时间" /></dd>
            </div>
          </dl>
        </div>
      </form>

      <form class="panel browser-tool-panel" aria-labelledby="date-to-timestamp-title" @submit.prevent="convertDate">
        <h2 id="date-to-timestamp-title">日期转时间戳</h2>
        <label class="browser-field" for="date-time">
          日期时间
          <input id="date-time" v-model="date" class="browser-control" type="text" spellcheck="false"
            placeholder="2026-01-01 12:30:00" :aria-invalid="!!dateError" />
        </label>
        <label class="browser-inline-field" for="date-zone">
          输入时区
          <select id="date-zone" v-model="zone" class="browser-control">
            <option value="beijing">北京时间（UTC+08:00）</option>
            <option value="utc">UTC</option>
          </select>
        </label>
        <div v-if="dateError" class="banner error" role="alert"><AlertCircle :size="17" /><span>{{ dateError }}</span></div>
        <div class="browser-actions">
          <button type="submit" class="button button-primary" :disabled="!date.trim()">转换为时间戳</button>
          <button type="button" class="button button-light" aria-label="填入当前时间的日期" @click="fillDate()">填入当前时间</button>
        </div>
        <div v-if="timestamps" class="timestamp-result" aria-live="polite">
          <dl class="timestamp-values">
            <div>
              <dt>秒</dt>
              <dd><code>{{ timestamps.seconds }}</code><CopyTextButton :text="timestamps.seconds" aria-label="复制秒级时间戳" /></dd>
            </div>
            <div>
              <dt>毫秒</dt>
              <dd><code>{{ timestamps.milliseconds }}</code><CopyTextButton :text="timestamps.milliseconds" aria-label="复制毫秒时间戳" /></dd>
            </div>
          </dl>
        </div>
      </form>
    </div>
  </BrowserToolPage>
</template>

<style scoped>
.timestamp-clock {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 18px;
  padding: 18px 24px;
}
.timestamp-clock h2 { margin-bottom: 6px; font-size: 13px; }
.timestamp-clock code { color: var(--green); font: 600 22px/1.35 var(--editor-font); font-variant-numeric: tabular-nums; }
.timestamp-result { padding-top: 16px; border-top: 1px solid var(--line); }
.timestamp-values { display: grid; gap: 14px; margin: 0; }
.timestamp-result > p { margin-bottom: 12px; }
.timestamp-values dt { margin-bottom: 5px; color: #57695e; font-size: 12px; }
.timestamp-values dd { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin: 0; }
.timestamp-values code { flex: 1; font: 13px var(--editor-font); overflow-wrap: anywhere; }
@media (max-width: 540px) { .timestamp-clock { padding: 16px 17px; } }
</style>
