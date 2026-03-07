<template>
  <div class="workspace-page">
    <div class="page-header">
      <div>
        <h1>记忆中心</h1>
        <p>统一管理 episode、pattern、outcome 和 feedback 记忆。</p>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" :disabled="backfilling" @click="handleBackfill">
          {{ backfilling ? '回填中...' : '回填历史反馈' }}
        </button>
        <button class="btn-refresh" :disabled="loading" @click="loadData">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <section class="overview-grid">
      <article class="metric-card">
        <span>总记忆数</span>
        <strong>{{ overview.total_memories }}</strong>
      </article>
      <article class="metric-card">
        <span>高可信 Pattern</span>
        <strong>{{ overview.high_confidence_patterns }}</strong>
      </article>
      <article class="metric-card">
        <span>成功 Outcome</span>
        <strong>{{ overview.successful_outcomes }}</strong>
      </article>
    </section>

    <section class="panel-card">
      <div class="filter-row">
        <h2>记忆列表</h2>
        <select v-model="memoryType" class="filter-input" @change="loadData">
          <option value="">全部类型</option>
          <option value="episode">episode</option>
          <option value="pattern">pattern</option>
          <option value="outcome">outcome</option>
          <option value="feedback">feedback</option>
        </select>
      </div>
      <div v-if="items.length === 0" class="empty">暂无记忆</div>
      <div v-else class="memory-list">
        <div v-for="item in items" :key="item.id" class="memory-card">
          <div class="memory-head">
            <strong>{{ item.title }}</strong>
            <span class="pill">{{ item.memory_type }}</span>
          </div>
          <p>{{ item.summary || '暂无摘要' }}</p>
          <div class="memory-meta">
            <span>confidence {{ item.confidence }}</span>
            <span>success {{ item.success_score }}</span>
            <span>{{ item.source }}</span>
          </div>
        </div>
      </div>
    </section>

    <div v-if="message" class="message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { memoriesApi } from '@/api/memories'

const loading = ref(false)
const backfilling = ref(false)
const message = ref('')
const memoryType = ref('')
const overview = ref({
  total_memories: 0,
  by_type: {},
  high_confidence_patterns: 0,
  successful_outcomes: 0
})
const items = ref<any[]>([])

async function loadData() {
  loading.value = true
  message.value = ''
  try {
    const [overviewRes, listRes] = await Promise.all([
      memoriesApi.getOverview(),
      memoriesApi.list({ memory_type: memoryType.value || undefined, limit: 50 })
    ])
    overview.value = overviewRes
    items.value = listRes.items || []
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '加载记忆中心失败'
  } finally {
    loading.value = false
  }
}

async function handleBackfill() {
  backfilling.value = true
  message.value = ''
  try {
    const result = await memoriesApi.backfillFeedback(300)
    message.value = `回填完成，新增 ${result.created}，更新 ${result.updated}`
    await loadData()
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '反馈回填失败'
  } finally {
    backfilling.value = false
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
.header-actions,
.filter-row,
.memory-head,
.memory-meta {
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

.header-actions {
  align-items: center;
}

.btn-refresh,
.btn-secondary {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
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

.filter-input {
  min-width: 180px;
  height: 40px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0 12px;
}

.memory-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.memory-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
}

.memory-card p {
  margin-top: 8px;
  color: #475569;
}

.memory-meta {
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
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .page-header,
  .header-actions,
  .filter-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
