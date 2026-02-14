<template>
  <div class="abnormal-types-page">
    <!-- 页面标题和操作栏 -->
    <div class="page-header">
      <div class="header-left">
        <h1>异常类型管理</h1>
        <p class="subtitle">管理异常类型的配置、阈值和状态</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-primary" @click="showCreateDialog = true">
          <Plus :size="18" />
          创建异常类型
        </button>
        <button class="btn btn-secondary" @click="showBatchUpdateDialog = true">
          <Settings :size="18" />
          批量更新阈值
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card">
        <div class="stat-icon total">
          <List :size="24" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon draft">
          <FileText :size="24" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.by_status.draft }}</div>
          <div class="stat-label">草稿</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon observed">
          <Eye :size="24" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.by_status.observed }}</div>
          <div class="stat-label">观察中</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon enabled">
          <CheckCircle :size="24" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.by_status.enabled }}</div>
          <div class="stat-label">已启用</div>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-group">
        <label>状态：</label>
        <select v-model="filterStatus" @change="loadAbnormalTypes">
          <option value="">全部</option>
          <option value="DRAFT">草稿</option>
          <option value="OBSERVED">观察中</option>
          <option value="ENABLED">已启用</option>
        </select>
      </div>
      <div class="filter-group">
        <label>风险等级：</label>
        <select v-model="filterRiskLevel" @change="loadAbnormalTypes">
          <option value="">全部</option>
          <option value="low">低</option>
          <option value="medium">中</option>
          <option value="high">高</option>
        </select>
      </div>
    </div>

    <!-- 异常类型列表 -->
    <div class="abnormal-types-list">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="abnormalTypes.length === 0" class="empty">暂无异常类型</div>
      <div v-else class="type-cards">
        <div
          v-for="type in abnormalTypes"
          :key="type.id"
          class="type-card"
          :class="[
            `status-${type.status.toLowerCase()}`,
            `risk-${type.risk_level}`
          ]"
          @click="viewDetail(type)"
        >
          <div class="card-header">
            <div class="type-info">
              <h3>{{ type.type_name }}</h3>
              <span class="type-code">{{ type.type_code }}</span>
            </div>
            <div class="status-badge" :class="type.status.toLowerCase()">
              {{ getStatusLabel(type.status) }}
            </div>
          </div>
          <p class="description">{{ type.description }}</p>
          <div class="card-stats">
            <div class="stat">
              <span class="label">出现次数：</span>
              <span class="value">{{ type.occurrence_count }}</span>
            </div>
            <div class="stat">
              <span class="label">风险等级：</span>
              <span class="value risk-badge" :class="type.risk_level">
                {{ getRiskLabel(type.risk_level) }}
              </span>
            </div>
          </div>
          <div class="card-actions">
            <button class="btn-sm btn-secondary" @click.stop="editType(type)">
              <Edit :size="14" />
              编辑
            </button>
            <button
              v-if="type.status === 'DRAFT'"
              class="btn-sm btn-danger"
              @click.stop="deleteType(type)"
            >
              <Trash2 :size="14" />
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建/编辑对话框 -->
    <div v-if="showCreateDialog || showEditDialog" class="modal-overlay" @click="closeDialog">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h2>{{ showCreateDialog ? '创建异常类型' : '编辑异常类型' }}</h2>
          <button class="btn-close" @click="closeDialog">
            <X :size="20" />
          </button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="saveType">
            <div class="form-group">
              <label>类型代码 *</label>
              <input
                v-model="formData.type_code"
                type="text"
                placeholder="例如：LINK_QUALITY_DEGRADE"
                :disabled="showEditDialog"
                required
              />
            </div>
            <div class="form-group">
              <label>类型名称 *</label>
              <input
                v-model="formData.type_name"
                type="text"
                placeholder="例如：链路质量下降"
                required
              />
            </div>
            <div class="form-group">
              <label>描述</label>
              <textarea
                v-model="formData.description"
                placeholder="描述异常类型..."
                rows="3"
              ></textarea>
            </div>
            <div class="form-group">
              <label>关键词</label>
              <input
                v-model="keywordsInput"
                type="text"
                placeholder="用逗号分隔，例如：CRC,error,quality"
              />
            </div>
            <div class="form-group">
              <label>风险等级 *</label>
              <select v-model="formData.risk_level" required>
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
              </select>
            </div>
            <div class="form-group">
              <label>阈值配置 *</label>
              <textarea
                v-model="thresholdConfigInput"
                placeholder='例如：{"crc_error_count": 50}'
                rows="4"
              ></textarea>
            </div>
            <div class="form-group">
              <label>启用异常跟踪</label>
              <input
                v-model="formData.enable_tracking"
                type="checkbox"
              />
            </div>
            <div class="form-group" v-if="formData.enable_tracking">
              <label>跟踪配置</label>
              <textarea
                v-model="trackingConfigInput"
                placeholder='例如：{"accumulation_threshold": 5, "dedup_window_minutes": 60, "cooldown_minutes": 60}'
                rows="4"
              ></textarea>
            </div>
            <div class="form-actions">
              <button type="button" class="btn btn-secondary" @click="closeDialog">
                取消
              </button>
              <button type="submit" class="btn btn-primary">
                保存
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 批量更新阈值对话框 -->
    <div v-if="showBatchUpdateDialog" class="modal-overlay" @click="showBatchUpdateDialog = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h2>批量更新阈值</h2>
          <button class="btn-close" @click="showBatchUpdateDialog = false">
            <X :size="20" />
          </button>
        </div>
        <div class="modal-body">
          <div class="batch-update-list">
            <div
              v-for="type in abnormalTypes"
              :key="type.id"
              class="batch-update-item"
            >
              <div class="type-info">
                <strong>{{ type.type_name }}</strong>
                <span class="type-code">{{ type.type_code }}</span>
              </div>
              <div class="threshold-config">
                <label>阈值配置：</label>
                <textarea
                  v-model="batchUpdates[type.type_code]"
                  :placeholder='JSON.stringify(type.threshold_config, null, 2)'
                  rows="3"
                ></textarea>
              </div>
            </div>
          </div>
          <div class="form-actions">
            <button class="btn btn-secondary" @click="showBatchUpdateDialog = false">
              取消
            </button>
            <button class="btn btn-primary" @click="batchUpdateThresholds">
              批量更新
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 详情对话框 -->
    <div v-if="showDetailDialog" class="modal-overlay" @click="showDetailDialog = false">
      <div class="modal modal-large" @click.stop>
        <div class="modal-header">
          <h2>异常类型详情</h2>
          <button class="btn-close" @click="showDetailDialog = false">
            <X :size="20" />
          </button>
        </div>
        <div class="modal-body" v-if="selectedType">
          <div class="detail-section">
            <h3>基本信息</h3>
            <div class="detail-grid">
              <div class="detail-item">
                <label>类型代码：</label>
                <span>{{ selectedType.type_code }}</span>
              </div>
              <div class="detail-item">
                <label>类型名称：</label>
                <span>{{ selectedType.type_name }}</span>
              </div>
              <div class="detail-item">
                <label>状态：</label>
                <span class="status-badge" :class="selectedType.status.toLowerCase()">
                  {{ getStatusLabel(selectedType.status) }}
                </span>
              </div>
              <div class="detail-item">
                <label>风险等级：</label>
                <span class="risk-badge" :class="selectedType.risk_level">
                  {{ getRiskLabel(selectedType.risk_level) }}
                </span>
              </div>
            </div>
          </div>
          <div class="detail-section">
            <h3>描述</h3>
            <p>{{ selectedType.description }}</p>
          </div>
          <div class="detail-section">
            <h3>关键词</h3>
            <div class="keywords-list">
              <span v-for="keyword in selectedType.keywords" :key="keyword" class="keyword-tag">
                {{ keyword }}
              </span>
            </div>
          </div>
          <div class="detail-section">
            <h3>阈值配置</h3>
            <pre>{{ JSON.stringify(selectedType.threshold_config, null, 2) }}</pre>
          </div>
          <div class="detail-section" v-if="selectedType.tracking_config">
            <h3>跟踪配置</h3>
            <pre>{{ JSON.stringify(selectedType.tracking_config, null, 2) }}</pre>
          </div>
          <div class="detail-section">
            <h3>统计信息</h3>
            <div class="detail-grid">
              <div class="detail-item">
                <label>出现次数：</label>
                <span>{{ selectedType.occurrence_count }}</span>
              </div>
              <div class="detail-item">
                <label>最后出现：</label>
                <span>{{ selectedType.last_occurred_at || '从未' }}</span>
              </div>
            </div>
          </div>
          <div class="form-actions">
            <button class="btn btn-secondary" @click="showDetailDialog = false">
              关闭
            </button>
            <button class="btn btn-primary" @click="editType(selectedType)">
              编辑
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Plus, Settings, List, FileText, Eye, CheckCircle, Edit, Trash2, X } from 'lucide-vue-next'
import { abnormalTypesApi, type AbnormalType, type AbnormalTypeStats } from '@/api/abnormal_types'

