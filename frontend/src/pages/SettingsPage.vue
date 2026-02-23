<template>
  <div class="settings-page">
    <h2>设置</h2>
    <label>模型提供商
      <select v-model="provider">
        <option value="deepseek">DeepSeek</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
      </select>
    </label>
    <label>模型名称 <input v-model="modelName" /></label>
    <label>API Key <input v-model="apiKey" type="password" /></label>
    <button @click="save">保存</button>
    <p v-if="saved">已保存</p>
    <router-link to="/">← 返回聊天</router-link>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import client from "@/api/client";

const provider = ref("deepseek"), modelName = ref("deepseek-chat"), apiKey = ref(""), saved = ref(false);

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
