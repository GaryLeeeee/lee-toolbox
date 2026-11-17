<script setup lang="ts">
import { computed, ref } from 'vue'
import { AlertCircle } from 'lucide-vue-next'
import BrowserToolPage from '../../shared/components/BrowserToolPage.vue'
import { dateRange, elementGroups, elementName, signForBirthday, signs } from './zodiac'

const birthday = ref('')
const result = computed(() => {
  if (!birthday.value) return { sign: null, error: '' }
  try {
    return { sign: signForBirthday(birthday.value), error: '' }
  } catch (cause) {
    return { sign: null, error: cause instanceof Error ? cause.message : '星座查询失败。' }
  }
})
</script>

<template>
  <BrowserToolPage tool-id="zodiac-lookup">
    <div class="browser-tool-grid zodiac-layout">
      <section class="panel browser-tool-panel" aria-labelledby="birthday-lookup-title">
        <h2 id="birthday-lookup-title">按生日查星座</h2>
        <label class="browser-field" for="zodiac-birthday">
          公历生日
          <input id="zodiac-birthday" v-model="birthday" class="browser-control" type="date" min="0001-01-01" max="9999-12-31" :aria-invalid="!!result.error" />
        </label>
        <div v-if="result.error" class="banner error" role="alert"><AlertCircle :size="17" /><span>{{ result.error }}</span></div>
        <div v-if="result.sign" class="zodiac-result" role="status">
          <div class="zodiac-result-symbol" aria-hidden="true">{{ result.sign.symbol }}</div>
          <div>
            <div class="zodiac-result-name">
              <h3>{{ result.sign.name }}</h3>
              <span class="element-badge" :class="result.sign.element">{{ elementName(result.sign.element) }}</span>
            </div>
            <p>{{ dateRange(result.sign) }}</p>
          </div>
        </div>
        <p class="browser-hint">查询按固定公历日期范围匹配，起止日期均包含在内。</p>
      </section>

      <aside class="zodiac-reference" aria-label="星座对照">
        <section class="panel browser-tool-panel" aria-labelledby="zodiac-dates-title">
          <h2 id="zodiac-dates-title">十二星座日期对照</h2>
          <table class="zodiac-table" aria-labelledby="zodiac-dates-title">
            <thead><tr><th scope="col">星座</th><th scope="col">公历日期</th><th scope="col">四象</th></tr></thead>
            <tbody>
              <tr v-for="sign in signs" :key="sign.name" :class="{ 'zodiac-match': result.sign?.name === sign.name }">
                <th scope="row"><span class="zodiac-symbol" aria-hidden="true">{{ sign.symbol }}</span>{{ sign.name }}</th>
                <td>{{ dateRange(sign) }}</td>
                <td><span class="element-badge" :class="sign.element">{{ elementName(sign.element) }}</span></td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="panel browser-tool-panel" aria-labelledby="zodiac-elements-title">
          <h2 id="zodiac-elements-title">四象分组</h2>
          <dl class="zodiac-elements">
            <div v-for="group in elementGroups" :key="group.id">
              <dt><span class="element-badge" :class="group.id">{{ group.name }}</span></dt>
              <dd>{{ group.signs.map(sign => sign.name).join('、') }}</dd>
            </div>
          </dl>
        </section>
      </aside>
    </div>
  </BrowserToolPage>
</template>

<style scoped>
.zodiac-layout { grid-template-columns: minmax(0, .8fr) minmax(0, 1.4fr); }
.zodiac-reference { display: grid; gap: 18px; min-width: 0; }
.zodiac-result {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 14px;
  border: 1px solid #dce9e0;
  border-radius: 8px;
  background: #f5f9f6;
}
.zodiac-result-symbol {
  display: grid;
  flex: 0 0 46px;
  height: 46px;
  place-items: center;
  border-radius: 8px;
  background: #e8f3eb;
  color: var(--green);
  font-size: 26px;
}
.zodiac-result-name { display: flex; flex-wrap: wrap; align-items: center; gap: 5px 9px; }
.zodiac-result h3 { color: var(--green); font-size: 19px; }
.zodiac-result p { margin-top: 3px; color: #57695e; font-size: 13px; }
.zodiac-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
.zodiac-table :is(th, td) { padding: 8px 6px; border-bottom: 1px solid var(--line); }
.zodiac-table thead { background: #f5f8f5; color: #53675a; }
.zodiac-table tr:last-child td, .zodiac-table tbody tr:last-child th { border-bottom: 0; }
.zodiac-table th { font-weight: 600; }
.zodiac-table th:first-child, .zodiac-table td:last-child { white-space: nowrap; }
.zodiac-symbol { display: inline-block; width: 22px; color: var(--green); }
.zodiac-match { background: #eaf4ed; }
.element-badge { display: inline-block; padding: 3px 7px; border-radius: 4px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.element-badge.fire { background: #f9eae5; color: #974027; }
.element-badge.earth { background: #f5eedd; color: #745722; }
.element-badge.air { background: #e2f1eb; color: #27674d; }
.element-badge.water { background: #e8effa; color: #375886; }
.zodiac-elements { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 15px; margin: 0; }
.zodiac-elements dd { margin: 6px 0 0; color: #53675a; font-size: 13px; line-height: 1.65; }
@media (max-width: 940px) { .zodiac-layout { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 420px) {
  .zodiac-table { font-size: 12px; }
  .zodiac-table :is(th, td) { padding-inline: 4px; }
  .zodiac-symbol { width: 16px; }
}
</style>
