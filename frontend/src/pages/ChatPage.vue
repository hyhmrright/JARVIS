<template>
  <div class="flex h-screen w-full bg-zinc-950 font-sans overflow-hidden">
    
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
          <span class="text-sm text-zinc-100">JARVIS</span>
        </div>
        <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors" title="New Chat" @click="chat.newConversation">
          <SquarePen class="w-4 h-4 text-zinc-400" />
        </button>
      </div>

      <nav class="flex-1 overflow-y-auto px-2 py-4 space-y-0.5 custom-scrollbar">
        <div
          v-for="c in chat.conversations"
          :key="c.id"
          :class="[
            'group flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer transition-colors relative',
            chat.currentConvId === c.id ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
          ]"
          @click="chat.selectConversation(c.id)"
        >
          <MessageSquare class="w-3.5 h-3.5 flex-shrink-0" />
          <span class="text-xs truncate flex-1">{{ c.title }}</span>
          <button
            class="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400"
            @click.stop="chat.deleteConversation(c.id)"
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
            
            <button class="opacity-0 group-hover:opacity-100 flex items-center gap-1.5 px-2 py-1 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 rounded transition-all text-[10px] font-bold uppercase tracking-wider" title="Sign out" @click="handleLogout">
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
            class="p-1.5 hover:bg-zinc-800 rounded transition-colors"
            @click="sidebarCollapsed = false"
          >
            <PanelLeft class="w-4 h-4 text-zinc-400" />
          </button>
          <h2 class="text-xs font-semibold text-zinc-100 tracking-tight">{{ currentConvTitle }}</h2>
        </div>
        <div class="flex items-center gap-3">
          <button 
            v-if="activeCanvasContent"
            :class="['p-1.5 rounded transition-colors', canvasVisible ? 'bg-zinc-100 text-zinc-950' : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800']"
            title="Toggle Canvas"
            @click="canvasVisible = !canvasVisible"
          >
            <Layout class="w-4 h-4" />
          </button>
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
                class="p-4 rounded-xl border border-zinc-800 bg-zinc-950/50 hover:bg-zinc-800 hover:border-zinc-700 transition-all text-left group"
                @click="input = s.prompt"
              >
                <div class="text-[13px] font-semibold text-zinc-200 group-hover:text-white">{{ s.text }}</div>
                <div class="text-[11px] text-zinc-500 mt-1">{{ s.sub }}</div>
              </button>
            </div>
          </div>

          <!-- Message Blocks -->
          <div
            v-for="(msg, idx) in chat.activeMessages"
            :key="idx"
            class="flex flex-col gap-4 animate-in fade-in duration-700"
          >
            <!-- Sender Label -->
            <div class="flex items-center gap-3 select-none">
              <div
                :class="['w-5 h-5 rounded-sm flex items-center justify-center text-[9px] font-bold tracking-tighter', 
                msg.role === 'ai' ? 'bg-white text-black' : 'bg-zinc-800 text-zinc-400']">
                {{ msg.role === 'ai' ? 'JARVIS' : (auth.displayName?.[0] || 'U') }}
              </div>
              <span class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">{{ msg.role === 'ai' ? 'Autonomous Agent' : 'User' }}</span>
            </div>

            <!-- Content Column -->
            <div class="pl-8 group relative min-h-[20px]">
              <div v-if="msg.image_urls && msg.image_urls.length > 0" class="flex flex-wrap gap-2 mb-2">
                <img v-for="(img, imgIdx) in msg.image_urls" :key="imgIdx" :src="img" class="max-w-[300px] max-h-[300px] object-contain rounded-md border border-zinc-700/50" />
              </div>
              
              <div v-if="editingMessageId === msg.id" class="space-y-2">
                <textarea
                  v-model="editInput"
                  class="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-[14px] text-zinc-100 focus:ring-1 focus:ring-white/20 focus:border-zinc-600 outline-none min-h-[100px] resize-none"
                ></textarea>
                <div class="flex gap-2 justify-end">
                  <button class="px-3 py-1.5 text-[11px] font-bold text-zinc-400 hover:text-zinc-200 transition-colors" @click="cancelEdit">CANCEL</button>
                  <button class="px-3 py-1.5 text-[11px] font-bold bg-white text-black rounded hover:bg-zinc-200 transition-all" @click="handleEditSubmit(msg)">SUBMIT</button>
                </div>
              </div>
              <div v-else class="markdown-body text-zinc-200 leading-[1.7] text-[14px]" v-html="renderMarkdown(msg.content)"></div>
              
              <!-- Message Actions (Human) -->
              <div v-if="msg.role === 'human' && !editingMessageId" class="absolute -top-1 -right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" title="Edit" @click="startEdit(msg)">
                  <SquarePen class="w-3 h-3" />
                </button>
              </div>
              
              <!-- HITL Security Box -->
              <div v-if="msg.pending_tool_call" class="mt-8 p-6 bg-zinc-950 border border-white/10 rounded-lg space-y-5 max-w-md shadow-2xl">
                <div class="flex items-center gap-2 text-[9px] font-black text-white tracking-[0.2em]">
                  <ShieldAlert class="w-3.5 h-3.5" />
                  CONFIRM EXECUTION
                </div>
                <div class="text-[13px] text-zinc-300">Target action: <code class="bg-zinc-800 text-white px-1.5 py-0.5 rounded font-mono">{{ msg.pending_tool_call.name }}</code></div>
                <div class="flex gap-2">
                  <button class="flex-1 py-2.5 bg-white text-black rounded text-[11px] font-bold hover:bg-zinc-200 transition-all" @click="chat.handleConsent(true)">APPROVE</button>
                  <button class="flex-1 py-2.5 bg-zinc-900 text-zinc-400 border border-zinc-800 rounded text-[11px] font-bold hover:bg-zinc-800 transition-all" @click="chat.handleConsent(false)">REJECT</button>
                </div>
              </div>

              <!-- Message Footer: Branch Nav & Actions -->
              <div v-if="msg.id" class="mt-3 flex items-center gap-4 text-zinc-500">
                <!-- Branch Switcher -->
                <div v-if="chat.getSiblings(msg).length > 1" class="flex items-center gap-1.5 bg-zinc-900/50 rounded-full px-2 py-0.5 border border-zinc-800/50">
                  <button 
                    class="hover:text-zinc-200 disabled:opacity-30 disabled:hover:text-zinc-500 transition-colors" 
                    :disabled="getBranchIndex(msg) === 0"
                    @click="navigateBranch(msg, -1)"
                  >
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                  </button>
                  <span class="text-[9px] font-medium tabular-nums text-zinc-400">{{ getBranchIndex(msg) + 1 }} / {{ chat.getSiblings(msg).length }}</span>
                  <button 
                    class="hover:text-zinc-200 disabled:opacity-30 disabled:hover:text-zinc-500 transition-colors" 
                    :disabled="getBranchIndex(msg) === chat.getSiblings(msg).length - 1"
                    @click="navigateBranch(msg, 1)"
                  >
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                  </button>
                </div>

                <!-- AI Specific: Regenerate -->
                <button 
                  v-if="msg.role === 'ai' && !chat.streaming" 
                  class="text-[10px] font-medium hover:text-zinc-300 flex items-center gap-1.5 transition-colors" 
                  @click="chat.regenerate(msg.id)"
                >
                  <RotateCcw class="w-3 h-3" />
                  Regenerate
                </button>
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
                <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" title="Copy" @click="copyText(msg.content)">
                  <Copy class="w-3 h-3" />
                </button>
                <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" title="Regenerate" @click="regenerate(idx)">
                  <RotateCcw class="w-3 h-3" />
                </button>
                <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" :class="{ 'text-emerald-400': isPlayingTTS === msg.content }" title="Read Aloud" @click="playTTS(msg.content)">
                  <Volume2 class="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>

          <!-- Typing Pulse -->
          <div v-if="chat.streaming" class="flex items-center gap-2 pl-8 py-4">
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse"></div>
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse [animation-delay:0.2s]"></div>
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse [animation-delay:0.4s]"></div>
            <span
              v-if="chat.routingAgent"
              class="ml-1 text-[9px] font-bold text-zinc-500 uppercase tracking-widest px-2 py-0.5 bg-zinc-800 rounded-full"
            >{{ agentLabel(chat.routingAgent) }}</span>
          </div>
        </div>
      </div>

      <!-- Footer Dock -->
      <div class="w-full bg-zinc-900 pt-2">
        <div class="max-w-3xl mx-auto px-6 pb-10">
          <div class="relative bg-zinc-950 border border-zinc-800 rounded-xl transition-all focus-within:border-zinc-700">
            <!-- Image Previews -->
            <div v-if="selectedImages.length > 0" class="flex flex-wrap gap-2 px-4 pt-3 pb-1">
              <div v-for="(img, idx) in selectedImages" :key="idx" class="relative group">
                <img :src="img" class="w-14 h-14 object-cover rounded-md border border-zinc-800" />
                <button 
                  class="absolute -top-1.5 -right-1.5 bg-zinc-900 text-zinc-400 rounded-full p-0.5 border border-zinc-800 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
                  @click="removeImage(idx)"
                >
                  <X class="w-3 h-3" />
                </button>
              </div>
            </div>

            <div class="flex items-end p-2 gap-1">
              <input 
                ref="fileInput" 
                type="file" 
                class="hidden" 
                multiple 
                accept="image/*" 
                @change="handleImageSelect" 
              />
              <button class="p-2.5 text-zinc-500 hover:text-white transition-colors" title="Attach Image" @click="fileInput?.click()">
                <Image class="w-4 h-4" />
              </button>
              <button class="p-2.5 text-zinc-500 hover:text-white transition-colors" @click="voiceOverlay?.start()">
                <Mic class="w-4 h-4" />
              </button>
              
              <textarea
                v-model="input"
                class="flex-1 bg-transparent border-none focus:ring-0 px-2 py-3 text-[14px] text-zinc-100 resize-none max-h-[300px] min-h-[44px] custom-scrollbar placeholder:text-zinc-600"
                :placeholder="$t('chat.inputPlaceholder')"
                rows="1"
                @keydown.enter="handleEnter"
              ></textarea>
              
              <!-- Stop button during streaming -->
              <button
                v-if="chat.streaming"
                class="p-2.5 bg-zinc-800 text-white rounded-lg transition-all active:scale-95 hover:bg-zinc-700"
                :title="$t('chat.stopGenerating')"
                @click="chat.cancelStream()"
              >
                <Square class="w-4 h-4" />
              </button>
              <!-- Send button otherwise -->
              <button
                v-else
                :disabled="!input.trim()"
                class="p-2.5 bg-white text-black rounded-lg disabled:opacity-10 transition-all active:scale-95"
                @click="handleSend"
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

    <!-- Right Sidebar for Live Canvas -->
    <LiveCanvas 
      :content="activeCanvasContent" 
      :is-visible="canvasVisible" 
      :collapsed="canvasCollapsed" 
      @close="canvasVisible = false"
      @submit="handleCanvasSubmit"
    />

    <VoiceOverlay ref="voiceOverlay" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick, computed } from "vue";
