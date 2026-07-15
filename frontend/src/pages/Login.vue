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
.login-page { min-height: 100vh; display: grid; place-items: center; padding: 24px; background: radial-gradient(circle at top, #17335f, #071120 58%); }
.login-card { width: min(440px, 100%); padding: 34px; border-radius: 24px; background: rgba(255,255,255,.97); box-shadow: 0 28px 80px rgba(0,0,0,.34); }
.login-brand { display: flex; align-items: center; gap: 14px; margin-bottom: 26px; }
.login-brand img { width: 52px; height: 52px; border-radius: 14px; }
.login-brand p, .login-brand h1 { margin: 0; }
.login-brand p { color: #2563eb; font-weight: 700; }
.login-brand h1 { margin-top: 3px; font-size: 24px; color: #0f172a; }
.provider-block { display: grid; gap: 9px; }
label, .sso-list span { color: #475569; font-size: 13px; font-weight: 700; }
input, select { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 10px; padding: 11px 12px; background: white; }
button { border: 0; border-radius: 10px; padding: 12px; color: white; background: #2563eb; font-weight: 700; cursor: pointer; }
button:disabled { opacity: .55; cursor: not-allowed; }
.sso-list { display: grid; gap: 10px; margin-top: 24px; padding-top: 20px; border-top: 1px solid #e2e8f0; }
.sso-button { color: #1e3a8a; background: #dbeafe; }
.login-error { padding: 10px 12px; border-radius: 10px; color: #b91c1c; background: #fee2e2; }
.login-empty { color: #64748b; text-align: center; }
</style>
