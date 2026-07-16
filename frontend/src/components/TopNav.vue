<template>
  <aside class="sidebar-nav" aria-label="主导航">
    <div class="nav-logo">
      <img src="/agenticops.jpg" alt="AgenticOps" class="logo-icon" />
      <div class="brand-copy">
        <strong>AgenticOps</strong>
        <span>智能运维控制台</span>
      </div>
    </div>

    <div class="nav-sections">
      <div class="nav-section" v-for="section in navSections" :key="section.title">
        <span class="section-title">{{ section.title }}</span>
        <nav class="nav-menu" :aria-label="section.title">
          <router-link
            v-for="item in section.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            exact-active-class="active"
          >
            <component :is="item.icon" :size="18" />
            <div class="nav-copy">
              <span>{{ item.label }}</span>
            </div>
          </router-link>
        </nav>
      </div>
    </div>

    <div class="sidebar-foot">
      <div class="user-row">
        <span class="user-avatar" aria-hidden="true">{{ userInitial }}</span>
        <div class="user-copy">
          <strong>{{ auth.user?.display_name || auth.user?.username }}</strong>
          <p>{{ auth.user?.roles.join(' / ') || '已认证用户' }}</p>
        </div>
      </div>
      <button class="logout-button" @click="logout">退出登录</button>
      <span class="sidebar-version">{{ appVersion }}</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import packageJson from '../../package.json'
import {
  Activity,
  Bell,
  Brain,
  House,
  MemoryStick,
  Radio,
  Server,
  Settings,
  ShieldCheck,
  Ticket,
  FileText
} from 'lucide-vue-next'

type NavItem = {
  path: string
  label: string
  icon: typeof House
  permission?: string
}

type NavSection = { title: string; items: NavItem[] }

const rawNavSections: NavSection[] = [
  {
    title: '指挥层',
    items: [
      { path: '/', label: '驾驶舱', icon: House },
      { path: '/cases', label: 'Case 中心', icon: Activity },
      { path: '/fabric', label: '执行中心', icon: ShieldCheck }
    ]
  },
  {
    title: '智能层',
    items: [
      { path: '/agents', label: '智能体中心', icon: Brain },
      { path: '/memories', label: '记忆中心', icon: MemoryStick }
    ]
  },
  {
    title: '观测层',
    items: [
      { path: '/events', label: '事件中心', icon: Radio },
      { path: '/logs', label: '日志中心', icon: FileText },
      { path: '/zabbix', label: 'Zabbix 中心', icon: Bell },
      { path: '/assets', label: '资产拓扑', icon: Server },
      { path: '/tickets', label: '工单', icon: Ticket },
      { path: '/settings', label: '设置', icon: Settings },
      { path: '/identity', label: '身份与权限', icon: ShieldCheck, permission: 'identities.manage' },
      { path: '/webhooks', label: 'Webhook', icon: Radio, permission: 'webhooks.manage' }
    ]
  }
]

const auth = useAuthStore()
const router = useRouter()
const userInitial = computed(() => (auth.user?.display_name || auth.user?.username || 'U').slice(0, 1).toUpperCase())
const navSections = computed(() => rawNavSections.map((section) => ({
  ...section,
  items: section.items.filter((item) => !item.permission || auth.user?.permissions.includes(item.permission))
})).filter((section) => section.items.length > 0))

async function logout() {
  await auth.logout()
  await router.replace({ name: 'Login' })
}

const appVersion = `v${packageJson.version}`
</script>

<style scoped>
.sidebar-nav {
  position: sticky;
  top: 0;
  width: 232px;
  height: 100vh;
  flex: 0 0 232px;
  min-height: 100vh;
  overflow-y: auto;
  color: #f8fafc;
  background: #111827;
  border-right: 1px solid #263244;
  padding: 18px 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 8px 16px;
  border-bottom: 1px solid #263244;
}

.nav-logo strong {
  display: block;
  font-size: 16px;
  line-height: 1.2;
  color: #f8fafc;
}

.brand-copy span {
  display: block;
  margin-top: 3px;
  color: #8f9bad;
  font-size: 12px;
}

.logo-icon {
  width: 34px;
  height: 34px;
  border: 1px solid #354157;
  border-radius: 6px;
}

.nav-sections {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 16px;
}

.logout-button {
  min-height: 36px;
  padding: 6px 10px;
  color: #b9c2cf;
  background: transparent;
  border: 1px solid #354157;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.16s ease, border-color 0.16s ease, background 0.16s ease;
}

.logout-button:hover {
  color: #fff;
  background: #1b2535;
  border-color: #536078;
}

.nav-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-title {
  padding: 0 10px;
  color: #778397;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  min-height: 42px;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  color: #aeb8c7;
  text-decoration: none;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  position: relative;
  transition: background 0.16s ease, color 0.16s ease;
}

.nav-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.nav-item:hover {
  color: #f8fafc;
  background: #1b2535;
}

.nav-item.active {
  color: #fff;
  background: #233251;
  border-color: #30456d;
  font-weight: 600;
}

.nav-item.active::after {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: #6f94ff;
  border-radius: 2px;
}

.sidebar-foot {
  display: grid;
  gap: 10px;
  padding: 12px 8px 0;
  border-top: 1px solid #263244;
}

.user-row {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
}

.user-avatar {
  display: inline-flex;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  align-items: center;
  justify-content: center;
  color: #dfe7ff;
  background: #233251;
  border: 1px solid #354a74;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
}

.user-copy {
  min-width: 0;
}

.user-copy strong,
.user-copy p {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-copy strong {
  color: #eef2f7;
  font-size: 13px;
}

.user-copy p {
  margin-top: 2px;
  color: #8f9bad;
  font-size: 11px;
}

.sidebar-version {
  color: #69768a;
  font-size: 11px;
  text-align: center;
}

@media (max-width: 980px) {
  .sidebar-nav {
    position: static;
    width: 100%;
    height: auto;
    flex-basis: auto;
    min-height: auto;
    overflow: visible;
    padding: 12px;
    gap: 10px;
  }

  .nav-logo {
    padding: 0 4px 10px;
  }

  .nav-sections {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
    scrollbar-width: thin;
  }

  .nav-section {
    display: inline-flex;
    margin-right: 12px;
    vertical-align: top;
  }

  .section-title {
    display: none;
  }

  .nav-menu {
    flex-direction: row;
  }

  .nav-item {
    min-height: 40px;
    padding: 8px 10px;
  }

  .nav-item.active::after {
    inset: auto 8px 0;
    width: auto;
    height: 3px;
  }

  .sidebar-foot {
    display: none;
  }
}
</style>
