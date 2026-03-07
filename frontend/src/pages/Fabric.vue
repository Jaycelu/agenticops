<template>
  <div class="workspace-page">
    <div class="page-header">
      <div>
        <h1>执行中心</h1>
        <p>统一查看修复计划、执行运行记录和 Automation Fabric 总览。</p>
      </div>
      <button class="btn-refresh" :disabled="loading" @click="loadData">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <section class="overview-grid">
      <article class="metric-card">
        <span>计划总数</span>
        <strong>{{ overview.total_plans }}</strong>
      </article>
      <article class="metric-card">
        <span>已批准计划</span>
        <strong>{{ overview.approved_plans }}</strong>
      </article>
      <article class="metric-card">
        <span>失败执行</span>
        <strong>{{ overview.failed_executions }}</strong>
      </article>
    </section>

    <div class="panel-grid">
      <section class="panel-card">
        <h2>最近计划</h2>
        <div v-if="plans.length === 0" class="empty">暂无计划</div>
        <div v-else class="card-list">
          <div v-for="plan in plans" :key="plan.id" class="info-card">
            <div class="info-head">
              <strong>{{ plan.plan_code }}</strong>
              <span class="pill">{{ plan.status }}</span>
            </div>
            <p>{{ plan.summary || '暂无摘要' }}</p>
            <div class="meta-row">
              <span>{{ plan.execution_mode }}</span>
              <span>{{ plan.approval_status }}</span>
              <span>{{ plan.risk_level }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="panel-card">
        <h2>最近执行</h2>
        <div v-if="executions.length === 0" class="empty">暂无执行记录</div>
        <div v-else class="card-list">
          <div v-for="item in executions" :key="item.id" class="info-card">
            <div class="info-head">
              <strong>{{ item.executor_name }}</strong>
              <span class="pill">{{ item.status }}</span>
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

    <div v-if="message" class="message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fabricApi } from '@/api/fabric'

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
      fabricApi.listPlans({ limit: 20 }),
      fabricApi.listExecutions({ limit: 20 })
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

.page-header p {
  margin-top: 6px;
  color: #64748b;
}

.btn-refresh {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
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

.metric-card,
.panel-card {
  background: #fff;
  border: 1px solid #dbe2ea;
  border-radius: 18px;
  padding: 18px;
}

.metric-card span {
  color: #64748b;
}

.metric-card strong {
  display: block;
  margin-top: 10px;
  font-size: 30px;
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.info-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
}

.info-card p {
  margin-top: 8px;
  color: #475569;
}

.meta-row {
  margin-top: 10px;
  color: #64748b;
  font-size: 13px;
  flex-wrap: wrap;
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: #e2e8f0;
  border-radius: 999px;
  font-size: 12px;
}

.empty,
.message {
  color: #64748b;
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
