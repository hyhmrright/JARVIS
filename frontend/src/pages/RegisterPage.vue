<template>
  <div class="auth-page">
    <h1>注册 JARVIS</h1>
    <form @submit.prevent="handleRegister">
      <input v-model="email" type="email" placeholder="邮箱" required />
      <input v-model="displayName" type="text" placeholder="显示名称（可选）" />
      <input v-model="password" type="password" placeholder="密码" required />
      <button type="submit" :disabled="loading">{{ loading ? "注册中..." : "注册" }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <p>已有账号？<router-link to="/login">登录</router-link></p>
  </div>
</template>

<script setup lang="ts">
/**
 * 注册页面
 *
 * 错误处理：根据 HTTP 状态码显示对应的中文提示
 *   409 → 邮箱已注册
 *   422 → 请求体校验失败（Pydantic 自动返回）
 *   429 → 速率限制超出（slowapi 自动返回）
 */
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { AxiosError } from "axios";

const auth = useAuthStore();
const router = useRouter();

// 表单字段
const email = ref("");
const displayName = ref("");
const password = ref("");

// UI 状态
const error = ref("");
const loading = ref(false);

/** 提交注册表单，成功后自动登录并跳转首页 */
async function handleRegister() {
  loading.value = true;
  error.value = "";
  try {
    await auth.register(email.value, password.value, displayName.value || undefined);
    router.push("/");
  } catch (e) {
    // 区分 HTTP 响应错误和网络层错误（断网、超时等）
    if (e instanceof AxiosError && e.response) {
      const status = e.response.status;
      if (status === 409) {
        error.value = "邮箱已被注册";
      } else if (status === 422) {
        // FastAPI 422 的 detail 可能是数组（Pydantic 校验错误列表）或字符串
        const detail = e.response.data?.detail;
        if (Array.isArray(detail)) {
          error.value = detail.map((d: { msg: string }) => d.msg).join("；");
        } else if (typeof detail === "string") {
          error.value = detail;
        } else {
          error.value = "输入信息有误，请检查后重试";
        }
      } else if (status === 429) {
        error.value = "请求太频繁，请稍后再试";
      } else {
        error.value = "注册失败，请稍后再试";
      }
    } else {
      error.value = "网络错误，请检查网络连接";
    }
  } finally {
    loading.value = false;
  }
}
</script>
