<template>
  <div class="auth-page">
    <div class="auth-card animate-slide-up">
      <div class="auth-brand">
        <span class="brand-icon">&#10022;</span>
        <h1>JARVIS</h1>
        <p class="brand-tagline">{{ $t("login.title") }}</p>
      </div>
      <div class="shimmer-line animate-shimmer"></div>
      <form class="auth-form" @submit.prevent="handleLogin">
        <div class="form-group animate-slide-up-delay-1">
          <label for="email">{{ $t("login.email") }}</label>
          <input id="email" v-model="email" type="email" :placeholder="$t('login.email')" required />
        </div>
        <div class="form-group animate-slide-up-delay-2">
          <label for="password">{{ $t("login.password") }}</label>
          <input
            id="password"
            v-model="password"
            type="password"
            :placeholder="$t('login.password')"
            required
          />
        </div>
        <button type="submit" class="btn-primary animate-slide-up-delay-3" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? $t("login.loading") : $t("login.submit") }}
        </button>
        <p v-if="error" class="error-msg">{{ error }}</p>
      </form>
      <p class="auth-footer">
        {{ $t("login.noAccount") }}
        <router-link to="/register">{{ $t("login.register") }}</router-link>
      </p>
    </div>
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

const email = ref("");
const password = ref("");

const error = ref("");
const loading = ref(false);

async function handleLogin() {
  loading.value = true;
  error.value = "";
  try {
    await auth.login(email.value, password.value);
    router.push("/");
  } catch (e) {
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

<!-- Styles provided by @/assets/styles/components.css -->
