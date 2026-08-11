<script setup lang="ts">
import { useAuthStore } from "./stores/auth";
import { useRouter } from "vue-router";

const { isAuthenticated, logout } = useAuthStore();
const router = useRouter();

function handleLogout() {
  logout();
  router.push({ name: "login" });
}
</script>

<template>
  <header v-if="isAuthenticated" class="topbar">
    <span class="brand">Snov Account Manager</span>
    <button type="button" class="link-button" @click="handleLogout">Sair</button>
  </header>
  <main>
    <router-view />
  </main>
</template>

<style scoped>
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: #1a1a2e;
  color: #fff;
}
.brand {
  font-weight: 600;
}
.link-button {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.4);
  color: #fff;
  border-radius: 4px;
  padding: 0.35rem 0.75rem;
  cursor: pointer;
}
.link-button:hover {
  background: rgba(255, 255, 255, 0.1);
}
</style>
