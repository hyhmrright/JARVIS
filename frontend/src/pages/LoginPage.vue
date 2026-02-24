<template>
  <div class="auth-page">
    <h1>登录 JARVIS</h1>
    <form @submit.prevent="handleLogin">
      <input v-model="email" type="email" placeholder="邮箱" required />
      <input v-model="password" type="password" placeholder="密码" required />
      <button type="submit" :disabled="loading">{{ loading ? "登录中..." : "登录" }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <p>没有账号？<router-link to="/register">注册</router-link></p>
  </div>
</template>

<script setup lang="ts">
/**
 * 登录页面
 *
 * 错误处理：根据 HTTP 状态码显示对应的中文提示
 *   401 → 邮箱或密码错误
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
const password = ref("");

// UI 状态
const error = ref("");
const loading = ref(false);

/** 提交登录表单，成功后跳转首页 */
async function handleLogin() {
  loading.value = true;
  error.value = "";
  try {
    await auth.login(email.value, password.value);
    router.push("/");
  } catch (e) {
    // 区分 HTTP 响应错误和网络层错误（断网、超时等）
    if (e instanceof AxiosError && e.response) {
      const status = e.response.status;
      if (status === 401) {
        error.value = "邮箱或密码错误";
      } else if (status === 429) {
        error.value = "请求太频繁，请稍后再试";
      } else {
        error.value = "登录失败，请稍后再试";
      }
    } else {
      error.value = "网络错误，请检查网络连接";
    }
  } finally {
    loading.value = false;
  }
}
</script>