const abnormalTypes = ref<AbnormalType[]>([])
const stats = ref<AbnormalTypeStats>({
  total: 0,
  by_status: { draft: 0, observed: 0, enabled: 0 },
  top_occurrences: []
})
const loading = ref(false)
const filterStatus = ref('')
const filterRiskLevel = ref('')

// 对话框状态
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showDetailDialog = ref(false)
const showBatchUpdateDialog = ref(false)
const selectedType = ref<AbnormalType | null>(null)

// 表单数据
const formData = ref<Partial<AbnormalType>>({
  type_code: '',
  type_name: '',
  description: '',
  keywords: [],
  threshold_config: {},
  risk_level: 'medium',
  enable_tracking: true,
  tracking_config: {}
})

const keywordsInput = computed({
  get: () => formData.value.keywords?.join(', ') || '',
  set: (value: string) => {
    formData.value.keywords = value.split(',').map(k => k.trim()).filter(k => k)
  }
})

const thresholdConfigInput = computed({
  get: () => JSON.stringify(formData.value.threshold_config || {}, null, 2),
  set: (value: string) => {
    try {
      formData.value.threshold_config = JSON.parse(value)
    } catch (e) {
      console.error('Invalid JSON:', e)
    }
  }
})

const trackingConfigInput = computed({
  get: () => JSON.stringify(formData.value.tracking_config || {}, null, 2),
  set: (value: string) => {
    try {
      formData.value.tracking_config = JSON.parse(value)
    } catch (e) {
      console.error('Invalid JSON:', e)
    }
  }
})

