<template>
  <div class="app-container">
    <div class="lang-switcher">
      <select :value="locale" @change="onLocaleChange">
        <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">
          {{ LOCALE_LABELS[code] }}
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
import { useI18n } from "vue-i18n";
import { SUPPORTED_LOCALES, LOCALE_LABELS, setLocale, type SupportedLocale } from "./i18n";

const { locale } = useI18n();

function onLocaleChange(e: Event) {
  setLocale((e.target as HTMLSelectElement).value as SupportedLocale);
}
</script>

<style>
:root {
  /* Premium Dark Theme Variables */
  --bg-primary: #0a0a0c;
  --bg-secondary: #16161a;
  --bg-tertiary: #1e1e24;
  
  --accent: #6366f1;
  --accent-dim: #4f46e5;
  --accent-light: #818cf8;
  
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  
  --border: rgba(255, 255, 255, 0.08);
  --border-bright: rgba(255, 255, 255, 0.15);
  
  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 20px;
  --radius-full: 9999px;
  
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.5);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
  
  --glass-bg: rgba(22, 22, 26, 0.7);
  --glass-border: rgba(255, 255, 255, 0.1);
  --glass-blur: blur(12px);
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}

.app-container {
  height: 100vh;
  width: 100vw;
}

/* Global Transitions */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.lang-switcher {
  position: fixed;
  top: 1rem;
  right: 1.5rem;
  z-index: 9999;
}

.lang-switcher select {
  padding: 0.4rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  font-size: 0.8rem;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
}

.lang-switcher select:hover {
  border-color: var(--accent);
  color: var(--text-primary);
  transform: translateY(-1px);
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: var(--radius-full);
}
::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}
</style>
