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
  background: linear-gradient(180deg, #eff4fb 0%, #f8fafc 42%, #f1f5f9 100%);
  display: flex;
}

.layout-content {
  flex: 1;
  min-width: 0;
  padding: 24px;
}

.layout-workspace {
  min-height: calc(100vh - 48px);
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
