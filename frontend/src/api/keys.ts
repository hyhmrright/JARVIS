// ─── Personal API Keys ────────────────────────────────────────────────────
import api from "./client";

export interface ApiKeyItem {
  id: string;
  name: string;
  prefix: string;
  scope: "full" | "readonly";
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface ApiKeyCreateRequest {
  name: string;
  scope: "full" | "readonly";
  expires_at?: string | null;
}

export interface ApiKeyCreateResponse extends ApiKeyItem {
  raw_key: string;
}

export const listApiKeys = (): Promise<ApiKeyItem[]> =>
  api.get("/keys").then((r) => r.data);

export const createApiKey = (
  req: ApiKeyCreateRequest,
): Promise<ApiKeyCreateResponse> => api.post("/keys", req).then((r) => r.data);

export const deleteApiKey = (id: string): Promise<void> =>
  api.delete(`/keys/${id}`);
