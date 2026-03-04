<template>
  <header class="flex items-center justify-between px-8 py-5 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800 sticky top-0 z-50">
    <div class="flex items-center gap-6">
      <router-link to="/" class="flex items-center gap-2 text-sm font-medium text-zinc-400 hover:text-white transition-colors group">
        {{ $t('common.backToChat') || 'Back' }}
      </router-link>
      <div class="w-px h-5 bg-zinc-800"></div>
      <h1 class="text-xl font-bold text-zinc-100 tracking-tight">{{ title }}</h1>
    </div>
    <div class="flex items-center gap-3">
      <slot name="actions"></slot>
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
}>();
</script>
