<template>
  <div class="automation-policies">
    <div class="page-header">
      <h1>自动化策略管理</h1>
      <button class="add-btn">
        <Plus :size="16" />
        新建策略
      </button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="policies.length" class="policies-list">
      <div v-for="policy in policies" :key="policy.id" class="policy-card">
        <div class="policy-header">
          <div class="policy-name">{{ policy.policy_name }}</div>
          <div class="policy-status" :class="{ enabled: policy.enabled }">
            {{ policy.enabled ? '已启用' : '已禁用' }}
          </div>
        </div>
        <div class="policy-body">
          <div class="policy-info">
            <span class="policy-type">{{ policy.policy_type }}</span>
            <span class="policy-risk" :class="policy.risk_level">
              {{ policy.risk_level }}
            </span>
          </div>
          <div class="policy-meta">
            <span>触发方式: {{ policy.trigger_type }}</span>
            <span>需要确认: {{ policy.require_confirm ? '是' : '否' }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="no-data">暂无策略</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import { getAutomationPolicies } from '@/api/automation'

const policies = ref<any[]>([])
const loading = ref(false)

const loadPolicies = async () => {
  loading.value = true
  try {
    const data = await getAutomationPolicies({ limit: 50 })
    policies.value = data.policies || []
  } catch (error) {
    console.error('Failed to load policies:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadPolicies()
})
</script>

<style scoped>
.automation-policies {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: #4a9eff;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.add-btn:hover {
  background: #3a8eef;
}

.loading, .no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
}

.policies-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.policy-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.policy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.policy-name {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
}

.policy-status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: #f5f5f5;
  color: #999;
}

.policy-status.enabled {
  background: #e8f5e9;
  color: #4caf50;
}

.policy-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.policy-info {
  display: flex;
  gap: 12px;
}

.policy-type {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: #e3f2fd;
  color: #2196f3;
}

.policy-risk {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: #f5f5f5;
  color: #666;
}

.policy-risk.low {
  background: #e8f5e9;
  color: #4caf50;
}

.policy-risk.medium {
  background: #fff3e0;
  color: #ff9800;
}

.policy-risk.high {
  background: #ffebee;
  color: #f44336;
}

.policy-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #999;
}
</style>