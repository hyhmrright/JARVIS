<template>
  <div class="min-h-screen w-full bg-zinc-950 text-zinc-50 antialiased selection:bg-zinc-50/10">
    <!-- Sophisticated Language Switcher -->
    <div class="fixed top-4 right-4 z-[100]">
      <select 
        :value="locale" 
        @change="onLocaleChange"
        class="appearance-none bg-zinc-900/50 backdrop-blur-md border border-zinc-800 px-3 py-1 rounded text-[10px] uppercase tracking-widest cursor-pointer outline-none hover:bg-zinc-800 transition-all font-bold text-zinc-400 hover:text-zinc-100"
      >
        <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">
          {{ code }}
        </option>
      </select>
    </div>

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
@import "tailwindcss";

@theme {
  --color-background: #09090b;
  --color-foreground: #fafafa;
  --color-border: #27272a;
  --color-muted: #18181b;
  --color-muted-foreground: #71717a;
  --color-accent: #27272a;
  --color-primary: #fafafa;
  --color-secondary: #18181b;
  --color-destructive: #ef4444;
  --radius-lg: 0.5rem;
}

@layer base {
  body {
    background-color: var(--color-background);
    color: var(--color-foreground);
  }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: #27272a; border-radius: 10px; }
</style>
