<template>
  <header class="page-nav-header">
    <div class="header-left">
      <router-link to="/" class="btn-back">
        <span class="back-icon">←</span>
        {{ $t('common.backToChat') }}
      </router-link>
      <div class="divider"></div>
      <h1 class="page-title">{{ title }}</h1>
    </div>
    <div class="header-right">
      <slot name="actions"></slot>
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
}>();
</script>

<style scoped>
.page-nav-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.btn-back {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: color 0.2s;
}

.btn-back:hover {
  color: var(--accent);
}

.divider {
  width: 1px;
  height: 20px;
  background: var(--border);
}

.page-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.back-icon {
  font-size: 1.2rem;
}
</style>
