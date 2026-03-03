<template>
  <div class="min-h-screen w-full bg-background text-foreground selection:bg-primary/10">
    <!-- Tiny Language Switcher -->
    <div class="fixed bottom-4 right-4 z-[100] opacity-40 hover:opacity-100 transition-opacity">
      <select 
        :value="locale" 
        @change="onLocaleChange"
        class="bg-transparent border-none text-[10px] uppercase tracking-widest cursor-pointer outline-none font-bold"
      >
        <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">
          {{ code }}
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
import { SUPPORTED_LOCALES, setLocale, type SupportedLocale } from "./i18n";

const { locale } = useI18n();

function onLocaleChange(e: Event) {
  setLocale((e.target as HTMLSelectElement).value as SupportedLocale);
}
</script>

<style>
@import "tailwindcss";

@theme {
  --color-background: #09090b; /* Zinc 950 */
  --color-foreground: #fafafa; /* Zinc 50 */
  --color-muted: #18181b;      /* Zinc 900 */
  --color-muted-foreground: #a1a1aa; /* Zinc 400 */
  --color-popover: #09090b;
  --color-card: #09090b;
  --color-border: #27272a;     /* Zinc 800 */
  --color-input: #27272a;
  --color-primary: #ffffff;
  --color-primary-foreground: #09090b;
  --color-secondary: #18181b;
  --color-accent: #27272a;
  --color-ring: #3f3f46;       /* Zinc 700 */
  
  --radius-lg: 0.75rem;
  --radius-md: 0.5rem;
  --radius-sm: 0.25rem;
}

@layer base {
  * { border-color: var(--color-border); }
  body {
    background-color: var(--color-background);
    color: var(--color-foreground);
    font-feature-settings: "cv02", "cv03", "cv04", "cv11";
  }
}

.page-enter-active, .page-leave-active { transition: opacity 0.15s ease; }
.page-enter-from, .page-leave-to { opacity: 0; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: #27272a; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #3f3f46; }
</style>
