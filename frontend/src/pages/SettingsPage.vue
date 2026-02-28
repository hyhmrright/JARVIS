<template>
  <div class="page-container">
    <div class="page-card animate-slide-up">
      <div class="page-header">
        <h2>{{ $t("settings.title") }}</h2>
        <router-link to="/" class="back-link">{{ $t("common.backToChat") }}</router-link>
      </div>
      <div class="shimmer-line animate-shimmer"></div>

      <form class="settings-form" @submit.prevent="save">
        <div class="form-group animate-slide-up-delay-1">
          <label for="provider">{{ $t("settings.provider") }}</label>
          <select id="provider" v-model="provider" @change="onProviderChange">
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="zhipuai">ZhipuAI (GLM)</option>
          </select>
        </div>

        <div class="form-group animate-slide-up-delay-2">
          <label for="modelSelect">{{ $t("settings.modelName") }}</label>
          <select id="modelSelect" v-model="modelSelect">
            <option v-for="m in currentProviderModels" :key="m" :value="m">{{ m }}</option>
            <option value="__custom__">{{ $t("settings.customModel") }}</option>
          </select>
          <input
            v-if="modelSelect === '__custom__'"
            id="modelName"
            v-model="customModelName"
            class="custom-model-input"
            :placeholder="$t('settings.customModelPlaceholder')"
            autocomplete="off"
          />
        </div>

        <div class="form-group animate-slide-up-delay-2">
          <label>{{ $t("settings.apiKeys") }}</label>
          <div v-for="(_, index) in apiKeys" :key="index" class="api-key-row">
            <input
              v-model="apiKeys[index]"
              type="password"
              :placeholder="$t('settings.apiKeyPlaceholder')"
            />
            <button
              v-if="apiKeys.length > 1"
              type="button"
              class="btn-remove-key"
              @click="apiKeys.splice(index, 1)"
            >
              &times;
            </button>
          </div>
          <button type="button" class="btn-add-key" @click="apiKeys.push('')">
            + {{ $t("settings.addApiKey") }}
          </button>
          <div v-if="existingKeyCount > 0" class="key-info">
            {{ $t("settings.existingKeys", { count: existingKeyCount }) }}
          </div>
        </div>

        <div class="form-group animate-slide-up-delay-3">
          <label for="personaOverride">{{ $t("settings.personaOverride") }}</label>
          <textarea
            id="personaOverride"
            v-model="personaOverride"
            :placeholder="$t('settings.personaPlaceholder')"
            rows="4"
            maxlength="2000"
          />
        </div>

        <div class="form-group animate-slide-up-delay-4">
          <label>{{ $t("settings.toolPermissions") }}</label>
          <p class="field-description">{{ $t("settings.toolPermissionsDescription") }}</p>
          <div class="tool-list">
            <label
              v-for="tool in toolRegistry"
              :key="tool.name"
              class="tool-item"
            >
              <input
                type="checkbox"
                :checked="enabledTools.includes(tool.name)"
                @change="toggleTool(tool.name)"
              />
              <span class="tool-label">{{ tool.label }}</span>
              <span class="tool-desc">{{ tool.description }}</span>
            </label>
          </div>
        </div>

        <button type="submit" class="btn-primary animate-slide-up-delay-4" :disabled="saving">
          {{ saving ? $t("settings.saving") : $t("settings.save") }}
        </button>
      </form>

      <Transition name="toast">
        <div v-if="saved" class="toast-success">
          {{ $t("settings.saved") }}
        </div>
      </Transition>
      <Transition name="toast">
        <div v-if="saveError" class="toast-error">
          {{ $t("settings.saveError") }}
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import client from "@/api/client";

const PROVIDER_MODELS: Record<string, string[]> = {
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  openai: ["gpt-4o-mini", "gpt-4o", "o1-mini", "o3-mini"],
  anthropic: ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
  zhipuai: [
    "glm-4-flash",
    "glm-4",
    "glm-4-plus",
    "glm-4.5",
    "glm-4.7",
    "glm-4.7-FlashX",
    "glm-5",
    "glm-z1-flash",
  ],
};

const DEFAULT_MODEL: Record<string, string> = {
  deepseek: "deepseek-chat",
  openai: "gpt-4o-mini",
  anthropic: "claude-3-5-haiku-20241022",
  zhipuai: "glm-4-flash",
};

