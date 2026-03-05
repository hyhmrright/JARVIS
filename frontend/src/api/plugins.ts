import api from "./client";

export interface PluginInfo {
  plugin_id: string;
  name: string;
  version: string;
  description: string;
  tools: string[];
  channels: string[];
}

export interface ConfigItem {
  value: string;
  is_secret: boolean;
}

export const pluginsApi = {
  list: () => api.get<PluginInfo[]>("/plugins"),

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
