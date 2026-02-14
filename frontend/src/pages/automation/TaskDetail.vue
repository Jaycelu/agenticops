<template>
  <div class="task-detail">
    <div class="page-header">
      <button @click="goBack" class="back-btn">
        <ArrowLeft :size="16" />
        返回
      </button>
      <h1>任务详情 #{{ taskId }}</h1>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="task" class="task-content">
      <!-- 基本信息 -->
      <div class="section">
        <h2>基本信息</h2>
        <div class="info-grid">
          <div class="info-item">
            <label>状态</label>
            <span class="task-status" :class="task.status">
              {{ statusLabels[task.status] || task.status }}
            </span>
          </div>
          <div class="info-item">
            <label>触发方式</label>
            <span>{{ task.triggered_by }}</span>
          </div>
          <div class="info-item">
            <label>设备IP</label>
            <span>{{ task.device_ip || '未知' }}</span>
          </div>
          <div class="info-item">
            <label>设备ID</label>
            <span>{{ task.netbox_device_id || '未知' }}</span>
          </div>
          <div class="info-item">
            <label>创建时间</label>
            <span>{{ formatTime(task.created_at) }}</span>
          </div>
          <div class="info-item">
            <label>开始时间</label>
            <span>{{ task.started_at ? formatTime(task.started_at) : '-' }}</span>
          </div>
          <div class="info-item">
            <label>完成时间</label>
            <span>{{ task.finished_at ? formatTime(task.finished_at) : '-' }}</span>
          </div>
        </div>
      </div>

      <!-- 决策结果 -->
      <div v-if="task.decision_result" class="section">
        <h2>决策结果</h2>
        <div class="decision-result">
          <div class="result-item">
            <label>规则名称</label>
            <span>{{ task.decision_result.rule_name || '无' }}</span>
          </div>
          <div v-if="task.decision_result.diagnosis" class="diagnosis-content">
            <div class="result-item">
              <label>问题类型</label>
              <span>{{ getDiagnosisTypeLabel(task.decision_result.diagnosis.diagnosis_type) }}</span>
            </div>
            <div class="result-item">
              <label>置信度</label>
              <span>{{ formatConfidence(task.decision_result.diagnosis.confidence) }}</span>
            </div>
            <div class="result-item">
              <label>严重程度</label>
              <span class="severity-badge" :class="task.decision_result.diagnosis.severity">
                {{ getSeverityLabel(task.decision_result.diagnosis.severity) }}
              </span>
            </div>
            <div class="result-item">
              <label>风险等级</label>
              <span>{{ getRiskLevelLabel(task.decision_result.diagnosis.risk_level) }}</span>
            </div>
            <div class="result-item full">
              <label>摘要</label>
              <p>{{ task.decision_result.diagnosis.summary }}</p>
            </div>
            <div class="result-item full">
              <label>建议</label>
              <ul>
                <li v-for="(rec, index) in task.decision_result.diagnosis.recommendations" :key="index">
                  {{ rec }}
                </li>
              </ul>
            </div>
            <div v-if="task.decision_result.diagnosis.evidence && task.decision_result.diagnosis.evidence.length > 0" class="result-item full">
              <label>证据</label>
              <div class="evidence-list">
                <div v-for="(ev, index) in task.decision_result.diagnosis.evidence" :key="index" class="evidence-item">
                  <span class="evidence-type">{{ ev.type }}:</span>
                  <span class="evidence-value">{{ ev.value }}</span>
                  <span class="evidence-desc">{{ ev.description }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 执行结果 -->
      <div v-if="task.execution_result" class="section">
        <h2>执行结果</h2>
        <pre class="execution-result">{{ JSON.stringify(task.execution_result, null, 2) }}</pre>
      </div>

      <!-- 人工反馈 -->
      <div class="section">
        <h2>人工反馈闭环</h2>
        <div class="feedback-form">
          <div class="result-item">
            <label>判定结果</label>
            <select v-model="feedbackVerdict" class="feedback-select">
              <option value="correct">正确</option>
              <option value="partial">部分正确</option>
              <option value="incorrect">误判</option>
            </select>
          </div>
          <div class="result-item">
            <label>反馈说明</label>
            <textarea v-model="feedbackComment" class="feedback-textarea" rows="3" placeholder="补充你对本次研判的评价与修正建议"></textarea>
          </div>
          <button class="submit-feedback-btn" @click="handleSubmitFeedback" :disabled="submittingFeedback">
            {{ submittingFeedback ? '提交中...' : '提交反馈' }}
          </button>
        </div>

        <div v-if="task.feedbacks && task.feedbacks.length > 0" class="feedback-list">
          <h3>历史反馈</h3>
          <div v-for="item in task.feedbacks" :key="item.id" class="feedback-item">
            <span class="feedback-verdict" :class="item.verdict">{{ getVerdictLabel(item.verdict) }}</span>
            <span class="feedback-time">{{ formatTime(item.created_at) }}</span>
            <p class="feedback-comment">{{ item.comment || '无说明' }}</p>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="no-data">任务不存在</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import { getAutomationTask, submitTaskFeedback } from '@/api/automation'

const route = useRoute()
const router = useRouter()
const taskId = ref(route.params.id)
const task = ref<any>(null)
const loading = ref(false)
const feedbackVerdict = ref<'correct' | 'incorrect' | 'partial'>('correct')
const feedbackComment = ref('')
const submittingFeedback = ref(false)

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

const severityLabels: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '严重'
}

