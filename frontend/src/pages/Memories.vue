<template>
  <div class="workspace-page app-page">
    <div class="page-header app-page-header">
      <div class="app-page-copy">
        <h1>记忆中心</h1>
        <p>统一管理 episode、pattern、outcome 和 feedback 记忆。</p>
      </div>
      <div class="header-actions app-actions">
        <button class="app-button app-button-secondary" :disabled="loading" @click="loadData">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <section class="overview-grid">
      <article class="metric-card app-stat-card">
        <span class="app-kpi-label">总记忆数</span>
        <strong class="app-kpi-value">{{ overview.total_memories }}</strong>
      </article>
      <article class="metric-card app-stat-card">
        <span class="app-kpi-label">高可信 Pattern</span>
        <strong class="app-kpi-value">{{ overview.high_confidence_patterns }}</strong>
      </article>
      <article class="metric-card app-stat-card">
        <span class="app-kpi-label">成功 Outcome</span>
        <strong class="app-kpi-value">{{ overview.successful_outcomes }}</strong>
      </article>
    </section>

    <section class="panel-card app-panel">
      <div class="filter-row app-section-header">
        <h2>记忆列表</h2>
        <select v-model="memoryType" class="filter-input app-select" @change="loadData">
          <option value="">全部类型</option>
          <option value="episode">episode</option>
          <option value="pattern">pattern</option>
          <option value="outcome">outcome</option>
          <option value="feedback">feedback</option>
        </select>
      </div>
      <div v-if="items.length === 0" class="empty app-empty">暂无记忆</div>
      <div v-else class="memory-list">
        <div v-for="item in items" :key="item.id" class="memory-card app-subcard">
          <div class="memory-head">
            <strong>{{ item.title }}</strong>
            <span class="pill app-pill">{{ item.memory_type }}</span>
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

    <div v-if="message" class="message app-message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { memoriesApi } from '@/api/memories'

const loading = ref(false)
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

.header-actions {
  align-items: center;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.filter-input {
  min-width: 180px;
}

.memory-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.memory-card p {
  margin-top: 8px;
  color: #43566f;
}

.memory-meta {
  margin-top: 10px;
  color: #5e738f;
  font-size: 13px;
  flex-wrap: wrap;
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
