<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
    @click.self="$emit('close')"
  >
    <div
      class="bg-zinc-900 border border-zinc-700 rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl mx-4"
    >
      <div class="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
        <h2 class="text-sm font-semibold text-zinc-100">Prompt Templates</h2>
        <button class="p-1 hover:bg-zinc-800 rounded" @click="$emit('close')">
          <X class="w-4 h-4 text-zinc-400" />
        </button>
      </div>
      <div class="px-5 py-3 border-b border-zinc-800 space-y-3">
        <input
          v-model="search"
          type="text"
          placeholder="Filter templates..."
          class="w-full bg-zinc-800 rounded-md px-3 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
        />
        <div class="flex gap-2 flex-wrap">
          <button
            v-for="cat in CATEGORIES"
            :key="cat"
            :class="[
              'px-2.5 py-1 rounded-md text-xs transition-colors capitalize',
              activeCategory === cat
                ? 'bg-zinc-100 text-zinc-900 font-medium'
                : 'bg-zinc-800 text-zinc-400 hover:text-zinc-100',
            ]"
            @click="activeCategory = cat"
          >
            {{ cat === 'all' ? 'All' : cat }}
          </button>
        </div>
      </div>
      <div class="flex-1 overflow-y-auto p-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div
          v-for="t in filtered"
          :key="t.id"
          class="bg-zinc-800/60 border border-zinc-700/50 rounded-lg p-3 cursor-pointer hover:border-zinc-500 hover:bg-zinc-800 transition-all"
          @click="$emit('select', t)"
        >
          <div class="text-xs font-medium text-zinc-100 mb-1">{{ t.name }}</div>
          <div class="text-[11px] text-zinc-400 mb-2 line-clamp-2">{{ t.description }}</div>
          <div class="flex flex-wrap gap-1">
            <span
              v-for="tag in t.tags.slice(0, 3)"
              :key="tag"
              class="text-[10px] px-1.5 py-0.5 bg-zinc-700 rounded text-zinc-400"
              >{{ tag }}</span
            >
          </div>
        </div>
        <div
          v-if="filtered.length === 0"
          class="col-span-2 text-center py-10 text-xs text-zinc-500"
        >
          No templates match your filter
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { X } from 'lucide-vue-next'
import { PROMPT_TEMPLATES, type PromptTemplate } from '@/data/prompt-templates'

defineEmits<{ close: []; select: [template: PromptTemplate] }>()

const CATEGORIES = ['all', 'coding', 'analysis', 'writing', 'productivity', 'language'] as const
const search = ref('')
const activeCategory = ref<string>('all')

const filtered = computed(() =>
  PROMPT_TEMPLATES.filter((t) => {
    const catOk = activeCategory.value === 'all' || t.category === activeCategory.value
    const sq = search.value.toLowerCase()
    const searchOk =
      !sq ||
      t.name.toLowerCase().includes(sq) ||
      t.description.toLowerCase().includes(sq) ||
      t.tags.some((tag) => tag.includes(sq))
    return catOk && searchOk
  }),
)
</script>
