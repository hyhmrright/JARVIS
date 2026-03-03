<template>
  <div class="chat-layout">
    <div class="bg-glow"></div>

    <!-- Sidebar -->
    <aside :class="['sidebar', { 'sidebar--collapsed': sidebarCollapsed }]">
      <div class="sidebar-brand">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="3" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
        </div>
        <span v-if="!sidebarCollapsed" class="brand-name">JARVIS</span>
        <button class="btn-icon-sm toggle-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <svg v-if="!sidebarCollapsed" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M15 18l-6-6 6-6"/></svg>
          <svg v-else viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M9 18l6-6-6-6"/></svg>
        </button>
      </div>

      <button class="btn-new-chat" @click="chat.newConversation">
        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2.5" fill="none"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span v-if="!sidebarCollapsed">{{ $t("chat.newConversation") }}</span>
      </button>

      <nav class="conv-list custom-scrollbar">
        <div
          v-for="c in chat.conversations"
          :key="c.id"
          :class="['conv-item', { active: chat.currentConvId === c.id }]"
          @click="chat.selectConversation(c.id)"
        >
          <svg class="item-icon" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span v-if="!sidebarCollapsed" class="conv-title">{{ c.title }}</span>
          <button
            v-if="!sidebarCollapsed"
            class="btn-delete-conv"
            @click.stop="chat.deleteConversation(c.id)"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </nav>

      <div class="sidebar-user" v-if="!sidebarCollapsed">
        <div class="user-avatar">{{ auth.displayName?.[0] || 'U' }}</div>
        <div class="user-info">
          <div class="user-name">{{ auth.displayName || 'User' }}</div>
          <div class="user-role">{{ auth.role }}</div>
        </div>
      </div>

      <footer class="sidebar-footer">
        <router-link to="/proactive" class="footer-link" :title="$t('proactive.title')">
          <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          <span v-if="!sidebarCollapsed">{{ $t("proactive.title") }}</span>
        </router-link>
        <router-link to="/settings" class="footer-link" :title="$t('chat.settings')">
          <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          <span v-if="!sidebarCollapsed">{{ $t("chat.settings") }}</span>
        </router-link>
        <button class="footer-link logout-btn" @click="handleLogout" :title="$t('chat.logout')">
          <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          <span v-if="!sidebarCollapsed">{{ $t("chat.logout") }}</span>
        </button>
      </footer>
    </aside>

    <!-- Main Chat -->
    <main class="chat-main">
      <header class="chat-header">
        <div class="header-left">
          <h2 class="chat-title">{{ currentConvTitle }}</h2>
          <div class="status-badge">
            <span class="dot pulse"></span>
            Agent Active
          </div>
        </div>
        <div class="header-right">
          <button class="btn-icon" @click="chat.newConversation" title="New Chat">
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
        </div>
      </header>

      <div ref="messagesEl" class="messages-container custom-scrollbar">
        <!-- Welcome Screen -->
        <div v-if="chat.messages.length === 0" class="welcome-container">
          <div class="welcome-glow"></div>
          <div class="welcome-card animate-slide-up">
            <div class="huge-logo">J</div>
            <h1>How can I help you today?</h1>
            <p class="welcome-subtitle">Ask anything, from code to automation tasks.</p>
            
            <div class="suggestion-grid">
              <div class="suggest-item" @click="input = 'Show me a demo of Live Canvas'">
                <div class="suggest-icon">🎨</div>
                <div class="suggest-text">Live Canvas Demo</div>
              </div>
              <div class="suggest-item" @click="input = 'Run a proactive security check'">
                <div class="suggest-icon">🛡️</div>
                <div class="suggest-text">Security Check</div>
              </div>
              <div class="suggest-item" @click="input = 'Analyze my local memories'">
                <div class="suggest-icon">🧠</div>
                <div class="suggest-text">Memory Analysis</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Message List -->
        <div
          v-for="(msg, idx) in chat.messages"
          :key="idx"
          :class="['msg-group', msg.role]"
        >
          <div class="msg-row">
            <div class="msg-avatar" :class="{ 'ai-avatar': msg.role === 'ai' }">
              <span v-if="msg.role === 'ai'">J</span>
              <span v-else>{{ auth.displayName?.[0] || 'U' }}</span>
            </div>
            <div class="msg-body">
              <div class="msg-bubble shadow-sm">
                <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                
                <!-- HITL Approval -->
                <div v-if="msg.pending_tool_call" class="approval-box animate-zoom-in">
                  <div class="approval-header">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                    <span>ACTION REQUIRED</span>
                  </div>
                  <p>Requesting execution of <code>{{ msg.pending_tool_call.name }}</code></p>
                  <div class="approval-btns">
                    <button class="btn-approve" @click="chat.handleConsent(true)">Allow</button>
                    <button class="btn-deny" @click="chat.handleConsent(false)">Deny</button>
                  </div>
                </div>

                <!-- Tool Trace -->
                <div v-if="msg.toolCalls?.length" class="tool-trace">
                  <div v-for="tc in msg.toolCalls" :key="tc.name" class="tool-tag">
                    <span :class="['dot', tc.status]"></span>
                    {{ tc.name }}
                  </div>
                </div>
              </div>

              <!-- Message Actions -->
              <div class="msg-actions" v-if="msg.role === 'ai' && msg.content">
                <button @click="copyText(msg.content)" title="Copy">
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                </button>
                <button @click="regenerate(idx)" title="Regenerate">
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="23 4 23 10 18 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
              </div>
            </div>
          </div>
          <LiveCanvas v-if="msg.role === 'ai' && hasHtml(msg.content)" :content="msg.content" />
        </div>

        <!-- Streaming Placeholder -->
        <div v-if="chat.streaming" class="msg-group ai">
          <div class="msg-row">
            <div class="msg-avatar ai-avatar">J</div>
            <div class="msg-body">
              <div class="msg-bubble streaming-bubble">
                <div class="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Bar -->
      <div class="input-section">
        <div class="input-wrapper-outer">
          <div class="input-toolbar" v-if="input.length > 50">
            <span class="char-count">{{ input.length }} chars</span>
          </div>
          <div class="input-wrapper">
            <button class="btn-icon circle-btn voice-trigger" @click="voiceOverlay?.start()">
              <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
            </button>
            <textarea
              v-model="input"
              class="chat-textarea custom-scrollbar"
              :placeholder="$t('chat.inputPlaceholder')"
              @keydown.enter.prevent="handleSend"
              rows="1"
            ></textarea>
            <button
              class="btn-send-main"
              :disabled="!input.trim() || chat.streaming"
              @click="handleSend"
            >
              <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
        </div>
        <p class="input-footer">JARVIS may produce inaccurate information.</p>
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

