<template>
  <div class="workspace-page app-page">
    <div class="page-header app-page-header">
      <div class="app-page-copy">
        <h1>执行中心</h1>
        <p>统一查看修复计划、执行运行记录和 Automation Fabric 总览。</p>
        <span v-if="requestedCaseId" class="app-badge app-badge-primary">聚焦 Case #{{ requestedCaseId }}</span>
      </div>
      <button class="app-button app-button-secondary" :disabled="loading" @click="loadData">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <section class="overview-grid">
      <article class="metric-card app-stat-card">
        <span class="app-kpi-label">计划总数</span>
        <strong class="app-kpi-value">{{ overview.total_plans }}</strong>
      </article>
      <article class="metric-card app-stat-card">
        <span class="app-kpi-label">已批准计划</span>
        <strong class="app-kpi-value">{{ overview.approved_plans }}</strong>
      </article>
      <article class="metric-card app-stat-card">
        <span class="app-kpi-label">失败执行</span>
        <strong class="app-kpi-value">{{ overview.failed_executions }}</strong>
      </article>
    </section>

    <div class="panel-grid">
      <section class="panel-card app-panel">
        <h2>最近计划</h2>
        <div v-if="plans.length === 0" class="empty app-empty">暂无计划</div>
        <div v-else class="card-list">
          <div v-for="plan in plans" :key="plan.id" class="info-card app-subcard">
            <div class="info-head">
              <strong>{{ plan.plan_code }}</strong>
              <span class="pill app-pill">{{ plan.status }}</span>
            </div>
            <p>{{ plan.summary || '暂无摘要' }}</p>
            <div class="meta-row">
              <span>{{ plan.execution_mode }}</span>
              <span>{{ plan.approval_status }}</span>
              <span>{{ plan.risk_level }}</span>
            </div>
            <div v-if="plan.plan_payload?.recommended_actions?.length" class="recommended-list">
              <div
                v-for="action in plan.plan_payload.recommended_actions.slice(0, 3)"
                :key="`${plan.id}-${action.priority_order}-${action.action_type}`"
                class="recommended-item"
              >
                <strong>{{ action.priority_order }}. {{ action.title }}</strong>
                <span>{{ action.reason }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="panel-card app-panel">
        <h2>最近执行</h2>
        <div v-if="executions.length === 0" class="empty app-empty">暂无执行记录</div>
        <div v-else class="card-list">
          <div v-for="item in executions" :key="item.id" class="info-card app-subcard">
            <div class="info-head">
              <strong>{{ item.executor_name }}</strong>
              <span class="pill app-pill">{{ item.status }}</span>
            </div>
            <p>{{ item.command_summary || '暂无命令摘要' }}</p>
            <div class="meta-row">
              <span>Case #{{ item.case_id }}</span>
              <span>{{ item.executor_type }}</span>
              <span>{{ formatTime(item.started_at) }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-if="message" class="message app-message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { fabricApi } from '@/api/fabric'

const route = useRoute()
const loading = ref(false)
const message = ref('')
const overview = ref({
  total_plans: 0,
  draft_plans: 0,
  approved_plans: 0,
  running_executions: 0,
  failed_executions: 0
})
const plans = ref<any[]>([])
const executions = ref<any[]>([])
const requestedCaseId = computed(() => {
  const raw = Array.isArray(route.query.caseId) ? route.query.caseId[0] : route.query.caseId
  const caseId = Number(raw)
  return Number.isInteger(caseId) && caseId > 0 ? caseId : null
})

function formatTime(value?: string): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

async function loadData() {
  loading.value = true
  message.value = ''
  try {
    const [overviewRes, plansRes, executionsRes] = await Promise.all([
      fabricApi.getOverview(),
      fabricApi.listPlans({ case_id: requestedCaseId.value || undefined, limit: 20 }),
      fabricApi.listExecutions({ case_id: requestedCaseId.value || undefined, limit: 20 })
    ])
    overview.value = overviewRes
    plans.value = plansRes.items || []
    executions.value = executionsRes.items || []
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '加载执行中心失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadData()
})

watch(
  () => route.query.caseId,
  async () => {
    await loadData()
  }
)
</script>

<style scoped>
.workspace-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header,
.info-head,
.meta-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.page-header {
  align-items: flex-start;
}

.overview-grid,
.panel-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.panel-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.info-card p {
  margin-top: 8px;
  color: #43566f;
}

.meta-row {
  margin-top: 10px;
  color: #5e738f;
  font-size: 13px;
  flex-wrap: wrap;
}

.recommended-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.recommended-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(15, 90, 224, 0.06);
}

.recommended-item strong {
  font-size: 13px;
}

.recommended-item span {
  color: #5e738f;
  font-size: 12px;
}

@media (max-width: 980px) {
  .overview-grid,
  .panel-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
