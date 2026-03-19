import { defineStore } from "pinia";
import client from "@/api/client";
import { pinConversation, patchConversation, deleteMessage } from "@/api";
import { useAuthStore } from "@/stores/auth";

interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done";
  result?: string;
}

interface Message {
  id?: string;
  parent_id?: string;
  role: "human" | "ai" | "tool";
  content: string;
  image_urls?: string[];
  toolCalls?: ToolCall[];
  tool_calls?: Array<{ name: string; id?: string; args?: Record<string, unknown> }> | null;
  pending_tool_call?: { name: string; args: Record<string, unknown>; pending_since: number };
  model_name?: string | null;
  model_provider?: string | null;
  tokens_input?: number | null;
  tokens_output?: number | null;
  created_at?: string | null;
  is_bookmarked?: boolean;
}

interface Conversation { id: string; title: string; active_leaf_id?: string | null; is_pinned: boolean; updated_at?: string }

function applyModelMeta(msg: Message, data: Record<string, unknown>) {
  if (msg.role !== "ai") return;
  if (data.model) msg.model_name = data.model as string;
  if (data.provider) msg.model_provider = data.provider as string;
  if (data.input_tokens != null) msg.tokens_input = data.input_tokens as number;
  if (data.output_tokens != null) msg.tokens_output = data.output_tokens as number;
}

