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
  tokens_in: number;
  tokens_out: number;
  messages: number;
}

const { t } = useI18n();

const days = ref(30);
const isLoading = ref(false);
const dailyData = ref<DayData[]>([]);
const totalTokensIn = ref(0);
const totalTokensOut = ref(0);

const totalMessages = computed(() => dailyData.value.reduce((s, d) => s + d.messages, 0));

const TOOLTIP_STYLE = {
  backgroundColor: "#09090b",
  borderColor: "#27272a",
  textStyle: { color: "#d4d4d8" },
} as const;

const PROVIDER_COLORS: Record<string, string> = {
  deepseek: "#6366f1",
  openai: "#10b981",
  anthropic: "#f59e0b",
  zhipuai: "#3b82f6",
  ollama: "#ec4899",
  unknown: "#6b7280",
};

const chartOptions = computed(() => {
  const dates = [...new Set(dailyData.value.map(d => d.day))].sort();
  const providers = [...new Set(dailyData.value.map(d => d.provider))].sort();
  const xLabels = dates.map(d => d.slice(5));

  const providerSeries = providers.map(provider => ({
    name: provider,
    type: "line",
    smooth: true,
    symbol: "none",
    lineStyle: { color: PROVIDER_COLORS[provider] ?? "#6b7280", width: 2 },
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
          itemStyle: { color: PROVIDER_COLORS[name] ?? "#6b7280" },
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
  try {
    const resp = await client.get(`/usage/summary?days=${days.value}`);
    dailyData.value = resp.data.daily;
    totalTokensIn.value = resp.data.total_tokens_in;
    totalTokensOut.value = resp.data.total_tokens_out;
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

.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin-bottom: 2rem; }
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

.animate-fade-in { animation: fadeIn 0.4s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

.spinner { width: 30px; height: 30px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
