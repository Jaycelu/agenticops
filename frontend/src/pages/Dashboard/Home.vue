<template>
  <div class="dashboard-page">
    <div class="dashboard-content">
      <section class="card section-top">
        <div class="section-title-row">
          <h1>运维驾驶舱</h1>
          <p>统一站点视角，支持从报表到详情一键穿透</p>
        </div>
        <div class="top-actions">
          <span class="sync-hint" :class="{ running: syncState.running }">
            {{ syncState.running ? '资产数据预热中...' : `上次预热：${syncState.lastLabel}` }}
          </span>
          <button class="btn-secondary refresh-btn" :disabled="loading.data || syncState.running" @click="handleManualRefresh">
            {{ loading.data || syncState.running ? '刷新中...' : '手动刷新' }}
          </button>
        </div>
      </section>
      <section class="base-section">
        <div class="section-header">
          <Building2 class="section-icon" :size="20" />
          <h3>选择基地</h3>
        </div>
        <div v-if="loading.sites" class="empty">加载基地列表中...</div>
        <div v-else-if="sites.length === 0" class="empty">暂无基地数据</div>
        <div v-else class="base-grid">
          <div
            v-for="site in sites"
            :key="site.id"
            class="base-card"
            :class="{ active: selectedSiteName === site.name }"
            @click="handleSiteSelect(site.name)"
          >
            <div class="base-icon">
              <Building2 :size="28" />
            </div>
            <div class="base-info">
              <div class="base-name">{{ site.name }}</div>
            </div>
          </div>
        </div>
      </section>

      <section class="middle-grid">
        <article class="card panel assets-panel">
          <div class="panel-header">
            <h2>资产统计</h2>
            <span class="muted">按站点聚合（含缓存与实时刷新）</span>
          </div>

          <div class="metric-grid four-col">
            <button class="metric-item metric-device" @click="goToAssets('device')">
              <span class="metric-value">{{ assetSnapshot.deviceCount }}</span>
              <span class="metric-label">设备总数</span>
            </button>
            <button class="metric-item metric-ip" @click="goToAssets('ip')">
              <span class="metric-value">{{ assetSnapshot.ipCount }}</span>
              <span class="metric-label">IP地址数量</span>
            </button>
            <button class="metric-item metric-rack" @click="goToAssets('rack')">
              <span class="metric-value">{{ assetSnapshot.rackCount }}</span>
              <span class="metric-label">机柜数量</span>
            </button>
            <button class="metric-item metric-vlan" @click="goToAssets('vlan')">
              <span class="metric-value">{{ assetSnapshot.vlanCount }}</span>
              <span class="metric-label">VLAN数量</span>
            </button>
          </div>

          <div class="pie-grid">
            <div class="pie-card">
              <h3>设备角色分布</h3>
              <div v-if="rolePie.segments.length === 0" class="empty">暂无数据</div>
              <div v-else class="pie-layout">
                <div class="pie-shell" :style="{ background: rolePie.gradient }"></div>
                <div class="pie-legend">
                  <button
                    v-for="segment in rolePie.segments"
                    :key="segment.label"
                    class="legend-row"
                    @click="goToAssets('device', { role: segment.label })"
                  >
                    <span class="dot" :style="{ background: segment.color }"></span>
                    <span class="legend-label">{{ segment.label }}</span>
                    <span class="legend-val">{{ segment.count }} / {{ segment.percent }}%</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="pie-card">
              <h3>厂商分布（NetBox manufacturer）</h3>
              <div v-if="vendorPie.segments.length === 0" class="empty">暂无数据</div>
              <div v-else class="pie-layout">
                <div class="pie-shell" :style="{ background: vendorPie.gradient }"></div>
                <div class="pie-legend">
                  <button
                    v-for="segment in vendorPie.segments"
                    :key="segment.label"
                    class="legend-row"
                    @click="goToAssets('device', { vendor: segment.label, keyword: segment.label })"
                  >
                    <span class="dot" :style="{ background: segment.color }"></span>
                    <span class="legend-label">{{ segment.label }}</span>
                    <span class="legend-val">{{ segment.count }} / {{ segment.percent }}%</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </article>

        <article class="card panel alerts-panel">
          <div class="panel-header">
            <h2>Zabbix 告警统计</h2>
            <span class="muted">按严重等级聚合</span>
          </div>

          <div class="metric-grid two-col">
            <button class="metric-item metric-critical" @click="goToAlerts('critical')">
              <span class="metric-value critical">{{ alarmStats.critical }}</span>
              <span class="metric-label">严重</span>
            </button>
            <button class="metric-item metric-warning" @click="goToAlerts('warning')">
              <span class="metric-value warning">{{ alarmStats.warning }}</span>
              <span class="metric-label">警告</span>
            </button>
          </div>

          <button class="metric-item full-width metric-total" @click="goToAlerts('all')">
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Building2 } from 'lucide-vue-next'
import { alertsApi } from '@/api/alerts'
import { assetsApi, Device, Site } from '@/api/assets'
import {
  getDashboardHourlyTrends,
  getDashboardSummary,
  getFeedbackStats,
  getSites as getAutomationSites
} from '@/api/automation'

