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
                  <option value="ollama">Ollama (Local)</option>
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

        <!-- Personal API Keys (PAT) -->
        <section class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6 shadow-sm">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase">
              {{ $t('apiKeys.title') }}
            </h3>
            <button
              type="button"
              class="text-xs font-medium px-3 py-1.5 bg-blue-600/20 text-blue-400 rounded-lg hover:bg-blue-600/30 transition-colors"
              @click="showCreateKeyModal = true"
            >
              + {{ $t('apiKeys.create') }}
            </button>
          </div>
          <p class="text-xs text-zinc-500 mb-4">{{ $t('apiKeys.description') }}</p>
          <div v-if="apiKeysList.length === 0" class="text-xs text-zinc-600 italic">
            {{ $t('apiKeys.empty') }}
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="key in apiKeysList"
              :key="key.id"
              class="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-zinc-200 truncate">{{ key.name }}</span>
                  <span
                    class="text-[10px] px-1.5 py-0.5 rounded font-mono"
                    :class="key.scope === 'readonly' ? 'bg-amber-500/20 text-amber-400' : 'bg-green-500/20 text-green-400'"
                  >{{ key.scope }}</span>
                </div>
                <div class="text-xs text-zinc-500 font-mono mt-0.5">
                  {{ key.prefix }}••••••••
                  <span v-if="key.last_used_at" class="ml-3 font-sans">
                    {{ $t('apiKeys.lastUsed') }}: {{ new Date(key.last_used_at).toLocaleDateString() }}
                  </span>
                </div>
              </div>
              <button
                type="button"
                class="ml-4 text-xs text-red-400 hover:text-red-300 transition-colors"
                @click="handleDeleteKey(key.id)"
              >
                {{ $t('apiKeys.revoke') }}
              </button>
            </div>
          </div>
        </section>

        <!-- Create Key Modal -->
        <Teleport to="body">
          <div v-if="showCreateKeyModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div class="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-sm mx-4 shadow-xl">
              <h4 class="text-sm font-semibold text-zinc-200 mb-4">{{ $t('apiKeys.createTitle') }}</h4>
              <div class="space-y-3">
                <input
                  v-model="newKeyName"
                  type="text"
                  class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
                  :placeholder="$t('apiKeys.namePlaceholder')"
                />
                <select
                  v-model="newKeyScope"
                  class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
                >
                  <option value="full">full — {{ $t('apiKeys.scopeFull') }}</option>
                  <option value="readonly">readonly — {{ $t('apiKeys.scopeReadonly') }}</option>
                </select>
              </div>
              <div class="flex gap-3 mt-5">
                <button
                  type="button"
                  class="flex-1 py-2.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors"
                  @click="handleCreateKey"
                >{{ $t('apiKeys.create') }}</button>
                <button
                  type="button"
                  class="flex-1 py-2.5 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors"
                  @click="showCreateKeyModal = false"
                >{{ $t('common.cancel') }}</button>
              </div>
            </div>
          </div>
        </Teleport>

        <!-- One-time key reveal modal -->
        <Teleport to="body">
          <div v-if="justCreatedKey" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div class="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-xl">
              <h4 class="text-sm font-semibold text-zinc-200 mb-2">{{ $t('apiKeys.revealTitle') }}</h4>
              <p class="text-xs text-amber-400 mb-4">{{ $t('apiKeys.revealWarning') }}</p>
              <div class="flex items-center gap-2 bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-3">
                <code class="flex-1 text-xs font-mono text-green-400 break-all">{{ justCreatedKey }}</code>
                <button type="button" class="text-xs text-zinc-400 hover:text-zinc-200 transition-colors whitespace-nowrap" @click="copyKey">
                  {{ keysCopied ? $t('common.copied') : $t('common.copy') }}
                </button>
              </div>
              <button
                type="button"
                class="w-full mt-4 py-2.5 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors"
                @click="justCreatedKey = null"
              >{{ $t('common.close') }}</button>
            </div>
          </div>
        </Teleport>

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
import { listApiKeys, createApiKey, deleteApiKey } from "@/api/keys";
import type { ApiKeyItem, ApiKeyCreateRequest } from "@/api/keys";

