<template>
  <div class="chat-layout">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-icon">&#10022;</span>
        <span class="brand-text">JARVIS</span>
      </div>
      <button class="new-chat-btn" @click="chat.newConversation()">
        <span class="plus-icon">+</span>
        {{ $t("chat.newConversation") }}
      </button>
      <ul class="conv-list">
        <li
          v-for="conv in chat.conversations"
          :key="conv.id"
          :class="['conv-item', { active: conv.id === chat.currentConvId }]"
          @click="chat.selectConversation(conv.id)"
        >
          <span class="conv-title">{{ conv.title }}</span>
          <button
            class="conv-delete"
            :title="$t('chat.deleteConfirm')"
            @click.stop="confirmDelete(conv.id)"
          >
            &times;
          </button>
        </li>
      </ul>
      <div class="sidebar-footer">
        <router-link to="/documents" class="footer-link">
          <span class="footer-icon">&#9635;</span>
          {{ $t("chat.documents") }}
        </router-link>
        <router-link to="/settings" class="footer-link">
          <span class="footer-icon">&#9881;</span>
          {{ $t("chat.settings") }}
        </router-link>
        <button class="footer-link logout-btn" @click="auth.logout(); router.push('/login')">
          <span class="footer-icon">&#10140;</span>
          {{ $t("chat.logout") }}
        </button>
      </div>
    </aside>

    <main class="chat-main">
      <div v-if="chat.messages.length === 0" class="empty-state">
        <span class="empty-icon">&#10022;</span>
        <h2>JARVIS</h2>
        <p>{{ $t("chat.inputPlaceholder") }}</p>
      </div>

      <div v-else ref="messagesEl" class="messages">
        <div
          v-for="(msg, i) in chat.messages"
          :key="i"
          :class="['message', msg.role]"
        >
          <div class="msg-avatar">
            <span v-if="msg.role === 'ai'" class="avatar-ai">&#10022;</span>
            <span v-else class="avatar-user">U</span>
          </div>
          <div class="msg-bubble">
            <p>{{ msg.content }}</p>
            <div v-if="msg.toolCalls?.length" class="tool-calls">
              <div v-for="(tc, ti) in msg.toolCalls" :key="ti" class="tool-call-card">
                <span class="tool-icon">&#9881;</span>
                <span class="tool-name">{{ tc.name }}</span>
                <span v-if="tc.status === 'running'" class="tool-status running">{{ $t('chat.toolRunning') }}</span>
                <span v-else class="tool-status done">&#10003;</span>
                <details v-if="tc.result" class="tool-result">
                  <summary>{{ $t('chat.toolResult') }}</summary>
                  <pre>{{ tc.result }}</pre>
                </details>
              </div>
            </div>
            <button
              v-if="!(chat.streaming && i === chat.messages.length - 1)"
              class="copy-btn"
              :title="$t('chat.copy')"
              @click="copyMessage(msg.content, i)"
            >
              <span v-if="copiedIndex === i">✓</span>
              <span v-else>⧉</span>
            </button>
          </div>
        </div>
        <div v-if="chat.streaming" class="streaming-indicator">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      </div>

      <div class="input-area">
        <div class="input-wrapper">
          <button class="voice-btn" disabled :title="$t('chat.voiceComingSoon')">
            <span>&#9834;</span>
          </button>
          <textarea
            v-model="input"
            :placeholder="$t('chat.inputPlaceholder')"
            :disabled="chat.streaming"
            rows="1"
            @keydown.enter.exact.prevent="send"
          />
          <button
            class="send-btn"
            :disabled="chat.streaming || !input.trim()"
            @click="send"
          >
            <span>&#10148;</span>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useChatStore } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";

const { t } = useI18n();
const chat = useChatStore();
const auth = useAuthStore();
const router = useRouter();
const input = ref("");
const messagesEl = ref<HTMLElement>();
const copiedIndex = ref<number | null>(null);

async function copyMessage(content: string, index: number): Promise<void> {
  try {
    await navigator.clipboard.writeText(content);
    copiedIndex.value = index;
    setTimeout(() => {
      copiedIndex.value = null;
    }, 1500);
  } catch {
    // Clipboard API unavailable (non-secure context or permission denied)
  }
}

onMounted(() => chat.loadConversations());

let scrollThrottleId: ReturnType<typeof setTimeout> | null = null;

watch(
  () => [chat.messages.length, chat.messages[chat.messages.length - 1]?.content] as const,
  () => {
    if (scrollThrottleId) return;
    scrollThrottleId = setTimeout(async () => {
      scrollThrottleId = null;
      await nextTick();
      messagesEl.value?.scrollTo(0, messagesEl.value.scrollHeight);
    }, 16);
  },
);

async function send(): Promise<void> {
  const text = input.value.trim();
  if (!text || chat.streaming) return;
  try {
    input.value = "";
    await chat.sendMessage(text);
  } catch {
    // Restore input on send failure so the user can retry
    input.value = text;
  }
}

async function confirmDelete(convId: string): Promise<void> {
  if (confirm(t("chat.deleteConfirm"))) {
    await chat.deleteConversation(convId);
  }
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ── Sidebar ── */
.sidebar {
  width: 260px;
  min-width: 260px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: var(--space-md);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-sm) var(--space-lg);
}

.sidebar-brand .brand-icon {
  font-size: 22px;
  color: var(--accent);
  filter: drop-shadow(0 0 8px var(--accent-a40));
}

.sidebar-brand .brand-text {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--text-primary);
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px var(--space-md);
  background: transparent;
  border: 1px solid var(--border-glow);
  border-radius: var(--radius-md);
  color: var(--accent);
  font-size: 14px;
  font-weight: 500;
  margin-bottom: var(--space-md);
  transition:
    background 0.3s ease,
    border-color 0.3s ease;
}

