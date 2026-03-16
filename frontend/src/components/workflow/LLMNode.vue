<template>
  <div class="px-4 py-3 shadow-md rounded-xl bg-zinc-900 border-2 border-zinc-800 group hover:border-zinc-600 transition-all min-w-[180px]">
    <div class="flex items-center gap-2 mb-2">
      <div class="w-6 h-6 rounded bg-purple-500/20 text-purple-400 flex items-center justify-center">
        <MessageSquare class="w-3.5 h-3.5" />
      </div>
      <div class="text-[10px] font-black uppercase tracking-widest text-zinc-400">LLM Node</div>
    </div>
    
    <div class="text-[12px] font-bold text-white truncate mb-1">{{ data.label }}</div>
    <div class="text-[9px] text-zinc-500 font-medium">{{ data.model }}</div>

    <Handle type="target" :position="Position.Top" class="!bg-zinc-600" />
    <Handle type="source" :position="Position.Bottom" class="!bg-zinc-600" />
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core';
import { MessageSquare } from 'lucide-vue-next';

defineProps<{
  data: {
    label: string;
    model: string;
    prompt?: string;
  };
}>();
</script>
