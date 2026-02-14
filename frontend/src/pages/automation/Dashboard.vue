<template>
  <div class="automation-dashboard">
    <div class="page-content">
      <!-- 页面标题 -->
      <div class="page-header">
        <div class="page-title">
          <Brain class="title-icon" :size="28" />
          <div>
            <h1>自动化中心</h1>
            <p class="subtitle">智能研判 · 自动化诊断 · 风险预警</p>
          </div>
        </div>
        <div class="date-selector" @click="openDatePicker">
          <Calendar class="calendar-icon" :size="20" />
          <input 
            ref="dateInputRef"
            type="date" 
            v-model="selectedDate" 
            @change="handleDateChange"
            :max="today"
          />
        </div>
      </div>

      <!-- 基地选择 -->
      <div class="base-section">
        <div class="section-header">
          <Building2 class="section-icon" :size="20" />
          <h3>选择基地</h3>
        </div>
        <div v-if="loadingSites" class="loading">加载基地列表中...</div>
        <div v-else-if="sites.length === 0" class="no-data">暂无基地数据</div>
        <div v-else class="base-grid">
          <div 
            v-for="site in sites" 
            :key="site.id"
            class="base-card"
            :class="{ active: selectedSiteId === site.id }"
            @click="handleSiteChange(site.id)"
          >
            <div class="base-icon">
              <Building2 :size="28" />
            </div>
            <div class="base-info">
              <div class="base-name">{{ site.site_name }}</div>
              <div class="base-desc">{{ site.description || '' }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div v-if="selectedSiteId" class="stats-section">
        <div class="section-header">
          <BarChart3 class="section-icon" :size="20" />
          <h3>统计概览</h3>
          <span class="date-display">{{ formatDateDisplay(selectedDate) }}</span>
        </div>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon samples">
              <Activity :size="24" />
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ summary.samples?.total || 0 }}</div>
              <div class="stat-label">采样总数</div>
              <div class="stat-sub">{{ summary.samples?.abnormal || 0 }} 异常 ({{ summary.samples?.abnormal_rate || 0 }}%)</div>
            </div>
          </div>

          <div class="stat-card clickable" @click="goToAbnormalSamples">
            <div class="stat-icon abnormal">
              <AlertTriangle :size="24" />
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ summary.samples?.abnormal || 0 }}</div>
              <div class="stat-label">异常条数</div>
            </div>
          </div>

          <div class="stat-card clickable" @click="goToAnalysisResults">
            <div class="stat-icon analysis">
              <Brain :size="24" />
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ summary.analysis?.total || 0 }}</div>
              <div class="stat-label">研判总数</div>
              <div class="stat-sub">{{ summary.analysis?.critical || 0 }} 严重 / {{ summary.analysis?.warning || 0 }} 警告</div>
            </div>
          </div>

          <div class="stat-card clickable" @click="goToTasks">
            <div class="stat-icon tasks">
              <Zap :size="24" />
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ summary.tasks?.total || 0 }}</div>
              <div class="stat-label">任务总数</div>
              <div class="stat-sub">成功率 {{ summary.tasks?.success_rate || 0 }}%</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 图表区域 -->
      <div v-if="selectedSiteId" class="charts-section">
        <div class="section-header">
          <LineChart class="section-icon" :size="20" />
          <h3>采样趋势（24小时）</h3>
        </div>
        <div class="charts-grid">
          <!-- 采样趋势图 -->
          <div class="chart-card">
            <div class="chart-content">
              <div v-if="loadingTrends" class="loading">加载中...</div>
              <div v-else-if="hourlyTrends.length > 0" class="trend-chart">
                <div class="trend-bars-container">
                  <div
                    v-for="(hour, index) in hourlyTrends"
                    :key="index"
                    class="trend-bar-group"
                  >
                    <div class="trend-bars">
                      <div
                        class="bar total"
                        :style="{ height: `${(hour.samples / maxHourlySamples) * 100}%` }"
                        :title="`总数: ${hour.samples}`"
                      ></div>
                      <div
                        class="bar abnormal"
                        :style="{ height: `${(hour.abnormal / maxHourlySamples) * 100}%` }"
                        :title="`异常: ${hour.abnormal}`"
                      ></div>
                    </div>
                    <div class="trend-label">{{ hour.hour }}</div>
                  </div>
                </div>
                <div class="trend-legend">
                  <div class="legend-item">
                    <div class="legend-color total"></div>
                    <span>总采样</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color abnormal"></div>
                    <span>异常采样</span>
                  </div>
                </div>
              </div>
              <div v-else class="no-data">暂无数据</div>
            </div>
          </div>

          <!-- 研判数量分布 -->
          <div class="chart-card">
            <div class="chart-header">
              <h4>研判数量分布</h4>
            </div>
            <div class="chart-content">
              <div v-if="summary.analysis" class="severity-distribution">
                <div class="severity-bar critical">
                  <div class="bar-fill" :style="{ width: `${getSeverityPercentage('critical')}%` }"></div>
                  <div class="bar-label">
                    <span class="label-text">严重</span>
                    <span class="label-value">{{ summary.analysis.critical || 0 }}</span>
                  </div>
                </div>
                <div class="severity-bar warning">
                  <div class="bar-fill" :style="{ width: `${getSeverityPercentage('warning')}%` }"></div>
                  <div class="bar-label">
                    <span class="label-text">警告</span>
                    <span class="label-value">{{ summary.analysis.warning || 0 }}</span>
                  </div>
                </div>
                <div class="severity-bar info">
                  <div class="bar-fill" :style="{ width: `${getSeverityPercentage('info')}%` }"></div>
                  <div class="bar-label">
                    <span class="label-text">信息</span>
                    <span class="label-value">{{ summary.analysis.info || 0 }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="no-data">暂无数据</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 任务状态分布 -->
      <div v-if="selectedSiteId" class="tasks-section">
        <div class="section-header">
          <Zap class="section-icon" :size="20" />
          <h3>任务状态分布</h3>
        </div>
        <div class="tasks-grid">
          <div class="task-card success">
            <div class="task-icon">
              <CheckCircle :size="24" />
            </div>
            <div class="task-content">
              <div class="task-value">{{ summary.tasks?.success || 0 }}</div>
              <div class="task-label">成功</div>
            </div>
          </div>
          <div class="task-card running">
            <div class="task-icon">
              <Clock :size="24" />
            </div>
            <div class="task-content">
              <div class="task-value">{{ summary.tasks?.running || 0 }}</div>
              <div class="task-label">运行中</div>
            </div>
          </div>
          <div class="task-card failed">
            <div class="task-icon">
              <XCircle :size="24" />
            </div>
            <div class="task-content">
              <div class="task-value">{{ summary.tasks?.failed || 0 }}</div>
              <div class="task-label">失败</div>
            </div>
          </div>
          <div class="task-card pending">
            <div class="task-icon">
              <Hourglass :size="24" />
            </div>
            <div class="task-content">
              <div class="task-value">{{ summary.tasks?.pending || 0 }}</div>
              <div class="task-label">待处理</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 反馈质量 -->
      <div v-if="selectedSiteId" class="tasks-section">
        <div class="section-header">
          <Brain class="section-icon" :size="20" />
          <h3>研判反馈质量</h3>
          <button class="btn-link" @click="goToFeedbackStats">查看详情</button>
        </div>
        <div class="tasks-grid">
          <div class="task-card success">
            <div class="task-content">
              <div class="task-value">{{ summary.feedback?.correct_rate || 0 }}%</div>
              <div class="task-label">正确率</div>
            </div>
          </div>
          <div class="task-card failed">
            <div class="task-content">
              <div class="task-value">{{ summary.feedback?.incorrect_rate || 0 }}%</div>
              <div class="task-label">误判率</div>
            </div>
          </div>
          <div class="task-card pending">
            <div class="task-content">
              <div class="task-value">{{ summary.feedback?.total || 0 }}</div>
              <div class="task-label">反馈总数</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Brain,
  Building2,
  Activity,
  Zap,
  BarChart3,
  LineChart,
  AlertTriangle,
  Calendar,
  CheckCircle,
  Clock,
  XCircle,
  Hourglass
} from 'lucide-vue-next'
import {
  getSites,
  getDashboardSummary,
  getDashboardHourlyTrends
} from '@/api/automation'

