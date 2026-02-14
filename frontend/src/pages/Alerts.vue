<template>
  <div class="page">
    <div class="page-content">
      <div class="page-header">
        <div class="page-title">
          <AlertTriangle class="title-icon" :size="28" />
          <h1>告警中心</h1>
        </div>
        <button @click="refreshData" class="btn-refresh" :disabled="loading">
          <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>

      <!-- 统计卡片 -->
      <div class="stats-grid">
        <div 
          class="stat-card" 
          :class="{ active: filterStatus === 'all' }"
          @click="setFilter('all')"
        >
          <div class="stat-icon stat-icon-danger">
            <AlertOctagon :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.total_alerts }}</div>
            <div class="stat-label">总告警数</div>
          </div>
        </div>
        <div 
          class="stat-card" 
          :class="{ active: filterStatus === 'unacknowledged' }"
          @click="setFilter('unacknowledged')"
        >
          <div class="stat-icon stat-icon-warning">
            <AlertCircle :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.unacknowledged }}</div>
            <div class="stat-label">未确认</div>
          </div>
        </div>
        <div 
          class="stat-card" 
          :class="{ active: filterStatus === 'acknowledged' }"
          @click="setFilter('acknowledged')"
        >
          <div class="stat-icon stat-icon-success">
            <CheckCircle2 :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.acknowledged }}</div>
            <div class="stat-label">已确认</div>
          </div>
        </div>
        <div 
          class="stat-card" 
          :class="{ active: filterStatus === 'hosts' }"
          @click="showHostsModal"
        >
          <div class="stat-icon stat-icon-info">
            <Server :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.enabled_hosts }}</div>
            <div class="stat-label">启用主机</div>
          </div>
        </div>
      </div>

      <!-- 当前筛选提示 -->
      <div v-if="filterStatus !== 'all'" class="filter-status-bar">
        <Filter class="filter-icon" :size="16" />
        <span class="filter-status-text">
          当前筛选: {{ getFilterLabel() }}
          <button @click="setFilter('all')" class="btn-clear-filter">
            <X :size="12" />
            显示全部
          </button>
        </span>
      </div>

      <!-- 严重级别统计 -->
      <div class="severity-stats">
        <div class="section-header">
          <BarChart3 class="section-icon" :size="20" />
          <h3>严重级别分布</h3>
        </div>
        <div class="severity-bars">
          <div v-for="(count, severity) in statistics.severity_stats" :key="severity" class="severity-item">
            <div class="severity-label">{{ severity }}</div>
            <div class="severity-bar-container">
              <div 
                class="severity-bar" 
                :style="{ 
                  width: (count / statistics.total_alerts * 100) + '%',
                  background: getSeverityColor(severity)
                }"
              ></div>
            </div>
            <div class="severity-count">{{ count }}</div>
          </div>
        </div>
      </div>

      <!-- 筛选区域 -->
      <div class="filter-section">
        <div class="filter-group">
          <div class="filter-input-wrapper">
            <Filter class="filter-input-icon" :size="16" />
            <select v-model="filters.severity" class="filter-input" @change="loadAlerts">
              <option value="">所有级别</option>
              <option value="5">灾难</option>
              <option value="4">严重</option>
              <option value="3">一般严重</option>
              <option value="2">警告</option>
              <option value="1">信息</option>
              <option value="0">未分类</option>
            </select>
          </div>
          <div class="filter-input-wrapper">
            <Server class="filter-input-icon" :size="16" />
            <select v-model="filters.host" class="filter-input" @change="loadAlerts">
              <option value="">所有主机</option>
              <option v-for="host in hosts" :key="host.hostid" :value="host.hostid">
                {{ host.name }}
              </option>
            </select>
          </div>
          <button @click="loadAlerts" class="btn-search">
            <Search :size="16" />
            搜索
          </button>
          <button @click="resetFilters" class="btn-reset">
            <RotateCcw :size="16" />
            重置
          </button>
        </div>
      </div>

      <!-- 告警列表 -->
      <div class="alerts-section">
        <div v-if="loading" class="loading">
          <Loader2 class="animate-spin" :size="40" />
          <p>加载中...</p>
        </div>
        <div v-else-if="alerts.length === 0" class="empty">
          <AlertCircleOff :size="48" />
          <p>暂无告警数据</p>
        </div>
        <div v-else class="alerts-list">
          <div 
            v-for="alert in alerts" 
            :key="alert.eventid" 
            class="alert-item"
            :class="getSeverityClass(alert.severity)"
            @click="openAlertDetail(alert)"
          >
            <div class="alert-header">
              <div class="alert-severity" :style="{ background: getSeverityColor(alert.severity) }">
                <AlertTriangle :size="14" />
                {{ alert.severity }}
              </div>
              <div class="alert-status" :class="{ acknowledged: alert.acknowledged === 1 }">
                <component :is="alert.acknowledged === 1 ? CheckCircle2 : AlertCircle" :size="14" />
                {{ alert.status }}
              </div>
              <div class="alert-time">
                <Clock :size="14" />
                {{ formatTime(alert.clock) }}
              </div>
            </div>
            <div class="alert-body">
              <div class="alert-host">
                <Server :size="16" />
                {{ alert.host }}
              </div>
              <div class="alert-name">{{ alert.name }}</div>
              <button 
                v-if="alert.acknowledged === 0" 
                @click.stop="acknowledgeAlert(alert)" 
                class="btn-acknowledge"
                :disabled="acknowledging"
              >
                <Check :size="14" />
                {{ acknowledging ? '确认中...' : '确认告警' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 告警详情弹窗 -->
  <div v-if="selectedAlert" class="modal-overlay" @click="closeAlertDetail">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <div class="modal-title">
          <AlertTriangle :size="24" />
          <h2>告警详情</h2>
        </div>
        <button @click="closeAlertDetail" class="btn-close">
          <X :size="20" />
        </button>
      </div>
      <div class="modal-body">
        <div class="detail-section">
          <div class="section-header">
            <Info :size="18" />
            <h3>告警信息</h3>
          </div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">告警ID:</span>
              <span class="detail-value">{{ selectedAlert.eventid }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">严重级别:</span>
              <span 
                class="detail-value severity-badge" 
                :style="{ background: getSeverityColor(selectedAlert.severity) }"
              >
                <AlertTriangle :size="12" />
                {{ selectedAlert.severity }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">主机:</span>
              <span class="detail-value">{{ selectedAlert.host }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">状态:</span>
              <span 
                class="detail-value status-badge"
                :class="{ acknowledged: selectedAlert.acknowledged === 1 }"
              >
                <component :is="selectedAlert.acknowledged === 1 ? CheckCircle2 : AlertCircle" :size="12" />
                {{ selectedAlert.status }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">发生时间:</span>
              <span class="detail-value">{{ formatTime(selectedAlert.clock) }}</span>
            </div>
          </div>
        </div>
        
        <div class="detail-section">
          <div class="section-header">
            <FileText :size="18" />
            <h3>告警描述</h3>
          </div>
          <div class="detail-description">
            {{ selectedAlert.name }}
          </div>
        </div>
        
        <div v-if="selectedAlert.acknowledged === 0" class="detail-actions">
          <button 
            @click="acknowledgeAlert(selectedAlert)" 
            class="btn-acknowledge-large"
            :disabled="acknowledging"
          >
            <Check :size="16" />
            {{ acknowledging ? '确认中...' : '确认此告警' }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 主机列表弹窗 -->
  <div v-if="showHostsModalDialog" class="modal-overlay" @click="closeHostsModal">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <div class="modal-title">
          <Server :size="24" />
          <h2>启用主机列表</h2>
        </div>
        <button @click="closeHostsModal" class="btn-close">
          <X :size="20" />
        </button>
      </div>
      <div class="modal-body">
        <div v-if="loadingHosts" class="loading">
          <Loader2 class="animate-spin" :size="40" />
          <p>加载中...</p>
        </div>
        <div v-else-if="enabledHostsList.length === 0" class="empty">
          <ServerOff :size="48" />
          <p>暂无主机数据</p>
        </div>
        <div v-else class="hosts-list">
          <div v-for="host in enabledHostsList" :key="host.hostid" class="host-item">
            <div class="host-icon">
              <Server :size="24" />
            </div>
            <div class="host-info">
              <div class="host-name">{{ host.name }}</div>
              <div class="host-ip">{{ host.host }}</div>
            </div>
            <div class="host-status" :class="{ enabled: host.status === '启用' }">
              <component :is="host.status === '启用' ? CheckCircle2 : XCircle" :size="12" />
              {{ host.status }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { alertsApi, Alert, AlertStatistics, Host } from '@/api/alerts'
import { 
  AlertTriangle, 
  RefreshCw, 
  AlertOctagon, 
  AlertCircle, 
  CheckCircle2, 
  Server, 
  Filter, 
  X, 
  BarChart3, 
  Search, 
  RotateCcw, 
  Loader2, 
  Check, 
  Info, 
  FileText, 
  ServerOff, 
  XCircle, 
  Clock 
} from 'lucide-vue-next'

const loading = ref(false)
const route = useRoute()
const alerts = ref<Alert[]>([])
const hosts = ref<Host[]>([])
const enabledHostsList = ref<Host[]>([])
const loadingHosts = ref(false)
const statistics = ref<AlertStatistics>({
  total_alerts: 0,
  acknowledged: 0,
  unacknowledged: 0,
  severity_stats: {},
  total_hosts: 0,
  enabled_hosts: 0,
  disabled_hosts: 0
})

const filters = ref({
  severity: '',
  host: ''
})

const filterStatus = ref<'all' | 'unacknowledged' | 'acknowledged'>('all')
const levelFilter = ref<'all' | 'critical' | 'warning'>('all')
const showHostsModalDialog = ref(false)

const selectedAlert = ref<Alert | null>(null)
const acknowledging = ref(false)

async function loadAlerts() {
  loading.value = true
  try {
    const params: any = {}
    if (filters.value.severity) params.severity = parseInt(filters.value.severity)
    if (filters.value.host) params.host = filters.value.host
    
    if (filterStatus.value === 'unacknowledged') {
      params.acknowledged = 0
    } else if (filterStatus.value === 'acknowledged') {
      params.acknowledged = 1
    }

    const response = await alertsApi.getAlerts(params)
    const allAlerts = response.alerts || []
    if (levelFilter.value === 'all') {
      alerts.value = allAlerts
      return
    }
    alerts.value = allAlerts.filter((item) => matchesLevel(item.severity, levelFilter.value))
  } catch (error) {
    console.error('Error loading alerts:', error)
  } finally {
    loading.value = false
  }
}

async function loadHosts() {
  try {
    const response = await alertsApi.getHosts({ limit: 1000 })
    hosts.value = response.hosts
  } catch (error) {
    console.error('Error loading hosts:', error)
  }
}

async function loadEnabledHosts() {
  loadingHosts.value = true
  try {
    const response = await alertsApi.getHosts({ limit: 1000 })
    enabledHostsList.value = response.hosts.filter(h => h.status === '启用')
  } catch (error) {
    console.error('Error loading enabled hosts:', error)
  } finally {
    loadingHosts.value = false
  }
}

async function loadStatistics() {
  try {
    const stats = await alertsApi.getStatistics()
    statistics.value = stats
  } catch (error) {
    console.error('Error loading statistics:', error)
  }
}

function resetFilters() {
  filters.value = {
    severity: '',
    host: ''
  }
  loadAlerts()
}

function setFilter(status: 'all' | 'unacknowledged' | 'acknowledged') {
  filterStatus.value = status
  loadAlerts()
}

function getFilterLabel(): string {
  const labels: Record<string, string> = {
    all: '全部告警',
    unacknowledged: '未确认告警',
    acknowledged: '已确认告警'
  }
  return labels[filterStatus.value]
}

function showHostsModal() {
  showHostsModalDialog.value = true
  loadEnabledHosts()
}

function closeHostsModal() {
  showHostsModalDialog.value = false
}

function refreshData() {
  loadAlerts()
  loadStatistics()
}

function formatTime(timestamp: string): string {
  const date = new Date(parseInt(timestamp) * 1000)
  return date.toLocaleString('zh-CN')
}

function getSeverityColor(severity: string): string {
  const colorMap: Record<string, string> = {
    '灾难': '#f44336',
    '严重': '#ff5722',
    '一般严重': '#ff9800',
    '警告': '#ffc107',
    '信息': '#2196f3',
    '未分类': '#9e9e9e'
  }
  return colorMap[severity] || '#9e9e9e'
}

function getSeverityClass(severity: string): string {
  return `severity-${severity}`
}

function matchesLevel(severity: string, level: 'critical' | 'warning') {
  const text = String(severity || '')
  if (level === 'critical') {
    return /灾难|严重|critical|high/i.test(text)
  }
  return /一般严重|警告|warning|medium/i.test(text)
}

function openAlertDetail(alert: Alert) {
  selectedAlert.value = alert
}

function closeAlertDetail() {
  selectedAlert.value = null
}

async function acknowledgeAlert(alert: Alert) {
  acknowledging.value = true
  try {
    const result = await alertsApi.acknowledgeAlerts([alert.eventid])
    console.log('告警确认成功:', result)
    
    await loadAlerts()
    await loadStatistics()
    
    if (selectedAlert.value && selectedAlert.value.eventid === alert.eventid) {
      closeAlertDetail()
    }
  } catch (error) {
    console.error('确认告警失败:', error)
    alert('确认告警失败，请稍后重试')
  } finally {
    acknowledging.value = false
  }
}

onMounted(() => {
  const queryStatus = route.query.status ? String(route.query.status) : ''
  const queryLevel = route.query.level ? String(route.query.level) : ''

  if (queryStatus === 'acknowledged' || queryStatus === 'unacknowledged') {
    filterStatus.value = queryStatus
  }
  if (queryLevel === 'critical' || queryLevel === 'warning') {
    levelFilter.value = queryLevel
  }

  loadAlerts()
  loadHosts()
  loadStatistics()
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
  color: #f44336;
}

.page-header h1 {
  color: #333;
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.btn-refresh {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(74, 158, 255, 0.3);
}

.btn-refresh:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.4);
}

.btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: white;
  padding: 24px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  gap: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid transparent;
}

.stat-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  transform: translateY(-4px);
}

.stat-card.active {
  box-shadow: 0 8px 24px rgba(74, 158, 255, 0.25);
  border-color: #4a9eff;
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.stat-icon-danger {
  background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
}

.stat-icon-warning {
  background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
}

.stat-icon-success {
  background: linear-gradient(135deg, #4caf50 0%, #388e3c 100%);
}

.stat-icon-info {
  background: linear-gradient(135deg, #2196f3 0%, #1976d2 100%);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: #333;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 8px;
  font-weight: 500;
}

.filter-status-bar {
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  padding: 16px 24px;
  border-radius: 12px;
  margin-bottom: 24px;
  border-left: 4px solid #4a9eff;
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-icon {
  color: #4a9eff;
  flex-shrink: 0;
}

.filter-status-text {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #1976d2;
  font-weight: 500;
}

.btn-clear-filter {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  background: #4a9eff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-clear-filter:hover {
  background: #2196f3;
  transform: translateY(-1px);
}

.severity-stats {
  background: white;
  padding: 24px;
  border-radius: 16px;
  margin-bottom: 32px;
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

.severity-stats h3 {
  margin: 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.severity-bars {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.severity-item {
  display: flex;
  align-items: center;
  gap: 14px;
}

.severity-label {
  width: 90px;
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.severity-bar-container {
  flex: 1;
  height: 28px;
  background: #f5f5f5;
  border-radius: 8px;
  overflow: hidden;
}

.severity-bar {
  height: 100%;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: 8px;
}

.severity-count {
  width: 50px;
  text-align: right;
  font-weight: 700;
  color: #333;
  font-size: 16px;
}

.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  margin-bottom: 32px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.filter-group {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.filter-input-wrapper {
  position: relative;
  min-width: 180px;
}

.filter-input-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #999;
  pointer-events: none;
}

.filter-input {
  width: 100%;
  padding: 10px 12px 10px 40px;
  border: 2px solid #e8eef5;
  border-radius: 10px;
  font-size: 14px;
  background: white;
  transition: all 0.3s;
}

.filter-input:focus {
  outline: none;
  border-color: #4a9eff;
  box-shadow: 0 0 0 4px rgba(74, 158, 255, 0.1);
}

.btn-search,
.btn-reset {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-search {
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(74, 158, 255, 0.3);
}

.btn-search:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.4);
}

.btn-reset {
  background: #f5f5f5;
  color: #333;
  border: 2px solid #e8eef5;
}

.btn-reset:hover {
  background: #e8eef5;
}

.alerts-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.loading,
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.loading p,
.empty p {
  margin: 0;
  font-size: 14px;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.alert-item {
  padding: 20px;
  border-radius: 12px;
  border-left: 4px solid #9e9e9e;
  background: #fafafa;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.alert-item:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.alert-item.severity-灾难 {
  border-left-color: #f44336;
  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
}

.alert-item.severity-严重 {
  border-left-color: #ff5722;
  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
}

.alert-item.severity-一般严重 {
  border-left-color: #ff9800;
  background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
}

.alert-item.severity-警告 {
  border-left-color: #ffc107;
  background: linear-gradient(135deg, #fffde7 0%, #fff9c4 100%);
}

.alert-item.severity-信息 {
  border-left-color: #2196f3;
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
}

.alert-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.alert-severity {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  color: white;
  font-size: 13px;
  font-weight: 600;
}

.alert-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  background: #f44336;
  color: white;
  font-size: 13px;
  font-weight: 600;
}

.alert-status.acknowledged {
  background: #4caf50;
}

.alert-time {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 13px;
  color: #666;
}

.alert-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.alert-host {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.alert-name {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
}

.btn-acknowledge {
  align-self: flex-start;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #4caf50 0%, #388e3c 100%);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-acknowledge:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
}

.btn-acknowledge:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 650px;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.2);
  animation: modalIn 0.3s ease-out;
}

@keyframes modalIn {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid #e8eef5;
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.modal-title h2 {
  margin: 0;
  color: #333;
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  color: #666;
  padding: 8px;
  transition: all 0.3s;
}

.btn-close:hover {
  background: #e8eef5;
  color: #333;
}

.modal-body {
  padding: 24px;
}

.detail-section {
  margin-bottom: 28px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section h3 {
  margin: 0 0 18px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 18px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-label {
  font-size: 13px;
  color: #666;
  font-weight: 600;
}

.detail-value {
  font-size: 15px;
  color: #333;
  font-weight: 500;
}

.severity-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  color: white;
  font-size: 13px;
  font-weight: 600;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  background: #f44336;
  color: white;
  font-size: 13px;
  font-weight: 600;
}

.status-badge.acknowledged {
  background: #4caf50;
}

.detail-description {
  padding: 18px;
  background: linear-gradient(135deg, #f5f5f5 0%, #e8eef5 100%);
  border-radius: 12px;
  font-size: 15px;
  color: #333;
  line-height: 1.8;
  border-left: 4px solid #4a9eff;
}

.detail-actions {
  margin-top: 28px;
  text-align: center;
}

.btn-acknowledge-large {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 32px;
  background: linear-gradient(135deg, #4caf50 0%, #388e3c 100%);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.3s;
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
}

.btn-acknowledge-large:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(76, 175, 80, 0.4);
}

.btn-acknowledge-large:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.hosts-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 500px;
  overflow-y: auto;
}

.host-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
  background: linear-gradient(135deg, #f5f5f5 0%, #e8eef5 100%);
  border-radius: 12px;
  transition: all 0.3s;
}

.host-item:hover {
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.host-icon {
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

.host-info {
  flex: 1;
}

.host-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 6px;
}

.host-ip {
  font-size: 14px;
  color: #666;
}

.host-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 20px;
  background: #f44336;
  color: white;
  font-size: 13px;
  font-weight: 600;
}

.host-status.enabled {
  background: #4caf50;
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
