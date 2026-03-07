<template>
  <div class="dashboard-page">
    <div class="dashboard-shell">
      <section class="hero-card">
        <div>
          <h1>AgenticOps 驾驶舱</h1>
          <p>当前驾驶舱已经切到新架构口径，核心看板围绕 case、智能体、记忆与执行织物。</p>
        </div>
        <div class="hero-actions">
          <button class="btn-secondary" :disabled="loading" @click="loadDashboard">
            {{ loading ? '刷新中...' : '刷新驾驶舱' }}
          </button>
          <button class="btn-primary" @click="router.push('/cases')">进入 Case 中心</button>
        </div>
      </section>

      <section class="stats-grid">
        <article class="metric-card">
          <span class="metric-label">Case 总量</span>
          <strong class="metric-value">{{ caseOverview.total_cases }}</strong>
          <span class="metric-sub">高风险 {{ caseOverview.high_risk_cases }}</span>
        </article>
        <article class="metric-card">
          <span class="metric-label">处理中</span>
          <strong class="metric-value">{{ caseOverview.open_cases }}</strong>
          <span class="metric-sub">执行中 {{ caseOverview.executing_cases }}</span>
        </article>
        <article class="metric-card">
          <span class="metric-label">记忆条目</span>
          <strong class="metric-value">{{ memoryOverview.total_memories }}</strong>
          <span class="metric-sub">高可信 pattern {{ memoryOverview.high_confidence_patterns }}</span>
        </article>
        <article class="metric-card">
          <span class="metric-label">执行织物</span>
          <strong class="metric-value">{{ fabricOverview.total_plans }}</strong>
          <span class="metric-sub">失败执行 {{ fabricOverview.failed_executions }}</span>
        </article>
      </section>

      <section class="panel-grid">
        <article class="panel-card">
          <div class="panel-head">
            <h2>Case 阶段分布</h2>
            <span>按新 case 生命周期聚合</span>
          </div>
          <div v-if="phaseRows.length === 0" class="empty">暂无数据</div>
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

        <article class="panel-card">
          <div class="panel-head">
            <h2>智能体健康</h2>
            <span>四类运维智能体最近运行统计</span>
          </div>
          <div v-if="agentHealth.length === 0" class="empty">暂无运行记录</div>
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
      </section>

      <section class="panel-grid">
        <article class="panel-card">
          <div class="panel-head">
            <h2>最近 Case</h2>
            <span>优先关注最新进入链路的事件</span>
          </div>
          <div v-if="recentCases.length === 0" class="empty">暂无 case</div>
          <div v-else class="case-list">
            <button
              v-for="item in recentCases"
              :key="item.id"
              class="case-item"
              @click="router.push('/cases')"
            >
              <div class="case-item-head">
                <strong>{{ item.case_code }}</strong>
                <span>{{ item.status }}</span>
              </div>
              <div class="case-item-title">{{ item.title }}</div>
              <div class="case-item-meta">
                <span>{{ item.current_phase }}</span>
                <span>{{ item.device_ip || item.host || '-' }}</span>
              </div>
            </button>
          </div>
        </article>

        <article class="panel-card">
          <div class="panel-head">
            <h2>记忆与执行概览</h2>
            <span>是否形成持续迭代闭环</span>
          </div>
          <div class="summary-grid">
            <div class="summary-box">
              <span>成功 outcome</span>
              <strong>{{ memoryOverview.successful_outcomes }}</strong>
            </div>
            <div class="summary-box">
              <span>已批准计划</span>
              <strong>{{ fabricOverview.approved_plans }}</strong>
            </div>
            <div class="summary-box">
              <span>草案计划</span>
              <strong>{{ fabricOverview.draft_plans }}</strong>
            </div>
            <div class="summary-box">
              <span>运行中执行</span>
              <strong>{{ fabricOverview.running_executions }}</strong>
            </div>
          </div>
        </article>
      </section>

      <div v-if="message" class="message">{{ message }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { agentsApi } from '@/api/agents'
import { casesApi, type CaseSummary } from '@/api/cases'
import { fabricApi } from '@/api/fabric'
import { memoriesApi } from '@/api/memories'

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

function formatTime(value?: string): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

async function loadDashboard() {
  loading.value = true
  message.value = ''
  try {
    const [caseData, healthData, memoryData, fabricData, recentData] = await Promise.all([
      casesApi.getOverview(),
      agentsApi.getHealth(),
      memoriesApi.getOverview(),
      fabricApi.getOverview(),
      casesApi.list({ limit: 8 })
    ])
    caseOverview.value = caseData
    agentHealth.value = healthData.items || []
    memoryOverview.value = memoryData
    fabricOverview.value = fabricData
    recentCases.value = recentData.items || []
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
.dashboard-page {
  min-height: calc(100vh - 64px);
  background: linear-gradient(180deg, #eef4ff 0%, #f8fafc 36%, #eef2f7 100%);
  padding: 24px;
}

.dashboard-shell {
  max-width: 1320px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-card,
.metric-card,
.panel-card {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(14px);
}

.hero-card {
  border-radius: 24px;
  padding: 28px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
}

.hero-card p {
  margin-top: 8px;
  color: #64748b;
  max-width: 720px;
}

.hero-actions {
  display: flex;
  gap: 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.metric-card {
  border-radius: 20px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-label {
  color: #64748b;
  font-size: 13px;
}

.metric-value {
  font-size: 34px;
  line-height: 1;
}

.metric-sub {
  color: #334155;
  font-size: 13px;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel-card {
  border-radius: 22px;
  padding: 22px;
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
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #0f766e);
}

.agent-item,
.case-item {
  border: 1px solid #dbe2ea;
  border-radius: 14px;
  padding: 14px;
  background: #fff;
}

.agent-item p {
  color: #64748b;
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
  color: #334155;
  font-size: 13px;
}

.case-item {
  text-align: left;
  cursor: pointer;
}

.case-item-title {
  margin: 10px 0 8px;
  font-weight: 600;
}

.case-item-meta {
  color: #64748b;
  font-size: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary-box {
  border: 1px solid #dbe2ea;
  border-radius: 16px;
  padding: 18px;
  background: #fff;
}

.summary-box span {
  color: #64748b;
  font-size: 13px;
}

.summary-box strong {
  display: block;
  margin-top: 10px;
  font-size: 28px;
}

.empty,
.message {
  color: #64748b;
}

@media (max-width: 1100px) {
  .stats-grid,
  .panel-grid {
    grid-template-columns: 1fr;
  }

  .hero-card {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
