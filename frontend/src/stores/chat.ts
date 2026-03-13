import { defineStore } from "pinia";
import client from "@/api/client";
import { useAuthStore } from "@/stores/auth";

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
  pending_tool_call?: { name: string; args: any };
}

interface Conversation { id: string; title: string }

export const useChatStore = defineStore("chat", {
  state: () => ({
    conversations: [] as Conversation[],
    currentConvId: null as string | null,
    messages: [] as Message[],
    streaming: false,
    routingAgent: null as string | null,
    abortController: null as AbortController | null,
  }),
  actions: {
    async loadConversations() {
      const { data } = await client.get("/conversations");
      this.conversations = data;
    },
    async selectConversation(convId: string) {
      this.currentConvId = convId;
      this.messages = [];
      this.routingAgent = null;
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
      this.routingAgent = null;
    },
    async deleteConversation(convId: string) {
      try {
        await client.delete(`/conversations/${convId}`);
        this.conversations = this.conversations.filter(c => c.id !== convId);
        if (this.currentConvId === convId) {
          this.currentConvId = null;
          this.messages = [];
          this.routingAgent = null;
        }
      } catch (err) {
        console.error("[chat] deleteConversation failed", err);
      }
    },

    cancelStream() {
      if (this.abortController) {
        this.abortController.abort();
      }
    },

    async handleConsent(approved: boolean) {
      const lastAiMsg = this.messages[this.messages.length - 1];
      if (!lastAiMsg || !lastAiMsg.pending_tool_call) return;

      const callInfo = lastAiMsg.pending_tool_call;
      lastAiMsg.pending_tool_call = undefined;

      await this.sendMessage(`[CONSENT:${approved ? 'ALLOW' : 'DENY'}] ${callInfo.name}`);
    },

    async sendMessage(content: string) {
      if (!this.currentConvId) {
        const title = content.slice(0, 30) + (content.length > 30 ? "..." : "");
        const { data } = await client.post("/conversations", { title });
        this.conversations.unshift(data);
        this.currentConvId = data.id;
      }

      if (!content.startsWith("[CONSENT:")) {
        this.messages.push({ role: "human", content });
        this.messages.push({ role: "ai", content: "" });
      }

      this.streaming = true;

      try {
        const auth = useAuthStore();
        const token = auth.token;
        const controller = new AbortController();
        this.abortController = controller;
        const response = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ conversation_id: this.currentConvId, content }),
          signal: controller.signal,
        });

        if (!response.ok) {
          let errorDetail = `HTTP ${response.status}`;
          const errorText = await response.text().catch(() => "");
          if (errorText) {
            try {
              const parsed = JSON.parse(errorText);
              errorDetail = typeof parsed.detail === "string"
                ? parsed.detail
                : JSON.stringify(parsed.detail);
            } catch {
              errorDetail = errorText;
            }
          }
          throw new Error(errorDetail);
        }
        if (!response.body) throw new Error("No response body");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                const aiMsg = this.messages[this.messages.length - 1];

                if (data.type === "routing") {
                  this.routingAgent = data.agent;
                } else if (data.type === "title_updated") {
                  const conv = this.conversations.find(c => c.id === this.currentConvId);
                  if (conv && data.title) {
                    conv.title = data.title;
                  }
                } else if (data.type === "approval_required") {
                  aiMsg.pending_tool_call = { name: data.tool, args: data.args };
                  this.streaming = false;
                  this.routingAgent = null;
                  return;
                }

                if (data.type === "tool_start") {
                  if (!aiMsg.toolCalls) {
                    aiMsg.toolCalls = [];
                  }
                  aiMsg.toolCalls.push({
                    name: data.tool,
                    args: data.args ?? {},
                    status: "running",
                  });
                } else if (data.type === "tool_end") {
                  const toolCall = aiMsg.toolCalls?.find(
                    (t: ToolCall) => t.name === data.tool && t.status === "running"
                  );
                  if (toolCall) {
                    toolCall.status = "done";
                    toolCall.result = data.result_preview;
                  }
                } else if (data.delta) {
                  aiMsg.content += data.delta;
                } else if (data.content) {
                  aiMsg.content = data.content;
                }
              } catch {
                // Ignore SSE parse errors
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name === "AbortError") {
          // User intentionally cancelled — do not show error toast
          return;
        }
        const aiMsg = this.messages[this.messages.length - 1];
        if (aiMsg?.role === "ai") {
          aiMsg.content = `> **System Warning**: Failed to communicate with the model.\n> \`${err.message}\`\n\nPlease check your configuration in **Settings** (e.g., ensure API keys are correctly filled) and try again.`;
        }
        console.error("[chat] streaming error:", err);
      } finally {
        this.abortController = null;
        this.streaming = false;
        this.routingAgent = null;
      }
    },
  },
});
