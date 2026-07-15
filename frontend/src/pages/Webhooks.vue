<template>
  <div class="app-page webhook-page">
    <div class="app-page-header">
      <div><h1>通用 Webhook</h1><p>事务 Outbox、HMAC 签名、重试与死信管理</p></div>
      <button class="app-button app-button-secondary" @click="load">刷新</button>
    </div>

    <section class="app-panel editor">
      <h2>{{ form.id ? '编辑 Endpoint' : '新增 Endpoint' }}</h2>
      <div class="form-grid">
        <label>名称<input v-model.trim="form.name" /></label>
        <label>HTTPS URL<input v-model.trim="form.url" placeholder="https://hooks.example.com/agenticops" /></label>
        <label>订阅事件（逗号分隔）<input v-model.trim="form.eventTypes" placeholder="approval.requested,approval.approved,execution.failed" /></label>
        <label>HMAC Secret<input v-model="form.secret" type="password" :placeholder="form.id ? '留空表示不轮换' : '至少 24 个字符'" /></label>
        <label>超时秒数<input v-model.number="form.timeout_seconds" type="number" min="1" max="30" /></label>
        <label>最大尝试次数<input v-model.number="form.max_attempts" type="number" min="1" max="20" /></label>
      </div>
      <label class="checkbox"><input v-model="form.enabled" type="checkbox" />启用</label>
      <div class="actions"><button class="app-button app-button-primary" :disabled="saving" @click="save">保存</button><button class="app-button app-button-secondary" @click="reset">清空</button></div>
    </section>

    <section class="app-panel">
      <h2>Endpoints</h2>
      <div class="card-list">
        <article v-for="item in endpoints" :key="item.id" class="app-subcard endpoint-card">
          <div><strong>{{ item.name }}</strong><p>{{ item.url }}</p><small>Secret 指纹 {{ item.secret_fingerprint }} · {{ item.event_types.join(', ') }}</small></div>
          <div class="actions"><button class="app-button app-button-secondary" @click="edit(item)">编辑</button><button class="app-button app-button-secondary" @click="testEndpoint(item.id)">测试</button></div>
        </article>
      </div>
    </section>

    <section class="app-panel">
      <div class="section-head"><h2>投递记录</h2><select v-model="deliveryStatus" @change="loadDeliveries"><option value="">全部</option><option value="pending">待投递</option><option value="retry">重试</option><option value="dead">死信</option><option value="delivered">已送达</option></select></div>
      <div class="card-list">
        <article v-for="item in deliveries" :key="item.id" class="app-subcard delivery-card">
          <div><strong>{{ item.event_type }}</strong><p>{{ item.event_id }}</p><small>{{ item.status }} · 尝试 {{ item.attempt_count }} · HTTP {{ item.last_http_status || '-' }} · {{ item.last_error_code || '-' }}</small></div>
          <button v-if="['dead','delivered'].includes(item.status)" class="app-button app-button-secondary" @click="redeliver(item.id)">重新投递</button>
        </article>
      </div>
    </section>
    <p v-if="message" class="app-message">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { webhooksApi } from '@/api/webhooks'

const endpoints = ref<any[]>([])
const deliveries = ref<any[]>([])
const deliveryStatus = ref('')
const saving = ref(false)
const message = ref('')
const blank = () => ({ id: 0, name: '', url: '', eventTypes: '*', secret: '', enabled: true, timeout_seconds: 10, max_attempts: 8 })
const form = reactive(blank())

function reset() { Object.assign(form, blank()) }
function edit(item: any) { Object.assign(form, { ...item, eventTypes: item.event_types.join(','), secret: '' }) }
async function loadDeliveries() { deliveries.value = (await webhooksApi.deliveries(deliveryStatus.value || undefined)).items || [] }
async function load() {
  try { endpoints.value = (await webhooksApi.endpoints()).items || []; await loadDeliveries() }
  catch (error: any) { message.value = error?.response?.data?.detail || '加载失败' }
}
async function save() {
  saving.value = true; message.value = ''
  try {
    await webhooksApi.save(form.id, {
      name: form.name, url: form.url, enabled: form.enabled,
      event_types: form.eventTypes.split(',').map((item) => item.trim()).filter(Boolean),
      secret: form.secret || null, timeout_seconds: form.timeout_seconds, max_attempts: form.max_attempts
    })
    reset(); await load(); message.value = 'Endpoint 已保存'
  } catch (error: any) { message.value = error?.response?.data?.detail || '保存失败' }
  finally { saving.value = false }
}
async function testEndpoint(id: number) { const result = await webhooksApi.test(id); message.value = `测试事件已入队：${result.event_id}`; await loadDeliveries() }
async function redeliver(id: number) { await webhooksApi.redeliver(id); message.value = '已重新入队'; await loadDeliveries() }
onMounted(load)
</script>

<style scoped>
.webhook-page { display: grid; gap: 16px; }
.app-page-header,.endpoint-card,.delivery-card,.section-head,.actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
label { display: grid; gap: 6px; color: #475569; font-size: 13px; font-weight: 700; }
input,select { border: 1px solid #cbd5e1; border-radius: 9px; padding: 9px 10px; background: white; }
.checkbox { display: flex; margin: 12px 0; }
.card-list { display: grid; gap: 10px; margin-top: 12px; }
.endpoint-card p,.delivery-card p { margin: 5px 0; color: #475569; overflow-wrap: anywhere; }
small { color: #64748b; }
@media(max-width:900px){.form-grid{grid-template-columns:1fr}.endpoint-card,.delivery-card{align-items:flex-start;flex-direction:column}}
</style>
