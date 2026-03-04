import client from "./client";

export interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface SystemStats {
  user_count: number;
  conversation_count: number;
  message_count: number;
  total_tokens_input: number;
  total_tokens_output: number;
}

export default {
  /** 获取用户列表 */
  async getUsers(page = 1, limit = 20) {
    const { data } = await client.get("/admin/users", { params: { page, limit } });
    return data;
  },

  /** 更新用户 */
  async updateUser(userId: string, data: { role?: string; is_active?: boolean }) {
    await client.patch(`/admin/users/${userId}`, data);
  },

  /** 删除用户 */
  async deleteUser(userId: string) {
    await client.delete(`/admin/users/${userId}`);
  },

  /** 获取系统统计 */
  async getStats(): Promise<SystemStats> {
    const { data } = await client.get("/admin/stats");
    return data;
  },

  /** 获取插件列表 */
  async getPlugins() {
    const { data } = await client.get("/plugins");
    return data;
  },

  /** 启用/禁用插件 */
  async enablePlugin(pluginId: string, enable: boolean) {
    await client.post(`/plugins/${pluginId}/enable`, null, { params: { enable } });
  },

  /** 安装插件 */
  async installPlugin(url: string) {
    await client.post("/plugins/install", { url });
  },
};
