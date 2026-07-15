<template>
  <div class="page app-page">
    <div class="page-content">
      <div class="page-header app-page-header">
        <div class="app-page-copy">
          <h1>本地工单</h1>
        </div>
        <button class="app-button app-button-secondary" :disabled="loading" @click="loadTickets">刷新</button>
      </div>

      <div class="filter-section">
        <select v-model="statusFilter" class="filter-input app-select" @change="loadTickets">
          <option value="">全部状态</option>
          <option value="open">open</option>
          <option value="in_progress">in_progress</option>
          <option value="resolved">resolved</option>
          <option value="closed">closed</option>
        </select>
      </div>

      <div v-if="loading" class="loading app-empty">加载中...</div>
      <div v-else-if="tickets.length === 0" class="empty app-empty">暂无工单</div>
      <div v-else class="ticket-list">
        <div v-for="item in tickets" :key="item.ticket_code" class="ticket-card app-panel">
          <div class="card-head">
            <strong>{{ item.ticket_code }}</strong>
            <span class="status app-badge">{{ item.status }}</span>
          </div>
          <div class="card-body">
            <div class="title">{{ item.title }}</div>
            <div class="meta">优先级: {{ item.priority }} | 请求人: {{ item.requester }}</div>
            <div class="meta">事件ID: {{ item.event_id || '-' }} | SourceEvent: {{ item.source_event_id || '-' }} | 创建时间: {{ formatTime(item.created_at) }}</div>
          </div>
          <div class="card-actions">
            <select v-model="statusMap[item.ticket_code]" class="status-select app-select">
              <option value="open">open</option>
              <option value="in_progress">in_progress</option>
              <option value="resolved">resolved</option>
              <option value="closed">closed</option>
            </select>
            <button class="app-button app-button-primary" @click="updateStatus(item.ticket_code)">更新状态</button>
          </div>
        </div>
      </div>
      <div v-if="message" class="message app-message">{{ message }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ticketsApi, type LocalTicketItem } from '@/api/tickets'

const loading = ref(false)
const tickets = ref<LocalTicketItem[]>([])
const statusFilter = ref('')
const statusMap = ref<Record<string, string>>({})
const message = ref('')

function formatTime(value?: string): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

async function loadTickets() {
  loading.value = true
  message.value = ''
  try {
    const result = await ticketsApi.listTickets({
      status: statusFilter.value || undefined,
      limit: 200
    })
    tickets.value = result.tickets || []
    const nextMap: Record<string, string> = {}
    tickets.value.forEach((item) => {
      nextMap[item.ticket_code] = item.status
    })
    statusMap.value = nextMap
  } catch (e: any) {
    message.value = e?.response?.data?.detail || '加载工单失败'
  } finally {
    loading.value = false
  }
}

async function updateStatus(ticketCode: string) {
  const status = statusMap.value[ticketCode]
  if (!status) return
  try {
    const result = await ticketsApi.updateStatus(ticketCode, status, 'manual_update_from_ui')
    message.value = result.message
    await loadTickets()
  } catch (e: any) {
    message.value = e?.response?.data?.detail || '更新工单失败'
  }
}

onMounted(async () => {
  await loadTickets()
})
</script>

<style scoped>
.page-content {
  max-width: 1200px;
  margin: 0 auto;
}

.filter-section {
  margin-bottom: 16px;
}

.status-select {
  min-width: 180px;
}

.ticket-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.status {
  background: rgba(59, 130, 246, 0.12);
  color: #0f5ae0;
}

.title {
  font-weight: 600;
}

.meta {
  margin-top: 4px;
  color: #5e738f;
  font-size: 12px;
}

.card-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
