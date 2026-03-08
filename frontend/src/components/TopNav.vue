<template>
  <aside class="sidebar-nav">
    <div class="nav-logo">
      <Network class="logo-icon" :size="24" />
      <div>
        <strong>NetOps AI</strong>
        <p>AgenticOps Workspace</p>
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
            <small>{{ item.desc }}</small>
          </div>
        </router-link>
      </nav>
    </div>

    <div class="sidebar-foot">
      <span>数据源</span>
      <p>NetBox / ELK / Zabbix</p>
    </div>

    <div class="sidebar-version">{{ appVersion }}</div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import packageJson from '../../package.json'
import {
  Activity,
  Bell,
  Brain,
  House,
  MemoryStick,
  Network,
  Radio,
  Server,
  Settings,
  ShieldCheck,
  Ticket,
  FileText
} from 'lucide-vue-next'

const navSections = ref([
  {
    title: '指挥层',
    items: [
      { path: '/', label: '驾驶舱', desc: 'Case / Agent / Memory 总览', icon: House },
      { path: '/cases', label: 'Case 中心', desc: '统一故障处置工作台', icon: Activity },
      { path: '/fabric', label: '执行中心', desc: '修复计划与执行记录', icon: ShieldCheck }
    ]
  },
  {
    title: '智能层',
    items: [
      { path: '/agents', label: '智能体中心', desc: '四类运维智能体运行态', icon: Brain },
      { path: '/memories', label: '记忆中心', desc: 'Episode / Pattern / Outcome', icon: MemoryStick }
    ]
  },
  {
    title: '观测层',
    items: [
      { path: '/events', label: '事件中心', desc: '告警与事件入口', icon: Radio },
      { path: '/logs', label: '日志中心', desc: '日志检索与分析', icon: FileText },
      { path: '/zabbix', label: 'Zabbix 中心', desc: '告警与实时状态数据源', icon: Bell },
      { path: '/assets', label: '资产拓扑', desc: '设备与站点上下文', icon: Server },
      { path: '/tickets', label: '工单', desc: '人工闭环与状态追踪', icon: Ticket },
      { path: '/settings', label: '设置', desc: '集成与运行配置', icon: Settings }
    ]
  }
])

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
  animation: pulse 2s ease-in-out infinite;
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
