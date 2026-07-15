import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Layout from '@/components/Layout.vue'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/auth/callback',
    name: 'AuthCallback',
    component: () => import('@/pages/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: Layout,
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/pages/Dashboard')
      },
      {
        path: 'dashboard',
        redirect: '/'
      },
      {
        path: 'assets',
        name: 'Assets',
        component: () => import('@/pages/Assets.vue')
      },
      {
        path: 'alerts',
        redirect: '/events'
      },
      {
        path: 'events',
        name: 'Events',
        component: () => import('@/pages/Events.vue')
      },
      {
        path: 'cases',
        name: 'Cases',
        component: () => import('@/pages/Cases.vue')
      },
      {
        path: 'agents',
        name: 'Agents',
        component: () => import('@/pages/Agents.vue')
      },
      {
        path: 'memories',
        name: 'Memories',
        component: () => import('@/pages/Memories.vue')
      },
      {
        path: 'fabric',
        name: 'Fabric',
        component: () => import('@/pages/Fabric.vue')
      },
      {
        path: 'tickets',
        name: 'Tickets',
        component: () => import('@/pages/Tickets.vue')
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/pages/Logs.vue')
      },
      {
        path: 'zabbix',
        name: 'Zabbix',
        component: () => import('@/pages/Zabbix.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/pages/Settings.vue')
      },
      {
        path: 'identity',
        name: 'IdentityAdmin',
        component: () => import('@/pages/IdentityAdmin.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (await auth.initialize()) return true
  return { name: 'Login', query: { redirect: to.fullPath } }
})

export default router
