<template>
  <div class="min-h-screen bg-black font-sans text-zinc-300 selection:bg-white/10">
    <div class="mx-auto max-w-6xl px-6 py-12">
      <!-- Header -->
      <header class="mb-8 flex flex-col justify-between gap-6 md:flex-row md:items-end">
        <div class="space-y-2">
          <div
            class="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-white"
          >
            <Zap class="h-3.5 w-3.5" />
            JARVIS ecosystem
          </div>
          <h1 class="text-4xl font-bold tracking-tight text-white">Skill Market</h1>
          <p class="max-w-lg text-sm text-zinc-500">
            Discover and install specialized AI capabilities. From code analysis to creative
            writing, extend your assistant with a single click.
          </p>
        </div>

        <div class="flex items-center gap-3">
          <div class="relative">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search skills..."
              class="w-64 rounded-lg border border-zinc-800 bg-zinc-900 py-2 pl-10 pr-4 text-sm text-white transition-colors focus:border-zinc-600 focus:outline-none"
            />
          </div>
          <button
            class="rounded-lg bg-zinc-800 px-4 py-2 text-sm font-bold text-zinc-300 transition-all hover:bg-zinc-700"
            @click="showInstallModal = true"
          >
            + Install from URL
          </button>
          <router-link
            to="/plugins"
            class="rounded-lg bg-zinc-800 px-4 py-2 text-sm font-bold text-zinc-300 transition-all hover:bg-zinc-700"
          >
            BACK
          </router-link>
        </div>
      </header>

      <!-- Category Tabs -->
      <div class="mb-8 flex flex-wrap gap-2">
        <button
          v-for="cat in categories"
          :key="cat"
          class="rounded-full border px-4 py-1.5 text-xs font-bold uppercase tracking-wider transition-all"
          :class="
            activeCategory === cat
              ? 'border-white bg-white text-black'
              : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
          "
          @click="activeCategory = cat"
        >
          {{ cat === '__all__' ? 'All' : cat }}
        </button>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="i in 6"
          :key="i"
          class="h-64 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/50"
        ></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="space-y-4 py-20 text-center">
        <ShieldAlert class="mx-auto h-12 w-12 text-red-500" />
        <p class="font-medium text-red-400">{{ error }}</p>
        <button class="text-sm text-zinc-500 underline hover:text-white" @click="loadSkills">
          Try Again
        </button>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredSkills.length === 0" class="py-20 text-center">
        <p class="text-zinc-500">No skills found matching your search.</p>
      </div>

      <!-- Skill Grid -->
      <div v-else class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="skill in filteredSkills"
          :key="skill.id"
          class="group flex flex-col justify-between rounded-2xl border border-zinc-800 bg-zinc-900 p-6 transition-all duration-300 hover:border-zinc-600"
        >
          <div class="space-y-4">
            <div class="flex items-start justify-between">
              <div
                class="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-800 text-white transition-colors group-hover:bg-white group-hover:text-black"
              >
                <Box class="h-5 w-5" />
              </div>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="tag in skill.tags.slice(0, 2)"
                  :key="tag"
                  class="rounded border border-zinc-700 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-zinc-500"
                >
                  {{ tag }}
                </span>
              </div>
            </div>

            <div>
              <h3 class="mb-1 text-lg font-bold text-white">{{ skill.name }}</h3>
              <p class="line-clamp-3 text-xs leading-relaxed text-zinc-500">
                {{ skill.description }}
              </p>
            </div>

            <div
              class="flex items-center gap-4 text-[10px] font-bold uppercase tracking-wider text-zinc-600"
            >
              <span class="flex items-center gap-1">
                <User class="h-3 w-3" /> {{ skill.author }}
              </span>
              <span class="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-400">
                {{ skill.type }}
              </span>
            </div>
          </div>

          <div class="mt-8 flex flex-col gap-2">
            <button
              :disabled="installingId === skill.id"
              class="flex w-full items-center justify-center gap-2 rounded-xl bg-white py-2.5 text-xs font-black uppercase tracking-widest text-black transition-all hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-50"
              @click="installSkill(skill, 'personal')"
            >
              <template v-if="installingId === skill.id">
                <div
                  class="h-3 w-3 animate-spin rounded-full border-2 border-black/20 border-t-black"
                ></div>
                Installing...
              </template>
              <template v-else>
                <Download class="h-3.5 w-3.5" />
                Install (Personal)
              </template>
            </button>
            <button
              v-if="isAdmin && skill.scope.includes('system')"
              :disabled="installingId === skill.id"
              class="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-700 py-2.5 text-xs font-black uppercase tracking-widest text-zinc-400 transition-all hover:border-zinc-500 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-50"
              @click="installSkill(skill, 'system')"
            >
              <Download class="h-3.5 w-3.5" />
              Install (System-wide)
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Install from URL Modal -->
    <InstallFromUrlModal
      v-if="showInstallModal"
      @close="showInstallModal = false"
      @installed="onInstalled"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Zap, Search, Box, User, Download, ShieldAlert } from "lucide-vue-next";
import { useAuthStore } from "@/stores/auth";
import { marketApi } from "@/api/plugins";
import type { MarketSkillOut } from "@/api/plugins";
import InstallFromUrlModal from "@/components/InstallFromUrlModal.vue";

const auth = useAuthStore();
const isAdmin = computed(() => auth.isAdmin);

const skills = ref<MarketSkillOut[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const searchQuery = ref("");
const installingId = ref<string | null>(null);
const activeCategory = ref("__all__");
const showInstallModal = ref(false);

const categories = computed(() => {
  const tagSet = new Set<string>();
  for (const s of skills.value) {
    for (const t of s.tags) tagSet.add(t);
  }
  return ["__all__", ...Array.from(tagSet).sort()];
});

const filteredSkills = computed(() => {
  let list = skills.value;
  if (activeCategory.value !== "__all__") {
    list = list.filter((s) => s.tags.includes(activeCategory.value));
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    list = list.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.author.toLowerCase().includes(q),
    );
  }
  return list;
});

async function loadSkills() {
  loading.value = true;
  error.value = null;
  try {
    skills.value = (await marketApi.listSkills()).data;
  } catch (err: unknown) {
    error.value = "Failed to fetch skills from registry.";
    console.error(err);
  } finally {
    loading.value = false;
  }
}

async function installSkill(skill: MarketSkillOut, scope: "personal" | "system") {
  installingId.value = skill.id;
  try {
    await marketApi.install({
      url: skill.install_url,
      type: skill.type,
      scope,
    });
    alert(`"${skill.name}" installed successfully.`);
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
      ?.detail;
    alert(typeof detail === "string" ? detail : "Installation failed.");
    console.error(err);
  } finally {
    installingId.value = null;
  }
}

function onInstalled(_pluginId: string) {
  // Reload list so newly installed plugin appears in PluginsPage
}

onMounted(loadSkills);
</script>
