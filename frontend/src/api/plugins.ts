import api from "./client";

export interface PluginInfo {
  plugin_id: string;
  name: string;
  version: string;
  description: string;
  tools: string[];
  channels: string[];
  config_schema?: Record<string, any>;
  requires?: string[];
}

export interface ConfigItem {
  value: string;
  is_secret: boolean;
}

export const pluginsApi = {
  list: () => api.get<PluginInfo[]>("/plugins"),

  reload: () => api.post<{ status: string }>("/plugins/reload"),

  getConfig: (pluginId: string) =>
    api.get<Record<string, ConfigItem>>(`/plugins/${pluginId}/config`),

  setConfig: (
    pluginId: string,
    key: string,
    value: string,
    is_secret = false,
  ) => api.put<void>(`/plugins/${pluginId}/config`, { key, value, is_secret }),

  deleteConfig: (pluginId: string, key: string) =>
    api.delete(`/plugins/${pluginId}/config/${key}`),
};

export interface MarketSkillOut {
  id: string;
  name: string;
  description: string;
  type: "mcp" | "skill_md" | "python_plugin";
  install_url: string;
  source?: string;
  author: string;
  tags: string[];
  scope: ("system" | "personal")[];
}

export interface InstalledPluginOut {
  id: string;
  plugin_id: string;
  name: string;
  type: "mcp" | "skill_md" | "python_plugin";
  install_url: string;
  scope: "system" | "personal";
  installed_by: string | null;
  created_at: string;
}

export interface InstallRequest {
  url: string;
  type?: "mcp" | "skill_md" | "python_plugin";
  scope: "system" | "personal";
}

export interface InstalledListResponse {
  system: InstalledPluginOut[];
  personal: InstalledPluginOut[];
}

export const marketApi = {
  listSkills: () => api.get<MarketSkillOut[]>("/plugins/market/skills"),
  detect: (url: string) =>
    api.get<{ type: string }>(
      `/plugins/detect?url=${encodeURIComponent(url)}`,
    ),
  install: (req: InstallRequest) =>
    api.post<InstalledPluginOut>("/plugins/install", req),
  uninstall: (id: string) => api.delete(`/plugins/install/${id}`),
  listInstalled: () => api.get<InstalledListResponse>("/plugins/installed"),
};
