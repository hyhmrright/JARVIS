<template>
  <div class="documents-page">
    <h2>知识库</h2>
    <input type="file" accept=".pdf,.txt,.md,.docx" @change="upload" :disabled="uploading" />
    <p v-if="uploading">上传中...</p>
    <p v-if="result">{{ result }}</p>
    <router-link to="/">← 返回聊天</router-link>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import client from "@/api/client";

const uploading = ref(false), result = ref("");

async function upload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  if (file.size > 50 * 1024 * 1024) { result.value = "文件不能超过 50MB"; return; }
  uploading.value = true;
  const form = new FormData();
  form.append("file", file);
  try {
    const { data } = await client.post("/documents", form);
    result.value = `上传成功，共切分 ${data.chunk_count} 个片段`;
  } catch {
    result.value = "上传失败，请检查文件格式";
  } finally {
    uploading.value = false;
  }
}
</script>
