import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Layout from '@/components/Layout.vue'

const routes: RouteRecordRaw[] = [
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
        path: 'settings',
        name: 'Settings',
        component: () => import('@/pages/Settings.vue')
      },
      {
        path: 'automation',
        name: 'Automation',
        redirect: '/automation/dashboard'
      },
      {
        path: 'automation/dashboard',
        redirect: '/fabric'
      },
      {
        path: 'automation/samples',
        redirect: '/logs'
      },
      {
        path: 'automation/tasks',
        redirect: '/fabric'
      },
      {
        path: 'automation/tasks/:id',
        redirect: '/fabric'
      },
      {
        path: 'automation/analysis-results',
        redirect: '/cases'
      },
      {
        path: 'automation/policies',
        redirect: '/fabric'
      },
      {
        path: 'automation/audit',
        redirect: '/fabric'
      },
      {
        path: 'automation/abnormal-types',
        redirect: '/cases'
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
