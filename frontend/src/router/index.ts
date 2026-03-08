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
        path: 'zabbix',
        name: 'Zabbix',
        component: () => import('@/pages/Zabbix.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/pages/Settings.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
