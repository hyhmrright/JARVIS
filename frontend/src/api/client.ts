/**
 * Axios HTTP 客户端
 *
 * 所有 API 请求统一通过此 client 发出，baseURL 为 "/api"，
 * 由 Vite devServer 或 Nginx 反向代理到后端。
 * 请求拦截器自动附加 JWT Bearer token（若已登录）。
 * 响应拦截器在 401 时清除 token 并跳转登录页。
 */
import axios from "axios";

const client = axios.create({ baseURL: "/api" });

// 请求拦截器：自动从 localStorage 读取 token 并附加到 Authorization 头
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 响应拦截器：401 时清除 token 并跳转登录页（排除 auth 端点）
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !error.config?.url?.startsWith("/auth/")
    ) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export default client;
