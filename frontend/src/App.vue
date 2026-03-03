<template>
  <div class="min-h-screen w-full bg-background text-foreground font-sans antialiased">
    <div class="fixed top-4 right-6 z-[100]">
      <select 
        :value="locale" 
        @change="onLocaleChange"
        class="appearance-none bg-secondary/50 backdrop-blur-md border border-border px-4 py-1.5 rounded-full text-xs text-muted-foreground hover:text-foreground transition-all cursor-pointer outline-none focus:ring-2 focus:ring-ring"
      >
        <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">
          {{ LOCALE_LABELS[code] }}
        </option>
      </select>
    </div>
    
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { SUPPORTED_LOCALES, LOCALE_LABELS, setLocale, type SupportedLocale } from "./i18n";

const { locale } = useI18n();

function onLocaleChange(e: Event) {
  setLocale((e.target as HTMLSelectElement).value as SupportedLocale);
}
</script>

<style>
@import "tailwindcss";

@theme {
  --color-background: #09090b;
  --color-foreground: #fafafa;
  --color-muted: #27272a;
  --color-muted-foreground: #a1a1aa;
  --color-popover: #09090b;
  --color-popover-foreground: #fafafa;
  --color-card: #09090b;
  --color-card-foreground: #fafafa;
  --color-border: #27272a;
  --color-input: #27272a;
  --color-primary: #fafafa;
  --color-primary-foreground: #18181b;
  --color-secondary: #27272a;
  --color-secondary-foreground: #fafafa;
  --color-accent: #27272a;
  --color-accent-foreground: #fafafa;
  --color-destructive: #ef4444;
  --color-destructive-foreground: #fafafa;
  --color-ring: #d4d4d8;
  
  --radius-lg: 0.5rem;
  --radius-md: calc(0.5rem - 2px);
  --radius-sm: calc(0.5rem - 4px);
}

@layer base {
  * {
    border-color: var(--color-border);
  }
  body {
    background-color: var(--color-background);
    color: var(--color-foreground);
  }
}

/* Custom transitions */
.page-enter-active, .page-leave-active {
  transition: all 0.2s ease-in-out;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Custom Scrollbar for modern look */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--color-muted-foreground); }
</style>
