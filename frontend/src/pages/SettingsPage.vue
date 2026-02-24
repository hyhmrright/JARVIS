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
          <select id="provider" v-model="provider">
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>
        <div class="form-group animate-slide-up-delay-2">
          <label for="modelName">{{ $t("settings.modelName") }}</label>
          <input id="modelName" v-model="modelName" />
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
import { ref, onMounted } from "vue";
import client from "@/api/client";

const provider = ref("deepseek");
const modelName = ref("deepseek-chat");
const apiKey = ref("");
const personaOverride = ref("");
const saved = ref(false);

onMounted(async () => {
  try {
    const { data } = await client.get("/settings");
    provider.value = data.model_provider;
    modelName.value = data.model_name;
    personaOverride.value = data.persona_override || "";
  } catch {
    // Use defaults on error
  }
});

async function save() {
  const payload: Record<string, unknown> = {
    model_provider: provider.value,
    model_name: modelName.value,
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
