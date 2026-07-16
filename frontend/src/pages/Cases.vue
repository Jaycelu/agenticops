<template>
  <div class="cases-page app-page">
    <div class="cases-header app-page-header">
      <div class="app-page-copy">
        <h1>Case 中心</h1>
      </div>
      <button class="app-button app-button-secondary" :disabled="loading" @click="loadCases">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div class="cases-filters app-toolbar">
      <select v-model="statusFilter" class="filter-input app-select" @change="loadCases">
        <option value="">全部状态</option>
        <option value="open">open</option>
        <option value="triaged">triaged</option>
        <option value="investigating">investigating</option>
        <option value="planned">planned</option>
        <option value="resolved">resolved</option>
        <option value="closed">closed</option>
      </select>
      <select v-model="phaseFilter" class="filter-input app-select" @change="loadCases">
        <option value="">全部阶段</option>
        <option value="intake">intake</option>
        <option value="analysis">analysis</option>
        <option value="remediation_draft">remediation_draft</option>
      </select>
    </div>

    <div v-if="loading" class="state-block app-empty">加载中...</div>
    <div v-else-if="cases.length === 0" class="state-block app-empty">暂无 case</div>
    <div v-else class="cases-layout">
      <div class="case-list">
        <button
          v-for="item in cases"
          :key="item.id"
          class="case-card app-card"
          :class="{ active: selectedCase?.id === item.id }"
          @click="selectCase(item.id)"
        >
          <div class="case-head">
            <strong>{{ item.case_code }}</strong>
            <span class="case-badge app-badge" :class="`status-${item.status}`">{{ item.status }}</span>
          </div>
          <div class="case-title">{{ item.title }}</div>
          <div class="case-meta">
            <span>{{ item.current_phase }}</span>
            <span>{{ item.risk_level }}</span>
            <span>{{ item.device_ip || item.host || '-' }}</span>
          </div>
        </button>
      </div>

      <div class="case-detail" v-if="selectedCase">
        <div class="detail-card app-panel">
          <div class="detail-head">
            <div class="app-page-copy">
              <h2>{{ selectedCase.title }}</h2>
              <p>{{ selectedCase.summary || '暂无摘要' }}</p>
            </div>
            <div class="detail-tags">
              <span class="pill app-pill">{{ selectedCase.case_code }}</span>
              <span class="pill app-pill">{{ selectedCase.status }}</span>
              <span class="pill app-pill">{{ selectedCase.current_phase }}</span>
              <button
                class="app-button app-button-primary run-agent-button"
                :disabled="startingGraph || isGraphActive"
                @click="startGraph"
              >
                {{ startingGraph ? '受理中...' : isGraphActive ? '智能体运行中' : '运行智能体' }}
              </button>
            </div>
          </div>
        </div>

        <section v-if="currentGraph" class="graph-status app-panel" aria-live="polite">
          <div>
            <span class="section-label">当前 Graph</span>
            <strong>{{ currentGraph.current_node }}</strong>
          </div>
          <div class="graph-status-meta">
            <span class="app-badge app-badge-primary">{{ currentGraph.status }}</span>
            <span>{{ currentGraph.current_state }}</span>
            <span class="graph-id">{{ currentGraph.graph_run_id }}</span>
          </div>
        </section>

        <div class="detail-grid">
          <div class="detail-card app-panel">
            <h3>证据</h3>
            <div v-if="evidence.length === 0" class="mini-empty app-empty">暂无证据</div>
            <div v-else class="detail-list">
              <div v-for="item in evidence" :key="item.id" class="detail-item app-subcard">
                <div class="detail-item-head">
                  <strong>{{ item.evidence_type }}</strong>
                  <span class="app-badge app-badge-neutral">{{ item.source_system }}</span>
                </div>
                <p>{{ item.summary || '-' }}</p>
              </div>
            </div>
          </div>

          <div class="detail-card app-panel">
            <h3>智能体输出</h3>
            <div v-if="agentRuns.length === 0" class="mini-empty app-empty">暂无运行记录</div>
            <div v-else class="detail-list">
              <div v-for="run in agentRuns" :key="run.id" class="detail-item app-subcard">
                <div class="detail-item-head">
                  <strong>{{ run.agent_name }}</strong>
                  <span class="app-badge app-badge-primary">{{ run.status }}</span>
                </div>
                <p v-if="run.claims?.[0]">{{ run.claims[0].claim_text }}</p>
                <p v-else>暂无 claim</p>
              </div>
            </div>
          </div>

          <div class="detail-card app-panel">
            <h3>修复计划</h3>
            <div v-if="plans.length === 0" class="mini-empty app-empty">暂无计划</div>
            <div v-else class="detail-list">
              <div v-for="plan in plans" :key="plan.id" class="detail-item app-subcard">
                <div class="detail-item-head">
                  <strong>{{ plan.plan_code }}</strong>
                  <span class="app-badge app-badge-warning">{{ plan.execution_mode }}</span>
                </div>
                <p>{{ plan.summary || '-' }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="diagnostic-grid">
          <section class="detail-card app-panel timeline-panel">
            <div class="section-heading">
              <div>
                <span class="section-label">Agent Timeline</span>
                <h3>诊断运行轨迹</h3>
              </div>
              <span class="app-badge app-badge-neutral">{{ timeline.length }} events</span>
            </div>
            <div v-if="timeline.length === 0" class="mini-empty app-empty">尚未生成 Graph Timeline</div>
            <ol v-else class="timeline-list">
              <li v-for="item in timeline" :key="item.id" class="timeline-item">
                <span class="timeline-dot" :class="`event-${item.event_type}`"></span>
                <div class="timeline-content">
                  <div class="detail-item-head">
                    <strong>{{ item.title }}</strong>
                    <time>{{ formatTime(item.created_at) }}</time>
                  </div>
                  <p>{{ item.actor_type }}<template v-if="item.actor_id"> · {{ item.actor_id }}</template></p>
                  <p v-if="item.payload?.reason" class="timeline-reason">{{ item.payload.reason }}</p>
                </div>
              </li>
            </ol>
          </section>

          <section class="detail-card app-panel">
            <div class="section-heading">
              <div>
                <span class="section-label">Hypothesis Board</span>
                <h3>根因候选</h3>
              </div>
            </div>
            <div v-if="hypotheses.length === 0" class="mini-empty app-empty">暂无结构化假设</div>
            <div v-else class="hypothesis-list">
              <article v-for="item in hypotheses" :key="item.id" class="hypothesis-card app-subcard">
                <div class="detail-item-head">
                  <strong>{{ item.cause_code }}</strong>
                  <span class="app-badge" :class="hypothesisStatusClass(item.status)">{{ item.status }}</span>
                </div>
                <p>{{ item.cause }}</p>
                <div class="confidence-row">
                  <span>置信度 {{ Math.round(item.confidence * 100) }}%</span>
                  <div class="progress-track"><span :style="{ width: `${Math.round(item.confidence * 100)}%` }"></span></div>
                </div>
                <dl class="evidence-counts">
                  <div><dt>支持证据</dt><dd>{{ item.supporting_evidence_ids?.length || 0 }}</dd></div>
                  <div><dt>反证</dt><dd>{{ item.contradicting_evidence_ids?.length || 0 }}</dd></div>
                  <div><dt>缺失</dt><dd>{{ item.missing_evidence?.length || 0 }}</dd></div>
                </dl>
                <p v-if="item.critic_decision" class="critic-result">Critic：{{ item.critic_decision }}</p>
              </article>
            </div>
          </section>

          <section class="detail-card app-panel">
            <div class="section-heading">
              <div>
                <span class="section-label">Budget Panel</span>
                <h3>运行预算</h3>
              </div>
              <span v-if="budget?.exhausted" class="app-badge app-badge-danger">已耗尽</span>
            </div>
            <div v-if="!budget" class="mini-empty app-empty">尚未创建运行预算</div>
            <div v-else class="budget-list">
              <div v-for="key in budgetKeys" :key="key" class="budget-row">
                <div><span>{{ budgetLabel(key) }}</span><strong>{{ budget.usage[key] }} / {{ budget.limits[key] }}</strong></div>
                <div class="progress-track"><span :style="{ width: `${budgetPercent(key)}%` }"></span></div>
              </div>
              <p v-if="budget.exhausted_reason" class="budget-warning">限制原因：{{ budget.exhausted_reason }}</p>
            </div>
          </section>
        </div>
      </div>
    </div>

    <div v-if="message" class="message app-message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { casesApi, type CaseSummary } from '@/api/cases'

const route = useRoute()
const loading = ref(false)
const message = ref('')
const statusFilter = ref('')
const phaseFilter = ref('')
const cases = ref<CaseSummary[]>([])
const selectedCase = ref<any | null>(null)
const evidence = ref<any[]>([])
const agentRuns = ref<any[]>([])
const plans = ref<any[]>([])
const graphRuns = ref<any[]>([])
const currentGraph = ref<any | null>(null)
const timeline = ref<any[]>([])
const hypotheses = ref<any[]>([])
const budget = ref<any | null>(null)
const startingGraph = ref(false)
let pollTimer: number | undefined
const activeGraphStatuses = new Set(['queued', 'running', 'waiting_evidence', 'paused'])
const isGraphActive = computed(() => currentGraph.value && activeGraphStatuses.has(currentGraph.value.status))
const budgetKeys = ['agent_runs', 'llm_calls', 'probe_calls', 'tool_calls', 'replan_count', 'runtime_seconds', 'target_devices']

function getRequestedCaseId(): number | null {
  const raw = Array.isArray(route.query.caseId) ? route.query.caseId[0] : route.query.caseId
  const caseId = Number(raw)
  return Number.isInteger(caseId) && caseId > 0 ? caseId : null
}

async function loadCases() {
  loading.value = true
  message.value = ''
  try {
    const result = await casesApi.list({
      status: statusFilter.value || undefined,
      current_phase: phaseFilter.value || undefined,
      limit: 100
    })
    cases.value = result.items || []
    if (cases.value.length > 0) {
      const nextId = getRequestedCaseId() || selectedCase.value?.id || cases.value[0].id
      await selectCase(nextId)
    } else {
      selectedCase.value = null
      evidence.value = []
      agentRuns.value = []
      plans.value = []
    }
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '加载 case 失败'
  } finally {
    loading.value = false
  }
}

async function selectCase(caseId: number) {
  try {
    const [detail, evidenceData, agentsData, plansData] = await Promise.all([
      casesApi.get(caseId),
      casesApi.getEvidence(caseId),
      casesApi.getAgents(caseId),
      casesApi.getPlans(caseId)
    ])
    selectedCase.value = detail
    evidence.value = evidenceData || []
    agentRuns.value = agentsData?.runs || []
    plans.value = plansData?.plans || []
    await loadGraphData(caseId)
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '加载 case 详情失败'
  }
}

async function loadGraphData(caseId: number) {
  const [runsResult, timelineResult, hypothesisResult] = await Promise.all([
    casesApi.getGraphRuns(caseId),
    casesApi.getTimeline(caseId),
    casesApi.getHypotheses(caseId)
  ])
  graphRuns.value = runsResult.items || []
  if (graphRuns.value.length > 0) {
    currentGraph.value = await casesApi.getGraphRun(caseId, graphRuns.value[0].graph_run_id)
    try {
      budget.value = await casesApi.getAgentBudget(caseId, currentGraph.value.graph_run_id)
    } catch (error: any) {
      if (error?.response?.status !== 404) throw error
      budget.value = null
    }
  } else {
    currentGraph.value = null
    budget.value = null
  }
  timeline.value = timelineResult.items || []
  hypotheses.value = hypothesisResult.items || []
}

async function startGraph() {
  if (!selectedCase.value) return
  startingGraph.value = true
  message.value = ''
  try {
    const accepted = await casesApi.runAgents(selectedCase.value.id)
    message.value = accepted.message || 'Agent Graph 已受理'
    await loadGraphData(selectedCase.value.id)
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '启动 Agent Graph 失败'
  } finally {
    startingGraph.value = false
  }
}

function formatTime(value?: string): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function hypothesisStatusClass(status: string): string {
  if (status === 'confirmed' || status === 'supported') return 'app-badge-success'
  if (status === 'rejected') return 'app-badge-danger'
  return 'app-badge-warning'
}

function budgetLabel(key: string): string {
  return ({
    agent_runs: 'Agent Run', llm_calls: 'LLM 调用', probe_calls: 'Probe 调用', tool_calls: '工具调用',
    replan_count: '重新规划', runtime_seconds: '运行秒数', target_devices: '目标设备'
  } as Record<string, string>)[key] || key
}

function budgetPercent(key: string): number {
  if (!budget.value?.limits?.[key]) return 0
  return Math.min(100, Math.round((budget.value.usage[key] / budget.value.limits[key]) * 100))
}

onMounted(async () => {
  await loadCases()
  pollTimer = window.setInterval(async () => {
    if (selectedCase.value && isGraphActive.value && !loading.value) {
      try {
        await loadGraphData(selectedCase.value.id)
        if (!isGraphActive.value) await selectCase(selectedCase.value.id)
      } catch {
        // Keep the last durable snapshot visible; the next poll retries.
      }
    }
  }, 2000)
})

onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

watch(
  () => route.query.caseId,
  async () => {
    const caseId = getRequestedCaseId()
    if (!caseId) return
    await selectCase(caseId)
  }
)
</script>

<style scoped>
.cases-filters {
  margin-top: -2px;
}

.cases-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
}