const { locale, t } = useI18n();

const onLocaleChange = (e: Event) => {
  const newLocale = (e.target as HTMLSelectElement).value;
  locale.value = newLocale;
  localStorage.setItem('jarvis_locale', newLocale);
};

const providerModels = ref<Record<string, string[]>>({
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  openai: ["gpt-4o-mini", "gpt-4o", "o1-mini", "o3-mini"],
  anthropic: ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
  zhipuai: ["glm-4-flash", "glm-4", "glm-4-plus", "glm-4.5", "glm-4.7", "glm-4.7-FlashX", "glm-5", "glm-z1-flash"],
  ollama: [],
});

const DEFAULT_MODEL: Record<string, string> = {
  deepseek: "deepseek-chat", openai: "gpt-4o-mini", anthropic: "claude-3-5-haiku-20241022", zhipuai: "glm-4-flash", ollama: "",
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

const currentProviderModels = computed(() => providerModels.value[provider.value] ?? []);
const effectiveModelName = computed(() => modelSelect.value === "__custom__" ? customModelName.value : modelSelect.value);
const existingKeyCount = computed(() => keyCounts.value[provider.value] ?? 0);

async function loadModels() {
  try {
    const { data } = await client.get("/settings/models");
    providerModels.value = data;
  } catch (err) {
    console.error("[settings] Failed to load models:", err);
  }
}

function onProviderChange() {
  modelSelect.value = DEFAULT_MODEL[provider.value] ?? providerModels.value[provider.value]?.[0] ?? "";
  customModelName.value = "";
  apiKeys.value = [""];
}

function toggleTool(name: string) {
  const idx = enabledTools.value.indexOf(name);
  if (idx >= 0) enabledTools.value.splice(idx, 1);
  else enabledTools.value.push(name);
}

// ── Personal API Keys ──────────────────────────────────────────────────────
const apiKeysList = ref<ApiKeyItem[]>([]);
const showCreateKeyModal = ref(false);
const newKeyName = ref("");
const newKeyScope = ref<"full" | "readonly">("full");
const justCreatedKey = ref<string | null>(null);
const keysCopied = ref(false);

async function loadApiKeys(): Promise<void> {
  try {
    apiKeysList.value = await listApiKeys();
  } catch {
    // silently ignore on load failure
  }
}

async function handleCreateKey(): Promise<void> {
  if (!newKeyName.value.trim()) return;
  const req: ApiKeyCreateRequest = {
    name: newKeyName.value.trim(),
    scope: newKeyScope.value,
  };
  const resp = await createApiKey(req);
  justCreatedKey.value = resp.raw_key;
  newKeyName.value = "";
  newKeyScope.value = "full";
  showCreateKeyModal.value = false;
  await loadApiKeys();
}

async function handleDeleteKey(id: string): Promise<void> {
  if (!confirm(t("apiKeys.confirmDelete"))) return;
  await deleteApiKey(id);
  await loadApiKeys();
}

function copyKey(): void {
  if (justCreatedKey.value) {
    navigator.clipboard.writeText(justCreatedKey.value);
    keysCopied.value = true;
    setTimeout(() => (keysCopied.value = false), 2000);
  }
}

onMounted(async () => {
  await loadModels();
  try {
    const { data } = await client.get("/settings");
    provider.value = data.model_provider;
    personaOverride.value = data.persona_override ?? "";
    keyCounts.value = data.key_counts ?? {};
    toolRegistry.value = data.tool_registry ?? [];
    enabledTools.value = data.enabled_tools ?? [];
    const savedModel = data.model_name ?? "";
    if (providerModels.value[provider.value]?.includes(savedModel)) modelSelect.value = savedModel;
    else { modelSelect.value = "__custom__"; customModelName.value = savedModel; }
  } catch { /* settings not yet saved, use defaults */ }
  await loadApiKeys();
});

async function save() {
  saving.value = true;
  try {
    const payload: any = { model_provider: provider.value, model_name: effectiveModelName.value, persona_override: personaOverride.value || null, enabled_tools: enabledTools.value };
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
