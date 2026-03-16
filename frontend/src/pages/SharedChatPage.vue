<template>
  <div class="flex h-screen bg-black text-zinc-300 font-sans selection:bg-white/10 overflow-hidden">
    <!-- Main Content -->
    <main class="flex-1 flex flex-col relative min-w-0">
      <!-- Header -->
      <header class="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-zinc-950/50 backdrop-blur-md z-10">
        <div class="flex items-center gap-3">
          <div class="w-6 h-6 bg-white text-black flex items-center justify-center rounded font-black text-[10px]">J</div>
          <h1 class="text-[13px] font-bold text-white tracking-tight truncate max-w-[200px] sm:max-w-md">
            {{ title }}
          </h1>
          <span class="px-1.5 py-0.5 bg-zinc-800 text-zinc-500 rounded text-[9px] font-bold uppercase tracking-widest">Shared</span>
        </div>
        <div class="flex items-center gap-2">
          <router-link to="/" class="text-[11px] font-bold text-zinc-400 hover:text-white transition-colors">
            GET JARVIS
          </router-link>
        </div>
      </header>

      <!-- Messages Area -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto custom-scrollbar">
        <div class="max-w-3xl mx-auto px-6 py-12 space-y-12">
          <div v-if="loading" class="flex flex-col items-center justify-center py-20 gap-4">
            <div class="w-5 h-5 border-2 border-white/10 border-t-white rounded-full animate-spin"></div>
            <span class="text-[10px] font-bold text-zinc-500 uppercase tracking-[0.2em]">Loading Conversation</span>
          </div>

          <div v-else-if="error" class="flex flex-col items-center justify-center py-20 gap-4 text-red-400">
            <ShieldAlert class="w-8 h-8" />
            <span class="text-[11px] font-bold uppercase tracking-[0.1em]">{{ error }}</span>
          </div>

          <template v-else>
            <div
              v-for="(msg, idx) in messages"
              :key="idx"
              class="flex flex-col gap-4 animate-in fade-in duration-700"
            >
              <!-- Sender Label -->
              <div class="flex items-center gap-3 select-none">
                <div
                  :class="['w-5 h-5 rounded-sm flex items-center justify-center text-[9px] font-bold tracking-tighter', 
                  msg.role === 'ai' ? 'bg-white text-black' : 'bg-zinc-800 text-zinc-400']">
                  {{ msg.role === 'ai' ? 'J' : 'U' }}
                </div>
                <span class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">{{ msg.role === 'ai' ? 'Autonomous Agent' : 'User' }}</span>
              </div>

              <!-- Content Column -->
              <div class="pl-8 group relative min-h-[20px]">
                <div v-if="msg.image_urls && msg.image_urls.length > 0" class="flex flex-wrap gap-2 mb-2">
                  <img v-for="(img, imgIdx) in msg.image_urls" :key="imgIdx" :src="img" class="max-w-[300px] max-h-[300px] object-contain rounded-md border border-zinc-700/50" />
                </div>
                <div class="markdown-body text-zinc-200 leading-[1.7] text-[14px]" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <footer class="h-12 border-t border-white/5 flex items-center justify-center bg-zinc-950/50">
        <p class="text-[10px] text-zinc-600 font-medium">Shared via JARVIS AI Assistant</p>
      </footer>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { marked } from "marked";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css";
import { ShieldAlert } from "lucide-vue-next";
import client from "@/api/client";

const route = useRoute();
const title = ref("Shared Conversation");
const messages = ref<any[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const messagesEl = ref<HTMLElement>();

const renderMarkdown = (text: string) => (text ? marked.parse(text) : "");

onMounted(async () => {
  marked.use({
    breaks: true,
    renderer: {
      code({ text, lang }: { text: string; lang?: string }): string {
        if (lang && hljs.getLanguage(lang)) {
          return `<pre><code class="hljs language-${lang}">${hljs.highlight(text, { language: lang }).value}</code></pre>\n`;
        }
        return `<pre><code class="hljs">${hljs.highlightAuto(text).value}</code></pre>\n`;
      },
    },
  });

  const token = route.params.token;
  try {
    const { data } = await client.get(`/public/share/${token}`);
    title.value = data.title;
    messages.value = data.messages;
  } catch (err: any) {
    error.value = err.response?.data?.detail || "Failed to load shared conversation";
  } finally {
    loading.value = false;
  }
});
</script>

<style>
.markdown-body {
  font-family: inherit;
  color: inherit;
}
.markdown-body pre {
  background-color: #09090b;
  border: 1px solid #27272a;
  border-radius: 0.5rem;
  padding: 1rem;
  margin: 1rem 0;
  overflow-x: auto;
}
.markdown-body code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.85em;
  background-color: rgba(255, 255, 255, 0.05);
  padding: 0.2em 0.4em;
  border-radius: 0.25rem;
}
.markdown-body pre code {
  background-color: transparent;
  padding: 0;
}
.markdown-body p { margin-bottom: 1rem; }
.markdown-body ul, .markdown-body ol { margin-bottom: 1rem; padding-left: 1.5rem; }
.markdown-body li { margin-bottom: 0.5rem; }
.markdown-body h1, .markdown-body h2, .markdown-body h3 {
  color: white;
  font-weight: 700;
  margin: 1.5rem 0 1rem;
}

.custom-scrollbar::-webkit-scrollbar { width: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #27272a; border-radius: 10px; }
</style>
