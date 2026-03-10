<template>
  <div class="page app-page">
    <div class="page-content">
      <div class="page-header app-page-header">
        <div class="page-title app-page-title">
          <span class="app-page-title-icon">
            <Radio :size="24" class="title-icon" />
          </span>
          <div class="app-page-copy">
            <h1>事件中心</h1>
            <p>统一处理 ELK 日志信号与 Zabbix 告警，关联 Case、Fabric 与工单闭环。</p>
          </div>
          <span class="mode-badge" :class="{ observe: automationMode?.is_observe_only }">
            {{ automationMode?.is_observe_only ? '观测模式' : '自动模式' }}
          </span>
        </div>
        <button @click="refreshData" class="btn-refresh app-button app-button-secondary" :disabled="loading">
          <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>

      <div class="stats-grid">
        <div class="stat-card app-stat-card">
          <div class="stat-icon stat-icon-info">
            <Radio :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ events.length }}</div>
            <div class="stat-label">当前页事件</div>
          </div>
        </div>
        <div class="stat-card app-stat-card">
          <div class="stat-icon stat-icon-warning">
            <AlertTriangle :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ openCount }}</div>
            <div class="stat-label">未关闭</div>
          </div>
        </div>
        <div class="stat-card app-stat-card">
          <div class="stat-icon stat-icon-success">
            <CheckCircle2 :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ resolvedCount }}</div>
            <div class="stat-label">已关闭</div>
          </div>
        </div>
        <div class="stat-card app-stat-card">
          <div class="stat-icon stat-icon-info">
            <BellRing :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ zabbixCount }}</div>
            <div class="stat-label">Zabbix 告警</div>
          </div>
        </div>
        <div class="stat-card app-stat-card">
          <div class="stat-icon stat-icon-primary">
            <FileText :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ logSignalCount }}</div>
            <div class="stat-label">日志信号</div>
          </div>
        </div>
        <div class="stat-card app-stat-card">
          <div class="stat-icon stat-icon-danger">
            <Layers3 :size="28" />
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ caseRequiredCount }}</div>
            <div class="stat-label">需进入 Case</div>
          </div>
        </div>
      </div>

      <div class="filter-section app-panel">
        <div class="filter-group">
          <select v-model="filters.status" class="filter-input app-select" @change="loadEvents">
            <option value="">全部状态</option>
            <option value="open">open</option>
            <option value="acknowledged">acknowledged</option>
            <option value="resolved">resolved</option>
          </select>
          <select v-model="filters.source" class="filter-input app-select" @change="loadEvents">
            <option value="">全部来源</option>
            <option value="ELK">ELK</option>
            <option value="ZABBIX">ZABBIX</option>
          </select>
          <select v-model="filters.event_type" class="filter-input app-select" @change="loadEvents">
            <option value="">全部事件类型</option>
            <option value="log_signal">log_signal</option>
            <option value="zabbix_alert">zabbix_alert</option>
          </select>
          <select v-model="filters.disposition" class="filter-input app-select" @change="loadEvents">
            <option value="">全部分流结果</option>
            <option value="noise">noise</option>
            <option value="ticket_only">ticket_only</option>
            <option value="case_required">case_required</option>
          </select>
        </div>
      </div>

      <div class="cluster-section app-panel" v-if="rootCauses.length > 0">
        <div class="app-section-header">
          <div class="app-page-copy">
            <h2>根因候选榜</h2>
            <p>对多个问题簇做跨簇归并和证据强度排序，优先呈现更可能的根因方向。</p>
          </div>
        </div>
        <div class="candidate-grid">
          <article v-for="item in rootCauses" :key="item.candidate_key" class="candidate-card app-card">
            <div class="candidate-head">
              <strong>{{ item.root_cause_candidate }}</strong>
              <span class="app-badge app-badge-danger">score {{ item.score }}</span>
            </div>
            <div class="candidate-meta">
              <span>设备: {{ item.representative_device || '-' }}</span>
              <span>站点: {{ item.site_name || '-' }}</span>
            </div>
            <div class="candidate-meta">
              <span>事件 {{ item.event_count }}</span>
              <span>Case {{ item.case_count }}</span>
              <span>簇 {{ item.merged_cluster_count }}</span>
            </div>
            <div class="candidate-meta">
              <span>信号族: {{ item.signal_family || '-' }}</span>
              <span>影响面: {{ item.impact_scope || '-' }}</span>
            </div>
            <div class="cluster-insight">
              <strong>排序理由:</strong>
              <span>{{ item.ranking_reason }}</span>
            </div>
            <div class="candidate-action-bar">
              <button class="app-button app-button-ghost" @click.stop="toggleCandidate(item.candidate_key)">
                {{ activeCandidateKey === item.candidate_key ? '取消聚焦' : '聚焦候选' }}
              </button>
              <button
                class="app-button app-button-secondary"
                :disabled="!resolveCandidateCaseId(item)"
                @click.stop="openCandidateCase(item)"
              >
                打开 Case
              </button>
              <button
                class="app-button app-button-primary"
                :disabled="!resolveCandidateCaseId(item)"
                @click.stop="openCandidateFabric(item)"
              >
                查看执行建议
              </button>
            </div>
            <div v-if="item.recommended_actions?.length" class="candidate-actions">
              <div v-for="action in item.recommended_actions" :key="`${item.candidate_key}-${action.priority_order}-${action.action_type}`" class="candidate-action app-subcard">
                <strong>{{ action.priority_order }}. {{ action.title }}</strong>
                <span>{{ action.reason }}</span>
              </div>
            </div>
            <div v-if="item.adjacent_devices?.length" class="cluster-badges">
              <span v-for="peer in item.adjacent_devices" :key="`${item.candidate_key}-${peer}`" class="app-badge app-badge-warning">
                {{ peer }}
              </span>
            </div>
          </article>
        </div>
      </div>

      <div class="cluster-section app-panel" v-if="clusters.length > 0">
        <div class="app-section-header">
          <div class="app-page-copy">
            <h2>事件聚类</h2>
            <p>基于站点、设备和信号族的跨源关联视图，用于把日志信号和 Zabbix 告警收敛成同一问题簇。</p>
          </div>
          <button v-if="activeClusterKey || activeCandidateKey" class="app-button app-button-ghost" @click="clearClusterFilter">
            清除聚类筛选
          </button>
        </div>
        <div class="cluster-grid">
          <article
            v-for="cluster in visibleClusters"
            :key="cluster.correlation_key"
            class="cluster-card app-card"
            :class="{ active: activeClusterKey === cluster.correlation_key }"
            @click="toggleCluster(cluster.correlation_key)"
          >
            <div class="cluster-head">
              <strong>{{ cluster.title }}</strong>
              <span class="app-badge" :class="severityBadgeClass(cluster.highest_severity)">{{ cluster.highest_severity }}</span>
            </div>
            <div class="cluster-meta">
              <span>事件数: {{ cluster.event_count }}</span>
              <span>Case: {{ cluster.case_count }}</span>
              <span>工单: {{ cluster.ticket_count }}</span>
            </div>
            <div class="cluster-meta">
              <span>主机: {{ cluster.host || '-' }}</span>
              <span>信号族: {{ cluster.signal_family || '-' }}</span>
            </div>
            <div class="cluster-meta">
              <span>设备: {{ cluster.device_name || '-' }}</span>
              <span>角色: {{ cluster.device_role || '-' }}</span>
              <span>站点: {{ cluster.site_name || '-' }}</span>
            </div>
            <div class="cluster-insight">
              <strong>候选根因:</strong>
              <span>{{ cluster.root_cause_candidate || '-' }}</span>
            </div>
            <div class="cluster-insight cluster-hint">
              <strong>拓扑提示:</strong>
              <span>{{ cluster.topology_hint || '-' }}</span>
            </div>
            <div class="cluster-insight">
              <strong>影响面:</strong>
              <span>{{ cluster.impact_scope || '-' }} / 邻接 {{ cluster.link_count || 0 }}</span>
            </div>
            <div v-if="cluster.adjacent_devices?.length" class="cluster-badges">
              <span v-for="peer in cluster.adjacent_devices" :key="`${cluster.correlation_key}-${peer}`" class="app-badge app-badge-warning">
                {{ peer }}
              </span>
            </div>
            <div class="cluster-badges">
              <span v-for="sourceCategory in cluster.source_categories" :key="sourceCategory" class="app-badge app-badge-neutral">
                {{ sourceCategory }}
              </span>
              <span
                v-for="(count, key) in cluster.dispositions"
                :key="`${cluster.correlation_key}-${key}`"
                class="app-badge app-badge-primary"
              >
                {{ key }}: {{ count }}
              </span>
            </div>
          </article>
        </div>
      </div>

      <div class="events-section app-panel">
        <div v-if="loading" class="loading app-empty">
          <Loader2 class="animate-spin" :size="40" />
          <p>加载中...</p>
        </div>
        <div v-else-if="filteredEvents.length === 0" class="empty app-empty">
          <AlertCircle :size="48" />
          <p>{{ activeClusterKey || activeCandidateKey ? '当前筛选下暂无事件' : '暂无事件数据' }}</p>
        </div>
        <div v-else class="events-list">
          <div v-for="item in filteredEvents" :key="item.id" class="alert-item app-card" @click="openDetail(item)">
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
                <span>来源: {{ item.source_label || item.source }}</span>
                <span>类型: {{ item.event_type || '-' }}</span>
                <span>分流: {{ item.disposition || '-' }}</span>
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
    <div class="modal-content app-modal" @click.stop>
      <div class="modal-header app-modal-header">
        <h3>事件详情</h3>
        <button class="btn-close app-button app-button-secondary" @click="closeDetail">关闭</button>
      </div>
      <div class="modal-body app-modal-body">
        <div class="detail-row"><span>名称</span><strong>{{ selectedEvent.name }}</strong></div>
        <div class="detail-row"><span>来源</span><strong>{{ selectedEvent.source_label || selectedEvent.source }}</strong></div>
        <div class="detail-row"><span>事件类型</span><strong>{{ selectedEvent.event_type || '-' }}</strong></div>
        <div class="detail-row"><span>信号键</span><strong>{{ selectedEvent.signal_key || '-' }}</strong></div>
        <div class="detail-row"><span>分流结果</span><strong>{{ selectedEvent.disposition || '-' }}</strong></div>
        <div class="detail-row"><span>分流原因</span><strong>{{ selectedEvent.disposition_reason || '-' }}</strong></div>
        <div class="detail-row"><span>主机</span><strong>{{ selectedEvent.host || '-' }}</strong></div>
        <div class="detail-row"><span>级别</span><strong>{{ selectedEvent.severity }}</strong></div>
        <div class="detail-row"><span>状态</span><strong>{{ selectedEvent.status }}</strong></div>
        <div class="detail-row"><span>关联Case</span><strong>{{ selectedEventCase.caseCode || relations.linked_case?.case_code || '-' }}</strong></div>
        <div class="detail-row"><span>推荐Skill</span><strong>{{ recommendedSkillCode || '-' }}</strong></div>
        <div class="detail-row"><span>发生时间</span><strong>{{ formatTime(selectedEvent.occurred_at) }}</strong></div>
        <div class="detail-actions">
          <button
            v-if="selectedEventCase.caseId || relations.linked_case?.case_id"
            class="btn-action primary app-button app-button-primary"
            @click="openCaseDetail(selectedEventCase.caseId || relations.linked_case?.case_id)"
          >
            打开 Case
          </button>
          <button class="btn-action primary app-button app-button-primary" :disabled="actionLoading" @click="dispatchReadonlySelected">
            {{ actionLoading ? '处理中...' : '触发只读研判' }}
          </button>
          <button class="btn-action app-button app-button-ghost" :disabled="playbookLoading" @click="generatePlaybookDraftSelected">
            {{ playbookLoading ? '生成中...' : '生成Playbook草稿' }}
          </button>
          <button class="btn-action app-button app-button-secondary" :disabled="ticketLoading" @click="createTicketSelected">
            {{ ticketLoading ? '处理中...' : '创建工单' }}
          </button>
          <button class="btn-action app-button app-button-secondary" :disabled="actionLoading" @click="markNoiseSelected">
            标记为噪声
          </button>
          <button class="btn-action app-button app-button-secondary" @click="loadRelations">刷新关联</button>
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
              <button class="btn-link-task app-button app-button-ghost" @click="openCaseDetail(relations.linked_case.case_id)">查看 Case</button>
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
              <span>来源: {{ task.source_model || 'unknown' }}</span>
              <span>Skill: {{ task.recommended_skill_code || recommendedSkillCode || '-' }}</span>
              <button class="btn-link-task app-button app-button-ghost" @click="openTaskDetail(task.task_id)">查看任务详情</button>
            </div>
          </div>
        </div>
        <div v-if="actionMessage" class="action-message">{{ actionMessage }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { eventsApi, type EventClusterItem, type EventItem, type RootCauseCandidateItem } from '@/api/events'
import { AlertCircle, AlertTriangle, BellRing, CheckCircle2, Clock, FileText, Layers3, Loader2, Radio, RefreshCw, Server } from 'lucide-vue-next'

interface LinkedTaskRelation {
  task_id: number
  task_code: string
  status: string
  source_model?: string
  case_id?: number | null
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
const route = useRoute()
const loading = ref(false)
const automationMode = ref<{ mode: string; is_observe_only: boolean } | null>(null)
const events = ref<EventItem[]>([])
const clusters = ref<EventClusterItem[]>([])
const rootCauses = ref<RootCauseCandidateItem[]>([])
const selectedEvent = ref<EventItem | null>(null)
const activeClusterKey = ref('')
const activeCandidateKey = ref('')
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
  source: '',
  event_type: '',
  disposition: ''
})