export const useChatStore = defineStore("chat", {
  state: () => ({
    conversations: [] as Conversation[],
    currentConvId: null as string | null,
    messages: [] as Message[],
    streaming: false,
    routingAgent: null as string | null,
    abortController: null as AbortController | null,
    activeLeafId: null as string | null,
    _switchLeafController: null as AbortController | null,
  }),
  getters: {
    activeMessages: (state) => {
      if (!state.messages.length) return [];
      const msgDict = new Map<string, Message>();
      const latestMsg = state.messages[state.messages.length - 1];
      
      for (const msg of state.messages) {
        if (msg.id) msgDict.set(msg.id, msg);
      }
      
      let currentId = state.activeLeafId || latestMsg.id;
      if (!currentId || !msgDict.has(currentId)) {
        return state.messages; // fallback for unpersisted messages
      }
      
      const thread = [];
      let depth = 0;
      while (currentId && msgDict.has(currentId) && depth < 500) {
        const m: Message = msgDict.get(currentId)!;
        thread.unshift(m);
        currentId = m.parent_id;
        depth++;
      }
      return thread;
    },
    getSiblings: (state) => (msg: Message) => {
      if (!msg.id) return [];
      return state.messages.filter(m => m.parent_id === msg.parent_id);
    }
  },
  actions: {
    switchBranch(messageId: string) {
      this.activeLeafId = messageId;
      if (!this.currentConvId) return;
      // Cancel any in-flight persist from a previous rapid switch
      this._switchLeafController?.abort();
      const controller = new AbortController();
      this._switchLeafController = controller;
      client
        .patch(
          `/conversations/${this.currentConvId}/active-leaf`,
          { active_leaf_id: messageId },
          { signal: controller.signal },
        )
        .catch((err) => {
          if (err.name !== "CanceledError" && err.code !== "ERR_CANCELED") {
            console.error("[chat] switchBranch persist failed", err);
          }
        })
        .finally(() => {
          if (this._switchLeafController === controller) {
            this._switchLeafController = null;
          }
        });
    },

    async loadConversations() {
      const { data } = await client.get("/conversations");
      this.conversations = data;
    },
    async _reloadMessages(convId: string): Promise<void> {
      const { data } = await client.get<Message[]>(`/conversations/${convId}/messages`);
      this.messages = data;
    },
    async selectConversation(convId: string) {
      this.currentConvId = convId;
      this.messages = [];
      this.routingAgent = null;
      // Restore the persisted active branch if available
      const conv = this.conversations.find((c) => c.id === convId);
      this.activeLeafId = conv?.active_leaf_id ?? null;
      try {
        await this._reloadMessages(convId);
      } catch (err) {
        console.error("[chat] selectConversation failed", err);
        this.currentConvId = null;
      }
    },
    newConversation() {
      this.currentConvId = null;
      this.messages = [];
      this.routingAgent = null;
      this.activeLeafId = null;
    },
    async deleteConversation(convId: string) {
      try {
        await client.delete(`/conversations/${convId}`);
        this.conversations = this.conversations.filter(c => c.id !== convId);
        if (this.currentConvId === convId) {
          this.currentConvId = null;
          this.messages = [];
          this.routingAgent = null;
          this.activeLeafId = null;
        }
      } catch (err) {
        console.error("[chat] deleteConversation failed", err);
      }
    },
    async removeMessage(msgId: string): Promise<void> {
      if (!this.currentConvId) return;
      const prev = [...this.messages];
      this.messages = this.messages.filter((m) => m.id !== msgId);
      if (this.activeLeafId === msgId) this.activeLeafId = null;
      try {
        await deleteMessage(this.currentConvId, msgId);
        // Reload to fix any broken ancestor chains in the message tree
        await this._reloadMessages(this.currentConvId);
      } catch {
        this.messages = prev;
        throw new Error("Failed to delete message");
      }
    },
    async togglePinConversation(convId: string) {
      const conv = this.conversations.find((c) => c.id === convId);
      if (!conv) return;
      const prev = conv.is_pinned;
      try {
        await pinConversation(convId);
        conv.is_pinned = !prev;
        this.conversations.sort(
          (a, b) =>
            Number(b.is_pinned) - Number(a.is_pinned) ||
            new Date(b.updated_at ?? 0).getTime() - new Date(a.updated_at ?? 0).getTime(),
        );
      } catch (err) {
        conv.is_pinned = prev;
        throw err;
      }
    },


    async toggleBookmark(msgId: string): Promise<boolean | undefined> {
      if (!this.currentConvId) return;
      const msg = this.messages.find((m) => m.id === msgId);
      if (!msg) return;
      const prev = msg.is_bookmarked;
      msg.is_bookmarked = !prev;
      try {
        const { data } = await client.patch<{ is_bookmarked: boolean }>(
          `/conversations/${this.currentConvId}/messages/${msgId}/bookmark`,
        );
        msg.is_bookmarked = data.is_bookmarked;
        return data.is_bookmarked;
      } catch (err) {
        msg.is_bookmarked = prev;
        throw err;
      }
    },

    async renameConversation(convId: string, title: string) {
      const conv = this.conversations.find((c) => c.id === convId);
      if (!conv) return;
      const prev = conv.title;
      conv.title = title;
      try {
        await patchConversation(convId, { title });
      } catch (err) {
        conv.title = prev;
        throw err;
      }
    },

    async regenerate(messageId: string) {
      if (!this.currentConvId || !messageId) return;
      this.streaming = true;
      try {
        const auth = useAuthStore();
        const response = await fetch("/api/chat/regenerate", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
          body: JSON.stringify({ conversation_id: this.currentConvId, message_id: messageId })
        });
        if (!response.ok) throw new Error("Regenerate failed");
        
        // We push a temporary empty AI message that will be populated by the stream
        const activeThread = this.activeMessages;
        const msg = activeThread.find(m => m.id === messageId);
        if (msg) {
            this.messages.push({ role: "ai", content: "", parent_id: msg.parent_id });
            this.activeLeafId = null; // Will attach to latest in UI
        }
        
        const reader = response.body!.getReader();
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
                if (data.type === "done") {
                  if (aiMsg?.role === "ai" && !aiMsg.id && data.ai_msg_id) {
                    aiMsg.id = data.ai_msg_id;
                    aiMsg.parent_id = data.human_msg_id ?? aiMsg.parent_id;
                  }
                  if (aiMsg) applyModelMeta(aiMsg, data);
                  this.activeLeafId = data.ai_msg_id ?? null;
                } else if (data.delta) {
                  aiMsg.content += data.delta;
                } else if (data.content) {
                  aiMsg.content = data.content;
                }
              } catch { /* empty */ }
            }
          }
        }
      } catch (err) {
        console.error(err);
      } finally {
        this.streaming = false;
      }
    },
    cancelStream() {
      if (this.abortController) {
        this.abortController.abort();
      }
    },

    async handleConsent(approved: boolean) {
      const pendingMsg = this.messages.find((m) => m.pending_tool_call);
      if (!pendingMsg) return;

      const callInfo = pendingMsg.pending_tool_call!;
      pendingMsg.pending_tool_call = undefined;

      await this.sendMessage(`[CONSENT:${approved ? 'ALLOW' : 'DENY'}] ${callInfo.name}`);
    },

    async sendMessage(content: string, imageUrls?: string[], parentId?: string, personaId?: string) {
      if (!this.currentConvId) {
        const title = content.slice(0, 30) + (content.length > 30 ? "..." : "");
        const { data } = await client.post("/conversations", { title });
        // Insert after any pinned conversations so ordering matches server
        const firstUnpinned = this.conversations.findIndex((c) => !c.is_pinned);
        if (firstUnpinned === -1) {
          this.conversations.push(data);
        } else {
          this.conversations.splice(firstUnpinned, 0, data);
        }
        this.currentConvId = data.id;
      }

      const actualParentId = parentId || (this.activeMessages.length > 0 ? this.activeMessages[this.activeMessages.length - 1].id : undefined);
      let doneReceived = false;

      if (!content.startsWith("[CONSENT:")) {
        this.messages.push({ role: "human", content, image_urls: imageUrls, parent_id: actualParentId });
        this.messages.push({ role: "ai", content: "", parent_id: undefined }); // Resulting AI msg will eventually get a parent_id from backend if we refresh, but for now we just link it optimistically
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
          body: JSON.stringify({
            conversation_id: this.currentConvId,
            content,
            image_urls: imageUrls,
            parent_message_id: actualParentId,
            persona_id: personaId,
          }),
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

                if (data.type === "human_msg_saved") {
                  // Patch early so human ID is available even if stream is cancelled
                  const humanMsg = this.messages[this.messages.length - 2];
                  if (humanMsg?.role === "human" && !humanMsg.id && data.human_msg_id) {
                    humanMsg.id = data.human_msg_id;
                  }
                } else if (data.type === "done") {
                  doneReceived = true;
                  // Fallback patch in case human_msg_saved was missed
                  const humanMsg = this.messages[this.messages.length - 2];
                  if (humanMsg?.role === "human" && !humanMsg.id && data.human_msg_id) {
                    humanMsg.id = data.human_msg_id;
                  }
                  if (aiMsg?.role === "ai" && !aiMsg.id && data.ai_msg_id) {
                    aiMsg.id = data.ai_msg_id;
                    aiMsg.parent_id = data.human_msg_id;
                  }
                  if (aiMsg) applyModelMeta(aiMsg, data);
                  this.activeLeafId = data.ai_msg_id ?? null;
                } else if (data.type === "routing") {
                  this.routingAgent = data.agent;
                } else if (data.type === "title_updated") {
                  const conv = this.conversations.find(c => c.id === this.currentConvId);
                  if (conv && data.title) {
                    conv.title = data.title;
                  }
                } else if (data.type === "approval_required") {
                  // Patch human message ID received before the approval pause
                  if (data.human_msg_id) {
                    const humanMsg = this.messages[this.messages.length - 2];
                    if (humanMsg?.role === "human" && !humanMsg.id) {
                      humanMsg.id = data.human_msg_id;
                    }
                  }
                  aiMsg.pending_tool_call = { name: data.tool, args: data.args ?? {}, pending_since: Date.now() };
                  this.streaming = false;
                  this.routingAgent = null;
                  this.activeLeafId = null;
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
          // User intentionally cancelled. Backend may have saved a partial AI
          // message — reload to get its ID so subsequent messages attach correctly.
          if (this.currentConvId) {
            const convId = this.currentConvId;
            for (const delay of [0, 200, 500]) {
              if (delay > 0) await new Promise((r) => setTimeout(r, delay));
              try {
                await this._reloadMessages(convId);
                if (this.messages.at(-1)?.role === "ai" && this.messages.at(-1)?.id) break;
              } catch (reloadErr) {
                console.warn("[chat] post-cancel message reload failed", reloadErr);
                break;
              }
            }
          }
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
        if (!doneReceived) {
          this.activeLeafId = null;
        }
      }
    },
  },
});
