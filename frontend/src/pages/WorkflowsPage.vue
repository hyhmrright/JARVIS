<template>
  <div class="min-h-screen bg-black text-zinc-300 font-sans selection:bg-white/10">
    <div class="max-w-5xl mx-auto px-6 py-12">
      <!-- Header -->
      <header class="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div class="space-y-2">
          <div class="flex items-center gap-2 text-[10px] font-black text-white tracking-[0.2em] uppercase">
            <GitFork class="w-3.5 h-3.5" />
            {{ $t('workflows.automations') }}
          </div>
          <h1 class="text-4xl font-bold text-white tracking-tight">{{ $t('workflows.title') }}</h1>
          <p class="text-zinc-500 text-sm max-w-lg">{{ $t('workflows.description') }}</p>
        </div>

        <router-link
          to="/studio"
          class="px-6 py-2.5 bg-white text-black rounded-xl text-sm font-black uppercase tracking-widest hover:bg-zinc-200 transition-all flex items-center gap-2"
        >
          <Plus class="w-4 h-4" />
          {{ $t('workflows.create') }}
        </router-link>
      </header>

      <!-- Search -->
      <div v-if="workflows.length > 0 || query" class="mb-8">
        <input
          v-model="query"
          type="text"
          :placeholder="$t('workflows.searchPlaceholder')"
          class="w-full max-w-sm bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-zinc-600 transition-colors"
        />
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div v-for="i in 4" :key="i" class="h-40 bg-zinc-900/50 rounded-2xl border border-zinc-800 animate-pulse"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="py-20 text-center space-y-4">
        <ShieldAlert class="w-12 h-12 text-red-500 mx-auto" />
        <p class="text-red-400 font-medium">{{ error }}</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="workflows.length === 0" class="py-20 text-center space-y-6 bg-zinc-900/30 rounded-3xl border border-dashed border-zinc-800">
        <div class="w-16 h-16 bg-zinc-900 rounded-full flex items-center justify-center mx-auto text-zinc-700">
          <GitFork class="w-8 h-8" />
        </div>
        <div class="space-y-1">
          <p class="text-white font-bold">{{ $t('workflows.emptyTitle') }}</p>
          <p class="text-zinc-500 text-sm">{{ $t('workflows.emptyDesc') }}</p>
        </div>
        <router-link to="/studio" class="text-white text-xs font-black uppercase tracking-widest underline decoration-zinc-700 hover:decoration-white transition-all">
          {{ $t('workflows.createNow') }}
        </router-link>
      </div>

      <!-- No match -->
      <div v-else-if="filtered.length === 0 && query" class="py-20 text-center text-zinc-500 text-sm">
        {{ $t('workflows.noMatch', { query }) }}
      </div>

      <!-- Workflow Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div
          v-for="wf in filtered"
          :key="wf.id"
          class="group bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col justify-between hover:border-zinc-600 transition-all duration-300"
        >
          <div class="space-y-4">
            <div class="flex items-start justify-between">
              <div class="w-10 h-10 bg-zinc-800 rounded-xl flex items-center justify-center text-white group-hover:bg-white group-hover:text-black transition-colors">
                <GitFork class="w-5 h-5" />
              </div>
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <router-link :to="`/studio?id=${wf.id}`" class="p-2 text-zinc-600 hover:text-white transition-colors">
                  <Pencil class="w-4 h-4" />
                </router-link>
                <button class="p-2 text-zinc-600 hover:text-red-400 transition-colors" @click="deleteWorkflow(wf)">
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>
            </div>

            <div>
              <h3 class="text-lg font-bold text-white mb-1">{{ wf.name }}</h3>
              <p class="text-zinc-500 text-xs line-clamp-2 leading-relaxed">{{ wf.description || $t('workflows.noDescription') }}</p>
            </div>

            <div class="bg-black/40 rounded-lg p-3 border border-white/5">
              <p class="text-[10px] text-zinc-600 font-black uppercase tracking-widest mb-1">{{ $t('workflows.nodesLabel') }}</p>
              <p class="text-[11px] text-zinc-400 font-mono">{{ $t('workflows.nodeCount', { count: wf.dsl?.nodes?.length ?? 0 }) }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { GitFork, Plus, Trash2, Pencil, ShieldAlert } from 'lucide-vue-next';
import client from '@/api/client';
import { useToast } from '@/composables/useToast';
import { useSearchFilter } from '@/composables/useSearchFilter';

const { t } = useI18n();
const { error: toastError } = useToast();

interface Workflow {
  id: string;
  name: string;
  description?: string;
  dsl: { nodes?: unknown[]; edges?: unknown[] };
}

const workflows = ref<Workflow[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const { query, filtered } = useSearchFilter(workflows);

const fetchWorkflows = async () => {
  loading.value = true;
  error.value = null;
  try {
    const { data } = await client.get('/workflows');
    workflows.value = data;
  } catch (err) {
    error.value = t('workflows.loadError');
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const deleteWorkflow = async (wf: Workflow) => {
  if (!confirm(t('workflows.deleteConfirm', { name: wf.name }))) return;
  try {
    await client.delete(`/workflows/${wf.id}`);
    workflows.value = workflows.value.filter((w) => w.id !== wf.id);
  } catch (err) {
    console.error('Delete failed:', err);
    toastError(t('workflows.deleteError'));
  }
};

onMounted(fetchWorkflows);
</script>
