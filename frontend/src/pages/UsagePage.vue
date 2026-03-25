<template>
  <div class="page-container">
    <PageHeader :title="$t('usage.title')" />

    <div class="page-content custom-scrollbar">
      <!-- Summary Cards -->
      <div class="stats-grid animate-fade-in">
        <div class="glass-card stat-card">
          <div class="stat-value">{{ totalTokensIn.toLocaleString() }}</div>
          <div class="stat-label">{{ $t("usage.tokensIn") }}</div>
        </div>
        <div class="glass-card stat-card highlight">
          <div class="stat-value">{{ totalTokensOut.toLocaleString() }}</div>
          <div class="stat-label">{{ $t("usage.tokensOut") }}</div>
        </div>
        <div class="glass-card stat-card">
          <div class="stat-value">{{ totalMessages }}</div>
          <div class="stat-label">{{ $t("usage.messages") }}</div>
        </div>
        <div class="glass-card stat-card">
          <div class="stat-value">~${{ estimatedCost.toFixed(4) }}</div>
          <div class="stat-label">{{ $t("usage.estimatedCost") }}</div>
        </div>
      </div>

      <div class="content-body animate-fade-in">
        <div class="controls-row">
          <div class="day-selector">
            <button
              v-for="d in [7, 30, 90]"
              :key="d"
              :class="['day-btn', { active: days === d }]"
              @click="days = d"
            >
              {{ d }}{{ $t("usage.days") }}
            </button>
          </div>
        </div>

        <div v-if="isLoading" class="state-placeholder">
          <div class="spinner"></div>
          <p>{{ $t("usage.loading") }}</p>
        </div>

        <div v-else-if="dailyData.length === 0" class="state-placeholder">
          <p>{{ $t("usage.noData") }}</p>
        </div>

        <div v-else class="charts-row">
          <div class="glass-card chart-section flex-[2]">
            <h2 class="chart-header">{{ $t("usage.chartTitle", { days }) }}</h2>
            <div class="h-[340px] w-full">
              <VChart :option="chartOptions" autoresize />
            </div>
          </div>
          <div class="glass-card chart-section flex-1 min-w-[280px]">
            <h2 class="chart-header">{{ $t("usage.providerShare") }}</h2>
            <div class="h-[340px] w-full">
              <VChart :option="pieOptions" autoresize />
            </div>
          </div>
        </div>

        <!-- Cost Breakdown -->
        <div v-if="dailyData.length > 0" class="glass-card chart-section cost-breakdown-card">
          <h2 class="chart-header">{{ $t("usage.usageDetails") }}</h2>
          <table class="cost-table">
            <thead>
              <tr>
                <th>{{ $t("usage.date") }}</th>
                <th>{{ $t("usage.provider") }}</th>
                <th>{{ $t("usage.model") }}</th>
                <th class="cost-num">{{ $t("usage.tokens") }}</th>
                <th class="cost-num">{{ $t("usage.estimatedCost") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in dailyData" :key="idx">
                <td class="text-zinc-500 font-mono text-[10px]">{{ row.day }}</td>
                <td>
                  <span class="provider-dot" :style="{ background: (PROVIDERS[row.provider] || PROVIDERS.unknown).color }"></span>
                  {{ row.provider }}
                </td>
                <td class="text-zinc-400">{{ row.model }}</td>
                <td class="cost-num cost-dim">{{ (row.tokens_in + row.tokens_out).toLocaleString() }}</td>
                <td class="cost-num">${{ row.estimated_cost_usd < 0.0001 ? '< 0.0001' : row.estimated_cost_usd.toFixed(4) }}</td>
              </tr>
            </tbody>
          </table>
          <p class="pricing-note">{{ $t("usage.pricingNote") }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import client from "@/api/client";
import PageHeader from "@/components/PageHeader.vue";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, PieChart } from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from "echarts/components";
import VChart from "vue-echarts";

use([
  CanvasRenderer,
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
]);

interface DayData {
  day: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  messages: number;
  estimated_cost_usd: number;
}

const { t } = useI18n();

const days = ref(30);
const isLoading = ref(false);
const dailyData = ref<DayData[]>([]);
const totalTokensIn = ref(0);
const totalTokensOut = ref(0);
const totalEstimatedCost = ref(0);

const totalMessages = computed(() => dailyData.value.reduce((s, d) => s + d.messages, 0));

const TOOLTIP_STYLE = {
  backgroundColor: "#09090b",
  borderColor: "#27272a",
  textStyle: { color: "#d4d4d8" },
} as const;

// Single source of truth for provider metadata (color only now, pricing from backend)
const PROVIDERS: Record<string, { color: string }> & { unknown: { color: string } } = {
  deepseek:  { color: "#6366f1" },
  openai:    { color: "#10b981" },
  anthropic: { color: "#f59e0b" },
  zhipuai:   { color: "#3b82f6" },
  ollama:    { color: "#ec4899" },
  unknown:   { color: "#6b7280" },
};

const estimatedCost = computed(() => totalEstimatedCost.value);

const chartOptions = computed(() => {
  const dates = [...new Set(dailyData.value.map(d => d.day))].sort();
  const providers = [...new Set(dailyData.value.map(d => d.provider))].sort();
  const xLabels = dates.map(d => d.slice(5));

  const providerSeries = providers.map(provider => ({
    name: provider,
    type: "line",
    smooth: true,
    symbol: "none",
    lineStyle: { color: (PROVIDERS[provider] ?? PROVIDERS.unknown).color, width: 2 },
    data: dates.map(date =>
      dailyData.value
        .filter(d => d.day === date && d.provider === provider)
        .reduce((sum, d) => sum + d.tokens_out, 0)
    ),
  }));

  const tokensInSeries = {
    name: t("usage.tokensIn"),
    type: "line",
    smooth: true,
    symbol: "none",
    lineStyle: { color: "#3f3f46", width: 1.5, type: "dashed" as const },
    data: dates.map(date =>
      dailyData.value
        .filter(d => d.day === date)
        .reduce((sum, d) => sum + d.tokens_in, 0)
    ),
  };

  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", ...TOOLTIP_STYLE },
    legend: {
      textStyle: { color: "#a1a1aa" },
      itemHeight: 8,
      bottom: 0,
    },
    grid: { left: "3%", right: "4%", bottom: "15%", containLabel: true },
    xAxis: {
      type: "category",
      data: xLabels,
      axisLine: { lineStyle: { color: "#3f3f46" } },
      axisLabel: { color: "#71717a", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#18181b" } },
      axisLine: { lineStyle: { color: "#3f3f46" } },
      axisLabel: { color: "#71717a", fontSize: 11 },
    },
    series: [...providerSeries, tokensInSeries],
  };
});

const pieOptions = computed(() => {
  const byProvider = dailyData.value.reduce<Record<string, number>>((acc, d) => {
    acc[d.provider] = (acc[d.provider] ?? 0) + d.tokens_out;
    return acc;
  }, {});

  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "item", ...TOOLTIP_STYLE, formatter: "{b}: {c} ({d}%)" },
    legend: {
      orient: "vertical",
      right: "5%",
      top: "center",
      textStyle: { color: "#a1a1aa", fontSize: 11 },
    },
    series: [{
      type: "pie",
      radius: ["45%", "70%"],
      center: ["40%", "50%"],
      data: Object.entries(byProvider)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({
          name,
          value,
          itemStyle: { color: (PROVIDERS[name] ?? PROVIDERS.unknown).color },
        })),
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 12, color: "#e4e4e7" } },
    }],
  };
});

