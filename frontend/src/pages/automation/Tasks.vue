<template>
  <div class="automation-tasks">
    <div class="page-content">
      <div class="page-header">
        <button @click="goBack" class="back-btn">
          <ArrowLeft :size="16" />
          返回
        </button>
        <div class="page-title">
          <ListChecks class="title-icon" :size="28" />
          <h1>自动化任务列表</h1>
        </div>
        <button @click="refreshTasks" class="btn-refresh" :disabled="loading">
          <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>

      <!-- 基地选择 -->
      <div class="base-section">
        <div class="section-header">
          <Building2 class="section-icon" :size="20" />
          <h3>选择基地</h3>
        </div>
        <div class="base-grid">
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

      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="tasks.length" class="tasks-list">
        <div
          v-for="task in tasks"
          :key="task.id"
          class="task-card"
          @click="goToDetail(task.id)"
        >
          <div class="task-header">
            <div class="task-id">#{{ task.id }}</div>
            <div class="task-status" :class="task.status">
              {{ statusLabels[task.status] || task.status }}
            </div>
          </div>
          <div class="task-body">
            <div class="task-summary">{{ task.decision_result?.diagnosis?.summary || task.decision_result?.summary || '无摘要' }}</div>
            <div class="task-meta">
              <span class="task-time">{{ formatTime(task.created_at) }}</span>
              <span class="task-device">设备IP: {{ task.device_ip || '未知' }}</span>
              <span class="task-type">{{ getDiagnosisTypeLabel(task.decision_result?.diagnosis?.diagnosis_type) }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="no-data">暂无任务</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { RefreshCw, Building2, ListChecks, ArrowLeft } from 'lucide-vue-next'
import { getAutomationTasks, getSites } from '@/api/automation'

const router = useRouter()
const route = useRoute()
const tasks = ref<any[]>([])
const sites = ref<any[]>([])
const selectedSiteId = ref<number | null>(null)
const loading = ref(false)
const startDate = ref<string>('')
const endDate = ref<string>('')

const statusLabels: Record<string, string> = {
  pending: '待处理',
  running: '运行中',
  success: '成功',
  failed: '失败',
  aborted: '已终止'
}

const diagnosisTypeLabels: Record<string, string> = {
  LINK_QUALITY_DEGRADE: '链路质量下降',
  INTERFACE_FLAP: '接口震荡',
  NEIGHBOR_UNSTABLE: '邻居不稳定',
  HIGH_ERROR_RATE: '高错误率',
  CONFIGURATION_ISSUE: '配置问题',
  HARDWARE_ISSUE: '硬件问题',
  UNKNOWN: '未知异常'
}

const loadTasks = async () => {
  loading.value = true
  try {
    if (!selectedSiteId.value) {
      console.warn('No site selected')
      return
    }
    const params: any = {
      site_id: selectedSiteId.value
    }
    // 如果有日期参数，则添加到请求中
    if (startDate.value) {
      params.start_date = startDate.value
    }
    if (endDate.value) {
      params.end_date = endDate.value
    }
    const data = await getAutomationTasks(params)
    tasks.value = data.tasks || []
  } catch (error) {
    console.error('Failed to load tasks:', error)
  } finally {
    loading.value = false
  }
}

const loadSites = async () => {
  try {
    const data = await getSites()
    sites.value = data.sites || []
    // 默认选择第一个基地（德阳基地）
    if (sites.value.length > 0 && !selectedSiteId.value) {
      selectedSiteId.value = sites.value[0].id
    }
  } catch (error) {
    console.error('Failed to load sites:', error)
  }
}

const handleSiteChange = (siteId: number) => {
  selectedSiteId.value = siteId
  loadTasks()
}

const refreshTasks = () => {
  loadTasks()
}

const goToDetail = (taskId: number) => {
  router.push(`/automation/tasks/${taskId}`)
}

const goBack = () => {
  router.push('/automation/dashboard')
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

const getDiagnosisTypeLabel = (type: string) => {
  return diagnosisTypeLabels[type] || type
}

// 监听selectedSiteId变化，自动加载任务
watch(selectedSiteId, (newSiteId) => {
  if (newSiteId) {
    loadTasks()
  }
})

onMounted(async () => {
  // 从路由参数中读取日期
  if (route.query.start_date) {
    startDate.value = route.query.start_date as string
  }
  if (route.query.end_date) {
    endDate.value = route.query.end_date as string
  }
  // 先加载基地列表
  await loadSites()
  // 基地加载完成后，selectedSiteId会被设置，watch会自动触发loadTasks
})
</script>

<style scoped>
.automation-tasks {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-content {
  width: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  gap: 16px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  color: #666;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.back-btn:hover {
  background: #f8f9fa;
  border-color: #4a9eff;
  color: #4a9eff;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

.title-icon {
  color: #4a9eff;
}

.btn-refresh {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  color: #666;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-refresh:hover {
  background: #f8f9fa;
  border-color: #4a9eff;
  color: #4a9eff;
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.base-section {
  background: white;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.section-icon {
  color: #4a9eff;
}

.section-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0;
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
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  background: #f8f9fa;
  cursor: pointer;
  transition: all 0.3s;
}

.base-card:hover {
  border-color: #4a9eff;
  background: white;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.15);
}

.base-card.active {
  border-color: #4a9eff;
  background: linear-gradient(135deg, rgba(74, 158, 255, 0.05), rgba(74, 158, 255, 0.02));
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.2);
}

.base-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: linear-gradient(135deg, #4a9eff 0%, #667eea 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.base-info {
  flex: 1;
  min-width: 0;
}

.base-name {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 4px;
}

.base-desc {
  font-size: 13px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.loading, .no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.task-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.3s;
}

.task-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-id {
  font-size: 14px;
  color: #999;
}

.task-status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.task-status.pending {
  background: #f5f5f5;
  color: #666;
}

.task-status.running {
  background: #e3f2fd;
  color: #2196f3;
}

.task-status.success {
  background: #e8f5e9;
  color: #4caf50;
}

.task-status.failed {
  background: #ffebee;
  color: #f44336;
}

.task-body {
  margin-top: 12px;
}

.task-summary {
  font-size: 16px;
  font-weight: 500;
  color: #1a1a2e;
  margin-bottom: 8px;
}

.task-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #999;
  align-items: center;
}

.task-type {
  padding: 2px 8px;
  background: #f0f0f0;
  border-radius: 4px;
  font-size: 11px;
  color: #666;
}
</style>