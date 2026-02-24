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
        <button type="submit" class="btn-primary animate-slide-up-delay-3">
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
import { ref } from "vue";
import client from "@/api/client";

const provider = ref("deepseek");
const modelName = ref("deepseek-chat");
const apiKey = ref("");
const saved = ref(false);

async function save() {
  await client.put("/settings", {
    model_provider: provider.value,
    model_name: modelName.value,
    api_keys: { [provider.value]: apiKey.value },
  });
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
