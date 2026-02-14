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
        active-class="active"
      >
        <component :is="item.icon" :size="18" />
        <span>{{ item.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Network, LayoutDashboard, Server, AlertTriangle, FileText, Settings, Bot } from 'lucide-vue-next'

const navItems = ref([
  { path: '/dashboard', label: '运维工作台', icon: LayoutDashboard },
  { path: '/assets', label: '资产', icon: Server },
  { path: '/alerts', label: '告警', icon: AlertTriangle },
  { path: '/logs', label: '日志', icon: FileText },
  { path: '/automation/dashboard', label: '自动化中心', icon: Bot },
  { path: '/automation/feedback-stats', label: '反馈统计', icon: Bot },
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
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white;
  padding: 0 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  position: relative;
  z-index: 100;
}

.top-nav::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(74, 158, 255, 0.3), transparent);
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 22px;
  font-weight: 700;
  color: #4a9eff;
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
  color: #a0a0c0;
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
  background: linear-gradient(135deg, rgba(74, 158, 255, 0.1), rgba(74, 158, 255, 0.05));
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
  background: linear-gradient(135deg, rgba(74, 158, 255, 0.2), rgba(74, 158, 255, 0.1));
  color: #4a9eff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(74, 158, 255, 0.2);
}

.nav-item.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 20px;
  height: 2px;
  background: #4a9eff;
  border-radius: 2px;
}
</style>
