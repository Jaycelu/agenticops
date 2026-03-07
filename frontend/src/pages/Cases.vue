<template>
  <div class="cases-page">
    <div class="cases-header">
      <div>
        <h1>Case 中心</h1>
        <p>统一查看故障 case、证据、智能体结论和修复计划。</p>
      </div>
      <button class="btn-refresh" :disabled="loading" @click="loadCases">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div class="cases-filters">
      <select v-model="statusFilter" class="filter-input" @change="loadCases">
        <option value="">全部状态</option>
        <option value="open">open</option>
        <option value="triaged">triaged</option>
        <option value="investigating">investigating</option>
        <option value="planned">planned</option>
        <option value="resolved">resolved</option>
        <option value="closed">closed</option>
      </select>
      <select v-model="phaseFilter" class="filter-input" @change="loadCases">
        <option value="">全部阶段</option>
        <option value="intake">intake</option>
        <option value="analysis">analysis</option>
        <option value="remediation_draft">remediation_draft</option>
      </select>
    </div>

    <div v-if="loading" class="state-block">加载中...</div>
    <div v-else-if="cases.length === 0" class="state-block">暂无 case</div>
    <div v-else class="cases-layout">
      <div class="case-list">
        <button
          v-for="item in cases"
          :key="item.id"
          class="case-card"
          :class="{ active: selectedCase?.id === item.id }"
          @click="selectCase(item.id)"
        >
          <div class="case-head">
            <strong>{{ item.case_code }}</strong>
            <span class="case-badge" :class="item.status">{{ item.status }}</span>
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
        <div class="detail-card">
          <div class="detail-head">
            <div>
              <h2>{{ selectedCase.title }}</h2>
              <p>{{ selectedCase.summary || '暂无摘要' }}</p>
            </div>
            <div class="detail-tags">
              <span class="pill">{{ selectedCase.case_code }}</span>
              <span class="pill">{{ selectedCase.status }}</span>
              <span class="pill">{{ selectedCase.current_phase }}</span>
            </div>
          </div>
        </div>

        <div class="detail-grid">
          <div class="detail-card">
            <h3>证据</h3>
            <div v-if="evidence.length === 0" class="mini-empty">暂无证据</div>
            <div v-else class="detail-list">
              <div v-for="item in evidence" :key="item.id" class="detail-item">
                <div class="detail-item-head">
                  <strong>{{ item.evidence_type }}</strong>
                  <span>{{ item.source_system }}</span>
                </div>
                <p>{{ item.summary || '-' }}</p>
              </div>
            </div>
          </div>

          <div class="detail-card">
            <h3>智能体输出</h3>
            <div v-if="agentRuns.length === 0" class="mini-empty">暂无运行记录</div>
            <div v-else class="detail-list">
              <div v-for="run in agentRuns" :key="run.id" class="detail-item">
                <div class="detail-item-head">
                  <strong>{{ run.agent_name }}</strong>
                  <span>{{ run.status }}</span>
                </div>
                <p v-if="run.claims?.[0]">{{ run.claims[0].claim_text }}</p>
                <p v-else>暂无 claim</p>
              </div>
            </div>
          </div>

          <div class="detail-card">
            <h3>修复计划</h3>
            <div v-if="plans.length === 0" class="mini-empty">暂无计划</div>
            <div v-else class="detail-list">
              <div v-for="plan in plans" :key="plan.id" class="detail-item">
                <div class="detail-item-head">
                  <strong>{{ plan.plan_code }}</strong>
                  <span>{{ plan.execution_mode }}</span>
                </div>
                <p>{{ plan.summary || '-' }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="message" class="message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
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
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '加载 case 详情失败'
  }
}

onMounted(async () => {
  await loadCases()
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
.cases-page {
  min-height: calc(100vh - 64px);
  background: #f5f7fa;
  padding: 24px;
}

.cases-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.cases-header p {
  color: #64748b;
  margin-top: 6px;
}

.btn-refresh {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
}

.cases-filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-input {
  min-width: 180px;
  height: 40px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0 12px;
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
  border: 1px solid #dbe2ea;
  background: #fff;
  border-radius: 14px;
  padding: 14px;
  cursor: pointer;
}

.case-card.active {
  border-color: #2563eb;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.12);
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
  color: #0f172a;
}

.case-meta {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.case-badge,
.pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  background: #e2e8f0;
  color: #334155;
  font-size: 12px;
}

.case-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-card {
  background: #fff;
  border: 1px solid #dbe2ea;
  border-radius: 16px;
  padding: 18px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.detail-head p {
  margin-top: 8px;
  color: #64748b;
}

.detail-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

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

.detail-item {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
}

.detail-item p {
  margin-top: 8px;
  color: #475569;
  font-size: 13px;
}

.state-block,
.mini-empty,
.message {
  color: #64748b;
}

@media (max-width: 1100px) {
  .cases-layout {
    grid-template-columns: 1fr;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