interface HourTrend {
  hour: string
  samples: number
  abnormal: number
}

interface AssetSnapshot {
  deviceCount: number
  ipCount: number
  rackCount: number
  vlanCount: number
  devices: Device[]
}

interface PieSegment {
  label: string
  count: number
  percent: number
  color: string
}

const ASSET_CACHE_TTL = 30 * 60 * 1000
const SYNC_THROTTLE = 90 * 1000
const PIE_COLORS = ['#3b82f6', '#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
const AUTO_REFRESH_INTERVAL = 30 * 60 * 1000

const router = useRouter()
const sites = ref<Site[]>([])
const selectedSiteName = ref<string>('')
const automationSites = ref<any[]>([])

const loading = ref({
  sites: false,
  data: false
})

const syncState = ref({
  running: false,
  lastLabel: '未执行'
})

const assetSnapshot = ref<AssetSnapshot>({
  deviceCount: 0,
  ipCount: 0,
  rackCount: 0,
  vlanCount: 0,
  devices: []
})

const alerts = ref<any[]>([])
const automationSummary = ref<any>({ tasks: { failed: 0 } })
const hourlyTrends = ref<HourTrend[]>([])
const feedbackStats = ref<Record<string, any>>({})
let autoRefreshTimer: number | null = null

const normalized = (value: string) => value.toLowerCase().replace(/[\s_-]/g, '')
const cacheKey = (siteName?: string) => `dashboard:assets:v3:${siteName || 'all'}`
const syncKey = (siteName?: string) => `dashboard:sync:v1:${siteName || 'all'}`

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
  return Math.max(...values, 1)
})

const roleDistribution = computed(() => buildDistribution(assetSnapshot.value.devices.map((d) => d.role || '未标注')))
const vendorDistribution = computed(() => buildDistribution(assetSnapshot.value.devices.map((d) => d.vendor || '未标注')))

const rolePie = computed(() => buildPie(roleDistribution.value, PIE_COLORS))
const vendorPie = computed(() => buildPie(vendorDistribution.value, PIE_COLORS))

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

function buildDistribution(values: string[]): Array<{ label: string; count: number; percent: number }> {
  const counter = values.reduce((acc: Record<string, number>, label) => {
    acc[label] = (acc[label] || 0) + 1
    return acc
  }, {})

  const total = values.length || 1
  const sorted = Object.entries(counter)
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => ({ label, count, percent: Math.round((count / total) * 100) }))

  if (sorted.length <= 5) {
    return sorted
  }

  const head = sorted.slice(0, 5)
  const tailCount = sorted.slice(5).reduce((sum, item) => sum + item.count, 0)
  head.push({ label: '其他', count: tailCount, percent: Math.round((tailCount / total) * 100) })
  return head
}

function buildPie(items: Array<{ label: string; count: number; percent: number }>, palette: string[]) {
  if (items.length === 0) {
    return { gradient: '', segments: [] as PieSegment[] }
  }

  const total = items.reduce((sum, item) => sum + item.count, 0)
  let cursor = 0
  const gradientParts: string[] = []

  const segments: PieSegment[] = items.map((item, index) => {
    const color = palette[index % palette.length]
    const start = cursor
    const angle = total > 0 ? (item.count / total) * 360 : 0
    const end = cursor + angle
    cursor = end
    gradientParts.push(`${color} ${start}deg ${end}deg`)

    return {
      ...item,
      color
    }
  })

  return {
    gradient: `conic-gradient(${gradientParts.join(', ')})`,
    segments
  }
}

function applySnapshot(snapshot: AssetSnapshot) {
  assetSnapshot.value = snapshot
}

