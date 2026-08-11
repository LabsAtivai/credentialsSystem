<script setup lang="ts">
import { reactive, ref } from "vue";
import type { Account, AccountCredentials } from "../types";
import { getAccountCredentials } from "../api/accounts";
import { extractErrorMessage } from "../api/client";

const props = defineProps<{ account: Account }>();
const emit = defineEmits<{ close: [] }>();

const confirmed = ref(false);
const loading = ref(false);
const errorMessage = ref("");
const credentials = ref<AccountCredentials | null>(null);
const revealed = reactive({
  snov_id: false,
  snov_secret: false,
  snov_email: false,
  snov_password: false,
});

async function handleConfirm() {
  confirmed.value = true;
  loading.value = true;
  errorMessage.value = "";
  try {
    credentials.value = await getAccountCredentials(props.account.id);
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

function toggleReveal(field: keyof typeof revealed) {
  revealed[field] = !revealed[field];
}

async function copyValue(value: string) {
  await navigator.clipboard.writeText(value);
}

function mask(value: string): string {
  return "•".repeat(Math.min(value.length, 16));
}

function handleClose() {
  // limpa credenciais da memória do componente antes de fechar
  credentials.value = null;
  revealed.snov_id = false;
  revealed.snov_secret = false;
  revealed.snov_email = false;
  revealed.snov_password = false;
  emit("close");
}
</script>

<template>
  <div class="modal-overlay" @click.self="handleClose">
    <div class="modal">
      <h2>Credenciais — {{ account.email }}</h2>

      <div v-if="!confirmed">
        <p>
          Você está prestes a visualizar credenciais sensíveis desta conta. Esse acesso será
          registrado na auditoria.
        </p>
        <div class="actions">
          <button type="button" class="btn btn-secondary" @click="handleClose">Cancelar</button>
          <button type="button" class="btn btn-primary" @click="handleConfirm">
            Ver credenciais
          </button>
        </div>
      </div>

      <div v-else>
        <p v-if="loading">Carregando credenciais...</p>
        <p v-else-if="errorMessage" class="error-text">{{ errorMessage }}</p>

        <div v-else-if="credentials" class="cred-list">
          <div v-for="field in (['snov_id', 'snov_secret', 'snov_email', 'snov_password'] as const)" :key="field" class="cred-row">
            <label>{{ field }}</label>
            <div class="cred-value">
              <code>{{ revealed[field] ? credentials[field] : mask(credentials[field]) }}</code>
              <button type="button" class="btn btn-secondary btn-sm" @click="toggleReveal(field)">
                {{ revealed[field] ? "Ocultar" : "Revelar" }}
              </button>
              <button type="button" class="btn btn-secondary btn-sm" @click="copyValue(credentials[field])">
                Copiar
              </button>
            </div>
          </div>
        </div>

        <div class="actions">
          <button type="button" class="btn btn-primary" @click="handleClose">Fechar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
h2 {
  margin-top: 0;
  font-size: 1.05rem;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
.cred-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.cred-row label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  color: #6b7280;
  margin-bottom: 0.2rem;
}
.cred-value {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.cred-value code {
  flex: 1;
  background: #f3f4f6;
  padding: 0.4rem 0.6rem;
  border-radius: 4px;
  overflow-x: auto;
  white-space: nowrap;
}
.btn-sm {
  padding: 0.3rem 0.6rem;
  font-size: 0.78rem;
}
</style>
