/**
 * Axios HTTP 客户端
 *
 * 所有 API 请求统一通过此 client 发出，baseURL 为 "/api"，
 * 由 Vite devServer 或 Nginx 反向代理到后端。
 * 请求拦截器自动附加 JWT Bearer token（若已登录）。
 */
import axios from "axios";

const client = axios.create({ baseURL: "/api" });

// 请求拦截器：自动从 localStorage 读取 token 并附加到 Authorization 头
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default client;
