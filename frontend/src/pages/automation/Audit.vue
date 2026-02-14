<template>
  <div class="automation-audit">
    <div class="page-header">
      <h1>自动化审计</h1>
      <button @click="refreshAudit" class="refresh-btn">
        <RefreshCw :size="16" />
        刷新
      </button>
    </div>

    <div class="audit-filters">
      <select v-model="filterSeverity" @change="loadAudit" class="filter-select">
        <option value="">全部严重级别</option>
        <option value="critical">严重</option>
        <option value="warning">警告</option>
        <option value="info">信息</option>
      </select>
      <select v-model="filterSite" @change="loadAudit" class="filter-select">
        <option value="">全部基地</option>
        <option v-for="site in sites" :key="site.id" :value="site.id">
          {{ site.site_name }}
        </option>
      </select>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="auditLogs.length" class="audit-list">
      <div v-for="log in auditLogs" :key="log.id" class="audit-item" :class="log.severity">
        <div class="audit-icon">
          <AlertTriangle v-if="log.severity === 'critical'" :size="20" />
          <AlertCircle v-else-if="log.severity === 'warning'" :size="20" />
          <Info v-else :size="20" />
        </div>
        <div class="audit-content">
          <div class="audit-summary">{{ log.summary }}</div>
          <div class="audit-meta">
            <span class="audit-time">{{ formatTime(log.created_at) }}</span>
            <span class="audit-device">设备: {{ log.netbox_device_id || '未知' }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="no-data">暂无审计记录</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RefreshCw, AlertTriangle, AlertCircle, Info } from 'lucide-vue-next'
import { getAnalysisResults, getSites } from '@/api/automation'

const auditLogs = ref<any[]>([])
const sites = ref<any[]>([])
const loading = ref(false)
const filterSeverity = ref('')
const filterSite = ref('')

const loadAudit = async () => {
  loading.value = true
  try {
    const params: any = { limit: 50 }
    if (filterSeverity.value) params.severity = filterSeverity.value
    if (filterSite.value) params.site_id = Number(filterSite.value)
    
    const data = await getAnalysisResults(params)
    auditLogs.value = data.results || []
  } catch (error) {
    console.error('Failed to load audit:', error)
  } finally {
    loading.value = false
  }
}

const loadSites = async () => {
  try {
    const data = await getSites()
    sites.value = data.sites || []
  } catch (error) {
    console.error('Failed to load sites:', error)
  }
}

const refreshAudit = () => {
  loadAudit()
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  loadSites()
  loadAudit()
})
</script>

<style scoped>
.automation-audit {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: white;
  color: #666;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;
}

.refresh-btn:hover {
  background: #f8f9fa;
  border-color: #4a9eff;
  color: #4a9eff;
}

.audit-filters {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.filter-select {
  padding: 8px 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  color: #666;
  background: white;
}

.loading, .no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
}

.audit-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.audit-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: 12px;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border-left: 4px solid transparent;
}

.audit-item.critical {
  border-left-color: #f44336;
}

.audit-item.warning {
  border-left-color: #ff9800;
}

.audit-item.info {
  border-left-color: #2196f3;
}

.audit-icon {
  color: #666;
}

.audit-item.critical .audit-icon {
  color: #f44336;
}

.audit-item.warning .audit-icon {
  color: #ff9800;
}

.audit-item.info .audit-icon {
  color: #2196f3;
}

.audit-content {
  flex: 1;
}

.audit-summary {
  font-size: 14px;
  font-weight: 500;
  color: #1a1a2e;
  margin-bottom: 4px;
}

.audit-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #999;
}
</style>