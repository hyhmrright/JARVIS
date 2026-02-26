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
          <input
            id="email"
            v-model="email"
            type="email"
            :placeholder="$t('login.email')"
            :class="{ 'input-error': emailError }"
            @blur="emailTouched = true"
          />
          <p class="field-error" :class="{ visible: emailError }">{{ emailError }}</p>
        </div>
        <div class="form-group animate-slide-up-delay-2">
          <label for="password">{{ $t("login.password") }}</label>
          <div class="password-wrapper">
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              :placeholder="$t('login.password')"
              :class="{ 'input-error': passwordError }"
              @blur="passwordTouched = true"
            />
            <button type="button" class="password-toggle" @click="showPassword = !showPassword">
              <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            </button>
          </div>
          <p class="field-error" :class="{ visible: passwordError }">{{ passwordError }}</p>
        </div>
        <button type="submit" class="btn-primary animate-slide-up-delay-3" :disabled="loading || !isFormValid">
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
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";
import { AxiosError } from "axios";

const { t } = useI18n();
const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const showPassword = ref(false);
const emailTouched = ref(false);
const passwordTouched = ref(false);

const error = ref("");
const loading = ref(false);

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const emailError = computed(() => {
  if (!emailTouched.value) return "";
  if (!email.value) return t("validation.emailRequired");
  if (!EMAIL_RE.test(email.value)) return t("validation.emailInvalid");
  return "";
});

const passwordError = computed(() => {
  if (!passwordTouched.value) return "";
  if (!password.value) return t("validation.passwordRequired");
  if (password.value.length < 8) return t("validation.passwordMinLength");
  return "";
});

const isFormValid = computed(
  () =>
    email.value.length > 0 &&
    !emailError.value &&
    password.value.length > 0 &&
    !passwordError.value,
);

async function handleLogin() {
  emailTouched.value = true;
  passwordTouched.value = true;
  if (!isFormValid.value) return;

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
