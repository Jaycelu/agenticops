<template>
  <div class="automation-samples">
    <div class="page-content">
      <div class="page-header">
        <button @click="goBack" class="back-btn">
          <ArrowLeft :size="16" />
          返回
        </button>
        <div class="page-title">
          <Activity class="title-icon" :size="28" />
          <h1>异常采样列表</h1>
        </div>
        <button @click="refreshSamples" class="btn-refresh" :disabled="loading">
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
      <div v-else-if="samples.length" class="samples-list">
        <div
          v-for="sample in samples"
          :key="sample.id"
          class="sample-card"
        >
          <div class="sample-header">
            <div class="sample-id">#{{ sample.id }}</div>
            <div class="sample-type" :class="sample.abnormal_type">
              {{ getAbnormalTypeLabel(sample.abnormal_type) }}
            </div>
          </div>
          <div class="sample-body">
            <div class="sample-summary">
              <div class="sample-metrics">
                <span class="metric">
                  <strong>CRC错误:</strong> {{ sample.crc_error_count }}
                </span>
                <span class="metric">
                  <strong>Flap次数:</strong> {{ sample.flap_count }}
                </span>
                <span class="metric">
                  <strong>邻居变化:</strong> {{ sample.neighbor_change_count }}
                </span>
              </div>
            </div>
            <div class="sample-meta">
              <span class="sample-time">{{ formatTime(sample.sampled_at) }}</span>
              <span class="sample-device">设备IP: {{ sample.device_ip || '未知' }}</span>
              <span class="sample-device-id">设备ID: {{ sample.netbox_device_id || '未知' }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="no-data">暂无异常采样数据</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { RefreshCw, Building2, Activity, ArrowLeft } from 'lucide-vue-next'
import { getLogSamples, getSites } from '@/api/automation'

const router = useRouter()
const route = useRoute()
const samples = ref<any[]>([])
const sites = ref<any[]>([])
const selectedSiteId = ref<number | null>(null)
const loading = ref(false)
const startDate = ref<string>('')
const endDate = ref<string>('')

const abnormalTypeLabels: Record<string, string> = {
  LINK_QUALITY_DEGRADE: '链路质量下降',
  INTERFACE_FLAP: '接口震荡',
  NEIGHBOR_UNSTABLE: '邻居不稳定',
  UNKNOWN: '未知异常'
}

const loadSamples = async () => {
  loading.value = true
  try {
    if (!selectedSiteId.value) {
      console.warn('No site selected')
      return
    }
    const params: any = {
      site_id: selectedSiteId.value,
      is_abnormal: true
    }
    // 如果有日期参数，则添加到请求中
    if (startDate.value) {
      params.start_date = startDate.value
    }
    if (endDate.value) {
      params.end_date = endDate.value
    }
    const data = await getLogSamples(params)
    samples.value = data.samples || []
  } catch (error) {
    console.error('Failed to load samples:', error)
  } finally {
    loading.value = false
  }
}

const loadSites = async () => {
  try {
    const data = await getSites()
    sites.value = data.sites || []
    // 默认选择第一个基地
    if (sites.value.length > 0 && !selectedSiteId.value) {
      const firstEnabled = sites.value.find((site: any) => site.automation_enabled)
      selectedSiteId.value = (firstEnabled || sites.value[0]).id
    }
  } catch (error) {
    console.error('Failed to load sites:', error)
  }
}

const handleSiteChange = (siteId: number) => {
  selectedSiteId.value = siteId
  loadSamples()
}

const refreshSamples = () => {
  loadSamples()
}

const goBack = () => {
  router.push('/automation/dashboard')
}

const getAbnormalTypeLabel = (type: string) => {
  return abnormalTypeLabels[type] || type
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

// 监听基地ID变化，自动加载数据
watch(selectedSiteId, (newId) => {
  if (newId) {
    loadSamples()
  }
})

onMounted(() => {
  // 从路由参数中读取日期
  if (route.query.start_date) {
    startDate.value = route.query.start_date as string
  }
  if (route.query.end_date) {
    endDate.value = route.query.end_date as string
  }
  loadSites()
})
</script>

<style scoped>
.automation-samples {
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

.samples-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sample-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
}

.sample-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.sample-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.sample-id {
  font-size: 14px;
  color: #999;
}

.sample-type {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.sample-type.LINK_QUALITY_DEGRADE {
  background: #fee2e2;
  color: #dc2626;
}

.sample-type.INTERFACE_FLAP {
  background: #fef3c7;
  color: #d97706;
}

.sample-type.NEIGHBOR_UNSTABLE {
  background: #dbeafe;
  color: #2563eb;
}

.sample-type.UNKNOWN {
  background: #f5f5f5;
  color: #666;
}

.sample-body {
  margin-top: 12px;
}

.sample-summary {
  margin-bottom: 8px;
}

.sample-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 14px;
  color: #1a1a2e;
}

.metric {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sample-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #999;
}
</style>
