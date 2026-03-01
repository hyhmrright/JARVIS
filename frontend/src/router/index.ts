import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/pages/LoginPage.vue") },
    { path: "/register", component: () => import("@/pages/RegisterPage.vue") },
    { path: "/", component: () => import("@/pages/ChatPage.vue"), meta: { requiresAuth: true } },
    { path: "/documents", component: () => import("@/pages/DocumentsPage.vue"), meta: { requiresAuth: true } },
    { path: "/settings", component: () => import("@/pages/SettingsPage.vue"), meta: { requiresAuth: true } },
    { path: "/usage", component: () => import("@/pages/UsagePage.vue"), meta: { requiresAuth: true } },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isLoggedIn) return "/login";
});

export default router;
