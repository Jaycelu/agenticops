<template>
  <div class="dashboard-page app-page">
    <div class="dashboard-shell">
      <section class="hero-card app-panel">
        <div class="app-page-copy">
          <h1>AgenticOps 驾驶舱</h1>
        </div>
        <div class="hero-actions app-actions">
          <button class="app-button app-button-secondary" :disabled="loading" @click="loadDashboard">
            {{ loading ? '刷新中...' : '刷新驾驶舱' }}
          </button>
          <button class="app-button app-button-primary" @click="router.push('/events')">进入事件中心</button>
        </div>
      </section>

      <section class="stats-grid">
        <article class="metric-card app-stat-card">
          <span class="metric-label app-kpi-label">统一事件</span>
          <strong class="metric-value app-kpi-value">{{ eventOverview.total }}</strong>
          <span class="metric-sub app-kpi-sub">日志 {{ eventOverview.logSignals }} / 告警 {{ eventOverview.zabbixAlerts }}</span>
        </article>
        <article class="metric-card app-stat-card">
          <span class="metric-label app-kpi-label">降噪率</span>
          <strong class="metric-value app-kpi-value">{{ eventOverview.noiseRate }}%</strong>
          <span class="metric-sub app-kpi-sub">noise {{ eventOverview.noise }}</span>
        </article>
        <article class="metric-card app-stat-card">
          <span class="metric-label app-kpi-label">直接工单率</span>
          <strong class="metric-value app-kpi-value">{{ eventOverview.ticketRate }}%</strong>
          <span class="metric-sub app-kpi-sub">ticket_only {{ eventOverview.ticketOnly }}</span>
        </article>
        <article class="metric-card app-stat-card">
          <span class="metric-label app-kpi-label">Case 提升率</span>
          <strong class="metric-value app-kpi-value">{{ eventOverview.caseRate }}%</strong>
          <span class="metric-sub app-kpi-sub">case_required {{ eventOverview.caseRequired }}</span>
        </article>
      </section>

      <section class="panel-grid">
        <article class="panel-card app-panel">
          <div class="panel-head">
            <h2>数据源健康</h2>
          </div>
          <div class="source-grid">
            <div v-for="item in sourceHealth" :key="item.key" class="source-card app-subcard">
              <div class="source-head">
                <strong>{{ item.name }}</strong>
                <span class="app-badge" :class="item.enabled ? 'app-badge-success' : 'app-badge-warning'">
                  {{ item.enabled ? '已启用' : '未启用' }}
                </span>
              </div>
              <div class="source-meta">
                <span>来源: {{ item.source }}</span>
                <span>更新: {{ formatTime(item.updated_at) }}</span>
              </div>
            </div>
          </div>
        </article>

        <article class="panel-card app-panel">
          <div class="panel-head">
            <h2>事件分流结构</h2>
          </div>
          <div v-if="dispositionRows.length === 0" class="empty app-empty">暂无事件数据</div>
          <div v-else class="bar-list">
            <div v-for="row in dispositionRows" :key="row.name" class="bar-row">
              <span class="bar-name">{{ row.name }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${row.percent}%` }"></div>
              </div>
              <strong class="bar-value">{{ row.count }}</strong>
            </div>
          </div>
        </article>
      </section>

      <section class="panel-grid">
        <article class="panel-card app-panel">
          <div class="panel-head">
            <h2>根因候选</h2>
          </div>
          <div v-if="rootCauseCandidates.length === 0" class="empty app-empty">暂无候选</div>
          <div v-else class="cluster-list">
            <button
              v-for="item in rootCauseCandidates"
              :key="item.candidate_key"
              class="cluster-item app-card"
              @click="router.push({ path: '/events', query: { candidateKey: item.candidate_key } })"
            >
              <div class="cluster-item-head">
                <strong>{{ item.root_cause_candidate }}</strong>
                <span class="app-badge app-badge-danger">score {{ item.score }}</span>
              </div>
              <div class="cluster-item-meta">
                <span>{{ item.representative_device || '-' }}</span>
                <span>{{ item.site_name || '-' }}</span>
              </div>
              <div class="cluster-item-meta">
                <span>事件 {{ item.event_count }}</span>
                <span>Case {{ item.case_count }}</span>
                <span>簇 {{ item.merged_cluster_count }}</span>
              </div>
            </button>
          </div>
        </article>

        <article class="panel-card app-panel">
          <div class="panel-head">
            <h2>热点问题簇</h2>
          </div>
          <div v-if="hotClusters.length === 0" class="empty app-empty">暂无聚类数据</div>
          <div v-else class="cluster-list">
            <button
              v-for="item in hotClusters"
              :key="item.correlation_key"
              class="cluster-item app-card"
              @click="router.push({ path: '/events', query: { correlationKey: item.correlation_key } })"
            >
              <div class="cluster-item-head">
                <strong>{{ item.title }}</strong>
                <span class="app-badge app-badge-primary">{{ item.highest_severity }}</span>
              </div>
              <div class="cluster-item-meta">
                <span>事件 {{ item.event_count }}</span>
                <span>Case {{ item.case_count }}</span>
                <span>工单 {{ item.ticket_count }}</span>
              </div>
              <div class="cluster-item-meta">
                <span>{{ item.device_name || item.host || '-' }}</span>
                <span>{{ item.device_role || item.signal_family || '-' }}</span>
              </div>
              <div class="cluster-item-meta">
                <span>{{ item.root_cause_candidate || '-' }}</span>
                <span>{{ item.site_name || '-' }}</span>
              </div>
              <div class="cluster-item-meta">
                <span>影响面 {{ item.impact_scope || '-' }}</span>
                <span>邻接 {{ item.link_count || 0 }}</span>
              </div>
              <div v-if="item.adjacent_devices?.length" class="cluster-peer-row">
                <span
                  v-for="peer in item.adjacent_devices"
                  :key="`${item.correlation_key}-${peer}`"
                  class="app-badge app-badge-warning"
                >
                  {{ peer }}
                </span>
              </div>
            </button>
          </div>
        </article>

        <article class="panel-card app-panel">
          <div class="panel-head">
            <h2>Case 与 MTTR</h2>
          </div>
          <div class="summary-grid">
            <div class="summary-box app-subcard">
              <span>处理中 Case</span>
              <strong>{{ caseOverview.open_cases }}</strong>
            </div>
            <div class="summary-box app-subcard">
              <span>高风险 Case</span>
              <strong>{{ caseOverview.high_risk_cases }}</strong>
            </div>
            <div class="summary-box app-subcard">
              <span>估算 MTTR</span>
              <strong>{{ mttrHours }}</strong>
            </div>
            <div class="summary-box app-subcard">
              <span>执行中</span>
              <strong>{{ caseOverview.executing_cases }}</strong>
            </div>
          </div>
          <div v-if="recentCases.length === 0" class="empty app-empty">暂无 case</div>
          <div v-else class="case-list compact-list">
            <button
              v-for="item in recentCases"
              :key="item.id"
              class="case-item app-card"
              @click="router.push({ path: '/cases', query: { caseId: String(item.id) } })"
            >
              <div class="case-item-head">
                <strong>{{ item.case_code }}</strong>
                <span class="app-badge app-badge-primary">{{ item.status }}</span>
              </div>
              <div class="case-item-title">{{ item.title }}</div>
              <div class="case-item-meta">
                <span>{{ item.current_phase }}</span>
                <span>{{ item.device_ip || item.host || '-' }}</span>
              </div>
            </button>
          </div>
        </article>

        <article class="panel-card app-panel">
          <div class="panel-head">
            <h2>闭环效果</h2>
          </div>
          <div class="summary-grid">
            <div class="summary-box app-subcard">
              <span>成功 outcome</span>
              <strong>{{ memoryOverview.successful_outcomes }}</strong>
            </div>
            <div class="summary-box app-subcard">
              <span>已批准计划</span>
              <strong>{{ fabricOverview.approved_plans }}</strong>
            </div>
            <div class="summary-box app-subcard">
              <span>草案计划</span>
              <strong>{{ fabricOverview.draft_plans }}</strong>
            </div>
            <div class="summary-box app-subcard">
              <span>运行中执行</span>
              <strong>{{ fabricOverview.running_executions }}</strong>
            </div>
            <div class="summary-box app-subcard">
              <span>记忆条目</span>
              <strong>{{ memoryOverview.total_memories }}</strong>
            </div>
            <div class="summary-box app-subcard">
              <span>高可信 pattern</span>
              <strong>{{ memoryOverview.high_confidence_patterns }}</strong>
            </div>
          </div>
        </article>
      </section>

      <section class="panel-grid">
        <article class="panel-card app-panel">
          <div class="panel-head">
            <h2>智能体健康</h2>
          </div>
          <div v-if="agentHealth.length === 0" class="empty app-empty">暂无运行记录</div>
          <div v-else class="agent-list">
            <div v-for="agent in agentHealth" :key="agent.agent_type" class="agent-item">
              <div>
                <strong>{{ agent.agent_type }}</strong>
                <p>最近运行：{{ formatTime(agent.last_run_at) }}</p>
              </div>
              <div class="agent-metrics">
                <span>总 {{ agent.total_runs }}</span>
                <span>运行中 {{ agent.running_runs }}</span>
                <span>失败 {{ agent.failed_runs }}</span>
              </div>
            </div>
          </div>
        </article>

        <article class="panel-card app-panel">
          <div class="panel-head">
            <h2>Case 阶段分布</h2>
          </div>
          <div v-if="phaseRows.length === 0" class="empty app-empty">暂无数据</div>
          <div v-else class="bar-list">
            <div v-for="row in phaseRows" :key="row.phase" class="bar-row">
              <span class="bar-name">{{ row.phase }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${row.percent}%` }"></div>
              </div>
              <strong class="bar-value">{{ row.count }}</strong>
            </div>
          </div>
        </article>
      </section>

      <div v-if="message" class="message app-message">{{ message }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { agentsApi } from '@/api/agents'
import { casesApi, type CaseSummary } from '@/api/cases'
import { eventsApi, type EventClusterItem, type EventItem, type RootCauseCandidateItem } from '@/api/events'
import { fabricApi } from '@/api/fabric'
import { memoriesApi } from '@/api/memories'
import { settingsApi, type IntegrationConfig } from '@/api/settings'

const router = useRouter()
const loading = ref(false)
const message = ref('')
const caseOverview = ref({
  total_cases: 0,
  open_cases: 0,
  executing_cases: 0,
  resolved_cases: 0,
  high_risk_cases: 0,
  by_phase: {} as Record<string, number>
})
const agentHealth = ref<any[]>([])
const memoryOverview = ref({
  total_memories: 0,
  by_type: {} as Record<string, number>,
  high_confidence_patterns: 0,
  successful_outcomes: 0
})
const fabricOverview = ref({
  total_plans: 0,
  draft_plans: 0,
  approved_plans: 0,
  running_executions: 0,
  failed_executions: 0
})
const recentCases = ref<CaseSummary[]>([])
const recentResolvedCases = ref<CaseSummary[]>([])
const recentEvents = ref<EventItem[]>([])
const hotClusters = ref<EventClusterItem[]>([])
const rootCauseCandidates = ref<RootCauseCandidateItem[]>([])
const integrations = ref<IntegrationConfig[]>([])

const phaseRows = computed(() => {
  const entries = Object.entries(caseOverview.value.by_phase || {})
  const total = entries.reduce((sum, [, count]) => sum + Number(count || 0), 0) || 1
  return entries
    .map(([phase, count]) => ({
      phase,
      count: Number(count || 0),
      percent: Math.round((Number(count || 0) / total) * 100)
    }))
    .sort((a, b) => b.count - a.count)
})

const eventOverview = computed(() => {
  const total = recentEvents.value.length || 0
  const noise = recentEvents.value.filter((item) => item.disposition === 'noise').length
  const ticketOnly = recentEvents.value.filter((item) => item.disposition === 'ticket_only').length
  const caseRequired = recentEvents.value.filter((item) => item.disposition === 'case_required').length
  const logSignals = recentEvents.value.filter((item) => item.source_category === 'log_signal').length
  const zabbixAlerts = recentEvents.value.filter((item) => item.source_category === 'zabbix_alert').length
  const rate = (value: number) => total > 0 ? Math.round((value / total) * 100) : 0
  return {
    total,
    noise,
    ticketOnly,
    caseRequired,
    logSignals,
    zabbixAlerts,
    noiseRate: rate(noise),
    ticketRate: rate(ticketOnly),
    caseRate: rate(caseRequired),
  }
})

const dispositionRows = computed(() => {
  const total = eventOverview.value.total || 1
  return [
    { name: 'noise', count: eventOverview.value.noise },
    { name: 'ticket_only', count: eventOverview.value.ticketOnly },
    { name: 'case_required', count: eventOverview.value.caseRequired },
  ].map((item) => ({
    ...item,
    percent: Math.round((item.count / total) * 100),
  }))
})

const mttrHours = computed(() => {
  const durations = recentResolvedCases.value
    .map((item) => {
      if (!item.opened_at || !item.last_activity_at) return null
      const start = new Date(item.opened_at).getTime()
      const end = new Date(item.last_activity_at).getTime()
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null
      return (end - start) / 3_600_000
    })
    .filter((value): value is number => value !== null)

  if (durations.length === 0) return '-'
  const avg = durations.reduce((sum, item) => sum + item, 0) / durations.length
  return `${avg.toFixed(1)}h`
})

const sourceHealth = computed(() => {
  const required = ['netbox', 'elk', 'zabbix']
  return required.map((key) => {
    const item = integrations.value.find((entry) => entry.integration_type === key)
    return {
      key,
      name: key.toUpperCase(),
      enabled: Boolean(item?.enabled),
      source: item?.source || 'settings',
      updated_at: item?.updated_at || null,
    }
  })
})

function formatTime(value?: string | null): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

async function loadDashboard() {
  loading.value = true
  message.value = ''
  try {
    const [caseData, healthData, memoryData, fabricData, recentData, resolvedData, eventData, clusterData, rootCauseData, integrationData] = await Promise.all([
      casesApi.getOverview(),
      agentsApi.getHealth(),
      memoriesApi.getOverview(),
      fabricApi.getOverview(),
      casesApi.list({ limit: 8 }),
      casesApi.list({ status: 'resolved', limit: 50 }),
      eventsApi.listEvents({ limit: 200 }),
      eventsApi.listClusters({ limit: 6 }),
      eventsApi.listRootCauses({ limit: 4 }),
      settingsApi.getIntegrations(),
    ])
    caseOverview.value = caseData
    agentHealth.value = healthData.items || []
    memoryOverview.value = memoryData
    fabricOverview.value = fabricData
    recentCases.value = recentData.items || []
    recentResolvedCases.value = resolvedData.items || []
    recentEvents.value = eventData.events || []
    hotClusters.value = clusterData.clusters || []
    rootCauseCandidates.value = rootCauseData.items || []
    integrations.value = integrationData.data || []
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '加载驾驶舱失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadDashboard()
})
</script>

<style scoped>
.dashboard-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.source-grid,
.cluster-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.source-card,
.cluster-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-head,
.source-meta,
.cluster-item-head,
.cluster-item-meta {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
}

.source-meta,
.cluster-item-meta {
  color: #5e738f;
  font-size: 13px;
}

.cluster-peer-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.panel-head span {
  color: #64748b;
  font-size: 13px;
}

.bar-list,
.agent-list,
.case-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.bar-row {
  display: grid;
  grid-template-columns: 120px 1fr 48px;
  align-items: center;
  gap: 12px;
}

.bar-track {
  height: 12px;
  background: rgba(148, 163, 184, 0.2);
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #0f5ae0, #0f766e);
}

.agent-item,
.case-item {
  border-color: rgba(148, 163, 184, 0.16);
}

.agent-item p {
  color: #5e738f;
  margin-top: 6px;
  font-size: 13px;
}

.agent-metrics,
.case-item-meta,
.case-item-head {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.agent-metrics {
  margin-top: 10px;
  color: #24405f;
  font-size: 13px;
}

.case-item {
  text-align: left;
  cursor: pointer;
}

.cluster-item {
  text-align: left;
  cursor: pointer;
}

.case-item-title {
  margin: 10px 0 8px;
  font-weight: 600;
}

.case-item-meta {
  color: #5e738f;
  font-size: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary-box span {
  color: #5e738f;
  font-size: 13px;
}

.summary-box strong {
  display: block;
  margin-top: 10px;
  font-size: 28px;
}

@media (max-width: 1100px) {
  .stats-grid,
  .panel-grid {
    grid-template-columns: 1fr;
  }

  .source-grid,
  .cluster-list,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .hero-card {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
