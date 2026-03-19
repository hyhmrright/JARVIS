<template>
  <div class="page-container">
    <PageHeader :title="$t('documents.title')" />

    <div class="page-content custom-scrollbar">
      <div class="flex items-center gap-3 mb-4">
        <label class="text-xs text-zinc-500">{{ $t("workspace.scope") }}:</label>
        <select
          v-model="selectedWorkspaceId"
          class="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-sm text-zinc-200 outline-none"
          @change="fetchDocuments"
        >
          <option :value="null">{{ $t("workspace.personal") }}</option>
          <option v-for="ws in workspace.workspaces" :key="ws.id" :value="ws.id">
            {{ ws.name }}
          </option>
        </select>
      </div>

      <div class="flex items-center gap-2 mb-3">
        <button
          class="flex items-center gap-2 px-3 py-1.5 text-xs rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
          @click="openUrlModal"
        >
          <Link class="w-3.5 h-3.5" />
          From URL
        </button>
      </div>

      <section class="glass-card upload-section animate-fade-in">
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
            <span class="upload-icon">{{ uploading ? '⏳' : '📤' }}</span>
            <p class="upload-text">
              {{ uploading ? $t("documents.uploading") : $t("documents.uploadZoneText") }}
            </p>
            <p class="upload-hint">{{ $t("documents.uploadZoneHint") }}</p>
          </div>
          <div v-if="uploading" class="progress-bar-container">
            <div class="progress-bar-fill" :style="{ width: uploadProgress + '%' }"></div>
          </div>
        </label>
      </section>

      <!-- Document List -->
      <section v-if="documents.length > 0" class="documents-list-section animate-fade-in">
        <h3 class="section-title">{{ $t("documents.uploadedTitle") }}</h3>
        <div class="documents-grid">
          <div v-for="doc in documents" :key="doc.id" class="glass-card doc-card">
            <div class="doc-icon">
              {{ doc.file_type === 'pdf' ? '📄' : doc.file_type === 'docx' ? '📝' : '📝' }}
            </div>
            <div class="doc-info">
              <h4 class="doc-filename" :title="doc.filename">{{ doc.filename }}</h4>
              <p class="doc-meta">
                {{ formatBytes(doc.file_size_bytes) }} • {{ doc.chunk_count }} chunks
              </p>
            </div>
            <button class="doc-delete-btn" title="Delete Document" @click="deleteDocument(doc.id)">
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      <!-- Knowledge Base Status -->
      <section class="info-grid animate-fade-in mt-8">
        <div class="glass-card info-card">
          <h4 class="info-title">Vector Store</h4>
          <p class="info-desc">Documents are automatically chunked and indexed in Qdrant for RAG-based retrieval.</p>
        </div>
        <div class="glass-card info-card">
          <h4 class="info-title">Privacy</h4>
          <p class="info-desc">All files are processed locally or in your private cloud sandbox environment.</p>
        </div>
      </section>
    </div>

    <!-- URL ingestion modal -->
    <div
      v-if="showUrlModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      @click.self="showUrlModal = false"
    >
      <div class="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-md shadow-xl">
        <h3 class="text-sm font-semibold text-zinc-100 mb-4">Add Web Page to Knowledge Base</h3>
        <input
          v-model="urlInput"
          type="url"
          placeholder="https://example.com/article"
          class="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 mb-4"
          @keydown.enter="handleIngestUrl"
        />
        <div class="mb-4">
          <label class="block text-xs text-zinc-400 mb-1.5">Add to workspace (optional)</label>
          <select
            v-model="urlWorkspaceId"
            class="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 outline-none focus:ring-1 focus:ring-zinc-500"
          >
            <option :value="null">Personal (no workspace)</option>
            <option v-for="ws in workspace.workspaces" :key="ws.id" :value="ws.id">{{ ws.name }}</option>
          </select>
        </div>
        <p v-if="urlError" class="text-xs text-red-400 mb-3">{{ urlError }}</p>
        <div class="flex justify-end gap-2">
          <button class="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-100" @click="showUrlModal = false">
            Cancel
          </button>
          <button
            :disabled="!urlInput || urlIngesting"
            class="px-4 py-1.5 text-xs bg-white text-black rounded-md disabled:opacity-30 hover:bg-zinc-200"
            @click="handleIngestUrl"
          >
            {{ urlIngesting ? 'Adding...' : 'Add Page' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { Trash2, Link } from "lucide-vue-next";
import client from "@/api/client";
import { ingestDocumentUrl } from "@/api";
import PageHeader from "@/components/PageHeader.vue";
import { useToast } from "@/composables/useToast";
import { useWorkspaceStore } from "@/stores/workspace";

interface DocumentItem {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  chunk_count: number;
  created_at: string;
}

const { t } = useI18n();
const { success, error: toastError } = useToast();
const workspace = useWorkspaceStore();
const uploading = ref(false);
const uploadProgress = ref(0);
const documents = ref<DocumentItem[]>([]);
const selectedWorkspaceId = ref<string | null>(null);

const showUrlModal = ref(false);
const urlInput = ref("");
const urlIngesting = ref(false);
const urlError = ref("");
const urlWorkspaceId = ref<string | null>(null);

const openUrlModal = () => {
  urlWorkspaceId.value = selectedWorkspaceId.value;
  showUrlModal.value = true;
};

const handleIngestUrl = async () => {
  if (!urlInput.value) return;
  urlIngesting.value = true;
  urlError.value = "";
  try {
    await ingestDocumentUrl(urlInput.value, urlWorkspaceId.value);
    showUrlModal.value = false;
    urlInput.value = "";
    await fetchDocuments();
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    urlError.value = err?.response?.data?.detail ?? "Failed to ingest URL";
  } finally {
    urlIngesting.value = false;
  }
};

function formatBytes(bytes: number) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function fetchDocuments() {
  try {
    const url = selectedWorkspaceId.value
      ? `/documents?workspace_id=${selectedWorkspaceId.value}`
      : "/documents";
    const { data } = await client.get(url);
    documents.value = data.documents;
  } catch (error) {
    console.error("Failed to fetch documents", error);
  }
}

async function deleteDocument(id: string) {
  if (!confirm(t('documents.deleteConfirm'))) return;
  try {
    await client.delete(`/documents/${id}`);
    await fetchDocuments();
    success(t('documents.deleteSuccess'));
  } catch {
    toastError(t('documents.deleteError'));
  }
}

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
    toastError(t("documents.fileTooLarge"));
    return;
  }
  uploading.value = true;
  uploadProgress.value = 0;
  const form = new FormData();
  form.append("file", file);
  try {
    const uploadUrl = selectedWorkspaceId.value
      ? `/documents?workspace_id=${selectedWorkspaceId.value}`
      : "/documents";
    const { data } = await client.post(uploadUrl, form, {
      onUploadProgress(e) {
        if (e.total) uploadProgress.value = Math.round((e.loaded / e.total) * 100);
      },
    });
    success(t("documents.uploadSuccess", { count: data.chunk_count }));
    await fetchDocuments();
  } catch {
    toastError(t("documents.uploadError"));
  } finally {
    uploading.value = false;
    uploadProgress.value = 0;
  }
}

