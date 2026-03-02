<template>
  <div class="chat-layout">
    <!-- Gradient Background -->
    <div class="bg-glow"></div>

    <aside :class="['sidebar', { 'sidebar--collapsed': sidebarCollapsed }]">
      <div class="sidebar-brand">
        <div class="brand-logo">J</div>
        <span v-if="!sidebarCollapsed" class="brand-name">JARVIS</span>
        <button class="btn-toggle-sidebar" @click="sidebarCollapsed = !sidebarCollapsed">
          {{ sidebarCollapsed ? '→' : '←' }}
        </button>
      </div>

      <button class="btn-new-chat" @click="chat.newConversation">
        <span class="plus-icon">+</span>
        <span v-if="!sidebarCollapsed">{{ $t("chat.newConversation") }}</span>
      </button>

      <nav class="conv-list custom-scrollbar">
        <div
          v-for="c in chat.conversations"
          :key="c.id"
          :class="['conv-item', { active: chat.currentConvId === c.id }]"
          @click="chat.selectConversation(c.id)"
        >
          <span class="conv-icon">💬</span>
          <span v-if="!sidebarCollapsed" class="conv-title">{{ c.title }}</span>
          <button
            v-if="!sidebarCollapsed"
            class="btn-delete-conv"
            @click.stop="chat.deleteConversation(c.id)"
          >
            ×
          </button>
        </div>
      </nav>

      <footer class="sidebar-footer">
        <router-link to="/proactive" class="footer-link" :title="$t('proactive.title')">
          <span class="footer-icon">⚡</span>
          <span v-if="!sidebarCollapsed">{{ $t("proactive.title") }}</span>
        </router-link>
        <router-link to="/settings" class="footer-link" :title="$t('chat.settings')">
          <span class="footer-icon">⚙️</span>
          <span v-if="!sidebarCollapsed">{{ $t("chat.settings") }}</span>
        </router-link>
        <button class="footer-link logout-btn" @click="handleLogout" :title="$t('chat.logout')">
          <span class="footer-icon">🚪</span>
          <span v-if="!sidebarCollapsed">{{ $t("chat.logout") }}</span>
        </button>
      </footer>
    </aside>

    <main class="chat-main">
      <header class="chat-header">
        <div class="header-info">
          <h2>{{ currentConvTitle }}</h2>
          <span class="status-indicator">Online</span>
        </div>
      </header>

      <div ref="messagesEl" class="messages-container custom-scrollbar">
        <div v-if="chat.messages.length === 0" class="welcome-screen">
          <div class="welcome-content">
            <h1>Hello, {{ auth.displayName || 'Friend' }}</h1>
            <p>How can I assist you today?</p>
            <div class="quick-actions">
              <button @click="input = 'Show me a demo of Live Canvas'">🎨 Live Canvas Demo</button>
              <button @click="input = 'What proactive tasks are running?'">⚡ Active Monitors</button>
            </div>
          </div>
        </div>

        <div
          v-for="(msg, idx) in chat.messages"
          :key="idx"
          :class="['msg-row', msg.role]"
        >
          <div class="msg-avatar">
            <span v-if="msg.role === 'ai'">J</span>
            <span v-else>{{ auth.displayName?.[0] || 'U' }}</span>
          </div>
          <div class="msg-content-wrapper">
            <div class="msg-bubble">
              <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
              
              <!-- HITL Approval -->
              <div v-if="msg.pending_tool_call" class="approval-card">
                <div class="approval-header">
                  <span>Security Check</span>
                  <span class="shield-icon">🛡️</span>
                </div>
                <p>AI is requesting to execute:</p>
                <code>{{ msg.pending_tool_call.name }}</code>
                <div class="approval-actions">
                  <button class="btn-approve" @click="chat.handleConsent(true)">Allow</button>
                  <button class="btn-deny" @click="chat.handleConsent(false)">Deny</button>
                </div>
              </div>

              <!-- Tool Calls -->
              <div v-if="msg.toolCalls?.length" class="tool-section">
                <div v-for="tc in msg.toolCalls" :key="tc.name" class="tool-pill">
                  <span :class="['status-dot', tc.status]"></span>
                  <span class="tool-name">{{ tc.name }}</span>
                </div>
              </div>
            </div>
            <LiveCanvas v-if="msg.role === 'ai' && hasHtml(msg.content)" :content="msg.content" />
          </div>
        </div>
        <div v-if="chat.streaming" class="msg-row ai">
          <div class="msg-avatar typing">...</div>
        </div>
      </div>

      <div class="input-container">
        <div class="input-wrapper">
          <button class="btn-voice" @click="voiceOverlay?.start()">
            🎤
          </button>
          <textarea
            v-model="input"
            class="chat-input"
            :placeholder="$t('chat.inputPlaceholder')"
            @keydown.enter.prevent="handleSend"
          ></textarea>
          <button
            class="btn-send"
            :disabled="!input.trim() || chat.streaming"
            @click="handleSend"
          >
            <span>↑</span>
          </button>
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
  if (!text) return '<span class="cursor">|</span>';
  return marked.parse(text);
};

