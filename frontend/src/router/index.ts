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
    { path: "/market", component: () => import("@/pages/SkillMarketPage.vue"), meta: { requiresAuth: true } },
    { path: "/personas", component: () => import("@/pages/PersonasPage.vue"), meta: { requiresAuth: true } },
    { path: "/workflows", component: () => import("@/pages/WorkflowsPage.vue"), meta: { requiresAuth: true } },
    { path: "/studio", component: () => import("@/pages/WorkflowStudioPage.vue"), meta: { requiresAuth: true } },
    { path: "/workspace/members", component: () => import("@/pages/WorkspaceMembersPage.vue"), meta: { requiresAuth: true } },
    { path: "/invite/:token", component: () => import("@/pages/InviteAcceptPage.vue") },
    { path: "/share/:token", component: () => import("@/pages/SharedChatPage.vue") },
    { path: "/:pathMatch(.*)*", name: "NotFound", component: () => import("@/pages/NotFoundPage.vue") },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();

  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { path: "/" };
  }

  if (to.path === "/login" && auth.isLoggedIn) {
    const redirect = to.query.redirect;
    const decoded = typeof redirect === "string" ? decodeURIComponent(redirect) : "";
    const redirectPath = decoded.startsWith("/") ? decoded : "/";
    return { path: redirectPath };
  }
});

export default router;