const router = useRouter()

// 状态
const loadingSites = ref(false)
const loadingTrends = ref(false)
const selectedSiteId = ref<number | null>(null)
const sites = ref<any[]>([])
const summary = ref<any>({})
const hourlyTrends = ref<any[]>([])
const selectedDate = ref(new Date().toISOString().split('T')[0])
const dateInputRef = ref<HTMLInputElement | null>(null)

// 计算属性
const today = computed(() => new Date().toISOString().split('T')[0])

const maxHourlySamples = computed(() => {
  if (hourlyTrends.value.length === 0) return 1
  return Math.max(...hourlyTrends.value.map((d: any) => d.samples))
})

// 方法
const formatDateDisplay = (date: string) => {
  const d = new Date(date)
  const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }
  return d.toLocaleDateString('zh-CN', options)
}

const getSeverityPercentage = (severity: string) => {
  const total = (summary.value.analysis?.total || 0)
  if (total === 0) return 0
  const count = summary.value.analysis?.[severity] || 0
  return Math.round((count / total) * 100)
}

const loadSites = async () => {
  loadingSites.value = true
  try {
    const data = await getSites()
    sites.value = data.sites || []
    // 默认选择第一个基地
    if (sites.value.length > 0 && !selectedSiteId.value) {
      selectedSiteId.value = sites.value[0].id
      // 基地选择完成后，加载其他数据
      await loadSummary()
    }
  } catch (error) {
    console.error('Failed to load sites:', error)
  } finally {
    loadingSites.value = false
  }
}

