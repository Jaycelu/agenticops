<template>
  <div class="dashboard-page">
    <div class="dashboard-content">
      <section class="card section-top">
        <div class="section-title-row">
          <h1>AI 运维驾驶舱</h1>
          <p>统一站点视角，支持从报表到详情一键穿透</p>
        </div>
        <div class="site-selector-row">
          <label for="site-select">站点选择</label>
          <select id="site-select" v-model="selectedSiteName" :disabled="loading.sites">
            <option value="">全部站点</option>
            <option v-for="site in sites" :key="site.id" :value="site.name">
              {{ site.name }}
            </option>
          </select>
        </div>
      </section>

      <section class="middle-grid">
        <article class="card panel">
          <div class="panel-header">
            <h2>资产统计</h2>
            <span class="muted">按站点聚合设备 / 机柜 / 厂商</span>
          </div>

          <div class="metric-grid">
            <button class="metric-item" @click="goToAssets('device')">
              <span class="metric-value">{{ assetStats.totalDevices }}</span>
              <span class="metric-label">设备总数</span>
            </button>
            <button class="metric-item" @click="goToAssets('rack')">
              <span class="metric-value">{{ assetStats.totalRacks }}</span>
              <span class="metric-label">机柜</span>
            </button>
            <button class="metric-item" @click="goToAssets('device', { role: switchRoleLabel })">
              <span class="metric-value">{{ assetStats.switchCount }}</span>
              <span class="metric-label">交换机</span>
            </button>
            <button class="metric-item" @click="goToAssets('device', { role: controllerRoleLabel })">
              <span class="metric-value">{{ assetStats.controllerCount }}</span>
              <span class="metric-label">控制器</span>
            </button>
          </div>

          <div class="subsection">
            <h3>设备角色分布</h3>
            <div v-if="topRoleDistribution.length === 0" class="empty">暂无数据</div>
            <div v-else class="bars-list">
              <button
                v-for="item in topRoleDistribution"
                :key="item.label"
                class="bar-item"
                @click="goToAssets('device', { role: item.label })"
              >
                <span class="bar-label">{{ item.label }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: item.percent + '%' }"></div>
                </div>
                <span class="bar-count">{{ item.count }}</span>
              </button>
            </div>
          </div>

          <div class="subsection">
            <h3>厂商分布（NetBox manufacturer）</h3>
            <div v-if="topVendorDistribution.length === 0" class="empty">暂无数据</div>
            <div v-else class="bars-list">
              <button
                v-for="item in topVendorDistribution"
                :key="item.label"
                class="bar-item"
                @click="goToAssets('device', { vendor: item.label, keyword: item.label })"
              >
                <span class="bar-label">{{ item.label }}</span>
                <div class="bar-track">
                  <div class="bar-fill vendor" :style="{ width: item.percent + '%' }"></div>
                </div>
                <span class="bar-count">{{ item.count }}</span>
              </button>
            </div>
          </div>
        </article>

        <article class="card panel">
          <div class="panel-header">
            <h2>Zabbix 告警统计</h2>
            <span class="muted">按严重等级聚合</span>
          </div>

          <div class="metric-grid two-col">
            <button class="metric-item" @click="goToAlerts('critical')">
              <span class="metric-value critical">{{ alarmStats.critical }}</span>
              <span class="metric-label">严重</span>
            </button>
            <button class="metric-item" @click="goToAlerts('warning')">
              <span class="metric-value warning">{{ alarmStats.warning }}</span>
              <span class="metric-label">警告</span>
            </button>
          </div>

          <button class="metric-item full-width" @click="goToAlerts('all')">
            <span class="metric-value">{{ alarmStats.total }}</span>
            <span class="metric-label">实时告警总数</span>
          </button>

          <p class="muted small" v-if="selectedSiteName">
            当前按站点关键字近似过滤：{{ selectedSiteName }}
          </p>
        </article>
      </section>

      <section class="bottom-grid">
        <article class="card panel">
          <div class="panel-header">
            <h2>自动化执行趋势（24小时）</h2>
            <button class="link-btn" @click="goToAutomationAbnormal">异常条数：{{ automationSummary.tasks.failed || 0 }}</button>
          </div>

          <div v-if="hourlyTrends.length === 0" class="empty">暂无趋势数据</div>
          <div v-else class="hourly-trend">
            <div
              v-for="point in hourlyTrends"
              :key="point.hour"
              class="hour-col"
              :title="`${point.hour} 样本:${point.samples} 异常:${point.abnormal}`"
            >
              <div class="hour-bars">
                <div class="hour-bar total" :style="{ height: `${calcHourlyPercent(point.samples)}%` }"></div>
                <div class="hour-bar abnormal" :style="{ height: `${calcHourlyPercent(point.abnormal)}%` }"></div>
              </div>
              <span class="hour-label">{{ point.hour.slice(0, 2) }}</span>
            </div>
          </div>
        </article>

        <article class="card panel">
          <div class="panel-header">
            <h2>研判准确率分布</h2>
            <span class="muted">已整合原反馈统计接口</span>
          </div>

          <div class="metric-grid two-col">
            <div class="metric-item">
              <span class="metric-value success">{{ feedbackSummary.correctRate }}%</span>
              <span class="metric-label">正确率</span>
            </div>
            <div class="metric-item">
              <span class="metric-value danger">{{ feedbackSummary.incorrectRate }}%</span>
              <span class="metric-label">误判率</span>
            </div>
          </div>

          <div class="subsection">
            <div class="bars-list">
              <div class="bar-item static">
                <span class="bar-label">正确</span>
                <div class="bar-track"><div class="bar-fill success" :style="{ width: feedbackSummary.correctRate + '%' }"></div></div>
                <span class="bar-count">{{ feedbackSummary.correct }}</span>
              </div>
              <div class="bar-item static">
                <span class="bar-label">误判</span>
                <div class="bar-track"><div class="bar-fill danger" :style="{ width: feedbackSummary.incorrectRate + '%' }"></div></div>
                <span class="bar-count">{{ feedbackSummary.incorrect }}</span>
              </div>
              <div class="bar-item static">
                <span class="bar-label">部分正确</span>
                <div class="bar-track"><div class="bar-fill warning" :style="{ width: feedbackSummary.partialRate + '%' }"></div></div>
                <span class="bar-count">{{ feedbackSummary.partial }}</span>
              </div>
            </div>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { alertsApi } from '@/api/alerts'
