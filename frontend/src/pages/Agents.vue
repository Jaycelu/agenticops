<template>
  <div class="workspace-page">
    <div class="page-header">
      <div>
        <h1>智能体中心</h1>
        <p>查看多运维智能体的目录、健康度和最近运行情况。</p>
      </div>
      <button class="btn-refresh" :disabled="loading" @click="loadData">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div class="panel-grid">
      <section class="panel-card">
        <h2>智能体目录</h2>
        <div v-if="catalog.length === 0" class="empty">暂无目录数据</div>
        <div v-else class="card-list">
          <div v-for="item in catalog" :key="item.agent_type" class="info-card">
            <div class="info-head">
              <strong>{{ item.name }}</strong>
              <span class="pill">{{ item.agent_type }}</span>
            </div>
            <p>{{ item.purpose }}</p>
            <div class="meta-row">
              <span>输入: {{ item.inputs.join(' / ') }}</span>
            </div>
            <div class="meta-row">
              <span>输出: {{ item.outputs.join(' / ') }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="panel-card">
        <h2>健康度</h2>
        <div v-if="health.length === 0" class="empty">暂无运行记录</div>
        <div v-else class="card-list">
          <div v-for="item in health" :key="item.agent_type" class="info-card">
            <div class="info-head">
              <strong>{{ item.agent_type }}</strong>
              <span class="pill">{{ item.total_runs }} runs</span>
            </div>
            <div class="stats-row">
              <span>运行中 {{ item.running_runs }}</span>
              <span>失败 {{ item.failed_runs }}</span>
              <span>最近 {{ formatTime(item.last_run_at) }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <section class="panel-card">
      <h2>最近运行</h2>
      <div v-if="runs.length === 0" class="empty">暂无运行记录</div>
      <div v-else class="table-like">
        <div v-for="run in runs" :key="run.id" class="table-row">
          <div>
            <strong>{{ run.agent_name }}</strong>
            <p>Case #{{ run.case_id }}</p>
          </div>
          <span>{{ run.agent_type }}</span>
          <span>{{ run.status }}</span>
          <span>{{ run.duration_ms || 0 }} ms</span>
          <span>{{ formatTime(run.started_at) }}</span>
        </div>
      </div>
    </section>

    <div v-if="message" class="message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { agentsApi } from '@/api/agents'

const loading = ref(false)
const message = ref('')
const catalog = ref<any[]>([])
const health = ref<any[]>([])
const runs = ref<any[]>([])

function formatTime(value?: string): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

async function loadData() {
  loading.value = true
  message.value = ''
  try {
    const [catalogRes, healthRes, runsRes] = await Promise.all([
      agentsApi.getCatalog(),
      agentsApi.getHealth(),
      agentsApi.listRuns({ limit: 20 })
    ])
    catalog.value = catalogRes || []
    health.value = healthRes.items || []
    runs.value = runsRes.items || []
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '加载智能体中心失败'
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

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
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

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel-card {
  background: #fff;
  border: 1px solid #dbe2ea;
  border-radius: 18px;
  padding: 18px;
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

.info-head,
.stats-row,
.table-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.info-card p {
  margin-top: 8px;
  color: #475569;
}

.meta-row,
.stats-row {
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

.table-like {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.table-row {
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
}

.table-row p,
.empty,
.message {
  color: #64748b;
}

@media (max-width: 980px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }

  .table-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
