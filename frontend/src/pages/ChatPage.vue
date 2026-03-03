<template>
  <div class="flex h-screen w-full bg-zinc-950 font-sans">
    
    <!-- Ultra-thin Sidebar -->
    <aside 
      :class="[
        'flex flex-col bg-zinc-950 border-r border-zinc-800 transition-all duration-300 ease-in-out',
        sidebarCollapsed ? 'w-0 border-none opacity-0' : 'w-[260px]'
      ]"
    >
      <div class="h-14 flex items-center px-4 justify-between">
        <div class="flex items-center gap-2 font-semibold tracking-tighter">
          <div class="w-5 h-5 bg-white text-black rounded-sm flex items-center justify-center text-[10px] font-bold">J</div>
          <span class="text-sm">JARVIS</span>
        </div>
        <button @click="chat.newConversation" class="p-1.5 hover:bg-zinc-800 rounded transition-colors" title="New Chat">
          <SquarePen class="w-4 h-4 text-zinc-400" />
        </button>
      </div>

      <nav class="flex-1 overflow-y-auto px-2 py-4 space-y-0.5 custom-scrollbar">
        <div
          v-for="c in chat.conversations"
          :key="c.id"
          @click="chat.selectConversation(c.id)"
          :class="[
            'group flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer transition-colors relative',
            chat.currentConvId === c.id ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
          ]"
        >
          <MessageSquare class="w-3.5 h-3.5 flex-shrink-0" />
          <span class="text-xs truncate flex-1">{{ c.title }}</span>
          <button
            @click.stop="chat.deleteConversation(c.id)"
            class="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400"
          >
            <Trash2 class="w-3 h-3" />
          </button>
        </div>
      </nav>

      <div class="p-4 border-t border-zinc-800 space-y-4">
        <div class="space-y-1">
          <router-link to="/proactive" class="flex items-center gap-3 px-2 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 transition-all">
            <Zap class="w-3.5 h-3.5" />
            <span>Automations</span>
          </router-link>
          <router-link to="/settings" class="flex items-center gap-3 px-2 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 transition-all">
            <Settings class="w-3.5 h-3.5" />
            <span>Settings</span>
          </router-link>
        </div>
        
        <div class="pt-2 border-t border-zinc-800">
          <div class="group flex items-center justify-between w-full px-2 py-2 bg-transparent hover:bg-zinc-900 rounded-lg transition-colors cursor-default">
            <div class="flex items-center gap-3 overflow-hidden">
              <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-zinc-800 to-zinc-700 flex items-center justify-center text-xs font-bold text-white shadow-sm border border-zinc-700/50 flex-shrink-0">
                {{ auth.displayName?.[0] || 'U' }}
              </div>
              <div class="flex flex-col overflow-hidden">
                <span class="text-xs font-medium text-zinc-200 truncate">{{ auth.displayName || 'User' }}</span>
                <span class="text-[10px] text-zinc-500 truncate">Free Plan</span>
              </div>
            </div>
            
            <button @click="handleLogout" class="opacity-0 group-hover:opacity-100 flex items-center gap-1.5 px-2 py-1 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 rounded transition-all text-[10px] font-bold uppercase tracking-wider" title="Sign out">
              <LogOut class="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- Content Well -->
    <main class="flex-1 flex flex-col min-w-0 bg-zinc-900 relative">
      <header class="h-14 flex items-center px-6 justify-between border-b border-zinc-800/50 bg-zinc-900/80 backdrop-blur-sm z-40">
        <div class="flex items-center gap-4">
          <button 
            v-if="sidebarCollapsed"
            @click="sidebarCollapsed = false"
            class="p-1.5 hover:bg-zinc-800 rounded transition-colors"
          >
            <PanelLeft class="w-4 h-4 text-zinc-400" />
          </button>
          <h2 class="text-xs font-semibold text-zinc-100 tracking-tight">{{ currentConvTitle }}</h2>
        </div>
        <div class="flex items-center gap-3">
          <button class="text-zinc-500 hover:text-zinc-300 transition-colors">
            <Share2 class="w-4 h-4" />
          </button>
        </div>
      </header>

      <!-- Messages Stream -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto custom-scrollbar">
        <div class="max-w-3xl mx-auto px-6 py-12 space-y-16">
          
          <!-- New Session Welcome -->
          <div v-if="chat.messages.length === 0" class="pt-20 text-center animate-in fade-in slide-in-from-bottom-4 duration-1000">
            <div class="w-10 h-10 bg-white text-black rounded-lg flex items-center justify-center font-bold mx-auto mb-6">J</div>
            <h1 class="text-2xl font-bold text-zinc-50 mb-12 tracking-tight">Intelligence at your service.</h1>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2 w-full max-w-lg mx-auto">
              <button 
                v-for="s in suggestions" :key="s.text"
                @click="input = s.prompt"
                class="p-4 rounded-xl border border-zinc-800 bg-zinc-950/50 hover:bg-zinc-800 hover:border-zinc-700 transition-all text-left group"
              >
                <div class="text-[13px] font-semibold text-zinc-200 group-hover:text-white">{{ s.text }}</div>
                <div class="text-[11px] text-zinc-500 mt-1">{{ s.sub }}</div>
              </button>
            </div>
          </div>

          <!-- Message Blocks -->
          <div
            v-for="(msg, idx) in chat.messages"
            :key="idx"
            class="flex flex-col gap-4 animate-in fade-in duration-700"
          >
            <!-- Sender Label -->
            <div class="flex items-center gap-3 select-none">
              <div :class="['w-5 h-5 rounded-sm flex items-center justify-center text-[9px] font-bold tracking-tighter', 
                msg.role === 'ai' ? 'bg-white text-black' : 'bg-zinc-800 text-zinc-400']">
                {{ msg.role === 'ai' ? 'JARVIS' : (auth.displayName?.[0] || 'U') }}
              </div>
              <span class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">{{ msg.role === 'ai' ? 'Autonomous Agent' : 'User' }}</span>
            </div>

            <!-- Content Column -->
            <div class="pl-8 group relative min-h-[20px]">
              <div class="markdown-body text-zinc-200 leading-[1.7] text-[14px]" v-html="renderMarkdown(msg.content)"></div>
              
              <!-- HITL Security Box -->
              <div v-if="msg.pending_tool_call" class="mt-8 p-6 bg-zinc-950 border border-white/10 rounded-lg space-y-5 max-w-md shadow-2xl">
                <div class="flex items-center gap-2 text-[9px] font-black text-white tracking-[0.2em]">
                  <ShieldAlert class="w-3.5 h-3.5" />
                  CONFIRM EXECUTION
                </div>
                <div class="text-[13px] text-zinc-300">Target action: <code class="bg-zinc-800 text-white px-1.5 py-0.5 rounded font-mono">{{ msg.pending_tool_call.name }}</code></div>
                <div class="flex gap-2">
                  <button @click="chat.handleConsent(true)" class="flex-1 py-2.5 bg-white text-black rounded text-[11px] font-bold hover:bg-zinc-200 transition-all">APPROVE</button>
                  <button @click="chat.handleConsent(false)" class="flex-1 py-2.5 bg-zinc-900 text-zinc-400 border border-zinc-800 rounded text-[11px] font-bold hover:bg-zinc-800 transition-all">REJECT</button>
                </div>
              </div>

              <!-- Tool Execution Logs -->
              <div v-if="msg.toolCalls?.length" class="mt-6 flex flex-col gap-2 pt-4 border-t border-zinc-800/50">
                <details v-for="(tc, i) in msg.toolCalls" :key="i" class="group bg-zinc-950/80 border border-zinc-800/80 rounded-xl overflow-hidden text-xs transition-all">
                  <summary class="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-zinc-900 transition-colors select-none marker:content-['']">
                    <div :class="['w-1.5 h-1.5 rounded-full flex-shrink-0 shadow-[0_0_8px_rgba(255,255,255,0.5)]', tc.status === 'running' ? 'bg-amber-400 animate-pulse shadow-amber-400/50' : 'bg-emerald-500 shadow-emerald-500/50']"></div>
                    <span class="font-mono text-zinc-300 font-semibold tracking-tight">{{ tc.name }}</span>
                    <span class="text-zinc-600 truncate flex-1 font-mono text-[10px]">{{ tc.args ? JSON.stringify(tc.args).substring(0, 50) + (JSON.stringify(tc.args).length > 50 ? '...' : '') : '' }}</span>
                    
                    <div class="flex items-center gap-2">
                      <span class="text-zinc-500 text-[9px] uppercase tracking-widest font-bold">{{ tc.status === 'running' ? 'Executing' : 'Completed' }}</span>
                      <svg class="w-3.5 h-3.5 text-zinc-500 transform transition-transform group-open:rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </div>
                  </summary>
                  
                  <div class="px-4 py-4 bg-[#0a0a0a] border-t border-zinc-800/80">
                    <div class="mb-2 flex items-center gap-2 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                      <Zap class="w-3 h-3" /> Payload
                    </div>
                    <pre class="text-zinc-300 font-mono text-[11px] bg-zinc-900/40 p-3 rounded-lg border border-zinc-800/50 overflow-x-auto whitespace-pre-wrap leading-relaxed">{{ tc.args ? JSON.stringify(tc.args, null, 2) : '{}' }}</pre>
                    
                    <div v-if="tc.result" class="mt-5">
                      <div class="mb-2 flex items-center gap-2 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                        <PanelLeft class="w-3 h-3" /> Output / Response
                      </div>
                      <pre class="text-zinc-300 font-mono text-[11px] bg-zinc-900/40 p-3 rounded-lg border border-zinc-800/50 overflow-x-auto whitespace-pre-wrap max-h-80 overflow-y-auto leading-relaxed custom-scrollbar">{{ tc.result }}</pre>
                    </div>
                  </div>
                </details>
              </div>

              <!-- Message Actions -->
              <div v-if="msg.role === 'ai' && msg.content" class="absolute -bottom-8 left-8 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button @click="copyText(msg.content)" class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" title="Copy">
                  <Copy class="w-3 h-3" />
                </button>
                <button @click="regenerate(idx)" class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" title="Regenerate">
                  <RotateCcw class="w-3 h-3" />
                </button>
              </div>
            </div>
            
            <!-- Canvas Inset -->
            <div v-if="msg.role === 'ai' && hasHtml(msg.content)" class="pl-8 mt-6">
              <LiveCanvas :content="msg.content" />
            </div>
          </div>

          <!-- Typing Pulse -->
          <div v-if="chat.streaming" class="flex items-center gap-2 pl-8 py-4">
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse"></div>
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse [animation-delay:0.2s]"></div>
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse [animation-delay:0.4s]"></div>
          </div>
        </div>
      </div>

      <!-- Footer Dock -->
      <div class="w-full bg-zinc-900 pt-2">
        <div class="max-w-3xl mx-auto px-6 pb-10">
          <div class="relative bg-zinc-950 border border-zinc-800 rounded-xl transition-all focus-within:border-zinc-700">
            <div class="flex items-end p-2 gap-1">
              <button @click="voiceOverlay?.start()" class="p-2.5 text-zinc-500 hover:text-white transition-colors">
                <Mic class="w-4 h-4" />
              </button>
              
              <textarea
                v-model="input"
                class="flex-1 bg-transparent border-none focus:ring-0 px-2 py-3 text-[14px] text-zinc-100 resize-none max-h-[300px] min-h-[44px] custom-scrollbar placeholder:text-zinc-600"
                :placeholder="$t('chat.inputPlaceholder')"
                @keydown.enter="handleEnter"
                rows="1"
              ></textarea>
              
              <button
                @click="handleSend"
                :disabled="!input.trim() || chat.streaming"
                class="p-2.5 bg-white text-black rounded-lg disabled:opacity-10 transition-all active:scale-95"
              >
                <ArrowUp class="w-4 h-4 stroke-[3px]" />
              </button>
            </div>
          </div>
          <div class="mt-4 flex justify-center items-center gap-4 text-[9px] font-bold text-zinc-600 uppercase tracking-widest">
            <span>Enterprise Guard Active</span>
            <div class="w-1 h-1 bg-zinc-800 rounded-full"></div>
            <span>End-to-End Encrypted</span>
          </div>
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
  Mic, ArrowUp, ShieldAlert, Share2, MessageSquare
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
  { text: 'Run Security Scan', sub: 'Audit current workspace structure', prompt: 'Run a proactive security check' },
  { text: 'Dynamic Canvas', sub: 'Generate interactive UI components', prompt: 'Show me a demo of Live Canvas' },
  { text: 'Deep Memory Search', sub: 'Search offline conversation logs', prompt: 'Search local memory for project roadmap' }
];

