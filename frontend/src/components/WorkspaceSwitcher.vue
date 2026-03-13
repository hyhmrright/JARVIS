<template>
  <div ref="dropdownRef" class="relative">
    <button
      class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800/60 hover:bg-zinc-700/60 border border-zinc-700/50 text-sm text-zinc-200 transition-colors"
      @click="open = !open"
    >
      <span class="max-w-[120px] truncate">
        {{ workspace.currentWorkspace?.name ?? $t("workspace.personal") }}
      </span>
      <ChevronDown
        class="w-3.5 h-3.5 text-zinc-400 shrink-0"
        :class="{ 'rotate-180': open }"
      />
    </button>

    <div
      v-if="open"
      class="absolute top-full mt-1 left-0 z-50 min-w-[180px] bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl py-1"
    >
      <button
        class="w-full text-left px-4 py-2 text-sm hover:bg-zinc-800 transition-colors"
        :class="{
          'text-white font-medium': !workspace.currentWorkspaceId,
          'text-zinc-300': workspace.currentWorkspaceId,
        }"
        @click="select(null)"
      >
        {{ $t("workspace.personal") }}
      </button>

      <div v-if="workspace.workspaces.length > 0" class="border-t border-zinc-800 my-1" />

      <button
        v-for="ws in workspace.workspaces"
        :key="ws.id"
        class="w-full text-left px-4 py-2 text-sm hover:bg-zinc-800 transition-colors"
        :class="{
          'text-white font-medium': workspace.currentWorkspaceId === ws.id,
          'text-zinc-300': workspace.currentWorkspaceId !== ws.id,
        }"
        @click="select(ws.id)"
      >
        {{ ws.name }}
      </button>

      <div class="border-t border-zinc-800 my-1" />

      <button
        class="w-full text-left px-4 py-2 text-xs text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
        @click="$router.push('/workspace/members'); open = false"
      >
        {{ $t("workspace.manageMembers") }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { ChevronDown } from "lucide-vue-next";
import { useWorkspaceStore } from "@/stores/workspace";

const workspace = useWorkspaceStore();
const open = ref(false);
const dropdownRef = ref<HTMLElement | null>(null);

function select(id: string | null) {
  workspace.switchWorkspace(id);
  open.value = false;
}

function handleOutside(e: MouseEvent) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    open.value = false;
  }
}

onMounted(() => document.addEventListener("mousedown", handleOutside));
onUnmounted(() => document.removeEventListener("mousedown", handleOutside));
</script>
