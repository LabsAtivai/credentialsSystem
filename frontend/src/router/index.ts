import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/accounts" },
    { path: "/login", name: "login", component: () => import("../views/LoginView.vue") },
    {
      path: "/accounts",
      name: "accounts",
      component: () => import("../views/AccountsView.vue"),
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach((to) => {
  const { isAuthenticated } = useAuthStore();
  if (to.meta.requiresAuth && !isAuthenticated.value) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && isAuthenticated.value) {
    return { name: "accounts" };
  }
  return true;
});

export default router;