.new-chat-btn:hover {
  background: var(--accent-a08);
  border-color: var(--accent);
}

.plus-icon {
  font-size: 18px;
  line-height: 1;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    background 0.2s ease,
    border-left 0.2s ease;
  border-left: 3px solid transparent;
  position: relative;
}

.conv-item:hover {
  background: var(--bg-elevated);
}

.conv-item.active {
  background: var(--accent-a06);
  border-left-color: var(--accent);
}

.conv-title {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.conv-delete {
  display: none;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 16px;
  padding: 0 4px;
  cursor: pointer;
  flex-shrink: 0;
  line-height: 1;
  border-radius: var(--radius-sm);
  transition: color 0.2s ease, background 0.2s ease;
}

.conv-item:hover .conv-delete {
  display: block;
}

.conv-delete:hover {
  color: var(--danger);
  background: var(--danger-a10);
}

.conv-item.active .conv-title {
  color: var(--text-primary);
}

.sidebar-footer {
  border-top: 1px solid var(--border);
  padding-top: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.footer-link {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 14px;
  transition:
    background 0.2s ease,
    color 0.2s ease;
  background: transparent;
  width: 100%;
  text-align: left;
}

.footer-link:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.footer-icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

.logout-btn {
  cursor: pointer;
}

/* ── Main Chat Area ── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  opacity: 0.4;
}

.empty-icon {
  font-size: 64px;
  color: var(--accent);
  filter: drop-shadow(0 0 24px var(--accent-a30));
}

.empty-state h2 {
  font-family: var(--font-heading);
  font-size: 24px;
  letter-spacing: 6px;
  color: var(--text-primary);
}

.empty-state p {
  color: var(--text-muted);
  font-size: 15px;
}

/* ── Messages ── */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-xl) var(--space-xl) 100px;
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.message {
  display: flex;
  gap: var(--space-md);
  max-width: 800px;
  animation: fadeIn 0.3s ease;
}

.message.human {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.ai {
  align-self: flex-start;
}

.msg-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.avatar-ai {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--accent), var(--accent-dim));
  color: var(--bg-primary);
  font-size: 16px;
}

.avatar-user {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--white-a08);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.msg-bubble {
  position: relative;
  padding: 12px 16px 36px;
  border-radius: var(--radius-lg);
  line-height: 1.6;
  font-size: 15px;
}

.message.human .msg-bubble {
  background: linear-gradient(135deg, var(--accent-a15), var(--accent-a08));
  border: 1px solid var(--accent-a12);
  color: var(--text-primary);
}

.message.ai .msg-bubble {
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
  color: var(--text-primary);
}

.msg-bubble p {
  white-space: pre-wrap;
  word-break: break-word;
}

.copy-btn {
  display: none;
  position: absolute;
  bottom: 6px;
  right: 8px;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 13px;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.2s ease, background 0.2s ease, border-color 0.2s ease;
  padding: 0;
}

.copy-btn:hover {
  color: var(--accent);
  background: var(--accent-a08);
  border-color: var(--accent-a30);
}

.msg-bubble:hover .copy-btn {
  display: flex;
}

/* ── Streaming Indicator ── */
.streaming-indicator {
  display: flex;
  gap: 6px;
  padding: 0 var(--space-xl);
  padding-left: 52px;
}

.streaming-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse-glow 1.4s infinite;
}

.streaming-indicator .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.streaming-indicator .dot:nth-child(3) {
  animation-delay: 0.4s;
}

/* ── Input Area ── */
.input-area {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: var(--space-md) var(--space-xl) var(--space-lg);
  background: linear-gradient(to top, var(--bg-primary) 60%, transparent);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: var(--space-sm);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-sm);
  transition: border-color 0.3s ease;
  max-width: 800px;
  margin: 0 auto;
}

.input-wrapper:focus-within {
  border-color: var(--accent-dim);
  box-shadow: 0 0 0 3px var(--accent-a06);
}

.input-wrapper textarea {
  flex: 1;
  background: transparent;
  border: none;
  padding: 8px;
  min-height: 24px;
  max-height: 120px;
  resize: none;
  font-size: 15px;
  line-height: 1.5;
}

.input-wrapper textarea:focus {
  box-shadow: none;
}

.voice-btn,
.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
}

.voice-btn {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.send-btn {
  background: linear-gradient(135deg, var(--accent), var(--accent-dim));
  color: var(--bg-primary);
}

.send-btn:hover:not(:disabled) {
  box-shadow: var(--shadow-glow);
  transform: scale(1.05);
}

.send-btn:disabled {
  background: var(--white-a06);
  color: var(--text-muted);
}

/* ── Reduced Motion ── */
@media (prefers-reduced-motion: reduce) {
  .message {
    animation: none;
  }

  .streaming-indicator .dot {
    animation: none;
    opacity: 0.6;
  }
}

/* ── Tool Calls ── */
.tool-calls {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 8px 0 4px;
}

.tool-call-card {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 6px 10px;
  background: var(--white-a04);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-secondary);
}

.tool-icon {
  font-size: 14px;
  color: var(--accent);
}

.tool-name {
  font-family: var(--font-mono, monospace);
  font-weight: 500;
}

.tool-status.running {
  color: var(--accent);
  font-size: 12px;
}

.tool-status.done {
  color: var(--success, #4caf50);
  font-size: 14px;
}

.tool-result {
  width: 100%;
  margin-top: 4px;
}

.tool-result summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--text-muted);
}

.tool-result pre {
  margin-top: 4px;
  padding: 8px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .sidebar {
    width: 200px;
    min-width: 200px;
  }
}
</style>
