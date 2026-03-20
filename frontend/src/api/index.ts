/**
 * API module — re-exports the shared Axios client and provides
 * typed helper functions for common API operations.
 */
import client from "./client";

export { default as api } from "./client";

// Conversation search
export const searchConversations = (q: string, limit = 20) =>
  client.get<Array<{ conv_id: string; title: string; snippet: string; updated_at: string }>>(
    "/conversations/search",
    { params: { q, limit } },
  );

// Conversation export (returns Blob)
export const exportConversation = (convId: string, format: "md" | "json" | "txt") =>
  client.get<Blob>(`/conversations/${convId}/export`, {
    params: { format },
    responseType: "blob",
  });

// PATCH conversation
export const patchConversation = (
  convId: string,
  data: { title?: string; persona_override?: string | null },
) => client.patch(`/conversations/${convId}`, data);

// Toggle pin on a conversation
export const pinConversation = (convId: string) =>
  client.patch(`/conversations/${convId}/pin`);

// Delete a single message
export const deleteMessage = (convId: string, msgId: string) =>
  client.delete(`/conversations/${convId}/messages/${msgId}`);

// URL ingestion
export const ingestDocumentUrl = (url: string, workspaceId?: string | null) =>
  client.post("/documents/ingest-url", { url, workspace_id: workspaceId ?? null });

// Rename a document
export const renameDocument = (
  docId: string,
  filename: string,
): Promise<{ id: string; filename: string; file_type: string; chunk_count: number }> =>
  client
    .patch(`/documents/${docId}`, { filename })
    .then((r) => r.data);