const visibleClusters = computed(() => {
  if (!activeCandidateKey.value) return clusters.value
  const candidate = rootCauses.value.find((item) => item.candidate_key === activeCandidateKey.value)
  if (!candidate) return clusters.value
  return clusters.value.filter((cluster) => {
    const siteMatched = !candidate.site_name || cluster.site_name === candidate.site_name
    const signalMatched = !candidate.signal_family || cluster.signal_family === candidate.signal_family
    const rootCauseMatched = !candidate.root_cause_candidate || cluster.root_cause_candidate === candidate.root_cause_candidate
    return siteMatched && signalMatched && rootCauseMatched
  })
})

const candidateClusterKeys = computed(() => new Set(visibleClusters.value.map((item) => item.correlation_key)))

const filteredEvents = computed(() => {
  let items = events.value
  if (activeCandidateKey.value) {
    items = items.filter((item) => item.correlation_key && candidateClusterKeys.value.has(item.correlation_key))
  }
  if (activeClusterKey.value) {
    items = items.filter((item) => item.correlation_key === activeClusterKey.value)
  }
  return items
})
const openCount = computed(() => filteredEvents.value.filter((item) => item.status !== 'resolved').length)
const resolvedCount = computed(() => filteredEvents.value.filter((item) => item.status === 'resolved').length)
const zabbixCount = computed(() => filteredEvents.value.filter((item) => item.source_category === 'zabbix_alert').length)
const logSignalCount = computed(() => filteredEvents.value.filter((item) => item.source_category === 'log_signal').length)
const caseRequiredCount = computed(() => filteredEvents.value.filter((item) => item.disposition === 'case_required').length)
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
  try {
    const apiUrl = '/api/settings/automation-mode'
    const response = await axios.get(apiUrl)
    if (response.data.success && response.data.data) {
      automationMode.value = {
        mode: response.data.data.mode,
        is_observe_only: response.data.data.is_observe_only
      }
    }
  } catch (error) {
    console.error('Error loading automation mode:', error)
  }
}