import { assetsApi, Device, Site } from '@/api/assets'
import {
  getDashboardHourlyTrends,
  getDashboardSummary,
  getFeedbackStats,
  getSites as getAutomationSites
} from '@/api/automation'

interface DistributionItem {
  label: string
  count: number
  percent: number
}

interface HourTrend {
  hour: string
  samples: number
  abnormal: number
}

const router = useRouter()

const sites = ref<Site[]>([])
const selectedSiteName = ref<string>('')
const automationSites = ref<any[]>([])

const loading = ref({
  sites: false,
  data: false
})

const devices = ref<Device[]>([])
const rackCount = ref(0)
const alerts = ref<any[]>([])
const automationSummary = ref<any>({ tasks: { failed: 0 } })
const hourlyTrends = ref<HourTrend[]>([])
const feedbackStats = ref<Record<string, any>>({})

const switchRoleLabel = '交换机'
const controllerRoleLabel = '控制器'

const normalized = (value: string) => value.toLowerCase().replace(/[\s_-]/g, '')

const selectedSite = computed(() => sites.value.find((item) => item.name === selectedSiteName.value) || null)

const selectedAutomationSiteId = computed<number | undefined>(() => {
  if (!selectedSite.value) return undefined
  const siteTokens = [selectedSite.value.name, selectedSite.value.slug].filter(Boolean).map(normalized)
  const match = automationSites.value.find((site) => {
    const autoTokens = [site.site_name, site.site_code].filter(Boolean).map((value: string) => normalized(String(value)))
    return siteTokens.some((token) => autoTokens.includes(token))
  })
  return match?.id
})

const maxHourlySamples = computed(() => {
  const values = hourlyTrends.value.map((item) => Math.max(item.samples || 0, item.abnormal || 0))
  const max = Math.max(...values, 1)
  return max
})

