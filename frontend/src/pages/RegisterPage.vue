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
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const email = ref(""), displayName = ref(""), password = ref(""), error = ref(""), loading = ref(false);

async function handleRegister() {
  loading.value = true;
  error.value = "";
  try {
    await auth.register(email.value, password.value, displayName.value || undefined);
    router.push("/");
  } catch {
    error.value = "注册失败，请检查邮箱是否已被使用";
  } finally {
    loading.value = false;
  }
}
</script>
