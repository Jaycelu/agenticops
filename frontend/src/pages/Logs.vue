<template>
  <div class="page app-page">
    <div class="page-content">
      <div class="page-header app-page-header">
        <div class="page-title app-page-title">
          <span class="app-page-title-icon">
            <FileSearch class="title-icon" :size="24" />
          </span>
          <div class="app-page-copy">
            <h1>日志分析</h1>
            <p>按日志范围进行检索、聚合和设备级分析，直接接入 Case 处理链路。</p>
          </div>
        </div>
        <button @click="refreshData" class="btn-refresh app-button app-button-secondary" :disabled="loading">
          <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>

      <!-- 日志范围选择 -->
      <div class="base-section app-panel">
        <div class="section-header">
          <Building2 class="section-icon" :size="20" />
          <h3>选择日志范围</h3>
        </div>
        <div class="base-grid">
          <div 
            v-for="base in bases" 
            :key="base.key"
            class="base-card"
            :class="{ active: selectedBase === base.key }"
            @click="selectBase(base.key)"
          >
            <div class="base-icon">
              <Building2 :size="28" />
            </div>
            <div class="base-info">
              <div class="base-name">{{ base.name }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 筛选区域 -->
      <div class="filter-section">
        <div class="filter-group">
          <div class="filter-item">
            <label class="filter-label">
              <Clock :size="14" />
              时间范围:
            </label>
            <select v-model="timeRange" class="filter-input app-select" @change="loadLogs">
              <optgroup label="最近">
                <option value="-10m,now">最近10分钟</option>
                <option value="-30m,now">最近30分钟</option>
                <option value="-1h,now">最近1小时</option>
                <option value="-3h,now">最近3小时</option>
                <option value="-1d,now">最近1天</option>
                <option value="-2d,now">最近2天</option>
                <option value="-7d,now">最近7天</option>
              </optgroup>
              <optgroup label="相对">
                <option value="today,now">今天</option>
                <option value="yesterday,today">昨天</option>
                <option value="-2d,-1d">前天</option>
                <option value="-7d,now">本周</option>
                <option value="-14d,-7d">上周</option>
                <option value="-30d,now">本月</option>
                <option value="-60d,-30d">上月</option>
              </optgroup>
            </select>
          </div>
          <div class="filter-item">
            <label class="filter-label">
              <Filter :size="14" />
              筛选条件:
            </label>
            <input 
              v-model="customFilter" 
              class="filter-input-text app-input" 
              placeholder="输入筛选条件，如: hostname:10.*"
              @keyup.enter="loadLogs"
            />
          </div>
          <div class="filter-item">
            <label class="filter-label">
              <List :size="14" />
              每页显示:
            </label>
            <select v-model="limit" class="filter-input app-select" @change="loadLogs">
              <option value="50">50条</option>
              <option value="100">100条</option>
              <option value="200">200条</option>
              <option value="500">500条</option>
            </select>
          </div>
          <div class="filter-item">
            <label class="filter-label">
              <Server :size="14" />
              主机筛选:
            </label>
            <input 
              v-model="hostnameFilter" 
              class="filter-input-text app-input" 
              placeholder="输入主机IP筛选，如: 10.0.0.1"
              @keyup.enter="applyHostnameFilter"
            />
          </div>
          <button @click="loadLogs" class="btn-search app-button app-button-primary">
            <Search :size="16" />
            查询
          </button>
        </div>
      </div>

      <!-- 统计信息 -->
      <div v-if="selectedBase" class="stats-section app-panel">
        <div class="stat-item">
          <span class="stat-label">范围:</span>
          <span class="stat-value">{{ selectedBaseName }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">时间范围:</span>
          <span class="stat-value">{{ timeRange }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">总日志数:</span>
          <span class="stat-value">{{ totalLogs }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">当前显示:</span>
          <span class="stat-value">{{ filteredLogs.length }} 条</span>
        </div>
        
        <div class="stat-divider"></div>
        
        <div class="stat-item">
          <label class="stat-label">
            <Layers :size="14" />
            日志级别:
          </label>
          <select v-model="levelFilter" class="stat-level-select app-select">
            <option v-for="level in logLevels" :key="level.value" :value="level.value">
              {{ level.label }} ({{ getLevelCount(level.value) }})
            </option>
          </select>
        </div>
      </div>

      <!-- 日志聚合设置 -->
      <div v-if="selectedBase && !showAggregatedView" class="aggregate-section app-panel">
        <div class="aggregate-header">
          <div class="section-header">
            <LayoutGrid class="section-icon" :size="20" />
            <h3>日志聚合</h3>
          </div>
          <button @click="toggleAggregateView" class="btn-aggregate app-button app-button-ghost">
            <LayoutGrid :size="16" />
            查看聚合视图
          </button>
        </div>
        <p class="aggregate-hint">当日志数量过多时，可以使用聚合功能按设备和日志级别进行分组展示</p>
      </div>

      <!-- 聚合视图 -->
      <div v-if="showAggregatedView" class="aggregate-view-section app-panel">
        <div class="aggregate-controls">
          <div class="section-header">
            <LayoutGrid class="section-icon" :size="20" />
            <h3>日志聚合视图</h3>
          </div>
          <button @click="toggleAggregateView" class="btn-close app-button app-button-secondary">
            <X :size="16" />
          </button>
        </div>

        <div v-if="aggregating" class="loading">
          <Loader2 class="animate-spin" :size="40" />
          <p>正在聚合日志数据，请稍候...</p>
        </div>

        <div v-else-if="aggregatedData && aggregatedData.aggregated_groups.length > 0" class="aggregate-results">
          <div class="aggregate-stats">
            <span class="aggregate-stat">总日志数: {{ aggregatedData.total_available || aggregatedData.total_logs }}</span>
            <span class="aggregate-stat">已聚合: {{ aggregatedData.total_logs }} 条</span>
            <span class="aggregate-stat">设备数: {{ aggregatedData.aggregated_groups.length }}</span>
            <button
              v-if="aggregatedData.case_id"
              class="btn-open-case app-button app-button-primary"
              @click="openCase(aggregatedData.case_id)"
            >
              打开 Case {{ aggregatedData.case_code || `#${aggregatedData.case_id}` }}
            </button>
            <span v-if="aggregatedData.has_more" class="aggregate-stat warning">
              <AlertTriangle :size="12" />
              还有 {{ (aggregatedData.total_available || 0) - aggregatedData.total_logs }} 条日志未聚合
            </span>
          </div>

          <div class="device-groups">
            <div 
              v-for="(group, deviceIndex) in aggregatedData.aggregated_groups" 
              :key="group.device"
              class="device-group"
            >
              <div class="device-group-header" @click="toggleDeviceGroup(deviceIndex)">
                <div class="device-group-info">
                  <span class="device-name">{{ group.device }}</span>
                  <span class="device-count">{{ group.total_count }} 条</span>
                </div>
                <div class="device-group-actions">
                  <button 
                    @click.stop="analyzeDeviceLogs(deviceIndex)" 
                    class="btn-analyze-device app-button app-button-ghost"
                    :disabled="deviceAnalyzing[deviceIndex]"
                  >
                    <Bot :size="14" />
                    {{ deviceAnalyzing[deviceIndex] ? '分析中...' : 'AI 分析' }}
                  </button>
                  <span class="device-expand-icon">
                    <ChevronDown v-if="expandedDeviceGroups[deviceIndex]" :size="16" />
                    <ChevronRight v-else :size="16" />
                  </span>
                </div>
              </div>

              <div v-if="expandedDeviceGroups[deviceIndex]" class="device-group-content">
                <!-- 设备分析结果 -->
                <div v-if="deviceAnalysisResults[deviceIndex]" class="device-analysis-result">
                  <div class="analysis-result-header">
                    <span class="analysis-result-title">
                      <Bot :size="16" />
                      AI 分析结果
                    </span>
                    <button @click="closeDeviceAnalysis(deviceIndex)" class="btn-close-small app-button app-button-secondary">
                      <X :size="14" />
                    </button>
                  </div>
                  <div v-if="deviceAnalysisMeta[deviceIndex]" class="analysis-meta">
                    <span class="meta-info">总日志: {{ deviceAnalysisMeta[deviceIndex].total_count }} 条</span>
                    <span class="meta-info">已分析: {{ deviceAnalysisMeta[deviceIndex].analyzed_count }} 条</span>
                    <button
                      v-if="deviceAnalysisMeta[deviceIndex].case_id"
                      class="btn-open-case small app-button app-button-primary"
                      @click="openCase(deviceAnalysisMeta[deviceIndex].case_id)"
                    >
                      打开 Case {{ deviceAnalysisMeta[deviceIndex].case_code || `#${deviceAnalysisMeta[deviceIndex].case_id}` }}
                    </button>
                    <span v-if="deviceAnalysisMeta[deviceIndex].has_more" class="meta-warning">
                      <AlertTriangle :size="12" />
                      日志数量过多，只分析了部分日志
                    </span>
                  </div>
                  <pre class="analysis-result-content">{{ deviceAnalysisResults[deviceIndex] }}</pre>
                </div>

                <div 
                  v-for="(levelGroup, levelIndex) in group.level_groups" 
                  :key="`${deviceIndex}-${levelIndex}`"
                  class="level-group"
                >
                  <div class="level-group-header" @click="toggleLevelGroup(deviceIndex, levelIndex)">
                    <div class="level-group-info">
                      <span class="level-badge" :class="`level-${levelGroup.level.toLowerCase()}`">
                        {{ levelGroup.level }}
                      </span>
                      <span class="level-count">{{ levelGroup.count }} 条</span>
                      <span class="level-time">{{ levelGroup.time_range }}</span>
                    </div>
                    <span class="level-expand-icon">
                      <ChevronDown v-if="expandedLevelGroups[`${deviceIndex}-${levelIndex}`]" :size="16" />
                      <ChevronRight v-else :size="16" />
                    </span>
                  </div>

                  <div v-if="expandedLevelGroups[`${deviceIndex}-${levelIndex}`]" class="level-group-content">
                    <div 
                      v-for="(log, logIndex) in levelGroup.logs.slice(0, 50)" 
                      :key="logIndex"
                      class="log-item-compact"
                    >
                      <div class="log-time-compact">{{ formatTime(log.timestamp) }}</div>
                      <div class="log-message-compact">{{ log.message }}</div>
                    </div>
                    <div v-if="levelGroup.logs.length > 50" class="log-more-hint">
                      还有 {{ levelGroup.logs.length - 50 }} 条日志未显示
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="!aggregating" class="empty">
          <FileX :size="48" />
          <p>暂无聚合结果</p>
        </div>
      </div>
      
      <!-- 日志列表 -->
      <div class="logs-section app-panel">
        <div v-if="loading" class="loading app-empty">
          <Loader2 class="animate-spin" :size="40" />
          <p>正在查询日志数据，请稍候...</p>
          <p class="loading-hint">如果查询时间较长，可能是筛选条件较复杂，请耐心等待</p>
        </div>
        <div v-else-if="!selectedBase" class="empty app-empty">
          <MapPinOff :size="48" />
          <p>请先选择日志范围</p>
        </div>
        <div v-else-if="logs.length === 0" class="empty app-empty">
          <div v-if="timeoutError" class="error-hint">
            <div class="error-icon">
              <AlertCircle :size="48" />
            </div>
            <h3>连接超时</h3>
            <p>无法连接到日志系统，请稍后重试。</p>
          </div>
          <div v-else-if="noLogsHint" class="no-logs-hint">
            <div class="hint-icon">
              <Info :size="48" />
            </div>
            <h3>[提示] 未找到日志记录</h3>
            <p>日志易无异常日志</p>
            <div class="hint-details">
              <p><strong>建议:</strong></p>
              <ol>
                <li>登录日志易系统（https://sre-log.trinasolar.com/）检查日志筛选条件</li>
                <li>验证查询时间范围和主机过滤条件是否正确</li>
                <li>若问题持续，请联系日志易管理员陆宇</li>
              </ol>
              <p><strong>备注:</strong> 无日志记录，请检查日志源配置</p>
            </div>
          </div>
          <div v-else>
            <FileX :size="48" />
            <p>暂无日志数据</p>
          </div>
        </div>
        <div v-else class="logs-list">
          <div 
            v-for="(log, index) in visibleLogs" 
            :key="index" 
            class="log-item"
          >
            <div class="log-main" @click="toggleLogDetail(index)">
              <div class="log-header">
                <div class="log-hostname">
                  <Server :size="14" />
                  {{ log.hostname }}
                </div>
                <div class="log-time">
                  <Clock :size="14" />
                  {{ formatTime(log.timestamp) }}
                </div>
                <div class="log-expand-icon">
                  <ChevronDown v-if="expandedLogs[index]" :size="16" />
                  <ChevronRight v-else :size="16" />
                </div>
              </div>
              <div class="log-message">{{ log.message }}</div>
            </div>
            <div class="log-actions">
              <button 
                @click="analyzeSingleLog(log, index)" 
                class="btn-analyze-single app-button app-button-ghost"
                :disabled="singleAnalyzing[index]"
              >
                <Bot :size="14" />
                {{ singleAnalyzing[index] ? '分析中...' : 'AI 分析' }}
              </button>
            </div>
            <!-- 日志详情 -->
            <div v-if="expandedLogs[index]" class="log-detail">
              <div class="detail-section">
                <h4>
                  <FileText :size="16" />
                  原始日志
                </h4>
                <pre>{{ log.message }}</pre>
              </div>
              <div class="detail-section">
                <h4>
                  <Info :size="16" />
                  完整信息
                </h4>
                <div class="detail-grid">
                  <div class="detail-item">
                    <span class="detail-label">主机名:</span>
                    <span class="detail-value">{{ log.hostname }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">时间戳:</span>
                    <span class="detail-value">{{ log.timestamp }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">日志级别:</span>
                    <span class="detail-value">{{ log.level }}</span>
                  </div>
                </div>
              </div>
              <!-- 单条日志分析结果 -->
              <div v-if="singleAnalysisResults[index]" class="log-analysis-result">
                <div class="analysis-result-header">
                  <span class="analysis-result-title">
                    <Bot :size="16" />
                    AI 分析结果
                  </span>
                  <button @click="closeSingleAnalysis(index)" class="btn-close-small app-button app-button-secondary">
                    <X :size="14" />
                  </button>
                </div>
                <pre class="analysis-result-content">{{ singleAnalysisResults[index] }}</pre>
              </div>
            </div>
          </div>
        </div>

        <!-- 分页控制 -->
        <div v-if="logs.length > 0 && totalLogs > limit" class="pagination">
          <button 
            @click="previousPage" 
            class="btn-page app-button app-button-secondary"
            :disabled="offset === 0"
          >
            <ChevronLeft :size="16" />
            上一页
          </button>
          <span class="page-info">
            {{ offset + 1 }} - {{ Math.min(offset + limit, totalLogs) }} / {{ totalLogs }}
          </span>
          <div class="page-jump">
            <input 
              type="number" 
              v-model="jumpPage" 
              class="page-jump-input app-input"
              :min="1"
              :max="totalPages"
              @keyup.enter="goToPage"
            />
            <span class="page-jump-text">/ {{ totalPages }} 页</span>
            <button 
              @click="goToPage" 
              class="btn-page-jump app-button app-button-primary"
              :disabled="!jumpPage || jumpPage < 1 || jumpPage > totalPages"
            >
              跳转
            </button>
          </div>
          <button 
            @click="nextPage" 
            class="btn-page app-button app-button-secondary"
            :disabled="offset + limit >= totalLogs"
          >
            下一页
            <ChevronRight :size="16" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'

import { logsApi, type AggregationParams, type AggregationResponse, type DeviceLogAnalysisRequest } from '@/api/logs'
import { 
  FileSearch, RefreshCw, Building2, Clock, Filter, List, Server, Search, 
  Layers, LayoutGrid, X, Loader2, AlertTriangle, Bot, ChevronDown, ChevronRight, 
  FileX, MapPinOff, AlertCircle, Info, FileText, ChevronLeft
} from 'lucide-vue-next'

interface BaseConfig {
  key: string
  name: string
  filter: string
  time_range: string
  site_code?: string
  site_name?: string
  aliases?: string[]
}

interface LogEntry {
  timestamp: string
  hostname: string
  message: string
  level: string
  raw: any
}

interface DeviceAnalysisMeta {
  total_count: number
  analyzed_count: number
  has_more: boolean
  case_id?: number | null
  case_code?: string | null
}

const router = useRouter()
const loading = ref(false)
const logs = ref<LogEntry[]>([])
const totalLogs = ref(0)
const selectedBase = ref<string>('')
const selectedBaseName = ref<string>('')
const timeRange = ref<string>('-1d,now')
const limit = ref<number>(200)
const offset = ref<number>(0)
const currentFilter = ref<string>('')
const customFilter = ref<string>('')
const hostnameFilter = ref<string>('')
const singleAnalyzing = ref<Record<number, boolean>>({})
const singleAnalysisResults = ref<Record<number, string>>({})
const noLogsHint = ref<boolean>(false)
const timeoutError = ref<boolean>(false)
const expandedLogs = ref<Record<number, boolean>>({})
const levelFilter = ref<string>('all')
const jumpPage = ref<number>(1)

const showAggregatedView = ref(false)
const aggregating = ref(false)
const aggregatedData = ref<AggregationResponse | null>(null)
const expandedDeviceGroups = ref<Record<number, boolean>>({})
const expandedLevelGroups = ref<Record<string, boolean>>({})
const deviceAnalyzing = ref<Record<number, boolean>>({})
const deviceAnalysisResults = ref<Record<number, string>>({})
const deviceAnalysisMeta = ref<Record<number, DeviceAnalysisMeta>>({})

const bases = ref<BaseConfig[]>([])

const totalPages = computed(() => {
  return Math.ceil(totalLogs.value / limit.value)
})

const logLevels = [
  { value: 'all', label: '全部' },
  { value: 'Emergencies', label: 'Emergencies' },
  { value: 'Alert', label: 'Alert' },
  { value: 'Critical', label: 'Critical' },
  { value: 'Error', label: 'Error' },
  { value: 'Warning', label: 'Warning' },
  { value: 'Notification', label: 'Notification' },
  { value: 'Informational', label: 'Informational' },
  { value: 'Debugging', label: 'Debugging' },
  { value: 'unknown', label: 'Unknown' }
]

function getLevelCount(level: string): number {
  if (level === 'all') {
    return logs.value.length
  }
  return logs.value.filter(log => log.level === level).length
}

const filteredLogs = computed(() => {
  if (levelFilter.value === 'all') {
    return logs.value
  }
  return logs.value.filter(log => log.level === levelFilter.value)
})

const visibleLogs = computed(() => {
  const logsToRender = filteredLogs.value
  if (logsToRender.length <= 200) {
    return logsToRender
  }
  return logsToRender.slice(0, 200)
})

async function loadBases() {
  try {
    const data = await logsApi.getScopes()
    bases.value = data.bases || []
  } catch (error) {
    console.error('Error loading bases:', error)
  }
}

function selectBase(baseKey: string) {
  selectedBase.value = baseKey
  const base = bases.value.find(b => b.key === baseKey)
  if (base) {
    selectedBaseName.value = base.name
    currentFilter.value = base.filter
    customFilter.value = base.filter
  }
  offset.value = 0
  clearLogsCache()
  expandedLogs.value = {}
  showAggregatedView.value = false
  aggregatedData.value = null
  deviceAnalysisResults.value = {}
  deviceAnalysisMeta.value = {}
  singleAnalysisResults.value = {}
  loadLogs()
}

function clearLogsCache() {
  const cacheKey = `logs_${selectedBase.value}_${timeRange.value}`
  sessionStorage.removeItem(cacheKey)
  sessionStorage.removeItem(cacheKey + '_time')
}

async function loadLogs() {
  if (!selectedBase.value) return

  loading.value = true
  noLogsHint.value = false
  timeoutError.value = false

  try {
    const filter = customFilter.value || currentFilter.value

    const data = await logsApi.queryLogsByBase(selectedBase.value, {
      time_range: timeRange.value,
      filter,
      limit: Number(limit.value),
      offset: Number(offset.value)
    })
    logs.value = data.logs || []
    totalLogs.value = data.total || 0

    if (logs.value.length === 0 && totalLogs.value === 0) {
      noLogsHint.value = true
    }

  } catch (error: any) {
    console.error('Error loading logs:', error)
    logs.value = []
    totalLogs.value = 0
    timeoutError.value = true
  } finally {
    loading.value = false
  }
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}

function toggleLogDetail(index: number) {
  expandedLogs.value[index] = !expandedLogs.value[index]
}

async function analyzeSingleLog(log: LogEntry, index: number) {
  singleAnalyzing.value[index] = true
  try {
    const response = await logsApi.analyzeSingleLog(log)
    singleAnalysisResults.value[index] = response.analysis
    expandedLogs.value[index] = true
  } catch (error) {
    console.error('Error analyzing log:', error)
    alert('分析失败，请稍后重试')
  } finally {
    singleAnalyzing.value[index] = false
  }
}

function closeSingleAnalysis(index: number) {
  delete singleAnalysisResults.value[index]
}

function refreshData() {
  loadLogs()
}

function previousPage() {
  if (offset.value > 0) {
    offset.value -= limit.value
    loadLogs()
  }
}

function nextPage() {
  if (offset.value + limit.value < totalLogs.value) {
    offset.value += limit.value
    loadLogs()
  }
}

function goToPage() {
  if (jumpPage.value >= 1 && jumpPage.value <= totalPages.value) {
    offset.value = (jumpPage.value - 1) * limit.value
    loadLogs()
  }
}

function applyHostnameFilter() {
  if (hostnameFilter.value) {
    customFilter.value += ` hostname:${hostnameFilter.value}`
  }
  loadLogs()
}

function toggleAggregateView() {
  showAggregatedView.value = !showAggregatedView.value
  if (showAggregatedView.value) {
    loadAggregatedData()
  }
}

async function loadAggregatedData() {
  aggregating.value = true
  try {
    const filter = customFilter.value || currentFilter.value
    const params: AggregationParams = {
      base_name: selectedBase.value,
      time_range: timeRange.value,
      filter: filter,
      create_case: true,
      run_pipeline: true,
      host: selectedBase.value,
      title: `[${selectedBaseName.value || selectedBase.value}] 日志聚合 Case`,
      aggregation: {
        by_device: true,
        by_level: true,
        by_time_window: "5m"
      }
    }

    const response = await logsApi.aggregateLogs(params)
    aggregatedData.value = response
  } catch (error) {
    console.error('Error loading aggregated data:', error)
    aggregatedData.value = null
  } finally {
    aggregating.value = false
  }
}

function toggleDeviceGroup(deviceIndex: number) {
  expandedDeviceGroups.value[deviceIndex] = !expandedDeviceGroups.value[deviceIndex]
}

function toggleLevelGroup(deviceIndex: number, levelIndex: number) {
  const key = `${deviceIndex}-${levelIndex}`
  expandedLevelGroups.value[key] = !expandedLevelGroups.value[key]
}

function openCase(caseId?: number | null) {
  if (!caseId) return
  void router.push({
    path: '/cases',
    query: { caseId: String(caseId) }
  })
}

async function analyzeDeviceLogs(deviceIndex: number) {
  if (!aggregatedData.value) return

  const group = aggregatedData.value.aggregated_groups[deviceIndex]
  deviceAnalyzing.value[deviceIndex] = true

  try {
    // 收集该设备的所有日志
    const allLogs: LogEntry[] = []
    for (const levelGroup of group.level_groups) {
      allLogs.push(...levelGroup.logs)
    }

    const params: DeviceLogAnalysisRequest = {
      base_name: selectedBase.value,
      base_name_cn: selectedBaseName.value,
      device: group.device,
      logs: allLogs,
      create_case: true,
      run_pipeline: true,
      device_ip: group.device,
      host: group.device,
      title: `[${selectedBaseName.value || selectedBase.value}] 设备日志分析 ${group.device}`
    }

    const response = await logsApi.analyzeDeviceLogs(params)
    if (response.success && response.result) {
      deviceAnalysisResults.value[deviceIndex] = response.result
      deviceAnalysisMeta.value[deviceIndex] = {
        total_count: response.log_count,
        analyzed_count: response.analyzed_count || response.log_count,
        has_more: Boolean(response.has_more),
        case_id: response.case_id,
        case_code: response.case_code
      }
    } else {
      throw new Error(response.error || '分析失败')
    }
  } catch (error) {
    console.error('Error analyzing device logs:', error)
    alert('分析失败，请稍后重试')
  } finally {
    deviceAnalyzing.value[deviceIndex] = false
  }
}

function closeDeviceAnalysis(deviceIndex: number) {
  delete deviceAnalysisResults.value[deviceIndex]
  delete deviceAnalysisMeta.value[deviceIndex]
}

onMounted(() => {
  loadBases()
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
}

.page-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  max-width: 1600px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.title-icon {
  color: currentColor;
}

.base-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.section-icon {
  color: #0f5ae0;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.base-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.base-card {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(241, 247, 255, 0.92));
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 18px;
  padding: 18px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 14px;
}

.base-card:hover {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(233, 244, 255, 0.96));
  transform: translateY(-2px);
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.1);
}

.base-card.active {
  border-color: rgba(15, 90, 224, 0.32);
  background: linear-gradient(180deg, rgba(236, 246, 255, 0.98), rgba(225, 241, 255, 0.94));
  box-shadow: 0 18px 34px rgba(15, 90, 224, 0.16);
}

.base-icon {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: linear-gradient(135deg, #0f5ae0 0%, #0f766e 100%);
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
}

.filter-section {
  margin-bottom: 24px;
}

.filter-group {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #5e738f;
}

.filter-input,
.filter-input-text {
  min-width: 160px;
}

.stats-section {
  margin-bottom: 24px;
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: center;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-label {
  font-size: 13px;
  color: #5e738f;
  font-weight: 500;
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
}

.stat-divider {
  width: 1px;
  height: 24px;
  background: rgba(148, 163, 184, 0.24);
}

.stat-level-select {
  font-size: 13px;
  cursor: pointer;
}

.aggregate-section {
  margin-bottom: 24px;
}

.aggregate-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.aggregate-hint {
  margin: 0;
  color: #5e738f;
  font-size: 14px;
}

.aggregate-view-section {
  margin-bottom: 24px;
}

.aggregate-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.aggregate-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.aggregate-stat {
  padding: 8px 14px;
  background: rgba(148, 163, 184, 0.12);
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  color: #24405f;
}

.aggregate-stat.warning {
  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
  color: #e65100;
  display: flex;
  align-items: center;
  gap: 6px;
}

.device-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-group {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.3s;
}

.device-group:hover {
  border-color: rgba(15, 90, 224, 0.28);
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.08);
}

.device-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(239, 245, 252, 0.9));
  cursor: pointer;
  transition: all 0.3s;
}

.device-group-header:hover {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(231, 241, 252, 0.95));
}

.device-group-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.device-name {
  font-size: 15px;
  font-weight: 600;
}

.device-count {
  padding: 4px 10px;
  background: linear-gradient(135deg, #0f5ae0 0%, #0f766e 100%);
  color: white;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.device-group-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-analyze-device:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-open-case.small {
  min-height: 34px;
  padding: 6px 12px;
  font-size: 12px;
}

.device-expand-icon {
  color: #666;
}

.device-group-content {
  padding: 16px 20px;
}

.device-analysis-result {
  background: linear-gradient(180deg, rgba(230, 244, 255, 0.96), rgba(216, 236, 255, 0.88));
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 16px;
  border-left: 4px solid #0f5ae0;
}

.analysis-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.analysis-result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #0f5ae0;
}

.analysis-meta {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.meta-info {
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
  color: #0f5ae0;
}

.meta-warning {
  padding: 4px 10px;
  background: rgba(255, 152, 0, 0.2);
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
  color: #e65100;
  display: flex;
  align-items: center;
  gap: 6px;
}

.analysis-result-content {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 12px;
  padding: 12px;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.level-group {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  overflow: hidden;
  margin-bottom: 10px;
}

.level-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(248, 250, 252, 0.86);
  cursor: pointer;
  transition: all 0.3s;
}

.level-group-header:hover {
  background: rgba(235, 241, 248, 0.92);
}

.level-group-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.level-badge {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.level-emergencies,
.level-alert,
.level-critical {
  background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
}

.level-error {
  background: linear-gradient(135deg, #ff5722 0%, #e64a19 100%);
}

.level-warning {
  background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
}

.level-notification,
.level-informational {
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
}

.level-debugging {
  background: linear-gradient(135deg, #9e9e9e 0%, #757575 100%);
}

.level-unknown {
  background: linear-gradient(135deg, #607d8b 0%, #455a64 100%);
}

.level-count {
  font-size: 13px;
  font-weight: 600;
}

.level-time {
  font-size: 12px;
  color: #64748b;
}

.level-expand-icon {
  color: #666;
}

.level-group-content {
  padding: 12px 16px;
}

.log-item-compact {
  padding: 8px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.log-item-compact:last-child {
  border-bottom: none;
}

.log-time-compact {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.log-message-compact {
  font-size: 13px;
  color: #0f172a;
  word-break: break-word;
}

.log-more-hint {
  text-align: center;
  padding: 8px;
  color: #64748b;
  font-size: 12px;
}

.loading,
.empty {
  padding: 80px 20px;
  gap: 16px;
}

.loading p,
.empty p {
  margin: 0;
  font-size: 14px;
}

.loading-hint {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.error-hint {
  text-align: center;
}

.error-icon {
  color: #f44336;
  margin-bottom: 16px;
}

.error-hint h3 {
  color: #f44336;
  margin: 0 0 8px 0;
}

.error-hint p {
  color: #64748b;
  margin: 0;
}

.no-logs-hint {
  text-align: center;
  max-width: 600px;
  margin: 0 auto;
}

.hint-icon {
  color: #4a9eff;
  margin-bottom: 16px;
}

.no-logs-hint h3 {
  color: #4a9eff;
  margin: 0 0 12px 0;
}

.no-logs-hint p {
  color: #64748b;
  margin: 0 0 16px 0;
}

.hint-details {
  text-align: left;
  background: rgba(248, 250, 252, 0.82);
  padding: 16px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.hint-details p {
  margin-bottom: 8px;
}

.hint-details p:last-child {
  margin-bottom: 0;
}

.hint-details ol {
  margin: 8px 0;
  padding-left: 20px;
}

.hint-details li {
  margin-bottom: 6px;
}

.logs-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.log-item {
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.3s;
}

.log-item:hover {
  border-color: rgba(15, 90, 224, 0.24);
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.08);
}

.log-main {
  padding: 16px 20px;
  cursor: pointer;
  transition: all 0.3s;
}

.log-main:hover {
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.88), rgba(234, 243, 252, 0.84));
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.log-hostname {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.log-time {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748b;
}

.log-expand-icon {
  color: #666;
}

.log-message {
  font-size: 14px;
  color: #0f172a;
  line-height: 1.6;
  word-break: break-word;
}

.log-actions {
  padding: 12px 20px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.82), rgba(235, 241, 248, 0.9));
  border-top: 1px solid rgba(148, 163, 184, 0.16);
}

.btn-analyze-single:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.log-detail {
  padding: 20px;
  background: rgba(248, 250, 252, 0.78);
  border-top: 1px solid rgba(148, 163, 184, 0.16);
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px 0;
  color: #0f172a;
  font-size: 14px;
  font-weight: 600;
}

.detail-section pre {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 14px;
  padding: 12px;
  font-size: 13px;
  word-break: break-word;
  margin: 0;
  max-height: 300px;
  overflow-y: auto;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.detail-value {
  font-size: 14px;
  color: #0f172a;
  font-weight: 500;
}

.log-analysis-result {
  background: linear-gradient(180deg, rgba(230, 244, 255, 0.96), rgba(216, 236, 255, 0.88));
  border-radius: 16px;
  padding: 16px;
  border-left: 4px solid #0f5ae0;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid rgba(148, 163, 184, 0.16);
}

.page-info {
  font-size: 14px;
  font-weight: 500;
  color: #0f172a;
}

.page-jump {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-jump-input {
  width: 60px;
  font-size: 14px;
  text-align: center;
}

.page-jump-text {
  font-size: 14px;
  color: #64748b;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