onMounted(() => {
  workspace.fetchWorkspaces();
  fetchDocuments();
});
</script>

<style scoped>
.page-container { height: 100vh; display: flex; flex-direction: column; background: var(--bg-primary); }
.page-content { flex: 1; padding: 2rem; overflow-y: auto; max-width: 800px; width: 100%; margin: 0 auto; }

.upload-section { padding: 3rem; margin-bottom: 2rem; }

.upload-zone {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border: 2px dashed var(--border); border-radius: var(--radius-lg); padding: 4rem 2rem;
  cursor: pointer; transition: all 0.2s; position: relative; overflow: hidden; background: rgba(255,255,255,0.02);
}

.upload-zone:hover { border-color: var(--accent); background: rgba(99, 102, 241, 0.05); }
.upload-zone.uploading { border-color: var(--accent); pointer-events: none; }

.file-input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }

.upload-icon { font-size: 3rem; margin-bottom: 1.5rem; display: block; }
.upload-text { font-size: 1.1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.5rem; }
.upload-hint { font-size: 0.85rem; color: var(--text-muted); }

.progress-bar-container { position: absolute; bottom: 0; left: 0; right: 0; height: 4px; background: var(--bg-tertiary); }
.progress-bar-fill { height: 100%; background: var(--accent); transition: width 0.2s ease; }

.documents-list-section { margin-top: 2rem; }
.section-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1rem; }
.documents-grid { display: grid; grid-template-columns: 1fr; gap: 1rem; }
.doc-card { display: flex; items-center: center; padding: 1rem 1.5rem; gap: 1rem; transition: background 0.2s; align-items: center; }
.doc-card:hover { background: var(--bg-secondary); }
.doc-icon { font-size: 1.5rem; }
.doc-info { flex: 1; min-width: 0; }
.doc-filename { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.2rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.doc-meta { font-size: 0.75rem; color: var(--text-muted); }
.doc-delete-btn { padding: 0.5rem; color: var(--text-muted); border-radius: 0.5rem; transition: all 0.2s; }
.doc-delete-btn:hover { color: #f44336; background: rgba(244, 67, 54, 0.1); }

.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
.info-card { padding: 1.5rem; }
.info-title { font-size: 0.8rem; font-weight: 800; text-transform: uppercase; color: var(--accent-light); margin-bottom: 0.75rem; }
.info-desc { font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; }

.mt-8 { margin-top: 2rem; }

.animate-fade-in { animation: fadeIn 0.4s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>
