<template>
  <div class="zabbix-page app-page">
    <div class="app-page-header">
      <div class="app-page-title">
        <span class="app-page-title-icon">
          <Bell :size="24" />
        </span>
        <div class="app-page-copy">
          <h1>Zabbix 中心</h1>
        </div>
      </div>
      <div class="app-actions">
        <button class="app-button app-button-ghost" :disabled="syncing || !status.configured" @click="syncToEvents">
          {{ syncing ? '同步中...' : '同步到事件中心' }}
        </button>
        <button class="app-button app-button-secondary" :disabled="loading" @click="loadData">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <section class="app-grid-4">
      <article class="app-stat-card">
        <span class="app-kpi-label">配置状态</span>
        <strong class="app-kpi-value">{{ status.configured ? '已配置' : '未配置' }}</strong>
        <span class="app-kpi-sub">Zabbix</span>
      </article>
      <article class="app-stat-card">
        <span class="app-kpi-label">活跃告警</span>
        <strong class="app-kpi-value">{{ totalAlerts }}</strong>
        <span class="app-kpi-sub">当前窗口</span>
      </article>
      <article class="app-stat-card">
        <span class="app-kpi-label">高风险告警</span>
        <strong class="app-kpi-value">{{ highRiskCount }}</strong>
        <span class="app-kpi-sub">high / disaster</span>
      </article>
      <article class="app-stat-card">
        <span class="app-kpi-label">已确认</span>
        <strong class="app-kpi-value">{{ acknowledgedCount }}</strong>
        <span class="app-kpi-sub">已在 Zabbix 中 acknowledged</span>
      </article>
    </section>

    <section class="app-panel">
      <div class="app-section-header">
        <div class="app-page-copy">
          <h2>筛选</h2>
        </div>
        <div class="app-toolbar">
          <input v-model="hostFilter" class="app-input host-input" placeholder="按主机名筛选，如 core-sw-01" @keyup.enter="loadData" />
          <select v-model="limit" class="app-select limit-select" @change="loadData">
            <option :value="20">20 条</option>
            <option :value="50">50 条</option>
            <option :value="100">100 条</option>
          </select>
        </div>
      </div>
    </section>

    <section class="app-panel">
      <div class="app-section-header">
        <div class="app-page-copy">
          <h2>最近告警</h2>
          <p v-if="responseError" class="error-text">{{ responseError }}</p>
        </div>
        <div class="severity-summary" v-if="Object.keys(bySeverity).length > 0">
          <span v-for="(count, key) in bySeverity" :key="key" class="app-badge app-badge-neutral">
            {{ key }}: {{ count }}
          </span>
        </div>
      </div>

      <div v-if="loading" class="app-empty">加载中...</div>
      <div v-else-if="!status.configured" class="app-empty">
        <BellOff :size="42" />
        <p>Zabbix 未配置</p>
      </div>
      <div v-else-if="alerts.length === 0" class="app-empty">
        <Bell :size="42" />
        <p>暂无活跃告警</p>
      </div>
      <div v-else class="app-list">
        <article v-for="item in alerts" :key="item.event_id" class="app-card alert-card">
          <div class="alert-head">
            <div class="alert-copy">
              <strong>{{ item.name }}</strong>
              <p>{{ item.host_name || item.host || 'unknown-host' }}</p>
            </div>
            <div class="alert-badges">
              <span class="app-badge" :class="severityClass(item.severity)">{{ item.severity }}</span>
              <span class="app-badge" :class="item.acknowledged ? 'app-badge-success' : 'app-badge-warning'">
                {{ item.acknowledged ? 'acknowledged' : 'unacknowledged' }}
              </span>
            </div>
          </div>
          <div class="alert-meta">
            <span>Event ID: {{ item.event_id || '-' }}</span>
            <span>Object ID: {{ item.object_id || '-' }}</span>
            <span>发生时间: {{ formatTime(item.clock) }}</span>
          </div>
          <div v-if="item.linked_event" class="linked-panel">
            <span class="app-badge app-badge-primary">事件中心 #{{ item.linked_event.event_id }}</span>
            <span class="app-badge app-badge-neutral">分流: {{ item.linked_event.disposition || '-' }}</span>
            <span v-if="item.linked_event.case_code" class="app-badge app-badge-danger">Case: {{ item.linked_event.case_code }}</span>
            <span v-if="item.linked_event.ticket_id" class="app-badge app-badge-success">工单: {{ item.linked_event.ticket_id }}</span>
            <div class="linked-actions">
              <button class="app-button app-button-ghost" @click="openEvent(item.linked_event.event_id)">打开事件</button>
              <button v-if="item.linked_event.case_id" class="app-button app-button-secondary" @click="openCase(item.linked_event.case_id)">打开 Case</button>
            </div>
          </div>
          <div v-else class="linked-panel linked-empty">
            <span class="app-badge app-badge-warning">尚未同步到事件中心</span>
          </div>
        </article>
      </div>
    </section>

    <div v-if="message" class="app-message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, BellOff } from 'lucide-vue-next'