// Markdown setup
marked.setOptions({
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
});

const renderMarkdown = (text: string) => {
  if (!text) return '<span class="cursor-pipe">|</span>';
  return marked.parse(text);
};

const hasHtml = (text: string) => /<html>[\s\S]*?<\/html>/.test(text);

const currentConvTitle = computed(() => {
  const c = chat.conversations.find((conv) => conv.id === chat.currentConvId);
  return c ? c.title : "New Session";
});

const handleSend = async () => {
  if (!input.value.trim() || chat.streaming) return;
  const msg = input.value;
  input.value = "";
  await chat.sendMessage(msg);
};

const copyText = (text: string) => {
  navigator.clipboard.writeText(text);
};

const regenerate = async (idx: number) => {
  // Simple implementation: send the previous human message again
  const prevHuman = chat.messages.slice(0, idx).reverse().find(m => m.role === 'human');
  if (prevHuman) {
    await chat.sendMessage(prevHuman.content);
  }
};

const handleLogout = () => {
  auth.logout();
  router.push("/login");
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesEl.value) {
    messagesEl.value.scrollTo({
      top: messagesEl.value.scrollHeight,
      behavior: "smooth",
    });
  }
};

watch(() => chat.messages.length, scrollToBottom);
watch(() => chat.streaming, (isStreaming) => { if (isStreaming) scrollToBottom(); });

onMounted(async () => {
  await chat.loadConversations();
});
</script>

<style scoped>
.chat-layout {
  display: flex; height: 100vh; background: var(--bg-primary);
  position: relative; overflow: hidden; color: var(--text-primary);
}

.bg-glow {
  position: absolute; top: -15%; left: -10%; width: 50%; height: 50%;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.08) 0%, transparent 70%);
  filter: blur(80px); pointer-events: none;
}

/* ── Sidebar ── */
.sidebar {
  width: 280px; background: var(--bg-secondary); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 100; backdrop-filter: var(--glass-blur);
}
.sidebar--collapsed { width: 80px; }

.sidebar-brand { padding: 1.5rem; display: flex; align-items: center; gap: 1rem; height: 70px; }
.brand-logo {
  width: 32px; height: 32px; background: var(--accent); border-radius: 8px;
  display: flex; align-items: center; justify-content: center; color: white;
}
.brand-name { font-weight: 800; letter-spacing: 1.5px; font-size: 1.1rem; }
.toggle-btn { background: transparent; border: none; color: var(--text-muted); cursor: pointer; padding: 4px; border-radius: 4px; }
.toggle-btn:hover { background: rgba(255,255,255,0.05); color: var(--text-primary); }

