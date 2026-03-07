<template>
  <div class="page">
    <div class="page-content">
      <div class="page-header">
        <div class="page-title">
          <Radio :size="28" class="title-icon" />
          <h1>事件中心</h1>
          <span class="mode-badge" :class="{ observe: mode === 'observe_only' }">
            {{ mode === 'observe_only' ? '观测模式' : '正常模式' }}
          </span>
        </div>
        <button @click="refreshData" class="btn-refresh" :disabled="loading">
          <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon stat-icon-info">
            <Radio :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ events.length }}</div>
            <div class="stat-label">当前页事件</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon stat-icon-warning">
            <AlertTriangle :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ openCount }}</div>
            <div class="stat-label">未关闭</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon stat-icon-success">
            <CheckCircle2 :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ resolvedCount }}</div>
            <div class="stat-label">已关闭</div>
          </div>
        </div>
      </div>

      <div class="filter-section">
        <div class="filter-group">
          <select v-model="filters.status" class="filter-input" @change="loadEvents">
            <option value="">全部状态</option>
            <option value="open">open</option>
            <option value="acknowledged">acknowledged</option>
            <option value="resolved">resolved</option>
          </select>
          <select v-model="filters.source" class="filter-input" @change="loadEvents">
            <option value="">全部来源</option>
            <option value="SPLUNK">SPLUNK</option>
            <option value="EDA">EDA</option>
            <option value="AUTOMATION">AUTOMATION</option>
          </select>
        </div>
      </div>

      <div class="events-section">
        <div v-if="loading" class="loading">
          <Loader2 class="animate-spin" :size="40" />
          <p>加载中...</p>
        </div>
        <div v-else-if="events.length === 0" class="empty">
          <AlertCircle :size="48" />
          <p>暂无事件数据</p>
        </div>
        <div v-else class="events-list">
          <div v-for="item in events" :key="item.id" class="alert-item" @click="openDetail(item)">
            <div class="alert-header">
              <div class="alert-severity">
                <AlertTriangle :size="14" />
                {{ item.severity }}
              </div>
              <div class="alert-status" :class="{ acknowledged: item.acknowledged }">
                {{ item.status }}
              </div>
              <div class="alert-time">
                <Clock :size="14" />
                {{ formatTime(item.occurred_at) }}
              </div>
            </div>
          <div class="alert-body">
              <div class="alert-host">
                <Server :size="16" />
                {{ item.host || 'unknown-host' }}
              </div>
              <div class="alert-name">{{ item.name }}</div>
              <div class="event-meta">
                <span>来源: {{ item.source }}</span>
                <span>事件ID: {{ item.external_event_id || '-' }}</span>
                <span v-if="getEventCase(item).caseCode">Case: {{ getEventCase(item).caseCode }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-if="selectedEvent" class="modal-overlay" @click="closeDetail">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>事件详情</h3>
        <button class="btn-close" @click="closeDetail">关闭</button>
      </div>
      <div class="modal-body">
        <div class="detail-row"><span>名称</span><strong>{{ selectedEvent.name }}</strong></div>
        <div class="detail-row"><span>来源</span><strong>{{ selectedEvent.source }}</strong></div>
        <div class="detail-row"><span>主机</span><strong>{{ selectedEvent.host || '-' }}</strong></div>
        <div class="detail-row"><span>级别</span><strong>{{ selectedEvent.severity }}</strong></div>
        <div class="detail-row"><span>状态</span><strong>{{ selectedEvent.status }}</strong></div>
        <div class="detail-row"><span>关联Case</span><strong>{{ selectedEventCase.caseCode || relations.linked_case?.case_code || '-' }}</strong></div>
        <div class="detail-row"><span>推荐Skill</span><strong>{{ recommendedSkillCode || '-' }}</strong></div>
        <div class="detail-row"><span>发生时间</span><strong>{{ formatTime(selectedEvent.occurred_at) }}</strong></div>
        <div class="detail-actions">
          <button
            v-if="selectedEventCase.caseId || relations.linked_case?.case_id"
            class="btn-action primary"
            @click="openCaseDetail(selectedEventCase.caseId || relations.linked_case?.case_id)"
          >
            打开 Case
          </button>
          <button class="btn-action primary" :disabled="actionLoading" @click="dispatchReadonlySelected">
            {{ actionLoading ? '处理中...' : '触发只读研判' }}
          </button>
          <button class="btn-action" :disabled="playbookLoading" @click="generatePlaybookDraftSelected">
            {{ playbookLoading ? '生成中...' : '生成Playbook草稿' }}
          </button>
          <button class="btn-action" :disabled="ticketLoading" @click="createTicketSelected">
            {{ ticketLoading ? '处理中...' : '创建工单' }}
          </button>
          <button class="btn-action" @click="loadRelations">刷新关联</button>
        </div>
        <div class="playbook-panel">
          <h4>Playbook Check</h4>
          <div v-if="playbookDraft.check && Object.keys(playbookDraft.check).length > 0" class="playbook-check">
            <span class="check-badge" :class="{ passed: !!playbookDraft.check.passed, failed: !playbookDraft.check.passed }">
              {{ playbookDraft.check.passed ? 'PASSED' : 'FAILED' }}
            </span>
            <span v-if="(playbookDraft.check.warnings || []).length > 0" class="check-note">
              warnings: {{ (playbookDraft.check.warnings || []).length }}
            </span>
            <span v-if="(playbookDraft.check.errors || []).length > 0" class="check-note error">
              errors: {{ (playbookDraft.check.errors || []).length }}
            </span>
          </div>
          <div v-else class="relation-item muted">暂无草稿校验结果</div>
          <pre v-if="playbookDraft.playbook_yaml" class="playbook-yaml">{{ playbookDraft.playbook_yaml }}</pre>
        </div>
        <div class="relation-panel">
          <h4>关联 Case</h4>
          <div v-if="relations.linked_case?.case_id" class="relation-item">
            <div class="relation-task-main">
              <span>Case: {{ relations.linked_case.case_code }}</span>
              <button class="btn-link-task" @click="openCaseDetail(relations.linked_case.case_id)">查看 Case</button>
            </div>
          </div>
          <div v-else class="relation-item muted">暂无 Case 关联</div>
          <h4>关联工单</h4>
          <div class="relation-item" v-if="relations.ticket && relations.ticket.ticket_id">
            工单号: {{ relations.ticket.ticket_id }} / 状态: {{ relations.ticket.status || '-' }}
          </div>
          <div class="relation-item muted" v-else>暂无工单关联</div>
          <h4>关联任务</h4>
          <div v-if="relations.linked_tasks.length === 0" class="relation-item muted">暂无任务关联</div>
          <div v-for="task in relations.linked_tasks" :key="task.task_id" class="relation-item">
            <div class="relation-task-main">
              <span>任务ID: {{ task.task_id }} ({{ task.task_code }})</span>
              <span class="task-status-badge" :class="getTaskStatusClass(task.status)">{{ task.status }}</span>
            </div>
            <div class="relation-task-meta">
              <span>Skill: {{ task.recommended_skill_code || recommendedSkillCode || '-' }}</span>
              <button class="btn-link-task" @click="openTaskDetail(task.task_id)">查看任务详情</button>
            </div>
          </div>
        </div>
        <div v-if="actionMessage" class="action-message">{{ actionMessage }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { eventsApi, type EventItem } from '@/api/events'
import { AlertCircle, AlertTriangle, CheckCircle2, Clock, Loader2, Radio, RefreshCw, Server } from 'lucide-vue-next'

interface LinkedTaskRelation {
  task_id: number
  task_code: string
  status: string
  recommended_skill_code?: string
}

interface EventRelationsState {
  ticket: Record<string, unknown>
  linked_case?: {
    case_id: number
    case_code: string
    created_at?: string
  } | null
  linked_tasks: LinkedTaskRelation[]
}

const router = useRouter()
const loading = ref(false)
const mode = ref('unknown')
const events = ref<EventItem[]>([])
const selectedEvent = ref<EventItem | null>(null)
const actionLoading = ref(false)
const playbookLoading = ref(false)
const ticketLoading = ref(false)
const actionMessage = ref('')
const playbookDraft = ref<{ check: Record<string, any>; playbook_yaml: string }>({
  check: {},
  playbook_yaml: ''
})
const relations = ref<EventRelationsState>({
  ticket: {},
  linked_case: null,
  linked_tasks: []
})
const filters = ref({
  status: '',
  source: ''
})

const openCount = computed(() => events.value.filter((item) => item.status !== 'resolved').length)
const resolvedCount = computed(() => events.value.filter((item) => item.status === 'resolved').length)
const recommendedSkillCode = computed(() => {
  const payload = selectedEvent.value?.payload || {}
  return (
    selectedEvent.value?.recommended_skill_code ||
    (payload.recommended_skill_code as string | undefined) ||
    (payload?.task?.recommended_skill_code as string | undefined) ||
    (payload?.raw?.recommended_skill_code as string | undefined) ||
    ''
  )
})

const selectedEventCase = computed(() => getEventCase(selectedEvent.value))

function formatTime(value?: string): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function getEventCase(item?: EventItem | null): { caseId?: number; caseCode?: string } {
  const payloadCase = (item?.payload || {}).case || {}
  return {
    caseId: item?.case_id || payloadCase.case_id,
    caseCode: item?.case_code || payloadCase.case_code
  }
}

async function loadMode() {
  const res = await eventsApi.getMode()
  mode.value = res.message
}

async function loadEvents() {
  loading.value = true
  try {
    const res = await eventsApi.listEvents({
      status: filters.value.status || undefined,
      source: filters.value.source || undefined,
      limit: 100
    })
    events.value = res.events || []
  } finally {
    loading.value = false
  }
}

async function refreshData() {
  await Promise.all([loadMode(), loadEvents()])
}

function openDetail(item: EventItem) {
  selectedEvent.value = item
  actionMessage.value = ''
  const cachedDraft = (item.payload || {}).playbook_draft || {}
  playbookDraft.value = {
    check: (cachedDraft.check as Record<string, any>) || {},
    playbook_yaml: ''
  }
  void loadRelations()
}

function closeDetail() {
  selectedEvent.value = null
  actionMessage.value = ''
  playbookDraft.value = { check: {}, playbook_yaml: '' }
  relations.value = { ticket: {}, linked_case: null, linked_tasks: [] }
}

async function dispatchReadonlySelected() {
  if (!selectedEvent.value) return
  actionLoading.value = true
  actionMessage.value = ''
  try {
    const result = await eventsApi.dispatchReadonly(selectedEvent.value.id, 'operator')
    actionMessage.value = result.message
      + (result.case_code ? `，Case: ${result.case_code}` : result.case_id ? `，Case ID: ${result.case_id}` : '')
      + (result.task_id ? `，任务ID: ${result.task_id}` : '')
    if (result.playbook_check) {
      playbookDraft.value = {
        check: result.playbook_check,
        playbook_yaml: playbookDraft.value.playbook_yaml
      }
    }
    if (selectedEvent.value && result.case_id) {
      selectedEvent.value = {
        ...selectedEvent.value,
        case_id: result.case_id || undefined,
        case_code: result.case_code || undefined,
        payload: {
          ...(selectedEvent.value.payload || {}),
          case: {
            case_id: result.case_id,
            case_code: result.case_code
          }
        }
      }
    }
    await loadRelations()
  } catch (e: any) {
    actionMessage.value = e?.response?.data?.detail || '触发失败'
  } finally {
    actionLoading.value = false
  }
}

async function createTicketSelected() {
  if (!selectedEvent.value) return
  ticketLoading.value = true
  actionMessage.value = ''
  try {
    const result = await eventsApi.createTicket(selectedEvent.value.id, {})
    actionMessage.value = result.message + (result.ticket_id ? `，工单号: ${result.ticket_id}` : '')
    await loadEvents()
    await loadRelations()
  } catch (e: any) {
    actionMessage.value = e?.response?.data?.detail || '工单创建失败'
  } finally {
    ticketLoading.value = false
  }
}

async function generatePlaybookDraftSelected() {
  if (!selectedEvent.value) return
  playbookLoading.value = true
  actionMessage.value = ''
  try {
    const result = await eventsApi.generatePlaybookDraft(selectedEvent.value.id, true)
    playbookDraft.value = {
      check: result.playbook_check || {},
      playbook_yaml: result.playbook_yaml || ''
    }
    actionMessage.value = result.message
    await loadEvents()
  } catch (e: any) {
    actionMessage.value = e?.response?.data?.detail || '草稿生成失败'
  } finally {
    playbookLoading.value = false
  }
}

async function loadRelations() {
  if (!selectedEvent.value) return
  const data = await eventsApi.getRelations(selectedEvent.value.id)
  relations.value = {
    ticket: data.ticket || {},
    linked_case: data.linked_case || null,
    linked_tasks: data.linked_tasks || []
  }
}

function getTaskStatusClass(status: string): string {
  const value = status.toLowerCase()
  if (value.includes('success') || value.includes('done') || value.includes('complete')) return 'status-success'
  if (value.includes('running') || value.includes('processing')) return 'status-running'
  if (value.includes('wait') || value.includes('pending')) return 'status-pending'
  if (value.includes('fail') || value.includes('error') || value.includes('reject')) return 'status-failed'
  return 'status-default'
}

function openTaskDetail(taskId: number) {
  void router.push({
    path: '/fabric',
    query: { taskId: String(taskId) }
  })
}

function openCaseDetail(caseId?: number | null) {
  if (!caseId) return
  void router.push({
    path: '/cases',
    query: { caseId: String(caseId) }
  })
}

onMounted(async () => {
  await refreshData()
})
</script>

<style scoped>
.page {
  min-height: calc(100vh - 64px);
  background: #f5f7fa;
  padding: 24px;
}

.page-content {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-icon {
  color: #2563eb;
}

.mode-badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: #e2e8f0;
  color: #334155;
}

.mode-badge.observe {
  background: #fef3c7;
  color: #92400e;
}

.btn-refresh {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  cursor: pointer;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon-info {
  background: #dbeafe;
  color: #1d4ed8;
}

.stat-icon-warning {
  background: #fef3c7;
  color: #b45309;
}

.stat-icon-success {
  background: #dcfce7;
  color: #15803d;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
}

.stat-label {
  color: #64748b;
  font-size: 13px;
}

.filter-section {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.filter-group {
  display: flex;
  gap: 12px;
}

.filter-input {
  height: 38px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0 12px;
}

.events-section {
  background: #fff;
  border-radius: 12px;
  padding: 18px;
}

.loading,
.empty {
  text-align: center;
  color: #64748b;
  padding: 42px 0;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
}

.alert-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.alert-severity,
.alert-status {
  font-size: 12px;
  border-radius: 999px;
  padding: 2px 8px;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  gap: 4px;
}

.alert-status.acknowledged {
  background: #dcfce7;
  color: #166534;
}

.alert-time {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.alert-body {
  margin-top: 10px;
}

.alert-host {
  font-size: 13px;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 4px;
}

.alert-name {
  margin-top: 6px;
  font-weight: 600;
  color: #0f172a;
}

.event-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
  display: flex;
  gap: 16px;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
}

.modal-content {
  width: min(720px, 92vw);
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid #e2e8f0;
}

.btn-close {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
}

.modal-body {
  padding: 16px 18px 18px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px dashed #e2e8f0;
  padding: 8px 0;
  font-size: 14px;
}

.detail-row span {
  color: #64748b;
}

.detail-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

.btn-action {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
}

.btn-action.primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.action-message {
  margin-top: 10px;
  font-size: 13px;
  color: #334155;
}

.relation-panel {
  margin-top: 12px;
  border-top: 1px solid #e2e8f0;
  padding-top: 10px;
}

.relation-panel h4 {
  font-size: 13px;
  color: #334155;
  margin: 8px 0 6px;
}

.relation-item {
  font-size: 12px;
  color: #475569;
  padding: 6px 0;
}

.playbook-panel {
  margin-top: 12px;
  border-top: 1px solid #e2e8f0;
  padding-top: 10px;
}

.playbook-panel h4 {
  font-size: 13px;
  color: #334155;
  margin: 8px 0 6px;
}

.playbook-check {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.check-badge {
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
}

.check-badge.passed {
  background: #dcfce7;
  color: #166534;
}

.check-badge.failed {
  background: #fee2e2;
  color: #991b1b;
}

.check-note {
  font-size: 12px;
  color: #64748b;
}

.check-note.error {
  color: #991b1b;
}

.playbook-yaml {
  max-height: 220px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
}

.relation-task-main,
.relation-task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.relation-task-meta {
  margin-top: 4px;
}

.task-status-badge {
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
}

.task-status-badge.status-success {
  color: #166534;
  background: #dcfce7;
}

.task-status-badge.status-running {
  color: #1d4ed8;
  background: #dbeafe;
}

.task-status-badge.status-pending {
  color: #92400e;
  background: #fef3c7;
}

.task-status-badge.status-failed {
  color: #991b1b;
  background: #fee2e2;
}

.task-status-badge.status-default {
  color: #334155;
  background: #e2e8f0;
}

.btn-link-task {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 12px;
  cursor: pointer;
}

.relation-item.muted {
  color: #94a3b8;
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
