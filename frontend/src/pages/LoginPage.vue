<template>
  <div class="auth-page">
    <h1>{{ $t('login.title') }}</h1>
    <form @submit.prevent="handleLogin">
      <input v-model="email" type="email" :placeholder="$t('login.email')" required />
      <input v-model="password" type="password" :placeholder="$t('login.password')" required />
      <button type="submit" :disabled="loading">{{ loading ? $t('login.loading') : $t('login.submit') }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <p>{{ $t('login.noAccount') }}<router-link to="/register">{{ $t('login.register') }}</router-link></p>
  </div>
</template>

<script setup lang="ts">
/**
 * 登录页面
 *
 * 错误处理：根据 HTTP 状态码显示对应的翻译提示
 *   401 → 邮箱或密码错误
 *   429 → 速率限制超出（slowapi 自动返回）
 */
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";
import { AxiosError } from "axios";

const { t } = useI18n();
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
        error.value = t("login.invalidCredentials");
      } else if (status === 429) {
        error.value = t("common.rateLimitError");
      } else {
        error.value = t("login.genericError");
      }
    } else {
      error.value = t("common.networkError");
    }
  } finally {
    loading.value = false;
  }
}
</script>
