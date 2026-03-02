<template>
  <div class="page-container">
    <PageHeader :title="$t('settings.title')" />

    <div class="page-content custom-scrollbar">
      <form class="settings-grid" @submit.prevent="save">
        <!-- AI Model Config -->
        <section class="glass-card section-card animate-fade-in">
          <h3 class="section-title">AI Model & Provider</h3>
          <div class="form-group">
            <label>{{ $t("settings.provider") }}</label>
            <select v-model="provider" class="modern-input" @change="onProviderChange">
              <option value="deepseek">DeepSeek</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="zhipuai">ZhipuAI (GLM)</option>
            </select>
          </div>

          <div class="form-group">
            <label>{{ $t("settings.modelName") }}</label>
            <select v-model="modelSelect" class="modern-input">
              <option v-for="m in currentProviderModels" :key="m" :value="m">{{ m }}</option>
              <option value="__custom__">{{ $t("settings.customModel") }}</option>
            </select>
            <input
              v-if="modelSelect === '__custom__'"
              v-model="customModelName"
              class="modern-input custom-input"
              :placeholder="$t('settings.customModelPlaceholder')"
            />
          </div>
        </section>

        <!-- API Keys -->
        <section class="glass-card section-card animate-fade-in">
          <h3 class="section-title">API Keys</h3>
          <p class="field-desc">Securely manage your keys for {{ provider.toUpperCase() }}</p>
          
          <div v-for="(_, index) in apiKeys" :key="index" class="api-key-row">
            <input
              v-model="apiKeys[index]"
              type="password"
              class="modern-input"
              :placeholder="$t('settings.apiKeyPlaceholder')"
            />
            <button
              v-if="apiKeys.length > 1"
              type="button"
              class="btn-icon-danger"
              @click="apiKeys.splice(index, 1)"
            >
              ×
            </button>
          </div>
          
          <button type="button" class="btn-ghost-full" @click="apiKeys.push('')">
            + Add Another Key
          </button>
          
          <div v-if="existingKeyCount > 0" class="key-status">
            {{ $t("settings.existingKeys", { count: existingKeyCount }) }} active
          </div>
        </section>

        <!-- Persona -->
        <section class="glass-card section-card full-width animate-fade-in">
          <h3 class="section-title">System Persona</h3>
          <div class="form-group">
            <label>{{ $t("settings.personaOverride") }}</label>
            <textarea
              v-model="personaOverride"
              class="modern-input persona-area"
              :placeholder="$t('settings.personaPlaceholder')"
              rows="4"
            ></textarea>
          </div>
        </section>

        <!-- Tools -->
        <section class="glass-card section-card full-width animate-fade-in">
          <h3 class="section-title">{{ $t("settings.toolPermissions") }}</h3>
          <p class="field-desc">{{ $t("settings.toolPermissionsDescription") }}</p>
          <div class="tool-grid">
            <label
              v-for="tool in toolRegistry"
              :key="tool.name"
              :class="['tool-pill', { active: enabledTools.includes(tool.name) }]"
            >
              <input
                type="checkbox"
                class="hidden-check"
                :checked="enabledTools.includes(tool.name)"
                @change="toggleTool(tool.name)"
              />
              <span class="tool-name">{{ tool.label }}</span>
            </label>
          </div>
        </section>

        <div class="form-actions">
          <button type="submit" class="btn-accent btn-large" :disabled="saving">
            {{ saving ? $t("settings.saving") : $t("settings.save") }}
          </button>
        </div>
      </form>
    </div>

    <!-- Toasts -->
    <Transition name="toast">
      <div v-if="saved" class="toast-popup success">{{ $t("settings.saved") }}</div>
    </Transition>
    <Transition name="toast">
      <div v-if="saveError" class="toast-popup error">{{ $t("settings.saveError") }}</div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import client from "@/api/client";
import PageHeader from "@/components/PageHeader.vue";

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
type PluginInfo = { id: string; name: string; version: string; description: string; tools: string[] };

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
  } catch {}
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

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background: var(--bg-primary); }
.page-content { flex: 1; padding: 2rem; overflow-y: auto; max-width: 1000px; width: 100%; margin: 0 auto; }

.settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
.section-card { padding: 1.5rem; }
.full-width { grid-column: span 2; }

.section-title { font-size: 0.8rem; font-weight: 800; text-transform: uppercase; color: var(--accent-light); letter-spacing: 1px; margin-bottom: 1.5rem; }

.form-group { display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1rem; }
.form-group label { font-size: 0.85rem; font-weight: 600; color: var(--text-secondary); }

.modern-input {
  background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: var(--radius-sm);
  color: var(--text-primary); padding: 0.75rem; font-size: 0.95rem; outline: none; transition: border-color 0.2s;
}
.modern-input:focus { border-color: var(--accent); }
.custom-input { margin-top: 0.5rem; }
.persona-area { height: 120px; resize: none; }

.api-key-row { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.btn-icon-danger {
  background: rgba(244, 67, 54, 0.1); color: #f44336; border: none; width: 40px; border-radius: var(--radius-sm); cursor: pointer;
}

.btn-ghost-full {
  background: transparent; border: 1px dashed var(--border); color: var(--text-muted);
  width: 100%; padding: 0.6rem; border-radius: var(--radius-sm); cursor: pointer; font-size: 0.85rem;
}
.btn-ghost-full:hover { border-color: var(--accent); color: var(--accent); }

.key-status { font-size: 0.75rem; color: #4caf50; margin-top: 0.5rem; }

/* ── Tool Grid ── */
.tool-grid { display: flex; flex-wrap: wrap; gap: 0.75rem; }
.tool-pill {
  padding: 0.5rem 1rem; border-radius: var(--radius-full); border: 1px solid var(--border);
  color: var(--text-secondary); cursor: pointer; transition: all 0.2s; font-size: 0.85rem;
}
.tool-pill.active { background: var(--accent); border-color: var(--accent); color: white; }
.hidden-check { display: none; }

.form-actions { grid-column: span 2; display: flex; justify-content: flex-end; padding-top: 1rem; }
.btn-accent.btn-large { padding: 0.8rem 2.5rem; font-size: 1rem; }

/* ── Toast ── */
.toast-popup {
  position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%);
  padding: 0.75rem 2rem; border-radius: var(--radius-full); font-weight: 600; z-index: 2000;
  box-shadow: var(--shadow-lg);
}
.toast-popup.success { background: #4caf50; color: white; }
.toast-popup.error { background: #f44336; color: white; }

.animate-fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translate(-50%, 20px); }
</style>
