<template>
  <div class="feedback-stats-page">
    <div class="page-header">
      <button @click="goBack" class="back-btn">返回</button>
      <h1>反馈统计详情</h1>
      <div class="filters">
        <div class="filter-chip">
          <Filter :size="14" />
          <select v-model="selectedDiagnosisTypeForTrend" @change="noop">
            <option value="">全部诊断类型</option>
            <option v-for="t in diagnosisTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div class="filter-chip">
          <Calendar :size="14" />
          <select v-model="windowDays" @change="loadAll">
            <option :value="7">近7天</option>
            <option :value="30">近30天</option>
          </select>
        </div>
        <div class="filter-chip">
          <Calendar :size="14" />
          <input type="date" v-model="startDate" @change="loadAll" />
        </div>
        <div class="filter-chip">
          <Calendar :size="14" />
          <input type="date" v-model="endDate" @change="loadAll" />
        </div>
        <div class="filter-chip">
          <Building2 :size="14" />
          <select v-model="selectedSiteId" @change="loadAll">
            <option :value="0">全部基地</option>
            <option v-for="site in sites" :key="site.id" :value="site.id">
              {{ site.site_name }}
            </option>
          </select>
        </div>
        <button class="export-btn" @click="exportCsv">
          <Download :size="14" />
          导出CSV
        </button>
      </div>
    </div>

    <div class="cards">
      <div class="card">
        <div class="label">诊断类型数</div>
        <div class="value">{{ statsData.total_types || 0 }}</div>
      </div>
      <div class="card">
        <div class="label">样本门槛</div>
        <div class="value">{{ minSamples }}</div>
      </div>
    </div>

    <div class="section">
      <h2>按诊断类型统计</h2>
      <div v-if="typeRows.length === 0" class="no-data">
        <CircleOff :size="20" />
        暂无反馈数据
      </div>
      <table v-else class="stats-table">
        <thead>
          <tr>
            <th>诊断类型</th>
            <th>总数</th>
            <th>正确率</th>
            <th>误判率</th>
            <th>部分正确率</th>
            <th>样本保护</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in typeRows"
            :key="row.diagnosis_type"
            @click="selectDiagnosisType(row.diagnosis_type)"
            :class="{ active: selectedDiagnosisType === row.diagnosis_type }"
          >
            <td>{{ row.diagnosis_type }}</td>
            <td>{{ row.total }}</td>
            <td>{{ toPercent(row.correct_rate) }}</td>
            <td>{{ toPercent(row.incorrect_rate) }}</td>
            <td>{{ toPercent(row.partial_rate) }}</td>
            <td>{{ row.is_sample_sufficient ? '通过' : '未达最小样本' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="section">
      <h2>正确率趋势 {{ selectedDiagnosisTypeForTrend ? `(${selectedDiagnosisTypeForTrend})` : '(全部类型)' }}</h2>
      <div class="metric-switch">
        <label><input type="radio" value="correct" v-model="chartMode" /> 正确率</label>
        <label><input type="radio" value="incorrect" v-model="chartMode" /> 误判率</label>
        <label><input type="radio" value="both" v-model="chartMode" /> 双线</label>
      </div>
      <div v-if="trendRows.length > 1" class="line-chart-wrap">
        <svg class="line-chart" viewBox="0 0 100 30" preserveAspectRatio="none">
          <polyline
            v-if="chartMode === 'correct' || chartMode === 'both'"
            :points="linePointsCorrect"
            fill="none"
            stroke="#2563eb"
            stroke-width="1.5"
          />
          <polyline
            v-if="chartMode === 'incorrect' || chartMode === 'both'"
            :points="linePointsIncorrect"
            fill="none"
            stroke="#dc2626"
            stroke-width="1.5"
          />
        </svg>
      </div>
      <div v-if="trendRows.length === 0" class="no-data">
        <CircleOff :size="20" />
        暂无趋势数据
      </div>
      <div v-else class="trend-list">
        <div v-for="point in trendRows" :key="`${point.type}-${point.date}`" class="trend-row">
          <span class="trend-date">{{ point.date }}</span>
          <div class="bar-wrap">
            <div
              class="bar"
              :class="chartMode === 'incorrect' ? 'incorrect' : 'correct'"
              :style="{ width: `${Math.round(displayRate(point) * 100)}%` }"
            ></div>
          </div>
          <span class="trend-value">{{ toPercent(displayRate(point)) }}</span>
          <span class="trend-meta">总{{ point.total }} / 误判{{ toPercent(point.incorrect_rate) }}</span>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>误判 TopN 与建议</h2>
      <div v-if="!insightsData.insights || insightsData.insights.length === 0" class="no-data">
        <CircleOff :size="20" />
        暂无洞察数据
      </div>
      <div v-else class="insight-list">
        <div v-for="item in insightsData.insights" :key="item.diagnosis_type" class="insight-item">
          <div class="insight-title">{{ item.diagnosis_type }}</div>
          <div class="insight-metrics">
            <span>样本: {{ item.total }}</span>
            <span>误判率: {{ toPercent(item.incorrect_rate) }}</span>
            <span>正确率: {{ toPercent(item.correct_rate) }}</span>
          </div>
          <div class="insight-suggestion">{{ item.suggestion }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Building2, Calendar, CircleOff, Download, Filter } from 'lucide-vue-next'
import { getFeedbackStats, getFeedbackTrends, getFeedbackInsights, getSites } from '@/api/automation'

const router = useRouter()
const route = useRoute()
const selectedSiteId = ref<number>(0)
const windowDays = ref<number>(30)
const minSamples = ref<number>(5)
const startDate = ref<string>('')
const endDate = ref<string>('')
const sites = ref<any[]>([])
const statsData = ref<any>({ total_types: 0, stats: {} })
const trendsData = ref<any>({ trends: {} })
const insightsData = ref<any>({ insights: [] })
const selectedDiagnosisType = ref<string>('')
const selectedDiagnosisTypeForTrend = ref<string>('')
const chartMode = ref<'correct' | 'incorrect' | 'both'>('correct')

const typeRows = computed(() => {
  const stats = statsData.value.stats || {}
  return Object.keys(stats).map((key) => ({
    diagnosis_type: key,
    ...stats[key]
  }))
})

const diagnosisTypes = computed(() => {
  const trends = trendsData.value.trends || {}
  return Object.keys(trends)
})

const trendRows = computed(() => {
  const trends = trendsData.value.trends || {}
  const rows: any[] = []
  Object.keys(trends).forEach((diagType) => {
    const selectedType = selectedDiagnosisTypeForTrend.value || selectedDiagnosisType.value
    if (selectedType && diagType !== selectedType) {
      return
    }
    ;(trends[diagType] || []).forEach((p: any) => rows.push({ type: diagType, ...p }))
  })
  rows.sort((a, b) => a.date.localeCompare(b.date))
  return rows
})

const toPercent = (v: number) => `${Math.round((v || 0) * 100)}%`
const noop = () => {}

const goBack = () => router.push('/automation/dashboard')

const selectDiagnosisType = (diagnosisType: string) => {
  selectedDiagnosisType.value = selectedDiagnosisType.value === diagnosisType ? '' : diagnosisType
  selectedDiagnosisTypeForTrend.value = selectedDiagnosisType.value
}

const buildLinePoints = (rateKey: 'correct_rate' | 'incorrect_rate') => {
  if (trendRows.value.length === 0) return ''
  const points = trendRows.value.map((p, i) => {
    const x = trendRows.value.length === 1 ? 0 : (i / (trendRows.value.length - 1)) * 100
    const y = 30 - Math.max(0, Math.min(30, (p[rateKey] || 0) * 30))
    return `${x},${y}`
  })
  return points.join(' ')
}

const linePointsCorrect = computed(() => buildLinePoints('correct_rate'))
const linePointsIncorrect = computed(() => buildLinePoints('incorrect_rate'))

const displayRate = (point: any) => {
  if (chartMode.value === 'incorrect') {
    return point.incorrect_rate || 0
  }
  return point.correct_rate || 0
}

const loadSites = async () => {
  const res = await getSites()
  sites.value = res.sites || []
}

const loadStats = async () => {
  const res = await getFeedbackStats({
    site_id: selectedSiteId.value || undefined,
    window_days: windowDays.value,
    min_samples: minSamples.value,
    start_date: startDate.value || undefined,
    end_date: endDate.value || undefined
  })
  statsData.value = res || { total_types: 0, stats: {} }
}

const loadTrends = async () => {
  const res = await getFeedbackTrends({
    site_id: selectedSiteId.value || undefined,
    window_days: windowDays.value,
    start_date: startDate.value || undefined,
    end_date: endDate.value || undefined
  })
  trendsData.value = res || { trends: {} }
}

const loadInsights = async () => {
  const res = await getFeedbackInsights({
    site_id: selectedSiteId.value || undefined,
    window_days: windowDays.value,
    min_samples: minSamples.value,
    top_n: 5,
    start_date: startDate.value || undefined,
    end_date: endDate.value || undefined
  })
  insightsData.value = res || { insights: [] }
}

const loadAll = async () => {
  await Promise.all([loadStats(), loadTrends(), loadInsights()])
}

const exportCsv = () => {
  const header = ['date', 'diagnosis_type', 'total', 'correct', 'incorrect', 'partial', 'correct_rate', 'incorrect_rate']
  const rows = trendRows.value.map((r: any) => [
    r.date,
    r.type,
    r.total,
    r.correct,
    r.incorrect,
    r.partial,
    r.correct_rate,
    r.incorrect_rate
  ])
  const insightHeader = ['', '', '', '', '', '', '', '']
  const insightTitle = ['insights_topn', 'diagnosis_type', 'total', 'correct_rate', 'incorrect_rate', 'sample_sufficient', 'suggestion', '']
  const insightRows = (insightsData.value.insights || []).map((i: any) => [
    'insight',
    i.diagnosis_type,
    i.total,
    i.correct_rate,
    i.incorrect_rate,
    i.is_sample_sufficient ? 'yes' : 'no',
    `"${String(i.suggestion || '').replace(/"/g, '""')}"`,
    ''
  ])
  const csv = [header, ...rows, insightHeader, insightTitle, ...insightRows].map((line) => line.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `feedback_trends_${windowDays.value}d.csv`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  if (route.query.site_id) {
    selectedSiteId.value = Number(route.query.site_id)
  }
  if (route.query.start_date) {
    startDate.value = String(route.query.start_date)
  }
  if (route.query.end_date) {
    endDate.value = String(route.query.end_date)
  }
  await loadSites()
  await loadAll()
})
</script>

<style scoped>
.feedback-stats-page {
  padding: 24px;
  max-width: 1280px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.filters {
  margin-left: auto;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #dbe2ea;
  border-radius: 8px;
  background: #fff;
  padding: 6px 10px;
}

.filter-chip select,
.filter-chip input {
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
}

.export-btn {
  border: 1px solid #d0d7e2;
  background: #fff;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.card {
  background: #fff;
  border: 1px solid #e8edf3;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}

.label {
  font-size: 12px;
  color: #667085;
}

.value {
  font-size: 24px;
  font-weight: 700;
}

.section {
  background: #fff;
  border: 1px solid #e8edf3;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}

.stats-table {
  width: 100%;
  border-collapse: collapse;
}

.stats-table th,
.stats-table td {
  padding: 10px 8px;
  border-bottom: 1px solid #eef2f6;
  text-align: left;
}

.stats-table tr.active {
  background: #eff6ff;
}

.trend-row {
  display: grid;
  grid-template-columns: 120px 1fr 70px 160px;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.line-chart-wrap {
  height: 80px;
  border: 1px solid #eef2f6;
  border-radius: 8px;
  padding: 6px;
  margin-bottom: 10px;
}

.line-chart {
  width: 100%;
  height: 100%;
}

.metric-switch {
  display: flex;
  gap: 14px;
  margin-bottom: 8px;
  font-size: 12px;
}

.bar-wrap {
  height: 10px;
  border-radius: 999px;
  background: #edf2f7;
  overflow: hidden;
}

.bar.correct {
  height: 100%;
  background: linear-gradient(90deg, #2e7d32, #66bb6a);
}

.bar.incorrect {
  height: 100%;
  background: linear-gradient(90deg, #dc2626, #f87171);
}

.no-data {
  color: #98a2b3;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.insight-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.insight-item {
  border: 1px solid #eef2f6;
  border-radius: 8px;
  padding: 10px;
}

.insight-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.insight-metrics {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #475467;
  margin-bottom: 6px;
}

.insight-suggestion {
  color: #0f172a;
  font-size: 13px;
}

.back-btn {
  border: 1px solid #d0d7e2;
  background: #fff;
  border-radius: 8px;
  padding: 6px 10px;
}
</style>
