<!-- frontend/src/pages/SearchPage.vue -->
<script setup lang="ts">
import { ref, computed, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import client from "@/api/client";

const { t } = useI18n();
const router = useRouter();

interface SearchResult {
  type: "message" | "document" | "memory";
  id: string;
  snippet: string;
  created_at: string;
  conversation_id?: string;
  conversation_title?: string;
  filename?: string;
  file_type?: string;
}

interface SearchResponse {
  results: SearchResult[];
  total: number;
}

const query = ref("");
const selectedTypes = ref<string>("messages,documents,memories");
const results = ref<SearchResult[]>([]);
const total = ref(0);
const loading = ref(false);
const searched = ref(false);

const typeOptions = [
  { value: "messages,documents,memories", labelKey: "search.types.all" },
  { value: "messages", labelKey: "search.types.messages" },
  { value: "documents", labelKey: "search.types.documents" },
  { value: "memories", labelKey: "search.types.memories" },
];

const canSearch = computed(() => query.value.trim().length >= 3);

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function onInput() {
  if (debounceTimer) clearTimeout(debounceTimer);
  if (!canSearch.value) {
    results.value = [];
    searched.value = false;
    return;
  }
  debounceTimer = setTimeout(doSearch, 300);
}

async function doSearch() {
  loading.value = true;
  searched.value = true;
  try {
    const resp = await client.get<SearchResponse>("/search", {
      params: { q: query.value.trim(), types: selectedTypes.value, limit: 20 },
    });
    results.value = resp.data.results;
    total.value = resp.data.total;
  } catch {
    results.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function highlightSnippet(snippet: string, kw: string): string {
  const safeSnippet = snippet
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
  const escapedKw = kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return safeSnippet.replace(new RegExp(escapedKw, "gi"), (m) => `<mark>${m}</mark>`);
}

function navigate(result: SearchResult) {
  if (result.type === "message" && result.conversation_id) {
    router.push({ path: "/", query: { conversation_id: result.conversation_id } });
  } else if (result.type === "document") {
    router.push("/documents");
  } else if (result.type === "memory") {
    router.push("/settings");
  }
}

function resultTypeKey(type: string): string {
  if (type === "message") return "search.types.messages";
  if (type === "document") return "search.types.documents";
  return "search.types.memories";
}

function onTypeChange() {
  if (canSearch.value) doSearch();
}

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer);
});
</script>

<template>
  <div class="search-page">
    <h1>{{ t("search.title") }}</h1>

    <div class="search-bar">
      <input
        v-model="query"
        type="text"
        :placeholder="t('search.placeholder')"
        autofocus
        @input="onInput"
      />
      <select v-model="selectedTypes" @change="onTypeChange">
        <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
          {{ t(opt.labelKey) }}
        </option>
      </select>
    </div>

    <p v-if="query.length > 0 && query.length < 3" class="hint">
      {{ t("search.minLength") }}
    </p>

    <div v-if="loading" class="loading">...</div>

    <div v-else-if="searched && results.length === 0" class="no-results">
      {{ t("search.noResults") }}
    </div>

    <div v-else-if="results.length > 0">
      <p class="result-count">{{ t("search.resultCount", { count: total }) }}</p>
      <ul class="result-list">
        <li
          v-for="result in results"
          :key="result.id"
          class="result-item"
          @click="navigate(result)"
        >
          <div class="result-meta">
            <span class="result-type">{{ t(resultTypeKey(result.type)) }}</span>
            <span v-if="result.type === 'message'" class="result-source">
              {{ t("search.labels.conversation", { title: result.conversation_title }) }}
            </span>
            <span v-else-if="result.type === 'document'" class="result-source">
              {{ t("search.labels.document", { filename: result.filename }) }}
            </span>
            <span v-else class="result-source">{{ t("search.labels.memory") }}</span>
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <p class="snippet" v-html="highlightSnippet(result.snippet, query)" />
          <span class="result-date">{{ new Date(result.created_at).toLocaleDateString() }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.search-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}
.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.search-bar input {
  flex: 1;
  padding: 8px 12px;
  font-size: 16px;
}
.search-bar select {
  padding: 8px;
}
.hint,
.no-results {
  color: #888;
}
.result-count {
  font-size: 13px;
  color: #888;
  margin-bottom: 12px;
}
.result-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.result-item {
  padding: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
}
.result-item:hover {
  background: #f5f5f5;
}
.result-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}
.result-type {
  font-size: 11px;
  background: #e8f0fe;
  color: #1a73e8;
  padding: 2px 6px;
  border-radius: 4px;
}
.result-source {
  font-size: 12px;
  color: #666;
}
.snippet {
  margin: 4px 0;
  font-size: 14px;
}
.snippet :deep(mark) {
  background: #fff176;
  padding: 0 2px;
}
.result-date {
  font-size: 11px;
  color: #aaa;
}
</style>