async function loadEvents() {
  loading.value = true
  try {
    const res = await eventsApi.listEvents({
      status: filters.value.status || undefined,
      source: filters.value.source || undefined,
      event_type: filters.value.event_type || undefined,
      disposition: filters.value.disposition || undefined,
      limit: 100
    })
    events.value = res.events || []
    const queryEventId = Number(route.query.eventId || 0)
    if (queryEventId) {
      const matched = events.value.find((item) => item.id === queryEventId)
      if (matched) {
        openDetail(matched)
      }
    }
  } finally {
    loading.value = false
  }
}

async function loadClusters() {
  const res = await eventsApi.listClusters({
    status: filters.value.status || undefined,
    source: filters.value.source || undefined,
    disposition: filters.value.disposition || undefined,
    limit: 8,
  })
  clusters.value = res.clusters || []
  if (activeClusterKey.value && !clusters.value.some((item) => item.correlation_key === activeClusterKey.value)) {
    activeClusterKey.value = ''
  }
}

async function loadRootCauses() {
  const res = await eventsApi.listRootCauses({
    status: filters.value.status || undefined,
    source: filters.value.source || undefined,
    disposition: filters.value.disposition || undefined,
    limit: 6,
  })
  rootCauses.value = res.items || []
}

async function refreshData() {
  await Promise.all([loadMode(), loadEvents(), loadClusters(), loadRootCauses()])
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

function toggleCluster(correlationKey: string) {
  activeClusterKey.value = activeClusterKey.value === correlationKey ? '' : correlationKey
  syncRouteFilters()
}

function clearClusterFilter() {
  activeClusterKey.value = ''
  activeCandidateKey.value = ''
  syncRouteFilters()
}

function toggleCandidate(candidateKey: string) {
  activeCandidateKey.value = activeCandidateKey.value === candidateKey ? '' : candidateKey
  activeClusterKey.value = ''
  syncRouteFilters()
}

function resolveCandidateCaseId(item: RootCauseCandidateItem): number | null {
  const candidate = rootCauses.value.find((entry) => entry.candidate_key === item.candidate_key)
  if (!candidate) return null
  const keySet = new Set(
    clusters.value
      .filter((cluster) => {
        const siteMatched = !candidate.site_name || cluster.site_name === candidate.site_name
        const signalMatched = !candidate.signal_family || cluster.signal_family === candidate.signal_family
        const rootCauseMatched = !candidate.root_cause_candidate || cluster.root_cause_candidate === candidate.root_cause_candidate
        return siteMatched && signalMatched && rootCauseMatched
      })
      .map((cluster) => cluster.correlation_key)
  )
  const matched = events.value.find((entry) => entry.case_id && entry.correlation_key && keySet.has(entry.correlation_key))
  return matched?.case_id || null
}

function openCandidateCase(item: RootCauseCandidateItem) {
  const caseId = resolveCandidateCaseId(item)
  if (!caseId) return
  openCaseDetail(caseId)
}

function openCandidateFabric(item: RootCauseCandidateItem) {
  const caseId = resolveCandidateCaseId(item)
  if (!caseId) return
  void router.push({
    path: '/fabric',
    query: { caseId: String(caseId) }
  })
}

function syncRouteFilters() {
  const nextQuery: Record<string, string> = {}
  if (activeClusterKey.value) nextQuery.correlationKey = activeClusterKey.value
  if (activeCandidateKey.value) nextQuery.candidateKey = activeCandidateKey.value
  void router.replace({ path: '/events', query: nextQuery })
}

function applyRouteFilters() {
  const correlationKey = Array.isArray(route.query.correlationKey) ? route.query.correlationKey[0] : route.query.correlationKey
  const candidateKey = Array.isArray(route.query.candidateKey) ? route.query.candidateKey[0] : route.query.candidateKey
  activeClusterKey.value = typeof correlationKey === 'string' ? correlationKey : ''
  activeCandidateKey.value = typeof candidateKey === 'string' ? candidateKey : ''
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
    await loadClusters()
    await loadRootCauses()
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
    await loadClusters()
    await loadRootCauses()
    await loadRelations()
  } catch (e: any) {
    actionMessage.value = e?.response?.data?.detail || '工单创建失败'
  } finally {
    ticketLoading.value = false
  }
}

