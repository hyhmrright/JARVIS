import { defineStore } from "pinia";
import client from "@/api/client";

interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done";
  result?: string;
}

interface Message {
  role: "human" | "ai";
  content: string;
  toolCalls?: ToolCall[];
}

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
    async selectConversation(convId: string) {
      this.currentConvId = convId;
      this.messages = [];
      try {
        const { data } = await client.get<Message[]>(`/conversations/${convId}/messages`);
        this.messages = data;
      } catch (err) {
        console.error("[chat] selectConversation failed", err);
        this.currentConvId = null;
      }
    },
    newConversation() {
      this.currentConvId = null;
      this.messages = [];
    },
    async deleteConversation(convId: string) {
      try {
        await client.delete(`/conversations/${convId}`);
        this.conversations = this.conversations.filter(c => c.id !== convId);
        if (this.currentConvId === convId) {
          this.currentConvId = null;
          this.messages = [];
        }
      } catch (err) {
        console.error("[chat] deleteConversation failed", err);
      }
    },
    async sendMessage(content: string) {
      if (!this.currentConvId) {
        const title = content.slice(0, 30) + (content.length > 30 ? "..." : "");
        const { data } = await client.post("/conversations", { title });
        this.conversations.unshift(data);
        this.currentConvId = data.id;
      }
      this.messages.push({ role: "human", content });
      this.streaming = true;
      this.messages.push({ role: "ai", content: "" });

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
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          // Keep the last (potentially incomplete) line in the buffer
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                // Access through reactive proxy via array index
                const aiMsg = this.messages[this.messages.length - 1];
                const eventType = data.type;
                if (eventType === "tool_start") {
                  if (!aiMsg.toolCalls) aiMsg.toolCalls = [];
                  aiMsg.toolCalls.push({
                    name: data.tool,
                    args: data.args ?? {},
                    status: "running",
                  });
                } else if (eventType === "tool_end") {
                  const tc = aiMsg.toolCalls?.find(
                    (t: ToolCall) => t.name === data.tool && t.status === "running",
                  );
                  if (tc) {
                    tc.status = "done";
                    tc.result = data.result_preview;
                  }
                } else {
                  // delta event (type === "delta" or legacy events without type)
                  if (data.delta) {
                    aiMsg.content += data.delta;
                  } else if (data.content) {
                    aiMsg.content = data.content;
                  }
                }
              } catch {
                // Skip unparseable SSE lines
              }
            }
          }
        }
      } catch (err) {
        // Remove the empty AI placeholder; keep the human message since it is
        // already persisted in the backend database.
        const aiMsg = this.messages[this.messages.length - 1];
        if (aiMsg?.role === "ai" && !aiMsg.content) {
          this.messages.pop();
        }
        throw err;
      } finally {
        this.streaming = false;
      }
    },
  },
});