const provider = ref("deepseek");
const modelSelect = ref("deepseek-chat");
const customModelName = ref("");
const apiKeys = ref<string[]>([""]);
const keyCounts = ref<Record<string, number>>({});
const personaOverride = ref("");
const enabledTools = ref<string[]>([]);
const toolRegistry = ref<{ name: string; label: string; description: string; default_enabled: boolean }[]>([]);
const saved = ref(false);
const saving = ref(false);
const saveError = ref(false);

const currentProviderModels = computed(
  () => PROVIDER_MODELS[provider.value] ?? [],
);

const effectiveModelName = computed(() =>
  modelSelect.value === "__custom__" ? customModelName.value : modelSelect.value,
);

const existingKeyCount = computed(() => keyCounts.value[provider.value] ?? 0);

function onProviderChange() {
  const defaultModel = DEFAULT_MODEL[provider.value] ?? PROVIDER_MODELS[provider.value]?.[0] ?? "";
  modelSelect.value = defaultModel;
  customModelName.value = "";
  apiKeys.value = [""];
}

function toggleTool(name: string) {
  const idx = enabledTools.value.indexOf(name);
  if (idx >= 0) {
    enabledTools.value.splice(idx, 1);
  } else {
    enabledTools.value.push(name);
  }
}

onMounted(async () => {
  try {
    const { data } = await client.get("/settings");
    provider.value = data.model_provider;
    personaOverride.value = data.persona_override ?? "";

    keyCounts.value = (data.key_counts ?? {}) as Record<string, number>;
    toolRegistry.value = (data.tool_registry ?? []) as typeof toolRegistry.value;
    enabledTools.value = (data.enabled_tools ?? []) as string[];

    const savedModel: string = data.model_name ?? "";
    const models = PROVIDER_MODELS[provider.value] ?? [];
    if (models.includes(savedModel)) {
      modelSelect.value = savedModel;
    } else {
      modelSelect.value = "__custom__";
      customModelName.value = savedModel;
    }
  } catch {
    // Use defaults on error
  }
});

async function save() {
  saving.value = true;
  saveError.value = false;
  try {
    const payload: Record<string, unknown> = {
      model_provider: provider.value,
      model_name: effectiveModelName.value,
      persona_override: personaOverride.value || null,
      enabled_tools: enabledTools.value,
    };
    const nonEmptyKeys = apiKeys.value.filter((k: string) => k.trim());
    if (nonEmptyKeys.length > 0) {
      payload.api_keys = { [provider.value]: nonEmptyKeys };
    }
    await client.put("/settings", payload);
    // Refresh key counts from server after save
    const { data: refreshed } = await client.get("/settings");
    keyCounts.value = (refreshed.key_counts ?? {}) as Record<string, number>;
    apiKeys.value = [""];
    saved.value = true;
    setTimeout(() => (saved.value = false), 2000);
  } catch {
    saveError.value = true;
    setTimeout(() => (saveError.value = false), 3000);
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.page-card {
  max-width: 480px;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.custom-model-input {
  margin-top: var(--space-sm);
}

.api-key-row {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-xs);
}

.api-key-row input {
  flex: 1;
}

.btn-remove-key {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--danger-a10, rgba(255, 59, 48, 0.1));
  border: 1px solid var(--danger, #ff3b30);
  color: var(--danger, #ff3b30);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.btn-add-key {
  background: transparent;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  padding: 6px 12px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  width: 100%;
  text-align: center;
}

.btn-add-key:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.key-info {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: var(--space-xs);
}

.field-description {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 var(--space-sm) 0;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.tool-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color 0.2s;
}

.tool-item:hover {
  border-color: var(--accent);
}

.tool-item input[type="checkbox"] {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  accent-color: var(--accent);
}

.tool-label {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

.tool-desc {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toast-success {
  margin-top: var(--space-lg);
  padding: var(--space-md);
  background: var(--accent-a10);
  border: 1px solid var(--border-glow);
  border-radius: var(--radius-md);
  color: var(--accent);
  text-align: center;
  font-size: 14px;
}

.toast-error {
  margin-top: var(--space-lg);
  padding: var(--space-md);
  background: var(--danger-a10, rgba(255, 59, 48, 0.1));
  border: 1px solid var(--danger, #ff3b30);
  border-radius: var(--radius-md);
  color: var(--danger, #ff3b30);
  text-align: center;
  font-size: 14px;
}

.toast-enter-active {
  animation: slideUp 0.3s ease;
}

.toast-leave-active {
  animation: fadeIn 0.3s ease reverse;
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    animation: none;
  }
}
</style>
