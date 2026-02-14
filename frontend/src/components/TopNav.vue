<template>
  <div class="top-nav">
    <div class="nav-logo">
      <Network class="logo-icon" :size="24" />
      <span>NetOps AI</span>
    </div>
    <nav class="nav-menu">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        exact-active-class="active"
      >
        <component :is="item.icon" :size="18" />
        <span>{{ item.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Network, House, Server, AlertTriangle, FileText, Settings, Bot } from 'lucide-vue-next'

const navItems = ref([
  { path: '/', label: '驾驶舱', icon: House },
  { path: '/assets', label: '资产', icon: Server },
  { path: '/alerts', label: '告警', icon: AlertTriangle },
  { path: '/logs', label: '日志', icon: FileText },
  { path: '/automation/dashboard', label: '自动化中心', icon: Bot },
  { path: '/automation/abnormal-types', label: '异常类型管理', icon: Settings },
  { path: '/settings', label: '设置', icon: Settings }
])
</script>

<style scoped>
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  background: #0f172a;
  color: white;
  padding: 0 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  position: relative;
  z-index: 100;
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 22px;
  font-weight: 700;
  color: #e2e8f0;
  letter-spacing: -0.5px;
}

.logo-icon {
  animation: pulse 2s ease-in-out infinite;
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
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  color: #94a3b8;
  text-decoration: none;
  border-radius: 10px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-size: 14px;
  font-weight: 500;
  position: relative;
  overflow: hidden;
}

.nav-item::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(148, 163, 184, 0.08);
  opacity: 0;
  transition: opacity 0.3s;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
  transform: translateY(-1px);
}

.nav-item:hover::before {
  opacity: 1;
}

.nav-item.active {
  background: rgba(30, 41, 59, 0.9);
  color: #f8fafc;
  font-weight: 600;
  box-shadow: none;
}

.nav-item.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: calc(100% - 16px);
  height: 3px;
  background: #38bdf8;
  border-radius: 999px;
}
</style>
