<template>
  <div class="usage-layout">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-icon">&#10022;</span>
        <span class="brand-text">JARVIS</span>
      </div>
      <div class="sidebar-footer">
        <router-link to="/" class="footer-link">
          <span class="footer-icon">&#10022;</span>
          {{ $t("chat.newConversation") }}
        </router-link>
        <router-link to="/documents" class="footer-link">
          <span class="footer-icon">&#9635;</span>
          {{ $t("chat.documents") }}
        </router-link>
        <router-link to="/settings" class="footer-link">
          <span class="footer-icon">&#9881;</span>
          {{ $t("chat.settings") }}
        </router-link>
      </div>
    </aside>

    <main class="usage-main">
      <h1 class="usage-title">{{ $t("usage.title") }}</h1>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ totalTokensIn.toLocaleString() }}</div>
          <div class="stat-label">{{ $t("usage.tokensIn") }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ totalTokensOut.toLocaleString() }}</div>
          <div class="stat-label">{{ $t("usage.tokensOut") }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ totalMessages }}</div>
          <div class="stat-label">{{ $t("usage.messages") }}</div>
        </div>
      </div>

      <div class="day-selector">
        <button
          v-for="d in [7, 30, 90]"
          :key="d"
          class="day-btn"
          :class="{ active: days === d }"
          @click="setDays(d)"
        >
          {{ d }}{{ $t("usage.days") }}
        </button>
      </div>

      <div v-if="isLoading" class="usage-empty">{{ $t("usage.loading") }}</div>
      <div v-else-if="dailyData.length === 0" class="usage-empty">
        {{ $t("usage.noData") }}
      </div>
      <div v-else class="chart-section">
        <h2 class="chart-title">
          {{ $t("usage.chartTitle", { days }) }}
        </h2>
        <div class="chart-container">
          <div
            v-for="day in chartData"
            :key="day.day"
            class="chart-bar-col"
          >
            <div
              class="chart-bar"
              :style="{ height: day.height + 'px' }"
              :title="`${day.day}: ${day.tokensOut.toLocaleString()} output tokens`"
            />
            <div class="chart-label">{{ day.label }}</div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import client from "@/api/client";

interface DayData {
  day: string;
  provider: string;
  tokens_in: number;
  tokens_out: number;
  messages: number;
}

const days = ref(30);
const isLoading = ref(false);
const dailyData = ref<DayData[]>([]);
const totalTokensIn = ref(0);
const totalTokensOut = ref(0);
const totalMessages = computed(() =>
  dailyData.value.reduce((s, d) => s + d.messages, 0)
);

const maxTokens = computed(() =>
  Math.max(...dailyData.value.map((d) => d.tokens_out), 1)
);

const chartData = computed(() =>
  dailyData.value.map((d) => ({
    day: d.day,
    label: d.day.slice(5), // MM-DD
    tokensOut: d.tokens_out,
    height: Math.max(4, Math.round((d.tokens_out / maxTokens.value) * 100)),
  }))
);

const fetchUsage = async () => {
  isLoading.value = true;
  try {
    const resp = await client.get(`/api/usage/summary?days=${days.value}`);
    dailyData.value = resp.data.daily;
    totalTokensIn.value = resp.data.total_tokens_in;
    totalTokensOut.value = resp.data.total_tokens_out;
  } catch (e) {
    console.error("Failed to fetch usage:", e);
  } finally {
    isLoading.value = false;
  }
};

const setDays = (d: number) => {
  days.value = d;
};

watch(days, fetchUsage);
onMounted(fetchUsage);
</script>

<style scoped>
.usage-layout {
  display: flex;
  height: 100vh;
  background: var(--color-bg);
  color: var(--color-text);
}

.sidebar {
  width: 240px;
  min-width: 200px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  padding: 1rem 0;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 1rem 1rem;
  font-size: 1.1rem;
  font-weight: 700;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 1rem;
}

.brand-icon {
  font-size: 1.3rem;
}

.sidebar-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.5rem;
}

.footer-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  color: var(--color-muted);
  text-decoration: none;
  transition: background 0.15s;
}

.footer-link:hover {
  background: var(--color-hover);
  color: var(--color-text);
}

.usage-main {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
  max-width: 860px;
}

.usage-title {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
  padding: 1.25rem;
  text-align: center;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-primary, #6366f1);
}

.stat-label {
  font-size: 0.8rem;
  color: var(--color-muted);
  margin-top: 0.25rem;
}

.day-selector {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.day-btn {
  padding: 0.35rem 0.9rem;
  border-radius: 0.4rem;
  font-size: 0.875rem;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.day-btn:hover {
  background: var(--color-hover);
  color: var(--color-text);
}

.day-btn.active {
  background: var(--color-primary, #6366f1);
  color: #fff;
  border-color: transparent;
}

.usage-empty {
  text-align: center;
  color: var(--color-muted);
  padding: 3rem 0;
}

.chart-section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 0.75rem;
  padding: 1.25rem;
}

.chart-title {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
}

.chart-container {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 120px;
  overflow-x: auto;
}

.chart-bar-col {
  flex: 1;
  min-width: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.chart-bar {
  width: 100%;
  background: var(--color-primary, #6366f1);
  border-radius: 2px 2px 0 0;
  opacity: 0.8;
  transition: opacity 0.15s;
}

.chart-bar:hover {
  opacity: 1;
}

.chart-label {
  font-size: 8px;
  color: var(--color-muted);
  white-space: nowrap;
}
</style>
