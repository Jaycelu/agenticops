<template>
  <main class="login-page">
    <section class="login-card">
      <div class="login-brand">
        <img src="/agenticops.jpg" alt="AgenticOps" />
        <div>
          <p>AgenticOps</p>
          <h1>统一身份认证</h1>
        </div>
      </div>

      <p v-if="callbackFailed" class="login-error">单点登录失败，请重新选择身份源。</p>
      <p v-if="error" class="login-error">{{ error }}</p>

      <div v-if="credentialProviders.length" class="provider-block">
        <label for="provider">身份源</label>
        <select id="provider" v-model="selectedProvider">
          <option v-for="provider in credentialProviders" :key="provider.key" :value="provider.key">
            {{ provider.display_name }}
          </option>
        </select>
        <label for="username">用户名</label>
        <input id="username" v-model.trim="username" autocomplete="username" />
        <label for="password">密码</label>
        <input id="password" v-model="password" type="password" autocomplete="current-password" @keyup.enter="submit" />
        <button :disabled="auth.loading || !username || !password" @click="submit">
          {{ auth.loading ? '正在认证…' : '登录' }}
        </button>
      </div>

      <div v-if="redirectProviders.length" class="sso-list">
        <span>企业单点登录</span>
        <button
          v-for="provider in redirectProviders"
          :key="provider.key"
          class="sso-button"
          @click="auth.startRedirect(provider.key)"
        >
          {{ provider.display_name }}
        </button>
      </div>

      <p v-if="!auth.providers.length && !loadingProviders" class="login-empty">
        尚未启用身份源，请先运行管理员初始化命令。
      </p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const selectedProvider = ref('')
const error = ref('')
const loadingProviders = ref(true)
const callbackFailed = computed(() => route.query.status === 'failed')
const credentialProviders = computed(() => auth.providers.filter((item) => item.flow === 'credentials'))
const redirectProviders = computed(() => auth.providers.filter((item) => item.flow === 'redirect'))

function safeRedirect(value: unknown): string {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : '/'
}

onMounted(async () => {
  if (route.query.status === 'success' && await auth.initialize(true)) {
    await router.replace(safeRedirect(route.query.redirect))
    return
  }
  try {
    await auth.loadProviders()
    selectedProvider.value = credentialProviders.value[0]?.key || ''
  } catch {
    error.value = '无法加载身份源，请检查后端服务。'
  } finally {
    loadingProviders.value = false
  }
})

async function submit() {
  error.value = ''
  try {
    await auth.login(selectedProvider.value, username.value, password.value)
    await router.replace(safeRedirect(route.query.redirect))
  } catch {
    error.value = '用户名、密码或身份源无效。'
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #111827;
}

.login-card {
  width: min(420px, 100%);
  padding: 30px;
  background: var(--app-surface);
  border: 1px solid #303b4d;
  border-radius: var(--app-radius-lg);
  box-shadow: var(--app-shadow-lg);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--app-border);
}

.login-brand img {
  width: 44px;
  height: 44px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

.login-brand p,
.login-brand h1 { margin: 0; }
.login-brand p { color: var(--app-primary); font-size: 13px; font-weight: 700; }
.login-brand h1 { margin-top: 2px; color: var(--app-text); font-size: 22px; }
.provider-block { display: grid; gap: 8px; }

label,
.sso-list span {
  color: var(--app-text-soft);
  font-size: 13px;
  font-weight: 600;
}

input,
select {
  width: 100%;
  min-height: 44px;
  padding: 9px 12px;
  color: var(--app-text);
  background: #fff;
  border: 1px solid var(--app-border-strong);
  border-radius: var(--app-radius-sm);
}

input:focus,
select:focus {
  outline: none;
  border-color: var(--app-primary);
  box-shadow: var(--app-focus);
}

button {
  min-height: 44px;
  padding: 10px 12px;
  color: #fff;
  background: var(--app-primary);
  border: 1px solid var(--app-primary);
  border-radius: var(--app-radius-sm);
  font-weight: 700;
  cursor: pointer;
  transition: background var(--app-transition-fast), border-color var(--app-transition-fast);
}

button:hover:not(:disabled) { background: var(--app-primary-strong); border-color: var(--app-primary-strong); }
button:disabled { opacity: .52; cursor: not-allowed; }
.sso-list { display: grid; gap: 9px; margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--app-border); }
.sso-button { color: #234aa9; background: var(--app-primary-soft); border-color: #d7e1ff; }
.sso-button:hover:not(:disabled) { background: #dce6ff; border-color: #c5d3fb; }
.login-error { padding: 10px 12px; margin-bottom: 14px; color: #a62828; background: var(--app-danger-soft); border: 1px solid #f0cccc; border-radius: var(--app-radius-sm); }
.login-empty { color: var(--app-text-muted); text-align: center; }

@media (max-width: 480px) {
  .login-page { padding: 12px; }
  .login-card { padding: 22px; }
}
</style>
