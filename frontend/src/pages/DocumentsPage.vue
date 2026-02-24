<template>
  <div class="page-container">
    <div class="page-card animate-slide-up">
      <div class="page-header">
        <h2>{{ $t("documents.title") }}</h2>
        <router-link to="/" class="back-link">{{ $t("common.backToChat") }}</router-link>
      </div>
      <div class="shimmer-line animate-shimmer"></div>

      <label
        class="upload-zone"
        :class="{ uploading: uploading }"
        @dragover.prevent
        @drop.prevent="onDrop"
      >
        <input
          type="file"
          accept=".pdf,.txt,.md,.docx"
          :disabled="uploading"
          class="file-input"
          @change="upload"
        />
        <div class="upload-content">
          <span class="upload-icon">&#8682;</span>
          <p class="upload-text">
            {{ uploading ? $t("documents.uploading") : $t("documents.title") }}
          </p>
          <p class="upload-hint">.pdf, .txt, .md, .docx</p>
        </div>
        <div v-if="uploading" class="progress-bar">
          <div class="progress-fill"></div>
        </div>
      </label>

      <div v-if="result" :class="['result-msg', resultType]">
        {{ result }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import client from "@/api/client";

const { t } = useI18n();
const uploading = ref(false);
const result = ref("");
const resultType = ref<"success" | "error">("success");

function onDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0];
  if (file) processFile(file);
}

function upload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) processFile(file);
}

async function processFile(file: File) {
  if (file.size > 50 * 1024 * 1024) {
    result.value = t("documents.fileTooLarge");
    resultType.value = "error";
    return;
  }
  uploading.value = true;
  result.value = "";
  const form = new FormData();
  form.append("file", file);
  try {
    const { data } = await client.post("/documents", form);
    result.value = t("documents.uploadSuccess", { count: data.chunk_count });
    resultType.value = "success";
  } catch {
    result.value = t("documents.uploadError");
    resultType.value = "error";
  } finally {
    uploading.value = false;
  }
}
</script>

<style scoped>
.page-card {
  max-width: 520px;
}

.upload-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-2xl) var(--space-lg);
  cursor: pointer;
  transition:
    border-color 0.3s ease,
    background 0.3s ease;
  position: relative;
  overflow: hidden;
}

.upload-zone:hover {
  border-color: var(--accent-dim);
  background: var(--accent-a03);
}

.upload-zone.uploading {
  border-color: var(--accent);
  pointer-events: none;
}

.file-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.upload-content {
  text-align: center;
}

.upload-icon {
  font-size: 36px;
  color: var(--accent-dim);
  display: block;
  margin-bottom: var(--space-md);
}

.upload-text {
  font-size: 15px;
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
}

.upload-hint {
  font-size: 13px;
  color: var(--text-muted);
}

.progress-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--bg-elevated);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-dim));
  border-radius: 2px;
  animation: shimmer 1.5s infinite;
  background-size: 200% 100%;
  width: 100%;
}

.result-msg {
  margin-top: var(--space-lg);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  font-size: 14px;
  text-align: center;
  animation: fadeIn 0.3s ease;
}

.result-msg.success {
  background: var(--success-a10);
  color: var(--success);
  border: 1px solid var(--success-a15);
}

.result-msg.error {
  background: var(--danger-a10);
  color: var(--danger);
  border: 1px solid var(--danger-a15);
}

@media (prefers-reduced-motion: reduce) {
  .progress-fill {
    animation: none;
  }

  .result-msg {
    animation: none;
  }
}
</style>
