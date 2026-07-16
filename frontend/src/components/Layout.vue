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
  background: var(--app-bg);
  display: flex;
}

.layout-content {
  flex: 1;
  min-width: 0;
  padding: 20px 24px 32px;
}

.layout-workspace {
  width: 100%;
  max-width: 1680px;
  min-height: calc(100vh - 52px);
  margin: 0 auto;
}

@media (max-width: 980px) {
  .layout {
    flex-direction: column;
  }

  .layout-content {
    padding: 16px;
  }
}

@media (max-width: 560px) {
  .layout-content {
    padding: 12px;
  }
}
</style>
