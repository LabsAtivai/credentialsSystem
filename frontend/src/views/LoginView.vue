<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { login } from "../api/auth";
import { useAuthStore } from "../stores/auth";
import { extractErrorMessage } from "../api/client";

const email = ref("");
const password = ref("");
const errorMessage = ref("");
const loading = ref(false);

const { setToken } = useAuthStore();
const router = useRouter();
const route = useRoute();

async function handleSubmit() {
  errorMessage.value = "";
  loading.value = true;
  try {
    const { access_token } = await login(email.value, password.value);
    setToken(access_token);
    const redirect = (route.query.redirect as string) || "/accounts";
    router.push(redirect);
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <form class="card login-card" @submit.prevent="handleSubmit">
      <h1>Snov Account Manager</h1>
      <div class="field">
        <label for="email">Email</label>
        <input id="email" v-model="email" type="email" required autocomplete="username" />
      </div>
      <div class="field">
        <label for="password">Senha</label>
        <input
          id="password"
          v-model="password"
          type="password"
          required
          autocomplete="current-password"
        />
      </div>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <button type="submit" class="btn btn-primary" :disabled="loading">
        {{ loading ? "Entrando..." : "Entrar" }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-card {
  padding: 2rem;
  width: min(360px, 90vw);
}
.login-card h1 {
  font-size: 1.2rem;
  margin-bottom: 1.5rem;
}
.login-card .btn {
  width: 100%;
}
</style>