function readAssetCache(siteName?: string): AssetSnapshot | null {
  try {
    const raw = localStorage.getItem(cacheKey(siteName))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.data || !parsed?.timestamp) return null
    if (Date.now() - Number(parsed.timestamp) > ASSET_CACHE_TTL) return null
    return parsed.data as AssetSnapshot
  } catch {
    return null
  }
}

function writeAssetCache(siteName: string | undefined, data: AssetSnapshot) {
  localStorage.setItem(
    cacheKey(siteName),
    JSON.stringify({
      timestamp: Date.now(),
      data
    })
  )
}

function shouldTriggerSync(siteName?: string) {
  const last = Number(localStorage.getItem(syncKey(siteName)) || 0)
  return Date.now() - last > SYNC_THROTTLE
}

async function prewarmAssets(siteName?: string) {
  if (!shouldTriggerSync(siteName)) return
  syncState.value.running = true
  try {
    await assetsApi.syncDevices(siteName)
    localStorage.setItem(syncKey(siteName), String(Date.now()))
    syncState.value.lastLabel = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch (error) {
    console.error('Failed to prewarm assets:', error)
  } finally {
    syncState.value.running = false
  }
}

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
  const siteSlug = selectedSite.value?.slug || undefined
  const cache = readAssetCache(siteName)
  if (cache) {
    applySnapshot(cache)
  }

  await prewarmAssets(siteName)

  try {
    let [deviceResp, rackResp, vlanResp] = await Promise.all([
      assetsApi.getDevices(siteSlug ? { site: siteSlug } : siteName ? { site: siteName } : undefined),
      assetsApi.getRacks(siteSlug ? { site: siteSlug } : siteName ? { site: siteName } : undefined),
      assetsApi.getVLANs(siteSlug ? { site: siteSlug } : siteName ? { site: siteName } : undefined)
    ])

    // 兜底：当站点过滤参数与NetBox字段不一致时，回退到全量并在前端按站点名/slug筛选
    if ((deviceResp.count || 0) === 0 && selectedSite.value) {
      const fallback = await assetsApi.getDevices()
      const tokens = [selectedSite.value.name, selectedSite.value.slug].filter(Boolean).map((v) => String(v).toLowerCase())
      const filtered = (fallback.devices || []).filter((item) => {
        const siteValue = String(item.site || '').toLowerCase()
        return tokens.some((token) => siteValue.includes(token))
      })
      deviceResp = { count: filtered.length, devices: filtered }
    }

    const ipResp = await assetsApi.getIPs()

    // Racks/VLAN 同样兜底
    if ((rackResp.count || 0) === 0 && selectedSite.value) {
      const fallback = await assetsApi.getRacks()
      const tokens = [selectedSite.value.name, selectedSite.value.slug].filter(Boolean).map((v) => String(v).toLowerCase())
      const filtered = (fallback.racks || []).filter((item: any) => {
        const siteValue = String(item.site || '').toLowerCase()
        return tokens.some((token) => siteValue.includes(token))
      })
      rackResp = { count: filtered.length, racks: filtered }
    }
    if ((vlanResp.count || 0) === 0 && selectedSite.value) {
      const fallback = await assetsApi.getVLANs()
      const tokens = [selectedSite.value.name, selectedSite.value.slug].filter(Boolean).map((v) => String(v).toLowerCase())
      const filtered = (fallback.vlans || []).filter((item: any) => {
        const siteValue = String(item.site || '').toLowerCase()
        return tokens.some((token) => siteValue.includes(token))
      })
      vlanResp = { count: filtered.length, vlans: filtered }
    }

    const nextSnapshot: AssetSnapshot = {
      deviceCount: deviceResp.count || 0,
      // IP 数量直接使用 NetBox IP 列表总数，保持与资产页口径一致
      ipCount: ipResp.count || 0,
      rackCount: rackResp.count || 0,
      vlanCount: vlanResp.count || 0,
      devices: deviceResp.devices || []
    }

    applySnapshot(nextSnapshot)
    writeAssetCache(siteName, nextSnapshot)
  } catch (error) {
    console.error('Failed to load assets data:', error)
  }
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

const goToAssets = (type: 'device' | 'rack' | 'ip' | 'vlan', extra?: Record<string, string>) => {
  const query: Record<string, string> = {
    type,
    ...extra
  }

  if (selectedSiteName.value && type !== 'ip') {
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

const handleSiteSelect = (siteName: string) => {
  if (selectedSiteName.value === siteName) return
  selectedSiteName.value = siteName
}

watch(selectedSiteName, () => {
  loadAllData()
})

onMounted(async () => {
  await loadSites()
  if (!selectedSiteName.value) {
    await loadAllData()
  }
  autoRefreshTimer = window.setInterval(() => {
    loadAllData()
  }, AUTO_REFRESH_INTERVAL)
})

const handleManualRefresh = async () => {
  const siteName = selectedSiteName.value || undefined
  localStorage.removeItem(cacheKey(siteName))
  localStorage.removeItem(syncKey(siteName))
  await loadAllData()
}

onUnmounted(() => {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
})
</script>

<style scoped>
.dashboard-page {
  min-height: calc(100vh - 64px);
  background:
    radial-gradient(circle at 4% 0%, rgba(56, 189, 248, 0.09), transparent 35%),
    radial-gradient(circle at 96% 4%, rgba(20, 184, 166, 0.08), transparent 35%),
    linear-gradient(135deg, #f6f9ff 0%, #eef4ff 100%);
}

.dashboard-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  border: 1px solid #dbe8ff;
}

.section-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.top-actions {
  min-width: 200px;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.sync-hint {
  font-size: 12px;
  color: #64748b;
}

.sync-hint.running {
  color: #2563eb;
}

.middle-grid,
.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.base-section {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.section-icon {
  color: #4a9eff;
}

.section-header h3 {
  margin: 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.base-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.base-card {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border: 2px solid transparent;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 14px;
}

.base-card:hover {
  background: linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.base-card.active {
  border-color: #4a9eff;
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.25);
}

.base-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.base-info {
  flex: 1;
}

.base-name {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 360px;
}

.assets-panel {
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.78) 0%, rgba(255, 255, 255, 0.9) 30%);
}

.alerts-panel {
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.7) 0%, rgba(255, 255, 255, 0.9) 35%);
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
  gap: 8px;
}

.metric-grid.four-col {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric-item {
  border: 1px solid #dbe5f5;
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
  border-color: #86b8ff;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.11);
}

.metric-device {
  border-top: 3px solid #3b82f6;
}

.metric-ip {
  border-top: 3px solid #06b6d4;
}

.metric-rack {
  border-top: 3px solid #14b8a6;
}

.metric-vlan {
  border-top: 3px solid #f59e0b;
}

.metric-critical {
  border-top: 3px solid #ef4444;
}

.metric-warning {
  border-top: 3px solid #f59e0b;
}

.metric-total {
  border-top: 3px solid #3b82f6;
}

.metric-item.full-width {
  width: 100%;
}

.metric-value {
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
  color: #0f172a;
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

.pie-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.pie-card {
  border: 1px solid #dbe5f5;
  border-radius: 8px;
  padding: 10px;
  background: #fff;
}

.pie-card h3 {
  font-size: 14px;
  color: #1e293b;
  margin-bottom: 8px;
}

.pie-layout {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 10px;
  align-items: center;
}

.pie-shell {
  width: 110px;
  height: 110px;
  border-radius: 50%;
  position: relative;
  border: 1px solid #dbe5f5;
}

.pie-shell::after {
  content: '';
  position: absolute;
  inset: 28px;
  border-radius: 50%;
  background: #fff;
  box-shadow: inset 0 0 0 1px #e2e8f0;
}

.pie-legend {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.legend-row {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  padding: 4px 6px;
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 6px;
  align-items: center;
  text-align: left;
  cursor: pointer;
}

.legend-row:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-label {
  font-size: 12px;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.legend-val {
  font-size: 11px;
  color: #64748b;
}

.subsection {
  display: flex;
  flex-direction: column;
  gap: 8px;
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

@media (max-width: 1280px) {
  .metric-grid.four-col {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1024px) {
  .middle-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .section-top {
    flex-direction: column;
    align-items: stretch;
  }

  .top-actions {
    min-width: 0;
    justify-content: space-between;
  }

  .pie-grid {
    grid-template-columns: 1fr;
  }

  .pie-layout {
    grid-template-columns: 96px 1fr;
  }

  .pie-shell {
    width: 96px;
    height: 96px;
  }

  .pie-shell::after {
    inset: 24px;
  }
}

@media (max-width: 760px) {
  .metric-grid.four-col,
  .metric-grid.two-col {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.refresh-btn {
  width: auto;
  min-width: 96px;
  justify-content: center;
}
</style>
