<template>
  <div class="analysis-results">
    <div class="page-content">
      <div class="page-header">
        <button @click="goBack" class="back-btn">
          <ArrowLeft :size="16" />
          返回
        </button>
        <div class="page-title">
          <Brain class="title-icon" :size="28" />
          <h1>研判结果列表</h1>
        </div>
        <button @click="refreshResults" class="btn-refresh" :disabled="loading">
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

      <!-- 筛选器 -->
      <div class="filter-section">
        <div class="filter-item">
          <label>严重程度:</label>
          <select v-model="severityFilter" @change="loadResults" class="filter-select">
            <option value="">全部</option>
            <option value="critical">严重</option>
            <option value="warning">警告</option>
            <option value="info">信息</option>
          </select>
        </div>
        <div class="filter-item">
          <label>状态:</label>
          <select v-model="statusFilter" @change="loadResults" class="filter-select">
            <option value="">全部</option>
            <option value="completed">已完成</option>
            <option value="pending">待处理</option>
            <option value="failed">失败</option>
          </select>
        </div>
      </div>

      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="results.length" class="results-list">
        <div
          v-for="result in results"
          :key="result.id"
          class="result-card clickable"
          :class="result.severity"
          @click="showDetail(result)"
        >
          <div class="result-header">
            <div class="result-id">#{{ result.id }}</div>
            <div class="result-severity" :class="result.severity">
              {{ getSeverityLabel(result.severity) }}
            </div>
          </div>
          <div class="result-body">
            <div class="result-type">{{ result.analysis_type }}</div>
            <div class="result-summary">{{ result.summary }}</div>
            <div class="result-details" v-if="result.recommendation">
              <strong>建议:</strong> {{ result.recommendation }}
            </div>
            <div class="result-meta">
              <span class="result-confidence">可信度: {{ getConfidenceLabel(result.confidence) }}</span>
              <span class="result-status">状态: {{ getStatusLabel(result.status) }}</span>
              <span class="result-device">设备IP: {{ result.device_ip || '未知' }}</span>
              <span class="result-time">{{ formatTime(result.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="no-data">暂无研判结果</div>
    </div>

    <!-- 研判结果详情弹窗 -->
    <div v-if="selectedResult" class="modal-overlay" @click="closeDetail">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>研判结果详情</h2>
          <button @click="closeDetail" class="close-btn">
            <X :size="20" />
          </button>
        </div>
        <div class="modal-body">
          <!-- 基本信息 -->
          <div class="detail-section">
            <h3>基本信息</h3>
            <div class="info-grid">
              <div class="info-item">
                <label>分析类型:</label>
                <span>{{ selectedResult.analysis_type }}</span>
              </div>
              <div class="info-item">
                <label>严重程度:</label>
                <span :class="selectedResult.severity">{{ getSeverityLabel(selectedResult.severity) }}</span>
              </div>
              <div class="info-item">
                <label>可信度:</label>
                <span>{{ getConfidenceLabel(selectedResult.confidence) }}</span>
              </div>
              <div class="info-item">
                <label>设备IP:</label>
                <span>{{ selectedResult.device_ip || '未知' }}</span>
              </div>
            </div>
          </div>

          <!-- 研判摘要 -->
          <div class="detail-section">
            <h3>研判摘要</h3>
            <p class="summary-text">{{ selectedResult.summary }}</p>
            <div v-if="selectedResult.recommendation" class="recommendation-box">
              <strong>建议:</strong>
              <p>{{ selectedResult.recommendation }}</p>
            </div>
          </div>

          <!-- 研判步骤 -->
          <div class="detail-section">
            <h3>研判步骤</h3>
            <div class="steps-container">
              <!-- 步骤1: 状态聚合 -->
              <div class="step-item">
                <div class="step-number">1</div>
                <div class="step-content">
                  <div class="step-title">状态聚合</div>
                  <div class="step-description">分析24小时内的采样数据，识别趋势性异常</div>
                  <div v-if="evidence.state_aggregation" class="step-details">
                    <div class="evidence-item">
                      <strong>时间窗口:</strong> 
                      {{ formatTime(evidence.state_aggregation.time_window?.start) }} - 
                      {{ formatTime(evidence.state_aggregation.time_window?.end) }}
                    </div>
                    <div class="evidence-item">
                      <strong>采样统计:</strong> 
                      总计 {{ evidence.state_aggregation.summary?.total_samples }} 次，
                      异常 {{ evidence.state_aggregation.summary?.abnormal_samples }} 次
                      ({{ (evidence.state_aggregation.summary?.abnormal_rate * 100 || 0).toFixed(1) }}%)
                    </div>
                  </div>
                </div>
              </div>

              <!-- 步骤2: 规则初判 -->
              <div class="step-item">
                <div class="step-number">2</div>
                <div class="step-content">
                  <div class="step-title">规则初判</div>
                  <div class="step-description">基于预定义规则进行初步诊断</div>
                  <div v-if="evidence.diagnosis" class="step-details">
                    <div class="evidence-item">
                      <strong>问题类型:</strong> {{ evidence.diagnosis.problem_type }}
                    </div>
                    <div class="evidence-item">
                      <strong>风险等级:</strong> {{ evidence.diagnosis.risk_level }}
                    </div>
                    <div class="evidence-item">
                      <strong>自动执行:</strong> {{ evidence.diagnosis.auto_executable ? '是' : '否' }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- 步骤3: AI增强 -->
              <div class="step-item">
                <div class="step-number">3</div>
                <div class="step-content">
                  <div class="step-title">AI增强</div>
                  <div class="step-description">使用LLM进行综合研判分析</div>
                  <div v-if="evidence.diagnosis?.details" class="step-details">
                    <div class="evidence-item">
                      <strong>详细分析:</strong> {{ evidence.diagnosis.details }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 证据链 -->
          <div class="detail-section">
            <h3>证据链</h3>
            <div class="evidence-grid">
              <!-- 日志证据 -->
              <div class="evidence-card">
                <div class="evidence-header">
                  <FileText :size="20" />
                  <h4>日志证据</h4>
                </div>
                <div v-if="evidence.diagnosis?.evidence?.log_evidence" class="evidence-body">
                  <div class="evidence-row">
                    <span class="evidence-label">CRC趋势:</span>
                    <span :class="evidence.diagnosis.evidence.log_evidence.crc_trend?.trend">
                      {{ evidence.diagnosis.evidence.log_evidence.crc_trend?.description || 'N/A' }}
                    </span>
                  </div>
                  <div class="evidence-row">
                    <span class="evidence-label">Flap频率:</span>
                    <span :class="evidence.diagnosis.evidence.log_evidence.flap_frequency?.frequency">
                      {{ evidence.diagnosis.evidence.log_evidence.flap_frequency?.description || 'N/A' }}
                    </span>
                  </div>
                  <div class="evidence-row">
                    <span class="evidence-label">邻居稳定性:</span>
                    <span :class="evidence.diagnosis.evidence.log_evidence.neighbor_stability?.stability">
                      {{ evidence.diagnosis.evidence.log_evidence.neighbor_stability?.description || 'N/A' }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- 配置证据 -->
              <div class="evidence-card">
                <div class="evidence-header">
                  <Settings :size="20" />
                  <h4>配置证据</h4>
                </div>
                <div v-if="evidence.diagnosis?.evidence?.config_evidence" class="evidence-body">
                  <div class="evidence-row">
                    <span class="evidence-label">接口配置:</span>
                    <span>{{ evidence.diagnosis.evidence.config_evidence.interface_config }}</span>
                  </div>
                  <div class="evidence-row">
                    <span class="evidence-label">QoS配置:</span>
                    <span>{{ evidence.diagnosis.evidence.config_evidence.qos_config }}</span>
                  </div>
                  <div class="evidence-row">
                    <span class="evidence-label">Storm Control:</span>
                    <span>{{ evidence.diagnosis.evidence.config_evidence.storm_control }}</span>
                  </div>
                </div>
              </div>

              <!-- 对端证据 -->
              <div class="evidence-card">
                <div class="evidence-header">
                  <Network :size="20" />
                  <h4>对端证据</h4>
                </div>
                <div v-if="evidence.diagnosis?.evidence?.peer_evidence" class="evidence-body">
                  <div class="evidence-row">
                    <span class="evidence-label">对端设备:</span>
                    <span>{{ evidence.diagnosis.evidence.peer_evidence.peer_device }}</span>
                  </div>
                  <div class="evidence-row">
                    <span class="evidence-label">对端接口:</span>
                    <span>{{ evidence.diagnosis.evidence.peer_evidence.peer_interface }}</span>
                  </div>
                  <div class="evidence-row">
                    <span class="evidence-label">对端错误:</span>
                    <span>{{ evidence.diagnosis.evidence.peer_evidence.peer_errors }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 详细数据 -->
          <div class="detail-section">
            <h3>详细数据</h3>
            <div class="json-viewer">
              <pre>{{ JSON.stringify(selectedResult.evidence, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { RefreshCw, Building2, Brain, ArrowLeft, X, FileText, Settings, Network } from 'lucide-vue-next'
import { getAnalysisResults, getSites } from '@/api/automation'

const router = useRouter()
const route = useRoute()
const results = ref<any[]>([])
const sites = ref<any[]>([])
const selectedSiteId = ref<number | null>(null)
const loading = ref(false)
const severityFilter = ref('')
const statusFilter = ref('')
const selectedResult = ref<any>(null)
const startDate = ref<string>('')
const endDate = ref<string>('')
const querySiteId = ref<number | null>(null)

const severityLabels: Record<string, string> = {
  critical: '严重',
  warning: '警告',
  info: '信息'
}

const confidenceLabels: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低'
}

const statusLabels: Record<string, string> = {
  completed: '已完成',
  pending: '待处理',
  failed: '失败'
}

const evidence = computed(() => {
  if (!selectedResult.value?.evidence) return {}
  return selectedResult.value.evidence
})

const loadResults = async () => {
  loading.value = true
  try {
    if (!selectedSiteId.value) {
      console.warn('No site selected')
      return
    }
    const params: any = {
      site_id: selectedSiteId.value,
      severity: severityFilter.value || undefined,
      status: statusFilter.value || undefined
    }
    // 如果有日期参数，则添加到请求中
    if (startDate.value) {
      params.start_date = startDate.value
    }
    if (endDate.value) {
      params.end_date = endDate.value
    }
    const data = await getAnalysisResults(params)
    results.value = data.results || []
  } catch (error) {
    console.error('Failed to load results:', error)
  } finally {
    loading.value = false
  }
}

const loadSites = async () => {
  try {
    const data = await getSites()
    sites.value = data.sites || []
    if (sites.value.length === 0) return

    if (querySiteId.value && sites.value.some((site: any) => site.id === querySiteId.value)) {
      selectedSiteId.value = querySiteId.value
      return
    }

    if (!selectedSiteId.value) {
      const firstEnabled = sites.value.find((site: any) => site.automation_enabled)
      selectedSiteId.value = (firstEnabled || sites.value[0]).id
    }
  } catch (error) {
    console.error('Failed to load sites:', error)
  }
}

const handleSiteChange = (siteId: number) => {
  selectedSiteId.value = siteId
  loadResults()
}

const refreshResults = () => {
  loadResults()
}

const showDetail = (result: any) => {
  selectedResult.value = result
}

const closeDetail = () => {
  selectedResult.value = null
}

const goBack = () => {
  router.push('/automation/dashboard')
}

const getSeverityLabel = (severity: string) => {
  return severityLabels[severity] || severity
}

const getConfidenceLabel = (confidence: string) => {
  return confidenceLabels[confidence] || confidence
}

const getStatusLabel = (status: string) => {
  return statusLabels[status] || status
}

const formatTime = (time: string) => {
  if (!time) return 'N/A'
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

// 监听selectedSiteId变化，自动加载结果
watch(selectedSiteId, (newSiteId) => {
  if (newSiteId) {
    loadResults()
  }
})

onMounted(async () => {
  if (route.query.site_id) {
    querySiteId.value = Number(route.query.site_id)
  }
  // 从路由参数中读取日期
  if (route.query.start_date) {
    startDate.value = route.query.start_date as string
  }
  if (route.query.end_date) {
    endDate.value = route.query.end_date as string
  }
  // 先加载基地列表
  await loadSites()
  // 基地加载完成后，selectedSiteId会被设置，watch会自动触发loadResults
})
</script>

<style scoped>
.analysis-results {
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

.filter-section {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-item label {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.filter-select {
  padding: 8px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  color: #1a1a2e;
  background: white;
  cursor: pointer;
  transition: all 0.3s;
}

.filter-select:hover {
  border-color: #4a9eff;
}

.loading, .no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
}

.result-card.clickable {
  cursor: pointer;
}

.result-card.clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.result-card.critical {
  border-left: 4px solid #ef4444;
}

.result-card.warning {
  border-left: 4px solid #f59e0b;
}

.result-card.info {
  border-left: 4px solid #3b82f6;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.result-id {
  font-size: 14px;
  color: #999;
}

.result-severity {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.result-severity.critical {
  background: #fee2e2;
  color: #dc2626;
}

.result-severity.warning {
  background: #fef3c7;
  color: #d97706;
}

.result-severity.info {
  background: #dbeafe;
  color: #2563eb;
}

.result-body {
  margin-top: 12px;
}

.result-type {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 8px;
}

.result-summary {
  font-size: 16px;
  font-weight: 500;
  color: #1a1a2e;
  margin-bottom: 8px;
  line-height: 1.5;
}

.result-details {
  font-size: 14px;
  color: #4b5563;
  margin-bottom: 12px;
  line-height: 1.5;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}

.result-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #999;
  flex-wrap: wrap;
}

/* 弹窗样式 */
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
  padding: 24px;
}

.modal-content {
  background: white;
  border-radius: 16px;
  max-width: 900px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  color: #666;
  cursor: pointer;
  transition: all 0.3s;
}

.close-btn:hover {
  background: #e2e8f0;
  color: #1a1a2e;
}

.modal-body {
  padding: 24px;
}

.detail-section {
  margin-bottom: 32px;
}

.detail-section h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 16px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.info-item span {
  font-size: 14px;
  color: #1a1a2e;
  font-weight: 500;
}

.info-item span.critical {
  color: #dc2626;
}

.info-item span.warning {
  color: #d97706;
}

.info-item span.info {
  color: #2563eb;
}

.summary-text {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  margin-bottom: 12px;
}

.recommendation-box {
  padding: 16px;
  background: #f0f9ff;
  border-left: 4px solid #3b82f6;
  border-radius: 8px;
}

.recommendation-box strong {
  display: block;
  margin-bottom: 8px;
  color: #1e40af;
}

.recommendation-box p {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  margin: 0;
}

/* 研判步骤 */
.steps-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-item {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
}

.step-number {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4a9eff 0%, #667eea 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
}

.step-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 4px;
}

.step-description {
  font-size: 14px;
  color: #666;
  margin-bottom: 12px;
}

.step-details {
  padding: 12px;
  background: white;
  border-radius: 8px;
}

.evidence-item {
  font-size: 13px;
  color: #4b5563;
  margin-bottom: 8px;
  line-height: 1.5;
}

.evidence-item:last-child {
  margin-bottom: 0;
}

.evidence-item strong {
  color: #1a1a2e;
}

/* 证据链 */
.evidence-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

.evidence-card {
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  overflow: hidden;
}

.evidence-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}

.evidence-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0;
}

.evidence-body {
  padding: 16px;
}

.evidence-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
}

.evidence-row:last-child {
  margin-bottom: 0;
}

.evidence-label {
  color: #666;
  font-weight: 500;
}

.evidence-row span {
  color: #1a1a2e;
  font-weight: 500;
}

.evidence-row span.increasing,
.evidence-row span.high,
.evidence-row span.unstable {
  color: #dc2626;
}

.evidence-row span.stable,
.evidence-row span.low {
  color: #16a34a;
}

/* JSON查看器 */
.json-viewer {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
}

.json-viewer pre {
  font-size: 12px;
  color: #a5b4fc;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* 动画 */
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
