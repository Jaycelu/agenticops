<template>
  <div class="layout">
    <TopNav />
    <div class="layout-content">
      <div class="layout-workspace">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import TopNav from '@/components/TopNav.vue'
</script>

<style scoped>
.layout {
  min-height: 100vh;
  background:
    radial-gradient(circle at top, rgba(56, 189, 248, 0.14), transparent 28%),
    linear-gradient(180deg, #edf3fb 0%, #f8fbff 42%, #eef3f9 100%);
  display: flex;
}

.layout-content {
  flex: 1;
  min-width: 0;
  padding: 24px;
  position: relative;
}

.layout-workspace {
  min-height: calc(100vh - 48px);
  position: relative;
}

.layout-workspace::before {
  content: '';
  position: absolute;
  inset: 8px 12px auto auto;
  width: 260px;
  height: 260px;
  pointer-events: none;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.12), transparent 68%);
  filter: blur(12px);
}

@media (max-width: 980px) {
  .layout {
    flex-direction: column;
  }

  .layout-content {
    padding: 16px;
  }
}
</style>