marked.setOptions({
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value;
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
});

const renderMarkdown = (text: string) => text ? marked.parse(text) : '<span class="cursor-block"></span>';
const hasHtml = (text: string) => /<html>[\s\S]*?<\/html>/.test(text);
const currentConvTitle = computed(() => chat.conversations.find((conv) => conv.id === chat.currentConvId)?.title || "Intelligence Terminal");

const handleSend = async () => {
  if (!input.value.trim() || chat.streaming) return;
  const msg = input.value;
  input.value = "";
  await chat.sendMessage(msg);
};

const handleEnter = (e: KeyboardEvent) => {
  // If IME is composing (e.g. typing Chinese), do nothing
  if (e.isComposing) return;
  
  // If Shift is pressed, let it act as a newline
  if (e.shiftKey) return;
  
  // Otherwise, prevent default newline and send
  e.preventDefault();
  handleSend();
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
.markdown-body :deep(pre) { background: #000; padding: 1.25rem; border-radius: 6px; margin: 1.5rem 0; border: 1px solid #27272a; overflow-x: auto; }
.markdown-body :deep(code) { font-family: 'JetBrains Mono', monospace; font-size: 0.85em; }
.markdown-body :deep(p) { margin-bottom: 1.5rem; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }

.cursor-block { display: inline-block; width: 6px; height: 14px; background: #fff; margin-left: 4px; animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

.custom-scrollbar::-webkit-scrollbar { width: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #27272a; border-radius: 10px; }

details > summary { list-style: none; }
details > summary::-webkit-details-marker { display: none; }
</style>
