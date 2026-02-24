<template>
  <div class="auth-page">
    <div class="auth-card animate-slide-up">
      <div class="auth-brand">
        <span class="brand-icon">&#10022;</span>
        <h1>JARVIS</h1>
        <p class="brand-tagline">{{ $t("register.title") }}</p>
      </div>
      <div class="shimmer-line animate-shimmer"></div>
      <form class="auth-form" @submit.prevent="handleRegister">
        <div class="form-group animate-slide-up-delay-1">
          <label for="email">{{ $t("register.email") }}</label>
          <input id="email" v-model="email" type="email" :placeholder="$t('register.email')" required />
        </div>
        <div class="form-group animate-slide-up-delay-1">
          <label for="displayName">{{ $t("register.displayName") }}</label>
          <input
            id="displayName"
            v-model="displayName"
            type="text"
            :placeholder="$t('register.displayName')"
          />
        </div>
        <div class="form-group animate-slide-up-delay-2">
          <label for="password">{{ $t("register.password") }}</label>
          <input
            id="password"
            v-model="password"
            type="password"
            :placeholder="$t('register.password')"
            required
          />
        </div>
        <button type="submit" class="btn-primary animate-slide-up-delay-3" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? $t("register.loading") : $t("register.submit") }}
        </button>
        <p v-if="error" class="error-msg">{{ error }}</p>
      </form>
      <p class="auth-footer">
        {{ $t("register.hasAccount") }}
        <router-link to="/login">{{ $t("register.login") }}</router-link>
      </p>
    </div>
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

const email = ref("");
const displayName = ref("");
const password = ref("");

const error = ref("");
const loading = ref(false);

async function handleRegister() {
  loading.value = true;
  error.value = "";
  try {
    await auth.register(email.value, password.value, displayName.value || undefined);
    router.push("/");
  } catch (e) {
    if (e instanceof AxiosError && e.response) {
      const status = e.response.status;
      if (status === 409) {
        error.value = t("register.emailTaken");
      } else if (status === 422) {
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

<!-- Styles provided by @/assets/styles/components.css -->