import { useRouter } from "vue-router";
import { useChatStore } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";
import { marked } from "marked";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css";

import {
  Trash2, Zap, Settings, LogOut,
  PanelLeft, SquarePen, Copy, RotateCcw,
  Mic, ArrowUp, Square, ShieldAlert, Share2, MessageSquare,
  Volume2, Layout, Image, X
} from "lucide-vue-next";

import LiveCanvas from "@/components/LiveCanvas.vue";
import VoiceOverlay from "@/components/VoiceOverlay.vue";
import client from "@/api/client";

const chat = useChatStore();
const auth = useAuthStore();
const router = useRouter();

const input = ref("");
const editingMessageId = ref<string | null>(null);
const editInput = ref("");
const fileInput = ref<HTMLInputElement>();
const selectedImages = ref<string[]>([]);
const sidebarCollapsed = ref(false);

const startEdit = (msg: any) => {
  editingMessageId.value = msg.id;
  editInput.value = msg.content;
};

const cancelEdit = () => {
  editingMessageId.value = null;
  editInput.value = "";
};

const handleEditSubmit = async (msg: any) => {
  const content = editInput.value;
  cancelEdit();
  await chat.sendMessage(content, undefined, msg.parent_id);
};

const getBranchIndex = (msg: any) => {
  const siblings = chat.getSiblings(msg);
  return siblings.findIndex(m => m.id === msg.id);
};

