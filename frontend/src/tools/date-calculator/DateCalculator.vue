<script setup lang="ts">
import { ref, watch } from 'vue'
import { AlertCircle } from 'lucide-vue-next'
import BrowserToolPage from '../../shared/components/BrowserToolPage.vue'
import CopyTextButton from '../../shared/components/CopyTextButton.vue'
import { daysBetween, offsetDate, todayInBeijing, type DayUnit } from './dates'

const today = todayInBeijing()
const firstDate = ref(today)
const secondDate = ref('')
const difference = ref<number | null>(null)
const differenceError = ref('')
const baseDate = ref(today)
const direction = ref<1 | -1>(1)
const amount = ref<number | ''>(1)
const unit = ref<DayUnit>('days')
const projected = ref<ReturnType<typeof offsetDate> | null>(null)
const projectionError = ref('')

watch([firstDate, secondDate], () => {
  difference.value = null
  differenceError.value = ''
})

watch([baseDate, direction, amount, unit], () => {
  projected.value = null
  projectionError.value = ''
})

function calculateDifference() {
  difference.value = null
  differenceError.value = ''
  try {
    difference.value = daysBetween(firstDate.value, secondDate.value)
  } catch (cause) {
    differenceError.value = cause instanceof Error ? cause.message : '日期差计算失败。'
  }
}

function calculateProjection() {
  projected.value = null
  projectionError.value = ''
  const count = amount.value
  try {
    if (typeof count !== 'number' || count < 0 || !Number.isSafeInteger(count)) {
      throw new Error('请输入大于或等于 0 的整数天数。')
    }
    projected.value = offsetDate(baseDate.value, count * direction.value, unit.value)
  } catch (cause) {
    projectionError.value = cause instanceof Error ? cause.message : '日期推算失败。'
  }
}
</script>

<template>
  <BrowserToolPage tool-id="date-calculator">
    <div class="browser-tool-grid">
      <form class="panel browser-tool-panel" aria-labelledby="date-difference-title" novalidate @submit.prevent="calculateDifference">
        <h2 id="date-difference-title">计算两个日期相差多少天</h2>
        <label class="browser-field" for="date-difference-first">
          第一个日期
          <input id="date-difference-first" v-model="firstDate" class="browser-control" type="date" min="0001-01-01" max="9999-12-31" />
        </label>
        <label class="browser-field" for="date-difference-second">
          第二个日期
          <input id="date-difference-second" v-model="secondDate" class="browser-control" type="date" min="0001-01-01" max="9999-12-31" />
        </label>
        <p class="browser-hint">按公历自然日计算，同一天相差 0 天。</p>
        <div v-if="differenceError" class="banner error" role="alert"><AlertCircle :size="17" /><span>{{ differenceError }}</span></div>
        <div class="browser-actions">
          <button type="submit" class="button button-primary" :disabled="!firstDate || !secondDate">计算天数</button>
        </div>
        <div v-if="difference !== null" class="calendar-result" role="status">
          <div class="calendar-value"><span>相差</span><strong>{{ difference }}</strong><span>天</span></div>
          <CopyTextButton :text="String(difference)" aria-label="复制相差天数" />
        </div>
      </form>

      <form class="panel browser-tool-panel" aria-labelledby="date-projection-title" novalidate @submit.prevent="calculateProjection">
        <h2 id="date-projection-title">向前或向后推算日期</h2>
        <label class="browser-field" for="date-projection-base">
          基准日期
          <input id="date-projection-base" v-model="baseDate" class="browser-control" type="date" min="0001-01-01" max="9999-12-31" />
        </label>
        <div class="date-offset-options">
          <label class="browser-field" for="date-projection-direction">
            方向
            <select id="date-projection-direction" v-model="direction" class="browser-control">
              <option :value="1">向后</option>
              <option :value="-1">向前</option>
            </select>
          </label>
          <label class="browser-field" for="date-projection-amount">
            天数
            <input id="date-projection-amount" v-model.number="amount" class="browser-control" type="number" min="0" step="1" inputmode="numeric" />
          </label>
          <label class="browser-field" for="date-projection-unit">
            单位
            <select id="date-projection-unit" v-model="unit" class="browser-control">
              <option value="days">自然日</option>
              <option value="workdays">工作日</option>
            </select>
          </label>
        </div>
        <p class="browser-hint">{{ unit === 'workdays' ? '工作日按周一至周五计算，从基准日期之后或之前开始计数。' : '从基准日期之后或之前开始计数。' }}</p>
        <div v-if="projectionError" class="banner error" role="alert"><AlertCircle :size="17" /><span>{{ projectionError }}</span></div>
        <div class="browser-actions">
          <button type="submit" class="button button-primary" :disabled="!baseDate || amount === ''">推算日期</button>
        </div>
        <div v-if="projected" class="calendar-result" role="status">
          <div>
            <div class="calendar-value">
              <strong><time :datetime="projected.date">{{ projected.date }}</time></strong><span>{{ projected.weekday }}</span>
            </div>
            <p v-if="projected.lunar" class="calendar-lunar">农历 {{ projected.lunar }}</p>
          </div>
          <CopyTextButton :text="projected.date" aria-label="复制推算日期" />
        </div>
      </form>
    </div>
  </BrowserToolPage>
</template>

<style scoped>
.date-offset-options { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, .85fr) minmax(0, 1fr); gap: 10px; }
.calendar-result {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px 14px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}
.calendar-value { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 9px; color: #57695e; }
.calendar-value strong { color: var(--green); font: 650 21px/1.35 var(--editor-font); }
.calendar-lunar { margin-top: 5px; color: #57695e; font-size: 13px; }
@media (max-width: 420px) {
  .date-offset-options { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .date-offset-options .browser-field:last-child { grid-column: 1 / -1; }
}
</style>
