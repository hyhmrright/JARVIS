<template>
  <div class="auth-page">
    <h1>{{ $t('register.title') }}</h1>
    <form @submit.prevent="handleRegister">
      <input v-model="email" type="email" :placeholder="$t('register.email')" required />
      <input v-model="displayName" type="text" :placeholder="$t('register.displayName')" />
      <input v-model="password" type="password" :placeholder="$t('register.password')" required />
      <button type="submit" :disabled="loading">{{ loading ? $t('register.loading') : $t('register.submit') }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <p>{{ $t('register.hasAccount') }}<router-link to="/login">{{ $t('register.login') }}</router-link></p>
  </div>
</template>

<script setup lang="ts">
/**
 * 注册页面
 *
 * 错误处理：根据 HTTP 状态码显示对应的翻译提示
 *   409 → 邮箱已注册
 *   422 → 请求体校验失败（Pydantic 自动返回）
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
        error.value = t("register.emailTaken");
      } else if (status === 422) {
        // FastAPI 422 的 detail 可能是数组（Pydantic 校验错误列表）或字符串
        const detail = e.response.data?.detail;
        if (Array.isArray(detail)) {
          error.value = detail.map((d: { msg: string }) => d.msg).join("；");
        } else if (typeof detail === "string") {
          error.value = detail;
        } else {
          error.value = t("register.validationError");
        }
      } else if (status === 429) {
        error.value = t("common.rateLimitError");
      } else {
        error.value = t("register.genericError");
      }
    } else {
      error.value = t("common.networkError");
    }
  } finally {
    loading.value = false;
  }
}
</script>