.btn-new-chat {
  margin: 0.5rem 1rem 1.5rem; padding: 0.8rem; background: var(--bg-tertiary);
  border: 1px solid var(--border-bright); border-radius: 12px; color: var(--text-primary);
  display: flex; align-items: center; gap: 0.75rem; cursor: pointer; transition: all 0.2s;
  font-weight: 600; font-size: 0.9rem;
}
.btn-new-chat:hover { background: var(--accent); border-color: var(--accent); transform: translateY(-1px); }

.conv-list { flex: 1; overflow-y: auto; padding: 0 0.75rem; }
.conv-item {
  padding: 0.7rem 1rem; border-radius: 10px; display: flex; align-items: center; gap: 0.75rem;
  cursor: pointer; color: var(--text-secondary); margin-bottom: 0.3rem; position: relative;
  transition: all 0.2s;
}
.conv-item:hover, .conv-item.active { background: rgba(255,255,255,0.04); color: var(--text-primary); }
.conv-item.active { box-shadow: inset 0 0 0 1px var(--border-bright); }
.conv-item.active::before { content: ''; position: absolute; left: 0; top: 25%; bottom: 25%; width: 3px; background: var(--accent); border-radius: 0 4px 4px 0; }

.conv-title { font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }
.btn-delete-conv { opacity: 0; background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 2px; }
.conv-item:hover .btn-delete-conv { opacity: 1; }
.btn-delete-conv:hover { color: #f44336; }

.sidebar-user {
  margin: 1rem; padding: 0.75rem; background: rgba(255,255,255,0.03); border-radius: 12px;
  display: flex; align-items: center; gap: 0.75rem;
}
.user-avatar { width: 32px; height: 32px; border-radius: 50%; background: var(--accent-dim); display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 0.8rem; }
.user-info { line-height: 1.2; }
.user-name { font-size: 0.85rem; font-weight: 600; }
.user-role { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; }

.sidebar-footer { padding: 0.75rem; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 0.25rem; }
.footer-link {
  display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem 0.75rem;
  color: var(--text-secondary); text-decoration: none; border-radius: 8px; font-size: 0.85rem; transition: all 0.2s;
}
.footer-link:hover { background: rgba(255,255,255,0.05); color: var(--text-primary); }

/* ── Main Chat ── */
.chat-main { flex: 1; display: flex; flex-direction: column; position: relative; background: var(--bg-primary); }

.chat-header {
  height: 70px; padding: 0 2rem; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
  background: var(--glass-bg); backdrop-filter: var(--glass-blur);
}
.header-left { display: flex; flex-direction: column; gap: 2px; }
.chat-title { font-size: 1rem; font-weight: 700; }
.status-badge { font-size: 0.65rem; color: #4caf50; display: flex; align-items: center; gap: 6px; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px; }
.dot { width: 6px; height: 6px; background: currentColor; border-radius: 50%; }
.dot.pulse { animation: status-pulse 2s infinite; }
@keyframes status-pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

.messages-container { flex: 1; padding: 2rem; overflow-y: auto; display: flex; flex-direction: column; gap: 2rem; }

/* ── Welcome Screen ── */
.welcome-container { flex: 1; display: flex; align-items: center; justify-content: center; position: relative; }
.welcome-glow { position: absolute; width: 300px; height: 300px; background: var(--accent); filter: blur(120px); opacity: 0.1; }
.welcome-card { text-align: center; z-index: 1; max-width: 600px; }
.huge-logo { font-size: 4rem; font-weight: 900; color: var(--accent); margin-bottom: 1rem; }
.welcome-card h1 { font-size: 2.5rem; font-weight: 800; margin-bottom: 0.5rem; letter-spacing: -1px; }
.welcome-subtitle { color: var(--text-secondary); margin-bottom: 3rem; }
.suggestion-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
.suggest-item {
  background: var(--bg-secondary); border: 1px solid var(--border); padding: 1.5rem 1rem;
  border-radius: 16px; cursor: pointer; transition: all 0.2s;
}
.suggest-item:hover { border-color: var(--accent); transform: translateY(-4px); background: var(--bg-tertiary); }
.suggest-icon { font-size: 1.5rem; margin-bottom: 0.75rem; }
.suggest-text { font-size: 0.85rem; font-weight: 600; color: var(--text-secondary); }

/* ── Messages ── */
.msg-group { display: flex; flex-direction: column; max-width: 850px; width: 100%; margin: 0 auto; }
.msg-row { display: flex; gap: 1.25rem; }
.msg-avatar {
  width: 34px; height: 34px; border-radius: 8px; background: var(--bg-tertiary);
  display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;
  border: 1px solid var(--border); font-size: 0.9rem;
}
.ai-avatar { background: var(--accent) !important; color: white; border: none; box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3); }

.msg-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.msg-bubble { line-height: 1.6; font-size: 1rem; color: var(--text-primary); }

.msg-actions {
  display: flex; gap: 0.75rem; opacity: 0; transition: opacity 0.2s; padding-left: 0.5rem;
}
.msg-group:hover .msg-actions { opacity: 1; }
.msg-actions button {
  background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 4px; border-radius: 4px;
}
.msg-actions button:hover { background: rgba(255,255,255,0.05); color: var(--accent-light); }

/* ── Tools & Approval ── */
.tool-trace { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem; }
.tool-tag {
  font-size: 0.75rem; background: var(--bg-tertiary); padding: 4px 10px; border-radius: 6px;
  display: flex; align-items: center; gap: 6px; border: 1px solid var(--border); color: var(--text-secondary);
}
.tool-tag .dot { width: 6px; height: 6px; border-radius: 50%; }
.tool-tag .dot.running { background: #ffb300; box-shadow: 0 0 8px #ffb300; }
.tool-tag .dot.done { background: #4caf50; }

.approval-box {
  margin-top: 1.5rem; background: rgba(99, 102, 241, 0.05); border: 1px solid var(--accent);
  border-radius: 12px; padding: 1.25rem;
}
.approval-header { display: flex; align-items: center; gap: 0.5rem; font-size: 0.7rem; font-weight: 900; color: var(--accent); margin-bottom: 0.75rem; letter-spacing: 1px; }
.approval-box code { display: block; background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 6px; margin: 0.75rem 0; font-family: monospace; font-size: 0.9rem; }
.approval-btns { display: flex; gap: 0.75rem; }
.approval-btns button { flex: 1; padding: 0.6rem; border-radius: 8px; border: none; font-weight: 700; cursor: pointer; transition: all 0.2s; }
.btn-approve { background: #4caf50; color: white; }
.btn-deny { background: rgba(244, 67, 54, 0.1); color: #f44336; border: 1px solid rgba(244, 67, 54, 0.2) !important; }
.btn-approve:hover { filter: brightness(1.1); transform: translateY(-1px); }

/* ── Streaming ── */
.typing-indicator { display: flex; gap: 4px; padding: 10px 0; }
.typing-indicator span { width: 6px; height: 6px; background: var(--text-muted); border-radius: 50%; animation: typing 1.4s infinite; }
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%, 100% { transform: translateY(0); opacity: 0.4; } 50% { transform: translateY(-4px); opacity: 1; } }

/* ── Input ── */
.input-section { padding: 0 2rem 2rem; }
.input-wrapper-outer { max-width: 850px; margin: 0 auto; display: flex; flex-direction: column; }
.input-toolbar { padding: 0 1rem 0.5rem; display: flex; justify-content: flex-end; }
.char-count { font-size: 0.7rem; color: var(--text-muted); }

.input-wrapper {
  background: var(--bg-secondary); border: 1px solid var(--border-bright); border-radius: 20px;
  padding: 0.6rem; display: flex; align-items: flex-end; gap: 0.5rem; box-shadow: var(--shadow-lg);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-wrapper:focus-within { border-color: var(--accent); box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1); }

.chat-textarea {
  flex: 1; background: transparent; border: none; color: var(--text-primary); padding: 0.6rem;
  resize: none; max-height: 200px; outline: none; font-size: 1rem; line-height: 1.5;
}
.circle-btn { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
.voice-trigger { color: var(--text-muted); background: transparent; border: none; cursor: pointer; }
.voice-trigger:hover { background: rgba(255,255,255,0.05); color: var(--accent); }

.btn-send-main {
  width: 40px; height: 40px; border-radius: 12px; background: var(--accent); color: white;
  border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.btn-send-main:disabled { background: var(--bg-tertiary); color: var(--text-muted); cursor: not-allowed; }
.btn-send-main:hover:not(:disabled) { background: var(--accent-light); transform: scale(1.05); }

.input-footer { text-align: center; font-size: 0.7rem; color: var(--text-muted); margin-top: 0.75rem; }

/* ── Markdown & Code ── */
.markdown-body :deep(pre) { background: #0d1117; padding: 1.25rem; border-radius: 12px; margin: 1.25rem 0; border: 1px solid var(--border); overflow-x: auto; }
.markdown-body :deep(code) { font-family: 'Fira Code', 'JetBrains Mono', monospace; font-size: 0.9em; color: var(--accent-light); }
.markdown-body :deep(p) { margin-bottom: 1rem; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }

.cursor-pipe { display: inline-block; width: 2px; height: 1em; background: var(--accent); margin-left: 2px; animation: blink 1s step-end infinite; vertical-align: middle; }
@keyframes blink { 50% { opacity: 0; } }

.animate-slide-up { animation: slideUp 0.5s cubic-bezier(0.2, 0.8, 0.2, 1); }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.animate-zoom-in { animation: zoomIn 0.3s ease-out; }
@keyframes zoomIn { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }

.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
