import { defineStore } from "pinia";
import client from "@/api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({ token: localStorage.getItem("token") as string | null }),
  getters: { isLoggedIn: (s) => !!s.token },
  actions: {
    async login(email: string, password: string) {
      const { data } = await client.post("/auth/login", { email, password });
      this.token = data.access_token;
      localStorage.setItem("token", data.access_token);
    },
    async register(email: string, password: string, display_name?: string) {
      const { data } = await client.post("/auth/register", { email, password, display_name });
      this.token = data.access_token;
      localStorage.setItem("token", data.access_token);
    },
    logout() {
      this.token = null;
      localStorage.removeItem("token");
    },
  },
});
