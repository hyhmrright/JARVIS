<template>
  <div class="flex h-screen w-full bg-background overflow-hidden text-[14px]">
    <!-- Minimal Sidebar -->
    <aside 
      :class="[
        'flex flex-col bg-background border-r border-border transition-all duration-300 ease-in-out',
        sidebarCollapsed ? 'w-0 border-none' : 'w-[260px]'
      ]"
    >
      <div class="h-14 flex items-center px-4 justify-between">
        <div class="flex items-center gap-2 font-bold tracking-tight select-none">
          <div class="w-6 h-6 bg-foreground text-background rounded flex items-center justify-center text-xs">J</div>
          <span>JARVIS</span>
        </div>
        <button @click="chat.newConversation" class="p-2 hover:bg-muted rounded-md transition-colors" title="New Chat">
          <SquarePen class="w-4 h-4 text-muted-foreground" />
        </button>
      </div>

      <nav class="flex-1 overflow-y-auto px-3 space-y-0.5 custom-scrollbar py-2">
        <div
          v-for="c in chat.conversations"
          :key="c.id"
          @click="chat.selectConversation(c.id)"
          :class="[
            'group flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors relative',
            chat.currentConvId === c.id ? 'bg-muted' : 'hover:bg-muted/50'
          ]"
        >
          <span class="text-sm truncate flex-1">{{ c.title }}</span>
          <button
            @click.stop="chat.deleteConversation(c.id)"
            class="opacity-0 group-hover:opacity-100 p-1 hover:text-destructive transition-opacity"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </nav>

      <div class="p-3 border-t border-border space-y-1">
        <router-link to="/proactive" class="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground">
          <Zap class="w-4 h-4" />
          <span>Automations</span>
        </router-link>
        <router-link to="/settings" class="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground">
          <Settings class="w-4 h-4" />
          <span>Settings</span>
        </router-link>
        <div class="pt-2 mt-2 border-t border-border flex items-center gap-3 px-3 py-2">
          <div class="w-7 h-7 rounded-full bg-muted flex items-center justify-center text-[10px] font-bold border border-border">
            {{ auth.displayName?.[0] || 'U' }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-xs font-medium truncate">{{ auth.displayName || 'User' }}</p>
          </div>
          <button @click="handleLogout" class="p-1.5 hover:text-destructive transition-colors">
            <LogOut class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Main Content Well -->
    <main class="flex-1 flex flex-col min-w-0 relative bg-background">
      <!-- Top Sticky Header -->
      <header class="h-14 flex items-center px-4 justify-between z-40 bg-background/80 backdrop-blur-md">
        <div class="flex items-center gap-2">
          <button 
            v-if="sidebarCollapsed"
            @click="sidebarCollapsed = false"
            class="p-2 hover:bg-muted rounded-md transition-colors mr-2"
          >
            <PanelLeft class="w-4 h-4 text-muted-foreground" />
          </button>
          <h2 class="text-sm font-medium truncate opacity-60">{{ currentConvTitle }}</h2>
        </div>
        <div class="flex items-center gap-2">
          <button class="p-2 hover:bg-muted rounded-md transition-colors text-muted-foreground">
            <Share2 class="w-4 h-4" />
          </button>
        </div>
      </header>

      <!-- Messages Scroll Area -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto custom-scrollbar scroll-smooth">
        <div class="max-w-3xl mx-auto px-6 py-10 space-y-12">
          
          <!-- Empty State -->
          <div v-if="chat.messages.length === 0" class="pt-20 flex flex-col items-center">
            <div class="w-12 h-12 bg-foreground text-background rounded-xl flex items-center justify-center font-black text-xl mb-8">J</div>
            <h1 class="text-2xl font-semibold mb-12">What can I help you with?</h1>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
              <button 
                v-for="s in suggestions" :key="s.text"
                @click="input = s.prompt"
                class="p-4 rounded-xl border border-border bg-card hover:bg-muted/50 transition-all text-left text-sm"
              >
                <div class="font-medium mb-1">{{ s.text }}</div>
                <div class="text-muted-foreground text-xs">{{ s.sub }}</div>
              </button>
            </div>
          </div>

          <!-- Message Pairs -->
          <div
            v-for="(msg, idx) in chat.messages"
            :key="idx"
            :class="['flex flex-col gap-4 animate-in fade-in duration-500']"
          >
            <!-- Label & Avatar -->
            <div class="flex items-center gap-3 opacity-40 select-none">
              <div :class="['w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold', 
                msg.role === 'ai' ? 'bg-foreground text-background' : 'bg-muted text-foreground border border-border']">
                {{ msg.role === 'ai' ? 'J' : (auth.displayName?.[0] || 'U') }}
              </div>
              <span class="text-[10px] font-black uppercase tracking-widest">{{ msg.role === 'ai' ? 'Jarvis' : 'You' }}</span>
            </div>

            <!-- Content -->
            <div :class="['pl-8 group relative']">
              <div class="markdown-body leading-relaxed text-[15px]" v-html="renderMarkdown(msg.content)"></div>
              
              <!-- HITL Approval -->
              <div v-if="msg.pending_tool_call" class="mt-6 p-5 bg-muted/30 border border-border rounded-xl space-y-4 max-w-md animate-in zoom-in-95">
                <div class="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                  <ShieldAlert class="w-3.5 h-3.5" />
                  Authorization Required
                </div>
                <div class="text-sm font-medium">AI wants to call <code class="text-primary">{{ msg.pending_tool_call.name }}</code></div>
                <div class="flex gap-2 pt-2">
                  <button @click="chat.handleConsent(true)" class="flex-1 py-2 bg-foreground text-background rounded-lg text-xs font-bold hover:opacity-90 transition-all">Allow</button>
                  <button @click="chat.handleConsent(false)" class="flex-1 py-2 bg-muted text-foreground border border-border rounded-lg text-xs font-bold hover:bg-background transition-all">Deny</button>
                </div>
              </div>

              <!-- Tool Trace -->
              <div v-if="msg.toolCalls?.length" class="mt-4 flex flex-wrap gap-2 pt-2 border-t border-border/50">
                <div v-for="tc in msg.toolCalls" :key="tc.name" class="flex items-center gap-2 px-2 py-1 rounded bg-muted/50 text-[10px] text-muted-foreground">
                  <div :class="['w-1.5 h-1.5 rounded-full', tc.status === 'running' ? 'bg-yellow-500 animate-pulse' : 'bg-emerald-500']"></div>
                  {{ tc.name }}
                </div>
              </div>

              <!-- Actions -->
              <div v-if="msg.role === 'ai' && msg.content" class="absolute -bottom-8 left-8 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button @click="copyText(msg.content)" class="p-1.5 hover:bg-muted rounded transition-colors text-muted-foreground" title="Copy">
                  <Copy class="w-3.5 h-3.5" />
                </button>
                <button @click="regenerate(idx)" class="p-1.5 hover:bg-muted rounded transition-colors text-muted-foreground" title="Regenerate">
                  <RotateCcw class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            
            <div v-if="msg.role === 'ai' && hasHtml(msg.content)" class="pl-8 mt-4">
              <LiveCanvas :content="msg.content" />
            </div>
          </div>

          <!-- Streaming -->
          <div v-if="chat.streaming" class="flex flex-col gap-4 animate-in fade-in duration-300 pl-8">
            <div class="flex gap-1.5 items-center py-4">
              <div class="w-1.5 h-1.5 bg-foreground/40 rounded-full animate-bounce"></div>
              <div class="w-1.5 h-1.5 bg-foreground/40 rounded-full animate-bounce [animation-delay:0.2s]"></div>
              <div class="w-1.5 h-1.5 bg-foreground/40 rounded-full animate-bounce [animation-delay:0.4s]"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Section -->
      <div class="w-full">
        <div class="max-w-3xl mx-auto px-6 pb-8 pt-4">
          <div class="relative bg-muted/50 border border-border rounded-2xl focus-within:border-border transition-all">
            <div class="flex items-end p-2 gap-1">
              <button @click="voiceOverlay?.start()" class="p-3 text-muted-foreground hover:text-foreground transition-colors">
                <Mic class="w-5 h-5" />
              </button>
              
              <textarea
                v-model="input"
                class="flex-1 bg-transparent border-none focus:ring-0 px-2 py-3 text-[15px] resize-none max-h-[250px] min-h-[44px] custom-scrollbar placeholder:text-muted-foreground/50"
                :placeholder="$t('chat.inputPlaceholder')"
                @keydown.enter.prevent="handleSend"
                rows="1"
              ></textarea>
              
              <button
                @click="handleSend"
                :disabled="!input.trim() || chat.streaming"
                class="p-3 bg-foreground text-background rounded-xl disabled:opacity-20 transition-all active:scale-90"
              >
                <ArrowUp class="w-5 h-5 stroke-[3px]" />
              </button>
            </div>
          </div>
          <p class="mt-3 text-[10px] text-center text-muted-foreground font-medium uppercase tracking-[0.1em] opacity-40">
            Powered by JARVIS Intelligent Core
          </p>
        </div>
      </div>
    </main>

    <VoiceOverlay ref="voiceOverlay" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useChatStore } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";