import { zabbixApi, type ZabbixAlertItem } from '@/api/zabbix'

const router = useRouter()
const loading = ref(false)
const syncing = ref(false)
const hostFilter = ref('')
const limit = ref(20)
const alerts = ref<ZabbixAlertItem[]>([])
const bySeverity = ref<Record<string, number>>({})
const responseError = ref('')
const message = ref('')
const status = ref({
  configured: false,
  source: 'zabbix',
  message: '',
})

const totalAlerts = computed(() => alerts.value.length)
const highRiskCount = computed(() => alerts.value.filter((item) => ['high', 'disaster'].includes(item.severity)).length)
const acknowledgedCount = computed(() => alerts.value.filter((item) => item.acknowledged).length)

function formatTime(value?: string | null): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function severityClass(severity: string): string {
  if (severity === 'disaster' || severity === 'high') return 'app-badge-danger'
  if (severity === 'average' || severity === 'warning') return 'app-badge-warning'
  if (severity === 'info') return 'app-badge-primary'
  return 'app-badge-neutral'
}

async function loadData() {
  loading.value = true
  responseError.value = ''
  try {
    const [statusRes, alertsRes] = await Promise.all([
      zabbixApi.getStatus(),
      zabbixApi.listAlerts({
        host: hostFilter.value || undefined,
        limit: Number(limit.value),
      })
    ])
    status.value = statusRes
    alerts.value = alertsRes.alerts || []
    bySeverity.value = alertsRes.by_severity || {}
    if (alertsRes.error) {
      responseError.value = alertsRes.error
    }
  } catch (error: any) {
    responseError.value = error?.response?.data?.detail || '加载 Zabbix 数据失败'
  } finally {
    loading.value = false
  }
}

async function syncToEvents() {
  syncing.value = true
  message.value = ''
  try {
    const result = await zabbixApi.syncAlerts({
      host: hostFilter.value || undefined,
      limit: Number(limit.value),
    })
    message.value = `已同步到事件中心：新增 ${result.created}，更新 ${result.updated}`
    await loadData()
    await router.push('/events')
  } catch (error: any) {
    message.value = error?.response?.data?.detail || '同步到事件中心失败'
  } finally {
    syncing.value = false
  }
}

function openEvent(eventId: number) {
  void router.push({
    path: '/events',
    query: { eventId: String(eventId) }
  })
}

function openCase(caseId: number) {
  void router.push({
    path: '/cases',
    query: { caseId: String(caseId) }
  })
}

onMounted(async () => {
  await loadData()
})
</script>

<style scoped>
.host-input {
  min-width: 260px;
}

.limit-select {
  min-width: 120px;
}

.severity-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.error-text {
  color: #b91c1c;
}

.alert-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.linked-panel {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  padding-top: 4px;
}

.linked-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.linked-empty {
  opacity: 0.9;
}

.alert-head,
.alert-meta,
.alert-badges {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: flex-start;
}

.alert-badges,
.alert-meta {
  flex-wrap: wrap;
}

.alert-copy p,
.alert-meta {
  color: #5e738f;
}

@media (max-width: 980px) {
  .alert-head,
  .alert-meta {
    flex-direction: column;
    align-items: flex-start;
  }

  .host-input,
  .limit-select {
    min-width: 100%;
  }

  .linked-actions {
    margin-left: 0;
    width: 100%;
  }
}
</style>