const loadSummary = async () => {
  if (!selectedSiteId.value) return
  try {
    const data = await getDashboardSummary({
      site_id: selectedSiteId.value,
      start_date: selectedDate.value,
      end_date: selectedDate.value
    })
    summary.value = data
    // 加载24小时趋势数据
    await loadHourlyTrends()
  } catch (error) {
    console.error('Failed to load summary:', error)
  }
}

const loadHourlyTrends = async () => {
  if (!selectedSiteId.value) return
  loadingTrends.value = true
  try {
    const data = await getDashboardHourlyTrends({
      site_id: selectedSiteId.value,
      date: selectedDate.value
    })
    hourlyTrends.value = data.trends
  } catch (error) {
    console.error('Failed to load hourly trends:', error)
  } finally {
    loadingTrends.value = false
  }
}

const handleSiteChange = (siteId: number) => {
  selectedSiteId.value = siteId
  loadSummary()
}

const handleDateChange = () => {
  if (selectedSiteId.value) {
    loadSummary()
  }
}

const openDatePicker = () => {
  if (dateInputRef.value) {
    dateInputRef.value.showPicker()
  }
}

const goToAbnormalSamples = () => {
  if (!selectedSiteId.value) return
  router.push({
    path: '/automation/samples',
    query: { start_date: selectedDate.value, end_date: selectedDate.value }
  })
}

const goToAnalysisResults = () => {
  if (!selectedSiteId.value) return
  router.push({
    path: '/automation/analysis-results',
    query: { start_date: selectedDate.value, end_date: selectedDate.value }
  })
}

const goToTasks = () => {
  if (!selectedSiteId.value) return
  router.push({
    path: '/automation/tasks',
    query: { start_date: selectedDate.value, end_date: selectedDate.value }
  })
}

const goToFeedbackStats = () => {
  if (!selectedSiteId.value) return
  router.push({
    path: '/automation/feedback-stats',
    query: { site_id: selectedSiteId.value.toString() }
  })
}

// 生命周期
onMounted(() => {
  loadSites()
})
</script>