const batchUpdates = ref<Record<string, string>>({})

// 加载异常类型列表
const loadAbnormalTypes = async () => {
  loading.value = true
  try {
    const params: any = {}
    if (filterStatus.value) params.status = filterStatus.value
    
    const data = await abnormalTypesApi.getAbnormalTypes(params)
    abnormalTypes.value = data.types
    
    // 初始化批量更新数据
    batchUpdates.value = {}
    data.types.forEach(type => {
      batchUpdates.value[type.type_code] = JSON.stringify(type.threshold_config, null, 2)
    })
  } catch (error) {
    console.error('Failed to load abnormal types:', error)
  } finally {
    loading.value = false
  }
}

// 加载统计信息
const loadStats = async () => {
  try {
    stats.value = await abnormalTypesApi.getAbnormalTypesStats()
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

// 查看详情
const viewDetail = (type: AbnormalType) => {
  selectedType.value = type
  showDetailDialog.value = true
}

// 编辑类型
const editType = (type: AbnormalType) => {
  selectedType.value = type
  formData.value = { ...type }
  showEditDialog.value = true
  showDetailDialog.value = false
}

// 删除类型
const deleteType = async (type: AbnormalType) => {
  if (!confirm(`确定要删除异常类型 "${type.type_name}" 吗？`)) return
  
  try {
    await abnormalTypesApi.deleteAbnormalType(type.id)
    await loadAbnormalTypes()
    await loadStats()
  } catch (error) {
    console.error('Failed to delete abnormal type:', error)
    alert('删除失败')
  }
}

// 保存类型
const saveType = async () => {
  try {
    if (showCreateDialog.value) {
      await abnormalTypesApi.createAbnormalType(formData.value)
    } else if (showEditDialog.value && selectedType.value) {
      await abnormalTypesApi.updateAbnormalType(selectedType.value.id, formData.value)
    }
    
    closeDialog()
    await loadAbnormalTypes()
    await loadStats()
  } catch (error) {
    console.error('Failed to save abnormal type:', error)
    alert('保存失败')
  }
}

// 批量更新阈值
const batchUpdateThresholds = async () => {
  try {
    const updates = Object.entries(batchUpdates.value)
      .filter(([_, config]) => config.trim())
      .map(([typeCode, config]) => ({
        type_code: typeCode,
        threshold_config: JSON.parse(config)
      }))
    
    await abnormalTypesApi.batchUpdateThresholds(updates)
    showBatchUpdateDialog.value = false
    await loadAbnormalTypes()
    alert('批量更新成功')
  } catch (error) {
    console.error('Failed to batch update thresholds:', error)
    alert('批量更新失败')
  }
}

// 关闭对话框
const closeDialog = () => {
  showCreateDialog.value = false
  showEditDialog.value = false
  selectedType.value = null
  formData.value = {
    type_code: '',
    type_name: '',
    description: '',
    keywords: [],
    threshold_config: {},
    risk_level: 'medium',
    enable_tracking: true,
    tracking_config: {}
  }
}

// 获取状态标签
const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    'DRAFT': '草稿',
    'OBSERVED': '观察中',
    'ENABLED': '已启用'
  }
  return labels[status] || status
}