const assetStats = computed(() => {
  const byRole = devices.value.reduce((acc: Record<string, number>, item) => {
    const key = item.role || '未标注'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})

  const switchCount = Object.entries(byRole)
    .filter(([role]) => /交换|switch/i.test(role))
    .reduce((sum, [, count]) => sum + count, 0)

  const controllerCount = Object.entries(byRole)
    .filter(([role]) => /控制|controller/i.test(role))
    .reduce((sum, [, count]) => sum + count, 0)

  return {
    totalDevices: devices.value.length,
    totalRacks: rackCount.value,
    switchCount,
    controllerCount,
    byRole
  }
})

const topRoleDistribution = computed<DistributionItem[]>(() => {
  const total = devices.value.length || 1
  return Object.entries(assetStats.value.byRole)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([label, count]) => ({
      label,
      count,
      percent: Math.round((count / total) * 100)
    }))
})

const topVendorDistribution = computed<DistributionItem[]>(() => {
  const total = devices.value.length || 1
  const byVendor = devices.value.reduce((acc: Record<string, number>, item) => {
    const key = item.vendor || '未标注'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})

  return Object.entries(byVendor)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([label, count]) => ({
      label,
      count,
      percent: Math.round((count / total) * 100)
    }))
})

const alarmStats = computed(() => {
  const all = alerts.value || []
  const critical = all.filter((item) => /灾难|严重|critical|high/i.test(String(item.severity || ''))).length
  const warning = all.filter((item) => /一般严重|警告|warning|medium/i.test(String(item.severity || ''))).length

  return {
    total: all.length,
    critical,
    warning
  }
})

const feedbackSummary = computed(() => {
  const rows = Object.values(feedbackStats.value || {}) as any[]
  const total = rows.reduce((sum, row) => sum + Number(row.total || 0), 0)
  const correct = rows.reduce((sum, row) => sum + Number(row.correct || 0), 0)
  const incorrect = rows.reduce((sum, row) => sum + Number(row.incorrect || 0), 0)
  const partial = rows.reduce((sum, row) => sum + Number(row.partial || 0), 0)

  const divide = (value: number) => (total > 0 ? Math.round((value / total) * 100) : 0)

  return {
    total,
    correct,
    incorrect,
    partial,
    correctRate: divide(correct),
    incorrectRate: divide(incorrect),
    partialRate: divide(partial)
  }
})

const calcHourlyPercent = (value: number) => Math.round((value / maxHourlySamples.value) * 100)

const loadSites = async () => {
  loading.value.sites = true
  try {
    const [assetResp, autoResp] = await Promise.all([assetsApi.getSites(), getAutomationSites()])
    sites.value = assetResp.sites || []
    automationSites.value = autoResp.sites || []

    if (!selectedSiteName.value && sites.value.length > 0) {
      selectedSiteName.value = sites.value[0].name
    }
  } catch (error) {
    console.error('Failed to load sites:', error)
  } finally {
    loading.value.sites = false
  }
}

const loadAssetsData = async () => {
  const siteName = selectedSiteName.value || undefined
  const [deviceResp, rackResp] = await Promise.all([
    assetsApi.getDevices(siteName ? { site: siteName } : undefined),
    assetsApi.getRacks(siteName ? { site: siteName } : undefined)
  ])

  devices.value = deviceResp.devices || []
  rackCount.value = rackResp.count || 0
}

const loadAlertsData = async () => {
  const response = await alertsApi.getAlerts({ limit: 2000 })
  const rows = response.alerts || []

  if (!selectedSite.value) {
    alerts.value = rows
    return
  }

  const tokens = [selectedSite.value.name, selectedSite.value.slug].filter(Boolean).map((item) => normalized(String(item)))
  alerts.value = rows.filter((item: any) => {
    const source = `${item.host || ''} ${item.name || ''}`
    const sourceNorm = normalized(source)
    return tokens.some((token) => sourceNorm.includes(token))
  })
}

const loadAutomationData = async () => {
  const siteId = selectedAutomationSiteId.value
  const date = new Date().toISOString().split('T')[0]

  const [summaryResp, trendResp, feedbackResp] = await Promise.all([
    getDashboardSummary({ site_id: siteId, start_date: date, end_date: date }),
    getDashboardHourlyTrends({ site_id: siteId, date }),
    getFeedbackStats({ site_id: siteId, window_days: 30, min_samples: 1 })
  ])

  automationSummary.value = summaryResp || { tasks: { failed: 0 } }
  hourlyTrends.value = trendResp?.trends || []
  feedbackStats.value = feedbackResp?.stats || {}
}