import { marked } from "marked";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css";

import { 
  Trash2, Zap, Settings, LogOut, 
  PanelLeft, SquarePen, Copy, RotateCcw,
  Mic, ArrowUp, ShieldAlert, Share2
} from "lucide-vue-next";

import LiveCanvas from "@/components/LiveCanvas.vue";
import VoiceOverlay from "@/components/VoiceOverlay.vue";

const { t } = useI18n();
const chat = useChatStore();
const auth = useAuthStore();
const router = useRouter();

const input = ref("");
const sidebarCollapsed = ref(false);
const messagesEl = ref<HTMLElement>();
const voiceOverlay = ref<InstanceType<typeof VoiceOverlay>>();

const suggestions = [
  { text: 'Analyze Workspace', sub: 'Run a security and structure check', prompt: 'Run a proactive security check' },
  { text: 'Canvas Interactive UI', sub: 'Generate a live reactive interface', prompt: 'Show me a demo of Live Canvas' },
  { text: 'Search local memory', sub: 'Retrieve info from past sessions', prompt: 'Search my local memory for architecture notes' }
];

marked.setOptions({
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value;
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
});

const renderMarkdown = (text: string) => text ? marked.parse(text) : '<span class="animate-pulse text-foreground/40 italic">Thinking...</span>';
const hasHtml = (text: string) => /<html>[\s\S]*?<\/html>/.test(text);
const currentConvTitle = computed(() => chat.conversations.find((conv) => conv.id === chat.currentConvId)?.title || "Intelligence Engine");

