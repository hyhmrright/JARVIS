<template>
  <div class="min-h-screen w-full bg-zinc-950 text-zinc-50 antialiased selection:bg-zinc-50/10">
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded"
    >
      {{ $t('common.skipToMain', 'Skip to main content') }}
    </a>
    <div id="main-content">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
    <ToastContainer />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import ToastContainer from '@/components/ToastContainer.vue'

const router = useRouter()

function onGlobalKeyDown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    // Don't override ChatPage's own Cmd+K (local conversation search)
    if (router.currentRoute.value.path === '/') return;
    e.preventDefault()
    router.push('/search')
  }
}

onMounted(() => window.addEventListener('keydown', onGlobalKeyDown))
onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalKeyDown))
</script>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: #27272a; border-radius: 10px; }
</style>
