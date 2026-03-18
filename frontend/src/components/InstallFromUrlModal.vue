<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    @click.self="$emit('close')"
  >
    <div class="w-full max-w-md rounded-xl bg-gray-900 p-6 shadow-xl">
      <h2 class="mb-4 text-lg font-semibold text-white">Install from URL</h2>

      <div class="mb-4">
        <label class="mb-1 block text-sm text-gray-400">URL or npx command</label>
        <input
          v-model="urlInput"
          type="text"
          class="w-full rounded-lg bg-gray-800 px-3 py-2 text-white placeholder-gray-500 outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="https://example.com/skill.md  or  npx @pkg/server"
          @input="onInputChange"
        />
        <div class="mt-1 h-5 text-sm">
          <span v-if="detecting" class="text-gray-400">Detecting…</span>
          <span v-else-if="detectedType" class="text-green-400">
            Detected as: {{ detectedType }} ✓
          </span>
          <span v-else-if="showManualSelector && urlInput" class="text-yellow-400">
            Cannot auto-detect — select type below
          </span>
        </div>
      </div>

      <div v-if="showManualSelector && urlInput" class="mb-4">
        <label class="mb-1 block text-sm text-gray-400">Plugin type</label>
        <select
          v-model="manualType"
          class="w-full rounded-lg bg-gray-800 px-3 py-2 text-white outline-none"
        >
          <option value="">-- choose --</option>
          <option value="mcp">MCP Server</option>
          <option value="skill_md">SKILL.md</option>
          <option value="python_plugin">Python Plugin</option>
        </select>
      </div>

      <div class="mb-6">
        <label class="mb-2 block text-sm text-gray-400">Install scope</label>
        <div class="flex gap-4">
          <label class="flex cursor-pointer items-center gap-2 text-white">
            <input v-model="scope" type="radio" value="personal" class="accent-blue-500" />
            Personal (just me)
          </label>
          <label
            class="flex items-center gap-2"
            :class="isAdmin ? 'cursor-pointer text-white' : 'cursor-not-allowed text-gray-500'"
            :title="isAdmin ? '' : 'Admin required for system-wide installs'"
          >
            <input
              v-model="scope"
              type="radio"
              value="system"
              :disabled="!isAdmin"
              class="accent-blue-500"
            />
            System-wide
          </label>
        </div>
      </div>

      <div class="flex justify-end gap-3">
        <button
          class="rounded-lg px-4 py-2 text-gray-400 hover:text-white"
          @click="$emit('close')"
        >
          Cancel
        </button>
        <button
          class="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          :disabled="!canInstall || installing"
          @click="doInstall"
        >
          {{ installing ? 'Installing…' : 'Install' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { useAuthStore } from "@/stores/auth";
import { marketApi } from "@/api/plugins";
import type { InstallRequest } from "@/api/plugins";

const emit = defineEmits<{
  close: [];
  installed: [pluginId: string];
}>();

const auth = useAuthStore();
const isAdmin = computed(() => auth.isAdmin);

const urlInput = ref("");
const scope = ref<"personal" | "system">("personal");
const detectedType = ref<string | null>(null);
const showManualSelector = ref(false);
const manualType = ref("");
const detecting = ref(false);
const installing = ref(false);

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer);
});

function onInputChange() {
  detectedType.value = null;
  showManualSelector.value = false;
  manualType.value = "";
  if (!urlInput.value.trim()) return;
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runDetect, 500);
}

async function runDetect() {
  detecting.value = true;
  try {
    const { data } = await marketApi.detect(urlInput.value.trim());
    detectedType.value = data.type;
    showManualSelector.value = false;
  } catch {
    detectedType.value = null;
    showManualSelector.value = true;
  } finally {
    detecting.value = false;
  }
}

const resolvedType = computed(() => detectedType.value || manualType.value || null);
const canInstall = computed(() => Boolean(urlInput.value.trim() && resolvedType.value));

async function doInstall() {
  if (!canInstall.value || !resolvedType.value) return;
  installing.value = true;
  try {
    const req: InstallRequest = {
      url: urlInput.value.trim(),
      type: resolvedType.value as InstallRequest["type"],
      scope: scope.value,
    };
    const { data } = await marketApi.install(req);
    emit("installed", data.plugin_id);
    emit("close");
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
      ?.detail;
    alert(typeof detail === "string" ? detail : "Install failed");
  } finally {
    installing.value = false;
  }
}
</script>
