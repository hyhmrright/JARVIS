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
    { path: "/admin", component: () => import("@/pages/AdminPage.vue"), meta: { requiresAuth: true, requiresAdmin: true } },
    { path: "/proactive", component: () => import("@/pages/ProactivePage.vue"), meta: { requiresAuth: true } },
    { path: "/plugins", name: "Plugins", component: () => import("@/pages/PluginsPage.vue"), meta: { requiresAuth: true } },
    { path: "/workspace/members", component: () => import("@/pages/WorkspaceMembersPage.vue"), meta: { requiresAuth: true } },
    { path: "/invite/:token", component: () => import("@/pages/InviteAcceptPage.vue") },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return "/login";
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return "/";
  }
});

export default router;