async function markNoiseSelected() {
  if (!selectedEvent.value) return
  actionLoading.value = true
  actionMessage.value = ''
  try {
    const result = await eventsApi.updateDisposition(selectedEvent.value.id, 'noise', 'manual_noise_closure')
    actionMessage.value = result.message
    await loadEvents()
    await loadClusters()
    await loadRootCauses()
    if (selectedEvent.value) {
      selectedEvent.value = {
        ...selectedEvent.value,
        disposition: 'noise',
        disposition_reason: 'manual_noise_closure',
        status: 'resolved',
        acknowledged: true,
      }
    }
    await loadRelations()
  } catch (e: any) {
    actionMessage.value = e?.response?.data?.detail || '标记噪声失败'
  } finally {
    actionLoading.value = false
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
    await loadClusters()
    await loadRootCauses()
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

function severityBadgeClass(severity?: string): string {
  const value = (severity || '').toLowerCase()
  if (['critical', 'high', 'disaster'].includes(value)) return 'app-badge-danger'
  if (['warning', 'average', 'medium'].includes(value)) return 'app-badge-warning'
  if (['info', 'low'].includes(value)) return 'app-badge-primary'
  return 'app-badge-neutral'
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
  applyRouteFilters()
})

watch(
  () => [route.query.correlationKey, route.query.candidateKey],
  () => {
    applyRouteFilters()
  }
)
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

.page-title {
  align-items: center;
  flex-wrap: wrap;
}

.title-icon {
  color: currentColor;
}

.mode-badge {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(59, 130, 246, 0.12);
  color: #0f5ae0;
  border: 1px solid rgba(59, 130, 246, 0.18);
}

.mode-badge.observe {
  background: rgba(245, 158, 11, 0.14);
  color: #92400e;
  border-color: rgba(245, 158, 11, 0.18);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
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

.stat-icon-primary {
  background: rgba(99, 102, 241, 0.16);
  color: #4f46e5;
}

.stat-icon-danger {
  background: rgba(239, 68, 68, 0.14);
  color: #b91c1c;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
}

.stat-label {
  color: #5e738f;
  font-size: 13px;
}

@media (max-width: 1280px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.filter-section {
  margin-bottom: 16px;
}

.cluster-section {
  margin-bottom: 16px;
}

.cluster-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.candidate-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.cluster-card {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color var(--app-transition-fast), transform var(--app-transition-fast);
}

.candidate-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.candidate-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.candidate-action-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.candidate-action {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
}

.candidate-action strong {
  font-size: 13px;
}

.candidate-action span {
  color: #5e738f;
  font-size: 12px;
}

.cluster-card.active {
  border-color: rgba(15, 90, 224, 0.35);
  box-shadow: 0 18px 42px rgba(15, 90, 224, 0.14);
}

.cluster-head,
.candidate-head,
.cluster-meta,
.candidate-meta,
.cluster-badges {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.cluster-meta {
  color: #5e738f;
  font-size: 13px;
}

.candidate-meta {
  color: #5e738f;
  font-size: 13px;
  display: flex;
  gap: 8px;
  justify-content: space-between;
  flex-wrap: wrap;
}

.cluster-badges {
  justify-content: flex-start;
}

.cluster-insight {
  display: flex;
  gap: 6px;
  flex-direction: column;
  color: #334155;
  font-size: 13px;
}

.cluster-insight strong {
  color: #0f172a;
  font-size: 12px;
}

.cluster-hint {
  color: #47627f;
}

.filter-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-input {
  min-width: 180px;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-item {
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
  padding: 4px 10px;
  background: rgba(148, 163, 184, 0.16);
  display: flex;
  align-items: center;
  gap: 4px;
}

.alert-status.acknowledged {
  background: rgba(34, 197, 94, 0.14);
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
  color: #5e738f;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
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

.detail-row {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.24);
  padding: 8px 0;
  font-size: 14px;
}

.detail-row span {
  color: #64748b;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.action-message {
  margin-top: 10px;
  font-size: 13px;
  color: #334155;
}

.relation-panel {
  margin-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
  padding-top: 10px;
}

.relation-panel h4 {
  font-size: 13px;
  color: #334155;
  margin: 8px 0 6px;
}

.relation-item {
  font-size: 12px;
  color: #43566f;
  padding: 6px 0;
}

.playbook-panel {
  margin-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
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
  min-height: 34px;
  padding: 6px 12px;
  font-size: 12px;
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

@media (max-width: 980px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .cluster-grid {
    grid-template-columns: 1fr;
  }

  .candidate-grid {
    grid-template-columns: 1fr;
  }

  .page-title,
  .filter-group,
  .alert-header,
  .event-meta,
  .detail-actions,
  .cluster-head,
  .cluster-meta,
  .relation-task-main,
  .relation-task-meta {
    flex-direction: column;
    align-items: flex-start;
  }

  .alert-time {
    margin-left: 0;
  }
}

@media (max-width: 1280px) and (min-width: 981px) {
  .cluster-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .candidate-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
