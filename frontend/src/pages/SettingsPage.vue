<template>
  <div class="settings-page">
    <h2>{{ $t('settings.title') }}</h2>
    <label>{{ $t('settings.provider') }}
      <select v-model="provider">
        <option value="deepseek">DeepSeek</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
      </select>
    </label>
    <label>{{ $t('settings.modelName') }} <input v-model="modelName" /></label>
    <label>{{ $t('settings.apiKey') }} <input v-model="apiKey" type="password" /></label>
    <button @click="save">{{ $t('settings.save') }}</button>
    <p v-if="saved">{{ $t('settings.saved') }}</p>
    <router-link to="/">{{ $t('common.backToChat') }}</router-link>
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
