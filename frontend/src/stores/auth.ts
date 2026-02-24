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
  state: () => ({ token: localStorage.getItem("token") as string | null }),
  getters: { isLoggedIn: (s) => !!s.token },
  actions: {
    /** 登录，成功后保存 token；失败时抛出 AxiosError */
    async login(email: string, password: string) {
      const { data } = await client.post("/auth/login", { email, password });
      this.token = data.access_token;
      localStorage.setItem("token", data.access_token);
    },
    /** 注册并自动登录，成功后保存 token；失败时抛出 AxiosError */
    async register(email: string, password: string, display_name?: string) {
      const { data } = await client.post("/auth/register", { email, password, display_name });
      this.token = data.access_token;
      localStorage.setItem("token", data.access_token);
    },
    /** 登出，清除 token */
    logout() {
      this.token = null;
      localStorage.removeItem("token");
    },
  },
});