const handleSend = async () => {
  if (!input.value.trim() || chat.streaming) return;
  const msg = input.value;
  input.value = "";
  await chat.sendMessage(msg);
};

const copyText = (text: string) => { navigator.clipboard.writeText(text); };
const regenerate = async (idx: number) => {
  const prevHuman = chat.messages.slice(0, idx).reverse().find(m => m.role === 'human');
  if (prevHuman) await chat.sendMessage(prevHuman.content);
};

const handleLogout = () => { auth.logout(); router.push("/login"); };

const scrollToBottom = async () => {
  await nextTick();
  if (messagesEl.value) messagesEl.value.scrollTo({ top: messagesEl.value.scrollHeight, behavior: "smooth" });
};

watch(() => chat.messages.length, scrollToBottom);
watch(() => chat.streaming, (isStreaming) => { if (isStreaming) scrollToBottom(); });
onMounted(async () => { await chat.loadConversations(); });
</script>

<style scoped>
.markdown-body :deep(pre) { background: #0d1117; padding: 1.25rem; border-radius: 8px; margin: 1.25rem 0; border: 1px solid var(--border); overflow-x: auto; }
.markdown-body :deep(code) { font-family: 'JetBrains Mono', monospace; font-size: 0.9em; }
.markdown-body :deep(p) { margin-bottom: 1.25rem; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
</style>
