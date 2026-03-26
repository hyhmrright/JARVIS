/**
 * Axios HTTP 客户端
 *
 * 所有 API 请求统一通过此 client 发出，baseURL 为 "/api"，
 * 由 Vite devServer 或 Nginx 反向代理到后端。
 * 请求拦截器自动附加 JWT Bearer token（若已登录）。
 * 响应拦截器在 401 时尝试用 refresh token 刷新，失败则跳转登录页。
 */
import axios from "axios";

const client = axios.create({ baseURL: "/api" });

// 请求拦截器：自动从 localStorage 读取 token 并附加到 Authorization 头
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let _isRefreshing = false;
let _pendingQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

function processQueue(err: unknown, token: string | null) {
  const queue = _pendingQueue;
  _pendingQueue = [];
  queue.forEach(({ resolve, reject }) =>
    err ? reject(err) : resolve(token as string),
  );
}

// 响应拦截器：401 时先尝试用 refresh token 换取新 access token，失败才跳转登录页
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.startsWith("/auth/") &&
      !originalRequest.url?.startsWith("/public/")
    ) {
      const refreshToken = localStorage.getItem("refresh_token");
      if (!refreshToken) {
        localStorage.removeItem("token");
        window.location.href = "/login";
        return Promise.reject(error);
      }

      if (_isRefreshing) {
        return new Promise((resolve, reject) => {
          _pendingQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return client(originalRequest);
        });
      }

      originalRequest._retry = true;
      _isRefreshing = true;

      try {
        const { data } = await axios.post<{ access_token: string }>(
          "/api/auth/refresh",
          { refresh_token: refreshToken },
        );
        localStorage.setItem("token", data.access_token);
        client.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
        processQueue(null, data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return client(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        localStorage.removeItem("token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
        return Promise.reject(refreshErr);
      } finally {
        _isRefreshing = false;
      }
    }
    return Promise.reject(error);
  },
);

export default client;
