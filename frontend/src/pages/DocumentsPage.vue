<template>
  <div class="documents-page">
    <h2>{{ $t('documents.title') }}</h2>
    <input type="file" accept=".pdf,.txt,.md,.docx" @change="upload" :disabled="uploading" />
    <p v-if="uploading">{{ $t('documents.uploading') }}</p>
    <p v-if="result">{{ result }}</p>
    <router-link to="/">{{ $t('common.backToChat') }}</router-link>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import client from "@/api/client";

const { t } = useI18n();
const uploading = ref(false);
const result = ref("");

async function upload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  if (file.size > 50 * 1024 * 1024) {
    result.value = t("documents.fileTooLarge");
    return;
  }
  uploading.value = true;
  const form = new FormData();
  form.append("file", file);
  try {
    const { data } = await client.post("/documents", form);
    result.value = t("documents.uploadSuccess", { count: data.chunk_count });
  } catch {
    result.value = t("documents.uploadError");
  } finally {
    uploading.value = false;
  }
}
</script>
