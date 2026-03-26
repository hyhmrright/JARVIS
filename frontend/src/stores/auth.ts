/**
 * 认证状态管理
 *
 * 管理 JWT token 的获取、持久化和清除。
 * token 同时保存在 Pinia state 和 localStorage 中，
 * 页面刷新时从 localStorage 恢复登录态。
 *
 * 注意：login/register 方法会将 AxiosError 原样抛出，
 * 由调用方（页面组件）负责根据 HTTP 状态码显示具体错误提示。
 */
import { defineStore } from "pinia";
import client from "@/api/client";

export const useAuthStore = defineStore("auth", {
  // 初始化时从 localStorage 恢复 token（若存在）
  state: () => ({
    token: localStorage.getItem("token") as string | null,
    role: localStorage.getItem("role") as string | null,
    displayName: localStorage.getItem("displayName") as string | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => s.role === "admin" || s.role === "superadmin",
  },
  actions: {
    /** 登录，成功后保存 token；失败时抛出 AxiosError */
    async login(email: string, password: string) {
      const { data } = await client.post("/auth/login", { email, password });
      this.token = data.access_token;
      this.role = data.role;
      this.displayName = data.display_name;
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("role", data.role);
      if (data.display_name) {
        localStorage.setItem("displayName", data.display_name);
      }
      if (data.refresh_token) {
        localStorage.setItem("refresh_token", data.refresh_token);
      }
    },
    /** 注册并自动登录，成功后保存 token；失败时抛出 AxiosError */
    async register(email: string, password: string, display_name?: string) {
      const { data } = await client.post("/auth/register", { email, password, display_name });
      this.token = data.access_token;
      this.role = data.role;
      this.displayName = data.display_name;
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("role", data.role);
      if (data.display_name) {
        localStorage.setItem("displayName", data.display_name);
      }
    },
    /** 更新显示名称并同步到本地存储 */
    async updateDisplayName(displayName: string | null) {
      const { data } = await client.patch("/auth/profile", { display_name: displayName });
      this.displayName = data.display_name;
      if (data.display_name) {
        localStorage.setItem("displayName", data.display_name);
      } else {
        localStorage.removeItem("displayName");
      }
    },
    /** 登出，撤销 refresh token 并清除本地状态 */
    async logout() {
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          await client.post("/auth/logout", { refresh_token: refreshToken });
        } catch {
          // Ignore errors — local cleanup happens regardless
        }
      }
      this.token = null;
      this.role = null;
      this.displayName = null;
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      localStorage.removeItem("displayName");
      localStorage.removeItem("refresh_token");
    },
  },
});
