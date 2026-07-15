<template>
  <div class="workspace-page app-page">
    <div class="page-header app-page-header">
      <div class="app-page-copy">
        <h1>执行中心</h1>
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
            <textarea
              v-if="plan.approval_status === 'pending' && canApprove"
              v-model="approvalComments[plan.id]"
              class="approval-comment"
              placeholder="审批意见（拒绝时建议必填）"
              maxlength="4000"
            />
            <div class="plan-actions">
              <button
                v-if="plan.status === 'draft' && canRequestApproval"
                class="app-button app-button-secondary"
                :disabled="actingPlanId === plan.id"
                @click="initiateApproval(plan)"
              >提交审批</button>
              <template v-if="plan.approval_status === 'pending' && canApprove">
                <button class="app-button app-button-primary" :disabled="actingPlanId === plan.id" @click="decide(plan, 'approved')">批准</button>
                <button class="app-button app-button-danger" :disabled="actingPlanId === plan.id" @click="decide(plan, 'rejected')">拒绝</button>
              </template>
              <button
                v-if="plan.approval_status === 'approved' && canExecute"
                class="app-button app-button-primary"
                :disabled="actingPlanId === plan.id"
                @click="execute(plan)"
              >执行已冻结方案</button>
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
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
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
const actingPlanId = ref<number | null>(null)
const approvalComments = ref<Record<number, string>>({})
const canRequestApproval = computed(() => auth.user?.permissions.includes('approvals.request'))
const canApprove = computed(() => auth.user?.permissions.includes('approvals.decide'))
const canExecute = computed(() => auth.user?.permissions.includes('executions.run'))
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

async function withPlanAction(planId: number, action: () => Promise<any>) {
  actingPlanId.value = planId
  message.value = ''
  try {
    const result = await action()
    const successMessage = result.message || (result.success ? '操作成功' : '操作未成功')
    await loadData()
    message.value = successMessage
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '操作失败'
  } finally {
    actingPlanId.value = null
  }
}

async function initiateApproval(plan: any) {
  await withPlanAction(plan.id, () => fabricApi.initiateApproval(plan.id, plan.risk_level))
}

async function decide(plan: any, decision: 'approved' | 'rejected') {
  await withPlanAction(plan.id, () => fabricApi.decideApproval(
    plan.id,
    decision,
    approvalComments.value[plan.id] || ''
  ))
}

async function execute(plan: any) {
  await withPlanAction(plan.id, () => fabricApi.executePlan(plan.id, crypto.randomUUID()))
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

.approval-comment { width: 100%; min-height: 72px; box-sizing: border-box; margin-top: 12px; padding: 10px; border: 1px solid #cbd5e1; border-radius: 10px; resize: vertical; }
.plan-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }

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