// 获取风险等级标签
const getRiskLabel = (riskLevel: string) => {
  const labels: Record<string, string> = {
    'low': '低',
    'medium': '中',
    'high': '高'
  }
  return labels[riskLevel] || riskLevel
}

onMounted(() => {
  loadAbnormalTypes()
  loadStats()
})
</script>

<style scoped>
.abnormal-types-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-left h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.subtitle {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover {
  background: #2563eb;
}

.btn-secondary {
  background: #6b7280;
  color: white;
}

.btn-secondary:hover {
  background: #4b5563;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.total {
  background: #e0f2fe;
  color: #0284c7;
}

.stat-icon.draft {
  background: #fef3c7;
  color: #d97706;
}

.stat-icon.observed {
  background: #dbeafe;
  color: #2563eb;
}

.stat-icon.enabled {
  background: #d1fae5;
  color: #059669;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.stat-label {
  font-size: 14px;
  color: #6b7280;
}

.filter-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-group label {
  font-size: 14px;
  color: #374151;
}

.filter-group select {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.abnormal-types-list {
  min-height: 400px;
}

.loading,
.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #6b7280;
  font-size: 16px;
}

.type-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.type-card {
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.2s;
  border-left: 4px solid #d1d5db;
}

.type-card:hover {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.type-card.status-draft {
  border-left-color: #f59e0b;
}

.type-card.status-observed {
  border-left-color: #3b82f6;
}

.type-card.status-enabled {
  border-left-color: #10b981;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.type-info h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.type-code {
  font-size: 12px;
  color: #6b7280;
  font-family: monospace;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.draft {
  background: #fef3c7;
  color: #d97706;
}

.status-badge.observed {
  background: #dbeafe;
  color: #2563eb;
}

.status-badge.enabled {
  background: #d1fae5;
  color: #059669;
}

.description {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #6b7280;
  line-height: 1.5;
}

.card-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  padding: 8px 0;
  border-top: 1px solid #e5e7eb;
  border-bottom: 1px solid #e5e7eb;
}

.stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.stat .label {
  color: #6b7280;
}

.stat .value {
  font-weight: 500;
  color: #1f2937;
}

.risk-badge {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}

.risk-badge.low {
  background: #d1fae5;
  color: #059669;
}

.risk-badge.medium {
  background: #fef3c7;
  color: #d97706;
}

.risk-badge.high {
  background: #fee2e2;
  color: #dc2626;
}

.card-actions {
  display: flex;
  gap: 8px;
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
}

.modal {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-large {
  max-width: 800px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: #6b7280;
}

.btn-close:hover {
  color: #1f2937;
}

.modal-body {
  padding: 24px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-group input[type="checkbox"] {
  width: auto;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.batch-update-list {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 16px;
}

.batch-update-item {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  margin-bottom: 12px;
}

.batch-update-item .type-info {
  margin-bottom: 8px;
}

.batch-update-item .type-code {
  margin-left: 8px;
  font-size: 12px;
  color: #6b7280;
  font-family: monospace;
}

.batch-update-item textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-family: monospace;
  font-size: 12px;
  resize: vertical;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.detail-item label {
  font-weight: 500;
  color: #6b7280;
}

.detail-item span {
  color: #1f2937;
}

.keywords-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.keyword-tag {
  padding: 4px 12px;
  background: #e5e7eb;
  border-radius: 16px;
  font-size: 12px;
  color: #374151;
}

.detail-section pre {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  font-size: 12px;
}
</style>
