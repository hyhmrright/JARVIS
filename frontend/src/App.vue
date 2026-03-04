<template>
  <div class="min-h-screen w-full bg-zinc-950 text-zinc-50 antialiased selection:bg-zinc-50/10">
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useChatStore } from '@/stores/chat';
// Global initialization if needed
</script>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: #27272a; border-radius: 10px; }
</style>
