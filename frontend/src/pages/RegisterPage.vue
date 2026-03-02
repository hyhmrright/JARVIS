<template>
  <div class="auth-page">
    <div class="bg-glow-auth"></div>
    <div class="auth-card animate-zoom-in">
      <div class="auth-header">
        <div class="brand-logo">J</div>
        <h1>{{ $t("register.title") }}</h1>
        <p class="brand-tagline">Join the future of personal AI.</p>
      </div>

      <form class="auth-form" @submit.prevent="handleRegister">
        <div class="form-group">
          <input
            v-model="email"
            type="email"
            class="modern-input"
            :placeholder="$t('register.email')"
            required
          />
        </div>
        <div class="form-group">
          <input
            v-model="displayName"
            type="text"
            class="modern-input"
            :placeholder="$t('register.displayName')"
          />
        </div>
        <div class="form-group">
          <input
            v-model="password"
            type="password"
            class="modern-input"
            :placeholder="$t('register.password')"
            required
          />
        </div>
        
        <button type="submit" class="btn-submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? $t("register.loading") : $t("register.submit") }}
        </button>
        
        <p v-if="error" class="error-msg animate-shake">{{ error }}</p>
      </form>

      <div class="auth-footer">
        {{ $t("register.hasAccount") }}
        <router-link to="/login" class="link-primary">{{ $t("register.login") }}</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
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
  if (!email.value || !password.value) return;
  loading.value = true;
  error.value = "";
  try {
    await auth.register(email.value, password.value, displayName.value);
    router.push("/");
  } catch (e) {
    if (e instanceof AxiosError && e.response?.status === 409) {
      error.value = t("register.emailTaken");
    } else {
      error.value = t("common.networkError");
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.auth-page {
  height: 100vh; width: 100vw; display: flex; align-items: center; justify-content: center;
  background: var(--bg-primary); position: relative; overflow: hidden;
}
.bg-glow-auth {
  position: absolute; width: 60%; height: 60%;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.1) 0%, transparent 70%);
  filter: blur(80px);
}
.auth-card {
  width: 100%; max-width: 400px; background: var(--glass-bg); backdrop-filter: var(--glass-blur);
  border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 3rem 2rem;
  box-shadow: var(--shadow-lg); text-align: center; z-index: 10;
}
.auth-header { margin-bottom: 2.5rem; }
.brand-logo {
  width: 48px; height: 48px; background: var(--accent); color: white; border-radius: 12px;
  display: flex; align-items: center; justify-content: center; font-size: 1.5rem; font-weight: 800; margin: 0 auto 1rem;
}
.brand-tagline { color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.5rem; }
.auth-form { display: flex; flex-direction: column; gap: 1.25rem; }
.modern-input {
  width: 100%; padding: 0.85rem 1rem; background: var(--bg-tertiary); border: 1px solid var(--border-bright);
  border-radius: var(--radius-sm); color: var(--text-primary); font-size: 1rem; outline: none; transition: all 0.2s;
}
.modern-input:focus { border-color: var(--accent); background: var(--bg-secondary); }
.btn-submit {
  padding: 0.85rem; background: var(--accent); color: white; border: none; border-radius: var(--radius-sm);
  font-size: 1rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
}
.btn-submit:hover:not(:disabled) { background: var(--accent-light); transform: translateY(-1px); }
.btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }
.error-msg { color: #f44336; font-size: 0.85rem; margin-top: 0.5rem; }
.auth-footer { margin-top: 2rem; font-size: 0.9rem; color: var(--text-secondary); }
.link-primary { color: var(--accent-light); text-decoration: none; font-weight: 600; margin-left: 0.5rem; }
.link-primary:hover { text-decoration: underline; }
.animate-zoom-in { animation: zoomIn 0.3s ease-out; }
.animate-shake { animation: shake 0.4s ease-in-out; }
@keyframes zoomIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
@keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-5px); } 75% { transform: translateX(5px); } }
.spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: white; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
