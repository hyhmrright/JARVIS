<template>
  <div class="h-screen flex flex-col bg-zinc-950 font-sans text-zinc-200">
    <PageHeader :title="$t('settings.title')" />

    <div class="flex-1 overflow-y-auto custom-scrollbar p-8">
      <form class="max-w-4xl mx-auto space-y-8 pb-20" @submit.prevent="save">
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <!-- AI Model Config -->
          <section class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6 shadow-sm">
            <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase mb-6">AI Model & Provider</h3>
            
            <div class="space-y-4">
              <div class="flex flex-col gap-2">
                <label class="text-xs font-semibold text-zinc-400">{{ $t("settings.provider") }}</label>
                <select v-model="provider" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" @change="onProviderChange">
                  <option value="deepseek">DeepSeek</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="zhipuai">ZhipuAI (GLM)</option>
                </select>
              </div>

              <div class="flex flex-col gap-2">
                <label class="text-xs font-semibold text-zinc-400">{{ $t("settings.modelName") }}</label>
                <select v-model="modelSelect" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors">
                  <option v-for="m in currentProviderModels" :key="m" :value="m">{{ m }}</option>
                  <option value="__custom__">{{ $t("settings.customModel") }}</option>
                </select>
                <input
                  v-if="modelSelect === '__custom__'"
                  v-model="customModelName"
                  class="mt-2 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors"
                  :placeholder="$t('settings.customModelPlaceholder')"
                />
              </div>
            </div>
          </section>

          <!-- API Keys -->
          <section class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6 shadow-sm">
            <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase mb-2">API Keys</h3>
            <p class="text-xs text-zinc-500 mb-6">Securely manage your keys for {{ provider.toUpperCase() }}</p>
            
            <div class="space-y-3">
              <div v-for="(_, index) in apiKeys" :key="index" class="flex gap-2">
                <input
                  v-model="apiKeys[index]"
                  type="password"
                  class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors"
                  :placeholder="$t('settings.apiKeyPlaceholder')"
                />
                <button
                  v-if="apiKeys.length > 1"
                  type="button"
                  class="w-10 flex items-center justify-center bg-red-500/10 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors"
                  @click="apiKeys.splice(index, 1)"
                >
                  ×
                </button>
              </div>
              
              <button type="button" class="w-full py-2.5 border border-dashed border-zinc-700 text-zinc-500 text-xs font-medium rounded-lg hover:border-zinc-500 hover:text-zinc-300 transition-colors" @click="apiKeys.push('')">
                + Add Another Key
              </button>
              
              <div v-if="existingKeyCount > 0" class="text-[11px] text-emerald-400 mt-2 font-medium">
                {{ $t("settings.existingKeys", { count: existingKeyCount }) }} active
              </div>
            </div>
          </section>
        </div>

        <!-- Global Preferences -->
        <section class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6 shadow-sm">
          <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase mb-6">Global Preferences</h3>
          
          <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">Language / 语言</label>
              <select 
                v-model="locale" 
                class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors"
                @change="onLocaleChange"
              >
                <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">{{ code }}</option>
              </select>
            </div>
            
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">{{ $t("settings.personaOverride") }}</label>
              <textarea
                v-model="personaOverride"
                class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-sm outline-none focus:border-zinc-600 transition-colors resize-none h-24"
                :placeholder="$t('settings.personaPlaceholder')"
              ></textarea>
            </div>
          </div>
        </section>

        <!-- Tools -->
        <section class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6 shadow-sm">
          <div class="mb-6">
            <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase mb-2">{{ $t("settings.toolPermissions") }}</h3>
            <p class="text-xs text-zinc-500">{{ $t("settings.toolPermissionsDescription") }}</p>
          </div>
          
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <label
              v-for="tool in toolRegistry"
              :key="tool.name"
              :class="[
                'flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all select-none',
                enabledTools.includes(tool.name) 
                  ? 'bg-zinc-800 border-zinc-700 text-white' 
                  : 'bg-zinc-950/50 border-zinc-800/50 text-zinc-500 hover:border-zinc-700/50 hover:bg-zinc-900'
              ]"
            >
              <input
                type="checkbox"
                class="hidden"
                :checked="enabledTools.includes(tool.name)"
                @change="toggleTool(tool.name)"
              />
              <div :class="['w-3 h-3 rounded-full border flex-shrink-0 transition-colors', enabledTools.includes(tool.name) ? 'bg-white border-white' : 'border-zinc-600 bg-transparent']"></div>
              <span class="text-xs font-medium">{{ tool.label }}</span>
            </label>
          </div>
        </section>

        <div class="flex justify-end pt-4">
          <button type="submit" class="px-8 py-3 bg-white text-black text-sm font-bold rounded-lg hover:bg-zinc-200 transition-colors disabled:opacity-50" :disabled="saving">
            {{ saving ? $t("settings.saving") : $t("settings.save") }}
          </button>
        </div>
      </form>
    </div>

    <!-- Toasts -->
    <Transition name="fade">
      <div v-if="saved" class="fixed bottom-8 left-1/2 -translate-x-1/2 px-6 py-3 bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-full text-sm font-medium backdrop-blur-md z-50">
        {{ $t("settings.saved") }}
      </div>
    </Transition>
    <Transition name="fade">
      <div v-if="saveError" class="fixed bottom-8 left-1/2 -translate-x-1/2 px-6 py-3 bg-red-500/20 text-red-400 border border-red-500/20 rounded-full text-sm font-medium backdrop-blur-md z-50">
        {{ $t("settings.saveError") }}
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import client from "@/api/client";
import PageHeader from "@/components/PageHeader.vue";
import { SUPPORTED_LOCALES } from "@/i18n";

