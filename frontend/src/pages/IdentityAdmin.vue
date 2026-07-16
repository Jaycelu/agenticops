<template>
  <div class="admin-page">
    <header>
      <div>
        <p class="eyebrow">SECURITY CONTROL PLANE</p>
        <h1>身份与权限</h1>
        <p>配置 Local、OIDC、LDAP/AD、SAML 身份源及用户角色。密钥保存后不会回显。</p>
      </div>
      <button @click="reload">刷新</button>
    </header>

    <p v-if="message" class="message">{{ message }}</p>

    <section class="panel">
      <h2>身份源</h2>
      <div class="provider-create">
        <input v-model.trim="newProvider.key" placeholder="provider key，例如 corp-oidc" />
        <select v-model="newProvider.type">
          <option value="local">Local</option><option value="oidc">OIDC</option>
          <option value="ldap">LDAP / AD</option><option value="saml">SAML</option>
        </select>
        <input v-model.trim="newProvider.name" placeholder="显示名称" />
        <button @click="createProvider">新增</button>
      </div>
      <article v-for="provider in providerForms" :key="provider.provider_key" class="provider-card">
        <div class="card-title">
          <strong>{{ provider.display_name }}</strong>
          <code>{{ provider.provider_key }} · {{ provider.provider_type }}</code>
          <label><input v-model="provider.enabled" type="checkbox" /> 启用</label>
        </div>
        <label>显示名称<input v-model="provider.display_name" /></label>
        <label>公开配置 JSON<textarea v-model="provider.configJson" rows="6" /></label>
        <label>组到角色映射 JSON<textarea v-model="provider.mappingJson" rows="4" /></label>
        <label>本次更新的密钥 JSON<textarea v-model="provider.secretsJson" rows="3" placeholder='例如 {"client_secret":"..."}' /></label>
        <small>已配置密钥：{{ Object.keys(provider.secret_status).filter((key) => provider.secret_status[key]).join(', ') || '无' }}</small>
        <button @click="saveProvider(provider)">保存身份源</button>
      </article>
    </section>

    <section class="panel">
      <h2>用户与手工角色</h2>
      <article v-for="user in users" :key="user.id" class="user-row">
        <div><strong>{{ user.display_name }}</strong><code>{{ user.username }}</code></div>
        <label><input v-model="user.active" type="checkbox" /> 启用</label>
        <div class="roles">
          <label v-for="role in roles" :key="role">
            <input v-model="manualRoles[user.id]" type="checkbox" :value="role" /> {{ role }}
          </label>
        </div>
        <button @click="saveUser(user)">保存用户</button>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { identityAdminApi, type IdentityProviderView, type UserView } from '@/api/identityAdmin'

type ProviderForm = IdentityProviderView & { configJson: string; mappingJson: string; secretsJson: string }
const providerForms = ref<ProviderForm[]>([])
const users = ref<UserView[]>([])
const manualRoles = reactive<Record<number, string[]>>({})
const roles = ['viewer', 'operator', 'approver', 'executor', 'admin']
const message = ref('')
const newProvider = reactive({ key: '', type: 'oidc', name: '' })

function toForm(item: IdentityProviderView): ProviderForm {
  return {
    ...item,
    configJson: JSON.stringify(item.config, null, 2),
    mappingJson: JSON.stringify(item.group_role_mapping, null, 2),
    secretsJson: '{}'
  }
}

async function reload() {
  message.value = ''
  try {
    providerForms.value = (await identityAdminApi.providers()).map(toForm)
    users.value = await identityAdminApi.users()
    users.value.forEach((user) => {
      manualRoles[user.id] = user.roles.filter((role) => !role.provider_id).map((role) => role.role)
    })
  } catch {
    message.value = '加载失败：当前账号可能没有身份管理权限。'
  }
}

async function createProvider() {
  if (!newProvider.key || !newProvider.name) return
  await identityAdminApi.saveProvider(newProvider.key, {
    provider_type: newProvider.type,
    display_name: newProvider.name,
    enabled: false,
    config: {}, secrets: {}, clear_secrets: [], group_role_mapping: {}
  })
  newProvider.key = ''; newProvider.name = ''
  await reload()
}

async function saveProvider(provider: ProviderForm) {
  try {
    await identityAdminApi.saveProvider(provider.provider_key, {
      provider_type: provider.provider_type,
      display_name: provider.display_name,
      enabled: provider.enabled,
      config: JSON.parse(provider.configJson),
      secrets: JSON.parse(provider.secretsJson),
      clear_secrets: [],
      group_role_mapping: JSON.parse(provider.mappingJson)
    })
    message.value = `身份源 ${provider.provider_key} 已保存。`
    await reload()
  } catch {
    message.value = `身份源 ${provider.provider_key} 保存失败，请检查 JSON 和必填配置。`
  }
}

async function saveUser(user: UserView) {
  try {
    await identityAdminApi.saveUser(user.id, {
      active: user.active,
      display_name: user.display_name,
      email: user.email || null,
      manual_roles: manualRoles[user.id] || []
    })
    message.value = `用户 ${user.username} 已保存。`
    await reload()
  } catch {
    message.value = `用户 ${user.username} 保存失败。`
  }
}

onMounted(reload)
</script>

<style scoped>
.admin-page { display: grid; gap: 20px; color: #0f172a; }
header { display: flex; justify-content: space-between; gap: 20px; align-items: start; }
h1, h2, p { margin-top: 0; } .eyebrow { color: #2563eb; font-weight: 800; letter-spacing: .08em; }
.panel { padding: 18px; border: 1px solid var(--app-border); border-radius: var(--app-radius-md); background: var(--app-surface); }
.provider-create { display: grid; grid-template-columns: 1fr 160px 1fr auto; gap: 10px; margin-bottom: 18px; }
.provider-card, .user-row { display: grid; gap: 12px; padding: 14px; margin-top: 10px; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); }
.card-title, .user-row > div:first-child { display: flex; align-items: center; gap: 12px; } code { color: #64748b; }
label { display: grid; gap: 6px; color: #475569; font-size: 13px; font-weight: 700; }
input, select, textarea { box-sizing: border-box; width: 100%; padding: 9px 10px; border: 1px solid #cbd5e1; border-radius: 9px; font: inherit; }
input[type='checkbox'] { width: auto; } textarea { font-family: ui-monospace, monospace; font-weight: 400; }
button { padding: 9px 14px; border: 0; border-radius: 9px; color: white; background: #2563eb; cursor: pointer; }
.roles { display: flex; flex-wrap: wrap; gap: 14px; } .roles label { display: flex; align-items: center; }
.message { padding: 10px 14px; border-radius: 10px; background: #dbeafe; color: #1e3a8a; }
@media (max-width: 900px) { .provider-create { grid-template-columns: 1fr; } }
</style>
