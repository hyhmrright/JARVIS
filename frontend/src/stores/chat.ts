import { defineStore } from "pinia";
import client from "@/api/client";

interface Message { role: "human" | "ai"; content: string }
interface Conversation { id: string; title: string }

export const useChatStore = defineStore("chat", {
  state: () => ({
    conversations: [] as Conversation[],
    currentConvId: null as string | null,
    messages: [] as Message[],
    streaming: false,
  }),
  actions: {
    async loadConversations() {
      const { data } = await client.get("/conversations");
      this.conversations = data;
    },
    async newConversation() {
      const { data } = await client.post("/conversations", { title: "New Chat" });
      this.conversations.unshift(data);
      this.currentConvId = data.id;
      this.messages = [];
    },
    async sendMessage(content: string) {
      if (!this.currentConvId) return;
      this.messages.push({ role: "human", content });
      this.streaming = true;
      const aiMsg: Message = { role: "ai", content: "" };
      this.messages.push(aiMsg);

      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ conversation_id: this.currentConvId, content }),
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        if (!resp.body) throw new Error("No response body");

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value);
          for (const line of text.split("\n")) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                aiMsg.content = data.content;
              } catch {
                // 跳过无法解析的 SSE 行
              }
            }
          }
        }
      } finally {
        this.streaming = false;
      }
    },
  },
});
