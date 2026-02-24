<template>
  <div class="lang-switcher">
    <select :value="locale" @change="onLocaleChange">
      <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">
        {{ LOCALE_LABELS[code] }}
      </option>
    </select>
  </div>
  <router-view />
</template>

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { SUPPORTED_LOCALES, LOCALE_LABELS, setLocale, type SupportedLocale } from "./i18n";

const { locale } = useI18n();

function onLocaleChange(e: Event) {
  setLocale((e.target as HTMLSelectElement).value as SupportedLocale);
}
</script>

<style scoped>
.lang-switcher {
  position: fixed;
  top: 12px;
  right: 16px;
  z-index: 9999;
}

.lang-switcher select {
  padding: 6px 32px 6px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: rgba(18, 18, 30, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    border-color 0.3s ease,
    color 0.3s ease;
  width: auto;
}

.lang-switcher select:hover {
  border-color: var(--accent-dim);
  color: var(--text-primary);
}

.lang-switcher select:focus {
  border-color: var(--accent-dim);
  box-shadow: 0 0 0 2px var(--accent-a10);
  color: var(--text-primary);
}
</style>