const loadAllData = async () => {
  loading.value.data = true
  try {
    await Promise.all([loadAssetsData(), loadAlertsData(), loadAutomationData()])
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  } finally {
    loading.value.data = false
  }
}

const goToAssets = (type: 'device' | 'rack', extra?: Record<string, string>) => {
  const query: Record<string, string> = {
    type,
    ...extra
  }

  if (selectedSiteName.value) {
    query.site = selectedSiteName.value
  }

  router.push({ path: '/assets', query })
}

const goToAlerts = (level: 'all' | 'critical' | 'warning') => {
  router.push({
    path: '/alerts',
    query: {
      level,
      site: selectedSiteName.value || ''
    }
  })
}

const goToAutomationAbnormal = () => {
  router.push({
    path: '/automation/tasks',
    query: {
      status: 'failed',
      site_id: selectedAutomationSiteId.value ? String(selectedAutomationSiteId.value) : ''
    }
  })
}

watch(selectedSiteName, () => {
  loadAllData()
})

onMounted(async () => {
  await loadSites()
  await loadAllData()
})
</script>

<style scoped>
.dashboard-page {
  min-height: calc(100vh - 64px);
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
}

.dashboard-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}

.section-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
}

.section-title-row h1 {
  font-size: 24px;
  color: #0f172a;
}

.section-title-row p {
  margin-top: 4px;
  font-size: 13px;
  color: #64748b;
}

.site-selector-row {
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.site-selector-row label {
  font-size: 13px;
  color: #475569;
  font-weight: 600;
}

.site-selector-row select {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  height: 36px;
  padding: 0 10px;
  color: #0f172a;
  background: #fff;
}

.middle-grid,
.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 320px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.panel-header h2 {
  font-size: 18px;
}

.muted {
  color: #64748b;
  font-size: 12px;
}

.muted.small {
  font-size: 11px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.metric-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  text-align: left;
}

button.metric-item {
  cursor: pointer;
}

button.metric-item:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.metric-item.full-width {
  width: 100%;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}

.metric-value.critical,
.metric-value.danger {
  color: #dc2626;
}

.metric-value.warning {
  color: #d97706;
}

.metric-value.success {
  color: #16a34a;
}

.metric-label {
  font-size: 12px;
  color: #475569;
}

.subsection {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.subsection h3 {
  font-size: 14px;
  color: #1e293b;
}

.bars-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bar-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
  background: #fff;
  display: grid;
  grid-template-columns: 90px 1fr 40px;
  align-items: center;
  gap: 8px;
  text-align: left;
}

button.bar-item {
  cursor: pointer;
}

button.bar-item:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.bar-item.static {
  cursor: default;
}

.bar-label {
  font-size: 12px;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-track {
  width: 100%;
  height: 8px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #60a5fa 0%, #2563eb 100%);
}

.bar-fill.vendor {
  background: linear-gradient(90deg, #34d399 0%, #10b981 100%);
}

.bar-fill.success {
  background: linear-gradient(90deg, #4ade80 0%, #16a34a 100%);
}

.bar-fill.danger {
  background: linear-gradient(90deg, #fb7185 0%, #dc2626 100%);
}

.bar-fill.warning {
  background: linear-gradient(90deg, #fbbf24 0%, #d97706 100%);
}

.bar-count {
  font-size: 12px;
  color: #1e293b;
  text-align: right;
}

.hourly-trend {
  display: flex;
  gap: 4px;
  align-items: flex-end;
  min-height: 160px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
}

.hour-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.hour-bars {
  width: 100%;
  height: 120px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
}

.hour-bar {
  width: 6px;
  border-radius: 999px 999px 0 0;
}

.hour-bar.total {
  background: #60a5fa;
}

.hour-bar.abnormal {
  background: #ef4444;
}

.hour-label {
  font-size: 10px;
  color: #64748b;
}

.empty {
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 16px;
  color: #64748b;
  font-size: 13px;
  text-align: center;
}

.link-btn {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
}

.link-btn:hover {
  background: #dbeafe;
}

@media (max-width: 1024px) {
  .middle-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .section-top {
    flex-direction: column;
    align-items: stretch;
  }

  .site-selector-row {
    min-width: 0;
  }
}
</style>
