<template>
  <div class="chat-layout">
    <aside class="sidebar">
      <button @click="chat.newConversation()">{{ $t('chat.newConversation') }}</button>
      <ul>
        <li v-for="conv in chat.conversations" :key="conv.id"
            :class="{ active: conv.id === chat.currentConvId }"
            @click="chat.currentConvId = conv.id">
          {{ conv.title }}
        </li>
      </ul>
      <div class="sidebar-footer">
        <router-link to="/documents">{{ $t('chat.documents') }}</router-link>
        <router-link to="/settings">{{ $t('chat.settings') }}</router-link>
        <button @click="auth.logout(); router.push('/login')">{{ $t('chat.logout') }}</button>
      </div>
    </aside>

    <main class="chat-main">
      <div class="messages" ref="messagesEl">
        <div v-for="(msg, i) in chat.messages" :key="i" :class="['message', msg.role]">
          <p>{{ msg.content }}</p>
        </div>
      </div>
      <div class="input-area">
        <button class="voice-btn" disabled :title="$t('chat.voiceComingSoon')">🎤</button>
        <textarea v-model="input" @keydown.enter.exact.prevent="send"
                  :placeholder="$t('chat.inputPlaceholder')" :disabled="chat.streaming" />
        <button @click="send" :disabled="chat.streaming || !input.trim()">{{ $t('chat.send') }}</button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from "vue";
import { useRouter } from "vue-router";
import { useChatStore } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";

const chat = useChatStore();
const auth = useAuthStore();
const router = useRouter();
const input = ref("");
const messagesEl = ref<HTMLElement>();

onMounted(() => chat.loadConversations());

watch(() => chat.messages.length, async () => {
  await nextTick();
  messagesEl.value?.scrollTo(0, messagesEl.value.scrollHeight);
});

async function send() {
  if (!input.value.trim() || chat.streaming) return;
  const msg = input.value;
  input.value = "";
  if (!chat.currentConvId) await chat.newConversation();
  await chat.sendMessage(msg);
}
</script>
