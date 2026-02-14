<template>
  <div class="layout">
    <TopNav />
    <div class="layout-content">
      <router-view />
    </div>
  </div>
</template>

<script setup lang="ts">
import TopNav from '@/components/TopNav.vue'
</script>

<style scoped>
.layout {
  min-height: 100vh;
  background: #f5f7fa;
}

.layout-content {
  padding: 0;
}
</style>