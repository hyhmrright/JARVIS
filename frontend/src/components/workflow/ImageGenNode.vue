<template>
  <div
    class="w-72 bg-zinc-900 border-2 rounded-xl shadow-xl overflow-hidden transition-colors"
    :class="selected ? 'border-pink-500' : 'border-zinc-800'"
  >
    <Handle type="target" :position="Position.Top" />

    <div class="px-4 py-3 bg-zinc-800/50 border-b border-zinc-800 flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-pink-500/20 flex items-center justify-center text-pink-400">
        <ImageIcon class="w-4 h-4" />
      </div>
      <div>
        <h3 class="text-sm font-bold text-zinc-100">{{ data.label || 'Image Generation' }}</h3>
        <p class="text-[10px] text-zinc-500 uppercase tracking-widest">DALL-E 3</p>
      </div>
    </div>

    <!-- eslint-disable vue/no-mutating-props -->
    <div class="p-4 space-y-4">
      <div class="space-y-1.5">
        <label class="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Prompt</label>
        <textarea
          v-model="data.prompt"
          rows="3"
          class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-300 outline-none focus:border-pink-500 transition-colors resize-none nodrag"
          placeholder="Describe the image to generate..."
        ></textarea>
      </div>

      <div class="space-y-1.5">
        <label class="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Size</label>
        <select
          v-model="data.size"
          class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-300 outline-none focus:border-pink-500 nodrag"
        >
          <option value="1024x1024">1024 x 1024</option>
        </select>
      </div>
      <!-- eslint-enable vue/no-mutating-props -->

      <!-- Execution Status Indicator -->
      <div v-if="data.status" class="pt-3 border-t border-zinc-800/50 flex items-center justify-between">
        <span
          class="text-[10px] font-bold uppercase tracking-widest"
          :class="{
            'text-amber-500': data.status === 'pending',
            'text-emerald-500': data.status === 'completed',
            'text-red-500': data.status === 'failed'
          }"
        >{{ data.status }}</span>
        <a
          v-if="data.output && data.output.startsWith('Image generated')"
          :href="data.output.split(' ').pop()"
          target="_blank"
          class="text-[10px] text-pink-400 hover:text-pink-300 underline"
        >View Image</a>
      </div>
    </div>

    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core';
import { Image as ImageIcon } from 'lucide-vue-next';

defineProps<{
  selected?: boolean;
  data: {
    label: string;
    prompt: string;
    size?: string;
    status?: 'pending' | 'completed' | 'failed';
    output?: string;
  };
}>();
</script>
