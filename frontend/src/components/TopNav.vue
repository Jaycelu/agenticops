<template>
  <aside class="sidebar-nav">
    <div class="nav-logo">
      <img src="/agenticops.jpg" alt="AgenticOps" class="logo-icon" />
      <div>
        <strong>AgenticOps</strong>
      </div>
    </div>

    <div class="nav-section" v-for="section in navSections" :key="section.title">
      <span class="section-title">{{ section.title }}</span>
      <nav class="nav-menu">
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

    <div class="sidebar-foot">
      <span>{{ auth.user?.display_name || auth.user?.username }}</span>
      <p>{{ auth.user?.roles.join(' / ') || '已认证用户' }}</p>
      <button class="logout-button" @click="logout">退出登录</button>
    </div>

    <div class="sidebar-version">{{ appVersion }}</div>
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
      { path: '/identity', label: '身份与权限', icon: ShieldCheck, permission: 'identities.manage' }
    ]
  }
]

const auth = useAuthStore()
const router = useRouter()
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
  width: 308px;
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.16), transparent 34%),
    linear-gradient(180deg, #071120 0%, #0f172a 45%, #111c32 100%);
  color: white;
  padding: 24px 18px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  box-shadow: 12px 0 40px rgba(15, 23, 42, 0.22);
}

.nav-logo {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 6px 8px 18px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.nav-logo strong {
  display: block;
  font-size: 20px;
  color: #f8fafc;
}

.nav-logo p {
  margin-top: 4px;
  color: #8ca3c6;
  font-size: 12px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  animation: pulse 2s ease-in-out infinite;
}

.logout-button {
  margin-top: 10px;
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 9px;
  padding: 8px 10px;
  color: #cbd5e1;
  background: rgba(15, 23, 42, 0.5);
  cursor: pointer;
}

.nav-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  padding: 0 10px;
  color: #7dd3fc;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.nav-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  color: #a8b7cc;
  text-decoration: none;
  border-radius: 14px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-size: 14px;
  font-weight: 500;
  position: relative;
  overflow: hidden;
  border: 1px solid transparent;
}

.nav-item::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(148, 163, 184, 0.05);
  opacity: 0;
  transition: opacity 0.3s;
}

.nav-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.nav-copy small {
  color: #7a8da8;
  font-size: 11px;
  line-height: 1.35;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: white;
  transform: translateX(3px);
}

.nav-item:hover::before {
  opacity: 1;
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.22), rgba(13, 148, 136, 0.16));
  color: #f8fafc;
  font-weight: 600;
  border-color: rgba(125, 211, 252, 0.2);
}

.nav-item.active::after {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  background: #7dd3fc;
  border-radius: 999px;
}

.sidebar-foot {
  margin-top: auto;
  padding: 14px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.sidebar-foot span {
  color: #7dd3fc;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sidebar-foot p {
  margin-top: 8px;
  color: #cbd5e1;
  font-size: 13px;
}

.sidebar-version {
  margin-top: 10px;
  padding: 0 4px;
  color: #7a8da8;
  font-size: 12px;
  letter-spacing: 0.06em;
}

@media (max-width: 980px) {
  .sidebar-nav {
    width: 100%;
    min-height: auto;
    padding: 16px;
  }

  .nav-logo {
    padding-bottom: 12px;
  }

  .sidebar-foot {
    margin-top: 0;
  }
}
</style>