const hasHtml = (text: string) => /<html>[\s\S]*?<\/html>/.test(text);

const currentConvTitle = computed(() => {
  const c = chat.conversations.find((conv) => conv.id === chat.currentConvId);
  return c ? c.title : t("chat.newConversation");
});

const handleSend = async () => {
  if (!input.value.trim() || chat.streaming) return;
  const msg = input.value;
  input.value = "";
  await chat.sendMessage(msg);
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
watch(() => chat.streaming, (isStreaming) => {
  if (isStreaming) scrollToBottom();
});

onMounted(async () => {
  await chat.loadConversations();
});
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: var(--bg-primary);
  position: relative;
  overflow: hidden;
}

.bg-glow {
  position: absolute;
  top: -10%;
  left: -10%;
  width: 40%;
  height: 40%;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
  filter: blur(60px);
  pointer-events: none;
}

/* ── Sidebar ── */
.sidebar {
  width: 280px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 100;
  backdrop-filter: var(--glass-blur);
}

.sidebar--collapsed {
  width: 80px;
}

.sidebar-brand {
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.brand-logo {
  width: 32px;
  height: 32px;
  background: var(--accent);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 1.2rem;
}

.brand-name {
  font-weight: 700;
  letter-spacing: 1px;
}

.btn-toggle-sidebar {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
}

.btn-new-chat {
  margin: 0 1rem 1rem;
  padding: 0.75rem;
  background: var(--border);
  border: 1px solid var(--border-bright);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-new-chat:hover {
  background: var(--bg-tertiary);
  border-color: var(--accent);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 0.5rem;
}

.conv-item {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
  position: relative;
}

.conv-item:hover, .conv-item.active {
  background: rgba(255,255,255,0.05);
  color: var(--text-primary);
}

.conv-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  bottom: 20%;
  width: 3px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}

.conv-title {
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-footer {
  padding: 1rem;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.footer-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
}

.footer-link:hover {
  background: rgba(255,255,255,0.05);
  color: var(--text-primary);
}

/* ── Main Chat ── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

.chat-header {
  padding: 1rem 2rem;
  border-bottom: 1px solid var(--border);
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
}

.header-info h2 {
  font-size: 1.1rem;
  font-weight: 600;
}

.status-indicator {
  font-size: 0.7rem;
  color: #4caf50;
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-indicator::before {
  content: '';
  width: 6px;
  height: 6px;
  background: currentColor;
  border-radius: 50%;
}

.messages-container {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
}

.welcome-screen {
  height: 80%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.welcome-content h1 {
  font-size: 3rem;
  margin-bottom: 1rem;
  background: linear-gradient(to right, var(--text-primary), var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.quick-actions {
  display: flex;
  gap: 1rem;
  margin-top: 2rem;
  justify-content: center;
}

.quick-actions button {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  padding: 0.75rem 1.5rem;
  border-radius: var(--radius-full);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s;
}

.quick-actions button:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}

/* ── Messages ── */
.msg-row {
  display: flex;
  gap: 1.5rem;
  margin-bottom: 2.5rem;
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
  border: 1px solid var(--border);
}

.ai .msg-avatar {
  background: var(--accent);
  color: white;
}

.msg-content-wrapper {
  flex: 1;
  min-width: 0;
}

.msg-bubble {
  font-size: 1rem;
  color: var(--text-primary);
  line-height: 1.6;
}

/* Markdown Styling */
.markdown-body :deep(pre) {
  background: #0d1117;
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
  overflow-x: auto;
  border: 1px solid var(--border);
}

.markdown-body :deep(code) {
  font-family: 'Fira Code', monospace;
  font-size: 0.9em;
}

/* ── Approval Card ── */
.approval-card {
  margin-top: 1rem;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid var(--accent);
  border-radius: var(--radius-md);
  padding: 1rem;
}

.approval-header {
  display: flex;
  justify-content: space-between;
  font-weight: bold;
  color: var(--accent);
  margin-bottom: 0.5rem;
}

.approval-actions {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.approval-actions button {
  flex: 1;
  padding: 0.5rem;
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  font-weight: 600;
}

.btn-approve { background: #4caf50; color: white; }
.btn-deny { background: #f44336; color: white; }

/* ── Input Area ── */
.input-container {
  padding: 1.5rem 2rem 2rem;
}

.input-wrapper {
  max-width: 900px;
  margin: 0 auto;
  background: var(--bg-secondary);
  border: 1px solid var(--border-bright);
  border-radius: var(--radius-lg);
  padding: 0.5rem;
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  box-shadow: var(--shadow-lg);
}

.chat-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-primary);
  padding: 0.75rem;
  resize: none;
  max-height: 200px;
  outline: none;
  font-size: 1rem;
  font-family: inherit;
}

.btn-voice, .btn-send {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.btn-send {
  background: var(--accent);
  color: white;
}

.btn-send:disabled {
  background: var(--bg-tertiary);
  color: var(--text-muted);
  cursor: not-allowed;
}

.btn-send:hover:not(:disabled) {
  background: var(--accent-light);
  transform: scale(1.05);
}

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
</style>