.case-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.case-card {
  width: 100%;
  text-align: left;
  cursor: pointer;
}

.case-card.active {
  border-color: rgba(15, 90, 224, 0.32);
  box-shadow: 0 18px 34px rgba(15, 90, 224, 0.14);
  background: linear-gradient(180deg, rgba(240, 247, 255, 0.96), rgba(255, 255, 255, 0.92));
}

.case-head,
.detail-item-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.case-title {
  margin-top: 10px;
  font-weight: 600;
}

.case-meta {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #5e738f;
  font-size: 12px;
}

.case-badge.status-open,
.case-badge.status-triaged,
.case-badge.status-investigating {
  background: rgba(59, 130, 246, 0.12);
  color: #0f5ae0;
}

.case-badge.status-planned {
  background: rgba(245, 158, 11, 0.14);
  color: #92400e;
}

.case-badge.status-resolved,
.case-badge.status-closed {
  background: rgba(34, 197, 94, 0.14);
  color: #166534;
}

.case-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.detail-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.run-agent-button { min-height: 44px; }
.graph-status { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.graph-status > div:first-child { display: flex; flex-direction: column; gap: 4px; }
.graph-status-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; color: #475569; }
.graph-id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.section-label { color: #64748b; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.section-heading h3 { margin: 3px 0 0; }
.diagnostic-grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(280px, .8fr); gap: 16px; }
.timeline-panel { grid-row: span 2; }
.timeline-list { list-style: none; margin: 0; padding: 0; }
.timeline-item { position: relative; display: grid; grid-template-columns: 18px 1fr; gap: 10px; padding: 0 0 18px; }
.timeline-item:not(:last-child)::before { content: ''; position: absolute; left: 6px; top: 12px; bottom: 0; width: 1px; background: #dbe4f0; }
.timeline-dot { position: relative; z-index: 1; width: 12px; height: 12px; margin-top: 4px; border-radius: 50%; background: #64748b; box-shadow: 0 0 0 4px #fff; }
.timeline-dot.event-case_state_transition { background: #0f5ae0; }
.timeline-dot.event-critic { background: #dc2626; }
.timeline-dot.event-evidence { background: #16a34a; }
.timeline-content { min-width: 0; }
.timeline-content time { color: #64748b; font-size: 12px; }
.timeline-content p { margin-top: 4px; color: #64748b; font-size: 12px; }
.timeline-content .timeline-reason { color: #334155; font-size: 13px; }
.hypothesis-list, .budget-list { display: flex; flex-direction: column; gap: 10px; }
.hypothesis-card p { margin-top: 8px; color: #475569; font-size: 13px; }
.confidence-row { display: grid; gap: 5px; margin-top: 12px; color: #475569; font-size: 12px; }
.progress-track { width: 100%; height: 7px; overflow: hidden; border-radius: 999px; background: #e8eef6; }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: #0f5ae0; transition: width 200ms ease; }
.evidence-counts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
.evidence-counts div { padding: 8px; border-radius: 10px; background: #f5f8fc; }
.evidence-counts dt { color: #64748b; font-size: 11px; }
.evidence-counts dd { margin: 3px 0 0; font-weight: 700; }
.critic-result { padding-top: 8px; border-top: 1px solid #e2e8f0; }
.budget-row > div:first-child { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; color: #475569; font-size: 13px; }
.budget-warning { color: #b91c1c; font-size: 13px; }

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.detail-card h3 {
  margin-bottom: 12px;
}

.detail-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-item p {
  margin-top: 8px;
  color: #43566f;
  font-size: 13px;
}

.detail-item-head span {
  white-space: nowrap;
}

@media (max-width: 1100px) {
  .cases-layout {
    grid-template-columns: 1fr;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }

  .diagnostic-grid { grid-template-columns: 1fr; }
  .timeline-panel { grid-row: auto; }
  .graph-status { align-items: flex-start; flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  .progress-track span { transition: none; }
}
</style>

<style scoped>
.case-card.active { background: var(--app-primary-soft); border-color: #9fb5ed; box-shadow: none; }
</style>