const navigateBranch = (msg: any, direction: number) => {
  const siblings = chat.getSiblings(msg);
  const currentIndex = siblings.findIndex(m => m.id === msg.id);
  const nextIndex = currentIndex + direction;
  if (nextIndex >= 0 && nextIndex < siblings.length) {
    chat.switchBranch(siblings[nextIndex].id!);
  }
};

const handleImageSelect = (e: Event) => {
  const files = (e.target as HTMLInputElement).files;
  if (!files) return;
  Array.from(files).forEach(file => {
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (ev.target?.result) {
        selectedImages.value.push(ev.target.result as string);
      }
    };
    reader.readAsDataURL(file);
  });
  // Reset input
  if (fileInput.value) fileInput.value.value = '';
};

const removeImage = (idx: number) => {
  selectedImages.value.splice(idx, 1);
};

const messagesEl = ref<HTMLElement>();
const voiceOverlay = ref<InstanceType<typeof VoiceOverlay>>();

// Canvas State
const canvasVisible = ref(false);
const canvasCollapsed = ref(false);

const activeCanvasContent = computed(() => {
  // Find the latest message with HTML, Chart or Form
  const lastCanvasMsg = [...chat.messages].reverse().find(m => m.role === 'ai' && (hasHtml(m.content) || hasCanvasData(m.content)));
  return lastCanvasMsg ? lastCanvasMsg.content : "";
});

