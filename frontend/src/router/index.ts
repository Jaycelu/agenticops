import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Layout from '@/components/Layout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: Layout,
    children: [
      {
        path: '',
        redirect: '/dashboard'
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/pages/Dashboard.vue')
      },
      {
        path: 'assets',
        name: 'Assets',
        component: () => import('@/pages/Assets.vue')
      },
      {
        path: 'alerts',
        name: 'Alerts',
        component: () => import('@/pages/Alerts.vue')
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
        name: 'AutomationDashboard',
        component: () => import('@/pages/automation/Dashboard.vue')
      },
      {
        path: 'automation/samples',
        name: 'AutomationSamples',
        component: () => import('@/pages/automation/Samples.vue')
      },
      {
        path: 'automation/tasks',
        name: 'AutomationTasks',
        component: () => import('@/pages/automation/Tasks.vue')
      },
      {
        path: 'automation/tasks/:id',
        name: 'AutomationTaskDetail',
        component: () => import('@/pages/automation/TaskDetail.vue')
      },
      {
        path: 'automation/analysis-results',
        name: 'AutomationAnalysisResults',
        component: () => import('@/pages/automation/AnalysisResults.vue')
      },
      {
        path: 'automation/policies',
        name: 'AutomationPolicies',
        component: () => import('@/pages/automation/Policies.vue')
      },
      {
        path: 'automation/audit',
        name: 'AutomationAudit',
        component: () => import('@/pages/automation/Audit.vue')
      },
      {
        path: 'automation/abnormal-types',
        name: 'AutomationAbnormalTypes',
        component: () => import('@/pages/automation/AbnormalTypes.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router