<style scoped>
.automation-dashboard {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  color: #3b82f6;
}

h1 {
  font-size: 28px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 4px 0 0 0;
}

.date-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.date-selector:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.1);
}

.calendar-icon {
  color: #6b7280;
  pointer-events: none;
}

.date-selector input[type="date"] {
  border: none;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  outline: none;
  pointer-events: none;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.section-icon {
  color: #3b82f6;
}

.section-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  flex: 1;
}

.btn-link {
  border: 1px solid #dbe4f0;
  background: #fff;
  color: #2563eb;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}

.date-display {
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
}

.base-section,
.stats-section,
.charts-section,
.tasks-section {
  margin-bottom: 32px;
}

.base-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.base-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.base-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.base-card.active {
  border-color: #3b82f6;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
}

.base-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #dbeafe;
  border-radius: 12px;
  color: #3b82f6;
}

.base-name {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
}

.base-desc {
  font-size: 13px;
  color: #6b7280;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.stat-card.clickable {
  cursor: pointer;
  transition: all 0.2s;
}

.stat-card.clickable:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
  transform: translateY(-2px);
}

.stat-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.stat-icon.samples {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #3b82f6;
}

.stat-icon.abnormal {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #ef4444;
}

.stat-icon.analysis {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #f59e0b;
}

.stat-icon.tasks {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  color: #10b981;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 4px;
}

.stat-sub {
  font-size: 13px;
  color: #9ca3af;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
  gap: 16px;
}

.chart-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  min-height: 350px;
}

.chart-header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.chart-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.chart-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.trend-chart {
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.trend-bars-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 200px;
  padding: 16px 8px 8px 8px;
  border-bottom: 1px solid #e5e7eb;
  overflow-x: auto;
  overflow-y: hidden;
}

.trend-bar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  min-width: 40px;
  height: 100%;
}

.trend-bars {
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: 2px;
  width: 100%;
  min-width: 30px;
}

.trend-label {
  margin-top: 8px;
  font-size: 10px;
  color: #6b7280;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
}

.bar {
  flex: 1;
  min-width: 12px;
  border-radius: 3px 3px 0 0;
  transition: height 0.3s;
}

.bar.total {
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
}

.bar.abnormal {
  background: linear-gradient(180deg, #ef4444 0%, #dc2626 100%);
}

.trend-legend {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
}

.legend-color {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  flex-shrink: 0;
}

.legend-color.total {
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
}

.legend-color.abnormal {
  background: linear-gradient(180deg, #ef4444 0%, #dc2626 100%);
}

.severity-distribution {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.severity-bar {
  position: relative;
  height: 48px;
  background: #f9fafb;
  border-radius: 8px;
  overflow: hidden;
}

.bar-fill {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  transition: width 0.5s ease-out;
}

.severity-bar.critical .bar-fill {
  background: linear-gradient(90deg, #fecaca 0%, #fee2e2 100%);
}

.severity-bar.warning .bar-fill {
  background: linear-gradient(90deg, #fde68a 0%, #fef3c7 100%);
}

.severity-bar.info .bar-fill {
  background: linear-gradient(90deg, #bfdbfe 0%, #dbeafe 100%);
}

.bar-label {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}

.label-text {
  font-weight: 600;
}

.label-value {
  font-size: 18px;
  font-weight: 700;
}

.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.task-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  transition: all 0.2s;
}

.task-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.task-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.task-card.success .task-icon {
  background: #d1fae5;
  color: #10b981;
}

.task-card.running .task-icon {
  background: #dbeafe;
  color: #3b82f6;
}

.task-card.failed .task-icon {
  background: #fee2e2;
  color: #ef4444;
}

.task-card.pending .task-icon {
  background: #fef3c7;
  color: #f59e0b;
}

.task-value {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
}

.task-label {
  font-size: 13px;
  color: #6b7280;
}

.loading,
.no-data {
  padding: 40px;
  text-align: center;
  color: #9ca3af;
  font-size: 14px;
}
</style>
