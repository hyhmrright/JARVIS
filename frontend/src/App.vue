<template>
  <!-- 全局语言切换（固定在右上角） -->
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
  top: 8px;
  right: 12px;
  z-index: 9999;
}

.lang-switcher select {
  padding: 4px 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}
</style>