const { locale } = useI18n();

const onLocaleChange = (e: Event) => {
  const newLocale = (e.target as HTMLSelectElement).value;
  locale.value = newLocale;
  localStorage.setItem('jarvis_locale', newLocale);
};

const PROVIDER_MODELS: Record<string, string[]> = {
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  openai: ["gpt-4o-mini", "gpt-4o", "o1-mini", "o3-mini"],
  anthropic: ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
  zhipuai: ["glm-4-flash", "glm-4", "glm-4-plus", "glm-4.5", "glm-4.7", "glm-4.7-FlashX", "glm-5", "glm-z1-flash"],
};

const DEFAULT_MODEL: Record<string, string> = {
  deepseek: "deepseek-chat", openai: "gpt-4o-mini", anthropic: "claude-3-5-haiku-20241022", zhipuai: "glm-4-flash",
};

type ToolRegistry = { name: string; label: string; description: string; default_enabled: boolean };

const provider = ref("deepseek");
const modelSelect = ref("deepseek-chat");
const customModelName = ref("");
const apiKeys = ref<string[]>([""]);
const keyCounts = ref<Record<string, number>>({});
const personaOverride = ref("");
const enabledTools = ref<string[]>([]);
const toolRegistry = ref<ToolRegistry[]>([]);
const saved = ref(false);
const saving = ref(false);
const saveError = ref(false);

const currentProviderModels = computed(() => PROVIDER_MODELS[provider.value] ?? []);
const effectiveModelName = computed(() => modelSelect.value === "__custom__" ? customModelName.value : modelSelect.value);
const existingKeyCount = computed(() => keyCounts.value[provider.value] ?? 0);

function onProviderChange() {
  modelSelect.value = DEFAULT_MODEL[provider.value] ?? PROVIDER_MODELS[provider.value]?.[0] ?? "";
  customModelName.value = "";
  apiKeys.value = [""];
}

function toggleTool(name: string) {
  const idx = enabledTools.value.indexOf(name);
  if (idx >= 0) enabledTools.value.splice(idx, 1);
  else enabledTools.value.push(name);
}

onMounted(async () => {
  try {
    const { data } = await client.get("/settings");
    provider.value = data.model_provider;
    personaOverride.value = data.persona_override ?? "";
    keyCounts.value = data.key_counts ?? {};
    toolRegistry.value = data.tool_registry ?? [];
    enabledTools.value = data.enabled_tools ?? [];
    const savedModel = data.model_name ?? "";
    if (PROVIDER_MODELS[provider.value]?.includes(savedModel)) modelSelect.value = savedModel;
    else { modelSelect.value = "__custom__"; customModelName.value = savedModel; }
  } catch { /* settings not yet saved, use defaults */ }
});

async function save() {
  saving.value = true;
  try {
    const payload: Record<string, unknown> = { model_provider: provider.value, model_name: effectiveModelName.value, persona_override: personaOverride.value || null, enabled_tools: enabledTools.value };
    const nonEmptyKeys = apiKeys.value.filter(k => k.trim());
    if (nonEmptyKeys.length > 0) payload.api_keys = { [provider.value]: nonEmptyKeys };
    await client.put("/settings", payload);
    const { data: refreshed } = await client.get("/settings");
    keyCounts.value = refreshed.key_counts ?? {};
    apiKeys.value = [""];
    saved.value = true;
    setTimeout(() => saved.value = false, 2000);
  } catch {
    saveError.value = true;
    setTimeout(() => saveError.value = false, 3000);
  } finally { saving.value = false; }
}
</script>