// Auto-open canvas when new content arrives
watch(activeCanvasContent, (newVal) => {
  if (newVal && !canvasVisible.value) {
    canvasVisible.value = true;
  }
});

const handleCanvasSubmit = async (values: any) => {
  await chat.sendMessage(`Form Submitted: ${JSON.stringify(values)}`);
};

const currentAudio = ref<HTMLAudioElement | null>(null);
const isPlayingTTS = ref<string | null>(null);

const playTTS = async function(text: string): Promise<void> {
  // If the same text is already playing, toggle pause
  if (isPlayingTTS.value === text && currentAudio.value) {
    currentAudio.value.pause();
    isPlayingTTS.value = null;
    return;
  }

  // Stop currently playing audio
  if (currentAudio.value) {
    currentAudio.value.pause();
  }

  try {
    isPlayingTTS.value = text;
    const cleanText = text
      .replace(/<[^>]*>?/gm, '')
      .replace(/[*#_`~[\]()]/g, '');

    const response = await client.post('/tts/synthesize', {
      text: cleanText.substring(0, 5000),
      voice: "zh-CN-XiaoxiaoNeural",
      rate: "+0%"
    }, {
      responseType: 'blob'
    });

    const audioUrl = URL.createObjectURL(response.data);
    const audio = new Audio(audioUrl);
    currentAudio.value = audio;

    audio.onended = () => {
      isPlayingTTS.value = null;
      URL.revokeObjectURL(audioUrl);
    };

    await audio.play();
  } catch (error) {
    console.error("TTS failed", error);
    isPlayingTTS.value = null;
  }
};

const AGENT_LABELS: Record<string, string> = {
  code: "Code Agent",
  research: "Research Agent",
  writing: "Writing Agent",
  complex: "Supervisor",
  simple: "Agent",
};

const agentLabel = (agent: string): string => AGENT_LABELS[agent] ?? agent;

const suggestions = [
  { text: 'Run Security Scan', sub: 'Audit current workspace structure', prompt: 'Run a proactive security check' },
  { text: 'Dynamic Canvas', sub: 'Generate interactive UI components', prompt: 'Show me a demo of Live Canvas' },
  { text: 'Deep Memory Search', sub: 'Search offline conversation logs', prompt: 'Search local memory for project roadmap' }
];

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

const renderMarkdown = (text: string) => text ? marked.parse(text) : '<span class="cursor-block"></span>';
const hasHtml = (text: string) => /<html>[\s\S]*?<\/html>/.test(text);
const hasCanvasData = (text: string) => {
  if (text.includes('"type": "chart"') || text.includes('"type": "form"')) return true;
  return false;
};
const currentConvTitle = computed(() => chat.conversations.find((conv) => conv.id === chat.currentConvId)?.title || "Intelligence Terminal");

const handleSend = async function(): Promise<void> {
  if ((!input.value.trim() && selectedImages.value.length === 0) || chat.streaming) return;
  const msg = input.value;
  const images = [...selectedImages.value];
  input.value = "";
  selectedImages.value = [];
  await chat.sendMessage(msg, images.length > 0 ? images : undefined);
};

const handleEnter = function(e: KeyboardEvent): void {
  // IME composition or Shift+Enter → allow newline
  if (e.isComposing || e.shiftKey) return;

  // Otherwise, send the message
  e.preventDefault();
  handleSend();
};

const copyText = function(text: string): void {
  navigator.clipboard.writeText(text);
};

const regenerate = async function(idx: number): Promise<void> {
  const prevHuman = chat.messages.slice(0, idx)
    .reverse()
    .find(m => m.role === 'human');
  if (prevHuman) {
    await chat.sendMessage(prevHuman.content);
  }
};

const handleLogout = function(): void {
  auth.logout();
  router.push("/login");
};

const scrollToBottom = async function(): Promise<void> {
  await nextTick();
  if (messagesEl.value) {
    messagesEl.value.scrollTo({
      top: messagesEl.value.scrollHeight,
      behavior: "smooth"
    });
  }
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
