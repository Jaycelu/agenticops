import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import '@/api/http'
import { useAuthStore } from '@/stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

window.addEventListener('auth:unauthorized', () => {
  const auth = useAuthStore(pinia)
  auth.clear()
  if (router.currentRoute.value.name !== 'Login') {
    void router.replace({ name: 'Login', query: { redirect: router.currentRoute.value.fullPath } })
  }
})
app.mount('#app')
