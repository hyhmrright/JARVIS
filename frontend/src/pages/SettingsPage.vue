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
          <select id="modelSelect" v-model="modelSelect" @change="onModelSelectChange">
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
          <label for="apiKey">{{ $t("settings.apiKey") }}</label>
          <input id="apiKey" v-model="apiKey" type="password" />
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

        <button type="submit" class="btn-primary animate-slide-up-delay-4">
          {{ $t("settings.save") }}
        </button>
      </form>

      <Transition name="toast">
        <div v-if="saved" class="toast-success">
          {{ $t("settings.saved") }}
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
const apiKey = ref("");
const personaOverride = ref("");
const saved = ref(false);

const currentProviderModels = computed(
  () => PROVIDER_MODELS[provider.value] ?? [],
);

const effectiveModelName = computed(() =>
  modelSelect.value === "__custom__" ? customModelName.value : modelSelect.value,
);

function onProviderChange() {
  const defaultModel = DEFAULT_MODEL[provider.value] ?? PROVIDER_MODELS[provider.value]?.[0] ?? "";
  modelSelect.value = defaultModel;
  customModelName.value = "";
}

function onModelSelectChange() {
  // reactive — template handles show/hide of custom input
}

onMounted(async () => {
  try {
    const { data } = await client.get("/settings");
    provider.value = data.model_provider;
    personaOverride.value = data.persona_override ?? "";

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
  const payload: Record<string, unknown> = {
    model_provider: provider.value,
    model_name: effectiveModelName.value,
    persona_override: personaOverride.value || null,
  };
  if (apiKey.value) {
    payload.api_keys = { [provider.value]: apiKey.value };
  }
  await client.put("/settings", payload);
  saved.value = true;
  setTimeout(() => (saved.value = false), 2000);
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
