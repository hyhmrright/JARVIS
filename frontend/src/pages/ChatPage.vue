<template>
  <div class="flex h-screen w-full bg-background overflow-hidden relative">
    <!-- Background subtle glow -->
    <div class="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] bg-primary/5 blur-[120px] pointer-events-none"></div>

    <!-- Sidebar -->
    <aside 
      :class="[
        'z-50 flex flex-col bg-card border-r border-border transition-all duration-300 ease-in-out',
        sidebarCollapsed ? 'w-[60px]' : 'w-72'
      ]"
    >
      <div class="h-[60px] flex items-center px-4 border-b border-border">
        <div class="flex items-center gap-3 overflow-hidden">
          <div class="flex-shrink-0 w-8 h-8 bg-primary rounded-md flex items-center justify-center">
            <Layers class="w-5 h-5 text-primary-foreground" />
          </div>
          <span v-if="!sidebarCollapsed" class="font-bold tracking-tight text-lg animate-in fade-in duration-500">JARVIS</span>
        </div>
        <button 
          @click="sidebarCollapsed = !sidebarCollapsed"
          class="ml-auto p-1.5 rounded-md hover:bg-accent text-muted-foreground transition-colors"
        >
          <ChevronLeft v-if="!sidebarCollapsed" class="w-4 h-4" />
          <ChevronRight v-else class="w-4 h-4" />
        </button>
      </div>

      <div class="p-3">
        <button 
          @click="chat.newConversation"
          class="w-full flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-all active:scale-[0.98]"
        >
          <Plus class="w-4 h-4" />
          <span v-if="!sidebarCollapsed" class="truncate">New Chat</span>
        </button>
      </div>

      <nav class="flex-1 overflow-y-auto px-2 space-y-1 custom-scrollbar">
        <div
          v-for="c in chat.conversations"
          :key="c.id"
          @click="chat.selectConversation(c.id)"
          :class="[
            'group relative flex items-center gap-3 px-3 py-2.5 rounded-md cursor-pointer transition-all',
            chat.currentConvId === c.id ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
          ]"
        >
          <MessageSquare class="w-4 h-4 flex-shrink-0" />
          <span v-if="!sidebarCollapsed" class="text-sm truncate flex-1">{{ c.title }}</span>
          <button
            v-if="!sidebarCollapsed"
            @click.stop="chat.deleteConversation(c.id)"
            class="opacity-0 group-hover:opacity-100 p-1 hover:text-destructive transition-all"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </nav>

      <div class="mt-auto p-2 border-t border-border bg-card/50">
        <div v-if="!sidebarCollapsed" class="flex items-center gap-3 px-2 py-3 mb-2 rounded-lg bg-secondary/30">
          <div class="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-bold text-primary text-xs border border-primary/20">
            {{ auth.displayName?.[0] || 'U' }}
          </div>
          <div class="flex-1 min-width-0">
            <p class="text-sm font-semibold truncate">{{ auth.displayName || 'User' }}</p>
            <p class="text-[10px] text-muted-foreground uppercase tracking-widest">{{ auth.role }}</p>
          </div>
        </div>
        
        <div class="flex flex-col gap-1">
          <router-link to="/proactive" class="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-all">
            <Zap class="w-4 h-4" />
            <span v-if="!sidebarCollapsed">Automations</span>
          </router-link>
          <router-link to="/settings" class="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-all">
            <Settings class="w-4 h-4" />
            <span v-if="!sidebarCollapsed">Settings</span>
          </router-link>
          <button @click="handleLogout" class="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-destructive/80 hover:bg-destructive/10 hover:text-destructive transition-all">
            <LogOut class="w-4 h-4" />
            <span v-if="!sidebarCollapsed">Sign Out</span>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 flex flex-col min-w-0 relative">
      <header class="h-[60px] flex items-center justify-between px-6 border-b border-border bg-background/80 backdrop-blur-md z-40">
        <div class="flex items-center gap-3">
          <h2 class="text-sm font-semibold truncate max-w-[300px]">{{ currentConvTitle }}</h2>
          <div class="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20">
            <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
            <span class="text-[10px] font-bold text-primary uppercase tracking-tight">Active</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button @click="chat.newConversation" class="p-2 rounded-md hover:bg-accent transition-colors text-muted-foreground">
            <SquarePen class="w-5 h-5" />
          </button>
        </div>
      </header>

      <!-- Messages Area -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto px-4 py-8 custom-scrollbar">
        <div class="max-w-3xl mx-auto space-y-10">
          
          <!-- Welcome -->
          <div v-if="chat.messages.length === 0" class="py-20 flex flex-col items-center text-center space-y-6">
            <div class="w-16 h-16 bg-primary/5 rounded-2xl flex items-center justify-center border border-border animate-in zoom-in duration-700">
              <Layers class="w-8 h-8 text-primary" />
            </div>
            <div class="space-y-2 animate-in slide-in-from-bottom-4 duration-700">
              <h1 class="text-4xl font-extrabold tracking-tight italic">How can I help?</h1>
              <p class="text-muted-foreground text-lg">Your autonomous AI agent is ready for any task.</p>
            </div>
            
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full mt-10">
              <button 
                v-for="suggest in suggestions" :key="suggest.text"
                @click="input = suggest.prompt"
                class="p-4 rounded-xl border border-border bg-card hover:border-primary/50 hover:shadow-lg transition-all text-left group"
              >
                <div class="text-xl mb-2">{{ suggest.icon }}</div>
                <div class="text-sm font-semibold group-hover:text-primary transition-colors">{{ suggest.text }}</div>
              </button>
            </div>
          </div>

          <!-- Message Bubbles -->
          <div
            v-for="(msg, idx) in chat.messages"
            :key="idx"
            :class="['flex flex-col gap-3 group animate-in fade-in slide-in-from-bottom-2 duration-300']"
          >
            <div :class="['flex gap-4', msg.role === 'human' ? 'flex-row-reverse' : '']">
              <div :class="[
                'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 font-bold text-xs',
                msg.role === 'ai' ? 'bg-primary text-primary-foreground shadow-lg' : 'bg-secondary border border-border'
              ]">
                {{ msg.role === 'ai' ? 'J' : (auth.displayName?.[0] || 'U') }}
              </div>
              
              <div :class="['max-w-[85%] flex flex-col gap-2', msg.role === 'human' ? 'items-end' : '']">
                <div :class="[
                  'px-4 py-3 rounded-2xl text-[15px] leading-relaxed',
                  msg.role === 'human' ? 'bg-primary text-primary-foreground' : 'bg-muted/50 border border-border'
                ]">
                  <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                  
                  <!-- HITL Approval -->
                  <div v-if="msg.pending_tool_call" class="mt-4 p-4 bg-background/50 border border-primary/30 rounded-xl space-y-3">
                    <div class="flex items-center gap-2 text-[10px] font-black text-primary tracking-widest">
                      <ShieldAlert class="w-3.5 h-3.5" />
                      SECURITY AUTHORIZATION
                    </div>
                    <div class="text-sm">Requesting: <code class="bg-primary/10 text-primary px-1.5 py-0.5 rounded">{{ msg.pending_tool_call.name }}</code></div>
                    <div class="flex gap-2 pt-1">
                      <button @click="chat.handleConsent(true)" class="flex-1 py-2 bg-primary text-primary-foreground rounded-lg text-xs font-bold hover:opacity-90 transition-all">Allow</button>
                      <button @click="chat.handleConsent(false)" class="flex-1 py-2 bg-destructive/10 text-destructive border border-destructive/20 rounded-lg text-xs font-bold hover:bg-destructive/20 transition-all">Deny</button>
                    </div>
                  </div>

                  <!-- Tools Trace -->
                  <div v-if="msg.toolCalls?.length" class="mt-3 flex flex-wrap gap-1.5 border-t border-border pt-3">
                    <div v-for="tc in msg.toolCalls" :key="tc.name" class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-background/50 border border-border text-[10px] font-medium text-muted-foreground">
                      <span :class="['w-1.5 h-1.5 rounded-full', tc.status === 'running' ? 'bg-yellow-500 animate-pulse' : 'bg-emerald-500']"></span>
                      {{ tc.name }}
                    </div>
                  </div>
                </div>

                <!-- Actions -->
                <div v-if="msg.role === 'ai' && msg.content" class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button @click="copyText(msg.content)" class="p-1.5 rounded-md hover:bg-accent text-muted-foreground" title="Copy">
                    <Copy class="w-3.5 h-3.5" />
                  </button>
                  <button @click="regenerate(idx)" class="p-1.5 rounded-md hover:bg-accent text-muted-foreground" title="Regenerate">
                    <RotateCcw class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
            <div v-if="msg.role === 'ai' && hasHtml(msg.content)" class="ml-12">
              <LiveCanvas :content="msg.content" />
            </div>
          </div>

          <!-- Streaming -->
          <div v-if="chat.streaming" class="flex gap-4 animate-in fade-in duration-300">
            <div class="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-xs shadow-lg">J</div>
            <div class="bg-muted/50 border border-border px-4 py-4 rounded-2xl">
              <div class="flex gap-1.5">
                <div class="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce"></div>
                <div class="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                <div class="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce [animation-delay:0.4s]"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Section -->
      <div class="p-4 md:p-6 bg-gradient-to-t from-background via-background to-transparent">
        <div class="max-w-3xl mx-auto relative group">
          <div class="absolute inset-0 bg-primary/5 rounded-[26px] blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity duration-500"></div>
          
          <div class="relative bg-card border border-border rounded-[24px] shadow-2xl transition-all duration-300 group-focus-within:border-primary/50 group-focus-within:ring-4 group-focus-within:ring-primary/5 overflow-hidden">
            <div class="flex items-end p-2 gap-2">
              <button 
                @click="voiceOverlay?.start()"
                class="mb-1 w-10 h-10 rounded-full flex items-center justify-center text-muted-foreground hover:bg-accent hover:text-primary transition-all active:scale-90"
              >
                <Mic class="w-5 h-5" />
              </button>
              
              <textarea
                v-model="input"
                class="flex-1 bg-transparent border-none focus:ring-0 px-2 py-3.5 text-sm md:text-[15px] resize-none max-h-[200px] min-h-[52px] custom-scrollbar"
                :placeholder="$t('chat.inputPlaceholder')"
                @keydown.enter.prevent="handleSend"
                rows="1"
              ></textarea>
              
              <button
                @click="handleSend"
                :disabled="!input.trim() || chat.streaming"
                class="mb-1 w-10 h-10 rounded-xl bg-primary text-primary-foreground flex items-center justify-center hover:opacity-90 disabled:bg-muted disabled:text-muted-foreground transition-all active:scale-90 shadow-lg shadow-primary/20"
              >
                <ArrowUp class="w-5 h-5" />
              </button>
            </div>
          </div>
          <p class="mt-3 text-[10px] text-center text-muted-foreground font-medium uppercase tracking-[0.2em] opacity-50">
            Enterprise Class AI Intelligence
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
  Plus, MessageSquare, Trash2, Zap, Settings, LogOut, 
  ChevronLeft, ChevronRight, SquarePen, Copy, RotateCcw,
  Mic, ArrowUp, Layers, ShieldAlert
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
  { icon: '🎨', text: 'Canvas Demo', prompt: 'Show me a demo of Live Canvas with a reactive UI' },
  { icon: '🛡️', text: 'Security Scan', prompt: 'Run a proactive security check on my current workspace' },
  { icon: '🧠', text: 'Memory Search', prompt: 'What did we talk about last time regarding the architecture?' }
];

marked.setOptions({
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value;
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
});

const renderMarkdown = (text: string) => text ? marked.parse(text) : '<span class="animate-pulse text-primary italic">Thinking...</span>';
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
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

.markdown-body :deep(pre) { border-radius: 12px; margin: 1.5rem 0; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); }
.markdown-body :deep(code) { font-family: 'JetBrains Mono', monospace; font-weight: 500; }
</style>
