<template>
  <div class="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        :class="[
          'px-4 py-3 rounded-lg text-sm font-medium shadow-lg pointer-events-auto max-w-xs',
          toast.type === 'success' ? 'bg-emerald-900/90 text-emerald-200 border border-emerald-800' :
          toast.type === 'error' ? 'bg-red-900/90 text-red-200 border border-red-800' :
          'bg-zinc-800/90 text-zinc-200 border border-zinc-700'
        ]"
      >
        {{ toast.message }}
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { toasts } = useToast()
</script>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.2s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(0.5rem); }
</style>
