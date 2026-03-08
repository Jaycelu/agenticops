<template>
  <div class="cases-page app-page">
    <div class="cases-header app-page-header">
      <div class="app-page-copy">
        <h1>Case 中心</h1>
        <p>统一查看故障 case、证据、智能体结论和修复计划。</p>
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
            </div>
          </div>
        </div>

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
      </div>
    </div>

    <div v-if="message" class="message app-message">{{ message }}</div>
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
}
</style>