const riskLevelLabels: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '严重风险'
}

const loadTask = async () => {
  loading.value = true
  try {
    const data = await getAutomationTask(Number(taskId.value))
    task.value = data
  } catch (error) {
    console.error('Failed to load task:', error)
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/automation/tasks')
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

const getDiagnosisTypeLabel = (type: string) => {
  return diagnosisTypeLabels[type] || type
}

const getSeverityLabel = (severity: string) => {
  return severityLabels[severity] || severity
}

const getRiskLevelLabel = (riskLevel: string) => {
  return riskLevelLabels[riskLevel] || riskLevel
}

const formatConfidence = (confidence: number) => {
  if (typeof confidence === 'number') {
    return `${(confidence * 100).toFixed(0)}%`
  }
  return confidence
}

const getVerdictLabel = (verdict: string) => {
  const map: Record<string, string> = {
    correct: '正确',
    incorrect: '误判',
    partial: '部分正确'
  }
  return map[verdict] || verdict
}

const handleSubmitFeedback = async () => {
  if (!task.value) return
  submittingFeedback.value = true
  try {
    await submitTaskFeedback(Number(taskId.value), {
      verdict: feedbackVerdict.value,
      comment: feedbackComment.value || undefined
    })
    feedbackComment.value = ''
    await loadTask()
  } catch (error) {
    console.error('Failed to submit feedback:', error)
  } finally {
    submittingFeedback.value = false
  }
}

onMounted(() => {
  loadTask()
})
</script>

<style scoped>
.task-detail {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.back-btn {
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

.back-btn:hover {
  background: #f8f9fa;
  border-color: #4a9eff;
  color: #4a9eff;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

.loading, .no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
}

.task-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.section h2 {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 20px 0;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item label {
  font-size: 12px;
  color: #999;
  font-weight: 500;
}

.info-item span {
  font-size: 14px;
  color: #1a1a2e;
}

.task-status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  display: inline-block;
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

.decision-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.diagnosis-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-item.full {
  grid-column: 1 / -1;
}

.result-item label {
  font-size: 12px;
  color: #999;
  font-weight: 500;
}

.result-item span {
  font-size: 14px;
  color: #1a1a2e;
}

.result-item p {
  font-size: 14px;
  color: #1a1a2e;
  margin: 0;
  line-height: 1.6;
}

.feedback-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feedback-select,
.feedback-textarea {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
}

.submit-feedback-btn {
  width: fit-content;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: #4a9eff;
  color: #fff;
  cursor: pointer;
}

.submit-feedback-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.feedback-list {
  margin-top: 20px;
}

.feedback-item {
  border: 1px solid #eef1f5;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
}

.feedback-verdict {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  margin-right: 8px;
}

.feedback-verdict.correct {
  background: #e8f5e9;
  color: #2e7d32;
}

.feedback-verdict.partial {
  background: #fff8e1;
  color: #ef6c00;
}

.feedback-verdict.incorrect {
  background: #ffebee;
  color: #c62828;
}

.feedback-time {
  color: #999;
  font-size: 12px;
}

.feedback-comment {
  margin: 8px 0 0 0;
}

.result-item ul {
  margin: 0;
  padding-left: 20px;
}

.result-item li {
  font-size: 14px;
  color: #1a1a2e;
  line-height: 1.6;
  margin-bottom: 8px;
}

.severity-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.severity-badge.low {
  background: #e8f5e9;
  color: #4caf50;
}

.severity-badge.medium {
  background: #fff3e0;
  color: #ff9800;
}

.severity-badge.high {
  background: #ffebee;
  color: #f44336;
}

.severity-badge.critical {
  background: #ffcdd2;
  color: #d32f2f;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
}

.evidence-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: white;
  border-radius: 4px;
}

.evidence-type {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.evidence-value {
  font-size: 14px;
  color: #1a1a2e;
  font-weight: 600;
}

.evidence-desc {
  font-size: 13px;
  color: #999;
}

.execution-result {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  font-size: 12px;
  color: #1a1a2e;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