const fetchUsage = async () => {
  isLoading.value = true;
  dailyData.value = [];
  totalTokensIn.value = 0;
  totalTokensOut.value = 0;
  totalEstimatedCost.value = 0;
  try {
    const resp = await client.get(`/usage/summary?days=${days.value}`);
    dailyData.value = resp.data.daily;
    totalTokensIn.value = resp.data.total_tokens_in;
    totalTokensOut.value = resp.data.total_tokens_out;
    totalEstimatedCost.value = resp.data.total_estimated_cost_usd;
  } catch (e) {
    console.error(e);
  } finally {
    isLoading.value = false;
  }
};

watch(days, fetchUsage);
onMounted(fetchUsage);
</script>

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background: var(--bg-primary); }
.page-content { flex: 1; padding: 2rem; overflow-y: auto; max-width: 1000px; width: 100%; margin: 0 auto; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2rem; }
@media (max-width: 640px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
.stat-card { padding: 1.5rem; text-align: center; }
.stat-card.highlight { border-color: var(--accent); }
.stat-value { font-size: 2.25rem; font-weight: 800; color: var(--text-primary); margin-bottom: 0.5rem; }
.stat-card.highlight .stat-value { color: var(--accent); }
.stat-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); }

.controls-row { display: flex; justify-content: flex-end; margin-bottom: 1.5rem; }
.day-selector { display: flex; background: var(--bg-secondary); padding: 0.3rem; border-radius: var(--radius-md); border: 1px solid var(--border); }
.day-btn { padding: 0.4rem 1rem; border: none; background: transparent; color: var(--text-secondary); border-radius: var(--radius-sm); cursor: pointer; transition: all 0.2s; font-size: 0.85rem; }
.day-btn.active { background: var(--bg-tertiary); color: var(--text-primary); box-shadow: var(--shadow-sm); }

.charts-row { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.chart-section { padding: 2rem; }
.chart-header { font-size: 1rem; font-weight: 700; margin-bottom: 2.5rem; color: var(--text-primary); }

.state-placeholder { height: 300px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1rem; color: var(--text-muted); }

.cost-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.cost-table th { text-align: left; color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; padding: 0 0 0.75rem; border-bottom: 1px solid var(--border); }
.cost-table td { padding: 0.6rem 0; border-bottom: 1px solid var(--border); color: var(--text-primary); }
.cost-table tr:last-child td { border-bottom: none; }
.cost-num { text-align: right; }
.cost-dim { color: var(--text-muted); }
.provider-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.5rem; vertical-align: middle; }
.pricing-note { margin-top: 1rem; font-size: 0.75rem; color: var(--text-muted); }
.cost-breakdown-card { margin-top: 1.5rem; }

.animate-fade-in { animation: fadeIn 0.4s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

.spinner { width: 30px; height: 30px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
