<template>
  <div class="min-h-screen bg-black text-zinc-300 font-sans selection:bg-white/10">
    <div class="max-w-5xl mx-auto px-6 py-12">
      <!-- Header -->
      <header class="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div class="space-y-2">
          <div class="flex items-center gap-2 text-[10px] font-black text-white tracking-[0.2em] uppercase">
            <UserCircle class="w-3.5 h-3.5" />
            {{ $t("personas.agentPersonalities") }}
          </div>
          <h1 class="text-4xl font-bold text-white tracking-tight">{{ $t("personas.title") }}</h1>
          <p class="text-zinc-500 text-sm max-w-lg">
            {{ $t("personas.description") }}
          </p>
        </div>
        
        <button 
          class="px-6 py-2.5 bg-white text-black rounded-xl text-sm font-black uppercase tracking-widest hover:bg-zinc-200 transition-all flex items-center gap-2"
          @click="openCreateModal"
        >
          <Plus class="w-4 h-4" />
          {{ $t("personas.create") }}
        </button>
      </header>

      <!-- Search -->
      <div v-if="personas.length > 0 || query" class="mb-8">
        <input
          v-model="query"
          type="text"
          :placeholder="$t('personas.searchPlaceholder')"
          class="w-full max-w-sm bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-zinc-600 transition-colors"
        />
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div v-for="i in 4" :key="i" class="h-48 bg-zinc-900/50 rounded-2xl border border-zinc-800 animate-pulse"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="py-20 text-center space-y-4">
        <ShieldAlert class="w-12 h-12 text-red-500 mx-auto" />
        <p class="text-red-400 font-medium">{{ error }}</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="personas.length === 0" class="py-20 text-center space-y-6 bg-zinc-900/30 rounded-3xl border border-dashed border-zinc-800">
        <div class="w-16 h-16 bg-zinc-900 rounded-full flex items-center justify-center mx-auto text-zinc-700">
          <Smile class="w-8 h-8" />
        </div>
        <div class="space-y-1">
          <p class="text-white font-bold">{{ $t("personas.emptyTitle") }}</p>
          <p class="text-zinc-500 text-sm">{{ $t("personas.emptyDesc") }}</p>
        </div>
        <button class="text-white text-xs font-black uppercase tracking-widest underline decoration-zinc-700 hover:decoration-white transition-all" @click="openCreateModal">
          {{ $t("personas.createNow") }}
        </button>
      </div>

      <!-- No search match -->
      <div v-else-if="filtered.length === 0 && query" class="py-20 text-center text-zinc-500 text-sm">
        {{ $t('personas.noMatch', { query }) }}
      </div>

      <!-- Persona Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div
          v-for="persona in filtered"
          :key="persona.id"
          class="group bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col justify-between hover:border-zinc-600 transition-all duration-300"
        >
          <div class="space-y-4">
            <div class="flex items-start justify-between">
              <div class="w-10 h-10 bg-zinc-800 rounded-xl flex items-center justify-center text-white group-hover:bg-white group-hover:text-black transition-colors">
                <span class="text-lg font-bold">{{ persona.name.charAt(0) }}</span>
              </div>
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button class="p-2 text-zinc-600 hover:text-white transition-colors disabled:opacity-40" :title="$t('common.clone')" :disabled="isCloning(persona.id)" @click="clonePersona(persona)">
                  <Copy class="w-4 h-4" />
                </button>
                <button class="p-2 text-zinc-600 hover:text-white transition-colors" @click="openEditModal(persona)">
                  <Pencil class="w-4 h-4" />
                </button>
                <button class="p-2 text-zinc-600 hover:text-red-400 transition-colors" @click="deletePersona(persona)">
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>
            </div>
            
            <div>
              <h3 class="text-lg font-bold text-white mb-1">{{ persona.name }}</h3>
              <p class="text-zinc-500 text-xs line-clamp-2 leading-relaxed">{{ persona.description || $t('personas.noDescription') }}</p>
            </div>

            <div class="bg-black/40 rounded-lg p-3 border border-white/5">
              <p class="text-[10px] text-zinc-600 font-black uppercase tracking-widest mb-1">{{ $t("personas.systemPromptLabel") }}</p>
              <p class="text-[11px] text-zinc-400 font-mono line-clamp-3 leading-relaxed">{{ persona.system_prompt }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center px-6">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="closeModal"></div>
        <div class="relative bg-zinc-950 border border-zinc-800 w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
          <div class="p-8 space-y-6">
            <div class="flex items-center justify-between">
              <h2 class="text-xl font-bold text-white tracking-tight">{{ editingPersona ? $t("personas.editPersona") : $t("personas.newPersona") }}</h2>
              <button class="text-zinc-500 hover:text-white transition-colors" @click="closeModal">
                <X class="w-5 h-5" />
              </button>
            </div>

            <div class="space-y-4">
              <div class="space-y-1.5">
                <label class="text-[10px] font-black text-zinc-500 uppercase tracking-widest">{{ $t("personas.nameLabel") }}</label>
                <input
                  v-model="form.name"
                  type="text"
                  :placeholder="$t('personas.namePlaceholder')"
                  class="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-zinc-600 transition-colors"
                />
              </div>

              <div class="space-y-1.5">
                <label class="text-[10px] font-black text-zinc-500 uppercase tracking-widest">{{ $t("personas.descLabel") }}</label>
                <input
                  v-model="form.description"
                  type="text"
                  :placeholder="$t('personas.descPlaceholder')"
                  class="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-zinc-600 transition-colors"
                />
              </div>

              <div class="space-y-1.5">
                <label class="text-[10px] font-black text-zinc-500 uppercase tracking-widest">{{ $t("personas.systemPromptLabel") }}</label>
                <textarea
                  v-model="form.system_prompt"
                  rows="6"
                  :placeholder="$t('personas.promptPlaceholder')"
                  class="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-zinc-600 transition-colors resize-none font-mono"
                ></textarea>
              </div>
            </div>

            <button
              :disabled="!isFormValid || saving"
              class="w-full py-3 bg-white text-black rounded-xl text-xs font-black uppercase tracking-widest hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
              @click="editingPersona ? updatePersona() : createPersona()"
            >
              <template v-if="saving">
                <div class="w-3 h-3 border-2 border-black/20 border-t-black rounded-full animate-spin"></div>
                {{ $t("personas.saving") }}
              </template>
              <template v-else>
                {{ $t("personas.save") }}
              </template>
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { UserCircle, Plus, Trash2, Pencil, ShieldAlert, Smile, X, Copy } from 'lucide-vue-next';
import client from '@/api/client';
import { useToast } from '@/composables/useToast';
import { useSearchFilter } from '@/composables/useSearchFilter';
import { useCloning } from '@/composables/useCloning';

const { t } = useI18n();
const { error: toastError } = useToast();

interface Persona {
  id: string;
  name: string;
  description?: string;
  system_prompt: string;
}

const personas = ref<Persona[]>([]);
const loading = ref(true);
const saving = ref(false);
const { isCloning, withCloning } = useCloning();
const error = ref<string | null>(null);
const showCreateModal = ref(false);
const editingPersona = ref<Persona | null>(null);
const { query, filtered } = useSearchFilter(personas);

const form = ref({
  name: "",
  description: "",
  system_prompt: ""
});

const isFormValid = computed(() => {
  return form.value.name.trim() && form.value.system_prompt.trim();
});

const closeModal = () => {
  showCreateModal.value = false;
  editingPersona.value = null;
  form.value = { name: "", description: "", system_prompt: "" };
};

const openCreateModal = () => {
  editingPersona.value = null;
  form.value = { name: "", description: "", system_prompt: "" };
  showCreateModal.value = true;
};

const openEditModal = (persona: Persona) => {
  editingPersona.value = persona;
  form.value = { name: persona.name, description: persona.description ?? "", system_prompt: persona.system_prompt };
  showCreateModal.value = true;
};

const fetchPersonas = async () => {
  loading.value = true;
  error.value = null;
  try {
    const { data } = await client.get("/personas");
    personas.value = data;
  } catch (err) {
    error.value = t("personas.loadError");
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const createPersona = async () => {
  if (!isFormValid.value || saving.value) return;
  saving.value = true;
  try {
    const { data } = await client.post("/personas", form.value);
    personas.value.push(data);
    closeModal();
  } catch (err) {
    console.error("Create failed:", err);
    toastError(t("personas.saveError"));
  } finally {
    saving.value = false;
  }
};

const updatePersona = async () => {
  if (!isFormValid.value || saving.value || !editingPersona.value) return;
  saving.value = true;
  try {
    const { data } = await client.put(`/personas/${editingPersona.value.id}`, form.value);
    const idx = personas.value.findIndex(p => p.id === data.id);
    if (idx !== -1) personas.value[idx] = data;
    closeModal();
  } catch (err) {
    console.error("Update failed:", err);
    toastError(t("personas.saveError"));
  } finally {
    saving.value = false;
  }
};

const clonePersona = async (persona: Persona) => {
  await withCloning(persona.id, async () => {
    try {
      const { data } = await client.post(`/personas/${persona.id}/clone`);
      personas.value.push(data);
    } catch (err) {
      console.error('Clone failed:', err);
      toastError(t('personas.cloneError'));
    }
  });
};

const deletePersona = async (persona: Persona) => {
  if (!confirm(t("personas.deleteConfirm", { name: persona.name }))) return;
  try {
    await client.delete(`/personas/${persona.id}`);
    personas.value = personas.value.filter(p => p.id !== persona.id);
  } catch (err) {
    console.error("Delete failed:", err);
    toastError(t("personas.deleteError"));
  }
};

onMounted(fetchPersonas);
</script>
