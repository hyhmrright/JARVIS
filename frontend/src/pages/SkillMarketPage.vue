<template>
  <div class="min-h-screen bg-black text-zinc-300 font-sans selection:bg-white/10">
    <div class="max-w-6xl mx-auto px-6 py-12">
      <!-- Header -->
      <header class="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div class="space-y-2">
          <div class="flex items-center gap-2 text-[10px] font-black text-white tracking-[0.2em] uppercase">
            <Zap class="w-3.5 h-3.5" />
            JARVIS ecosystem
          </div>
          <h1 class="text-4xl font-bold text-white tracking-tight">Skill Market</h1>
          <p class="text-zinc-500 text-sm max-w-lg">
            Discover and install specialized AI capabilities. From code analysis to creative writing, 
            extend your assistant with a single click.
          </p>
        </div>
        
        <div class="flex items-center gap-3">
          <div class="relative">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input 
              v-model="searchQuery"
              type="text" 
              placeholder="Search skills..." 
              class="bg-zinc-900 border border-zinc-800 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-zinc-600 transition-colors w-64"
            />
          </div>
          <router-link to="/plugins" class="px-4 py-2 bg-zinc-800 text-zinc-300 rounded-lg text-sm font-bold hover:bg-zinc-700 transition-all">
            BACK
          </router-link>
        </div>
      </header>

      <!-- Loading State -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="i in 6" :key="i" class="h-64 bg-zinc-900/50 rounded-2xl border border-zinc-800 animate-pulse"></div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="py-20 text-center space-y-4">
        <ShieldAlert class="w-12 h-12 text-red-500 mx-auto" />
        <p class="text-red-400 font-medium">{{ error }}</p>
        <button class="text-sm text-zinc-500 underline hover:text-white" @click="fetchSkills">Try Again</button>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredSkills.length === 0" class="py-20 text-center">
        <p class="text-zinc-500">No skills found matching your search.</p>
      </div>

      <!-- Skill Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div 
          v-for="skill in filteredSkills" 
          :key="skill.id"
          class="group bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col justify-between hover:border-zinc-600 transition-all duration-300"
        >
          <div class="space-y-4">
            <div class="flex items-start justify-between">
              <div class="w-10 h-10 bg-zinc-800 rounded-xl flex items-center justify-center text-white group-hover:bg-white group-hover:text-black transition-colors">
                <Box class="w-5 h-5" />
              </div>
              <span v-if="skill.installed" class="px-2 py-0.5 bg-green-500/10 text-green-400 rounded text-[9px] font-black uppercase tracking-widest border border-green-500/20">
                Installed
              </span>
            </div>
            
            <div>
              <h3 class="text-lg font-bold text-white mb-1">{{ skill.name }}</h3>
              <p class="text-zinc-500 text-xs line-clamp-3 leading-relaxed">{{ skill.description }}</p>
            </div>

            <div class="flex items-center gap-4 text-[10px] text-zinc-600 font-bold uppercase tracking-wider">
              <span class="flex items-center gap-1"><User class="w-3 h-3" /> {{ skill.author }}</span>
              <span>v{{ skill.version }}</span>
            </div>
          </div>

          <div class="mt-8">
            <button 
              v-if="!skill.installed"
              :disabled="installingId === skill.id"
              class="w-full py-2.5 bg-white text-black rounded-xl text-xs font-black uppercase tracking-widest hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
              @click="installSkill(skill)"
            >
              <template v-if="installingId === skill.id">
                <div class="w-3 h-3 border-2 border-black/20 border-t-black rounded-full animate-spin"></div>
                Installing...
              </template>
              <template v-else>
                <Download class="w-3.5 h-3.5" />
                Install Skill
              </template>
            </button>
            <button 
              v-else
              :disabled="installingId === skill.id"
              class="w-full py-2.5 bg-zinc-800 text-zinc-400 rounded-xl text-xs font-black uppercase tracking-widest hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
              @click="uninstallSkill(skill)"
            >
              <template v-if="installingId === skill.id">
                <div class="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
                Removing...
              </template>
              <template v-else>
                <Trash2 class="w-3.5 h-3.5" />
                Uninstall
              </template>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Zap, Search, Box, User, Download, Trash2, ShieldAlert } from "lucide-vue-next";
import client from "@/api/client";

interface Skill {
  id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  md_url: string;
  installed: boolean;
}

const skills = ref<Skill[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const searchQuery = ref("");
const installingId = ref<string | null>(null);

const filteredSkills = computed(() => {
  if (!searchQuery.value) return skills.value;
  const q = searchQuery.value.toLowerCase();
  return skills.value.filter(s => 
    s.name.toLowerCase().includes(q) || 
    s.description.toLowerCase().includes(q) ||
    s.author.toLowerCase().includes(q)
  );
});

const fetchSkills = async () => {
  loading.value = true;
  error.value = null;
  try {
    const { data } = await client.get("/plugins/market/skills");
    skills.value = data;
  } catch (err: any) {
    error.value = "Failed to fetch skills from registry.";
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const installSkill = async (skill: Skill) => {
  installingId.value = skill.id;
  try {
    await client.post(`/plugins/market/install/${skill.id}?md_url=${encodeURIComponent(skill.md_url)}`);
    skill.installed = true;
  } catch (err) {
    console.error("Install failed:", err);
    alert("Installation failed. Check console for details.");
  } finally {
    installingId.value = null;
  }
};

const uninstallSkill = async (skill: Skill) => {
  if (!confirm(`Are you sure you want to uninstall ${skill.name}?`)) return;
  installingId.value = skill.id;
  try {
    await client.delete(`/plugins/market/uninstall/${skill.id}`);
    skill.installed = false;
  } catch (err) {
    console.error("Uninstall failed:", err);
  } finally {
    installingId.value = null;
  }
};

onMounted(fetchSkills);
</script>
