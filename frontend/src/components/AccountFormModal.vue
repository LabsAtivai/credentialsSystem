<script setup lang="ts">
import { reactive } from "vue";
import type { Account, AccountCreatePayload } from "../types";

const props = defineProps<{
  account: Account | null;
  saving?: boolean;
  errorMessage?: string;
}>();
const emit = defineEmits<{ save: [payload: AccountCreatePayload]; close: [] }>();

const isEdit = !!props.account;

const form = reactive<AccountCreatePayload>({
  email: props.account?.email ?? "",
  snov_id: "",
  snov_secret: "",
  snov_email: "",
  snov_password: "",
  description: props.account?.description ?? "",
});

function buildPayload(): AccountCreatePayload {
  // Em edição, envia apenas campos preenchidos (backend trata PATCH parcial).
  const payload: AccountCreatePayload = { ...form };
  if (isEdit) {
    for (const key of Object.keys(payload) as (keyof AccountCreatePayload)[]) {
      if (payload[key] === "" || payload[key] === undefined) {
        delete payload[key];
      }
    }
  }
  return payload;
}

function handleSubmit() {
  emit("save", buildPayload());
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal">
      <h2>{{ isEdit ? "Editar conta" : "Nova conta" }}</h2>
      <form @submit.prevent="handleSubmit">
        <div class="field">
          <label for="acc-email">Email</label>
          <input id="acc-email" v-model="form.email" type="email" required />
        </div>
        <div class="field">
          <label for="acc-snov-id">Snov ID (client id)</label>
          <input
            id="acc-snov-id"
            v-model="form.snov_id"
            type="text"
            :required="!isEdit"
            :placeholder="isEdit ? 'Deixe em branco para manter' : ''"
          />
        </div>
        <div class="field">
          <label for="acc-snov-secret">Snov Secret</label>
          <input
            id="acc-snov-secret"
            v-model="form.snov_secret"
            type="password"
            autocomplete="new-password"
            :required="!isEdit"
            :placeholder="isEdit ? 'Deixe em branco para manter' : ''"
          />
        </div>
        <div class="field">
          <label for="acc-snov-email">Snov Email</label>
          <input
            id="acc-snov-email"
            v-model="form.snov_email"
            type="email"
            :required="!isEdit"
            :placeholder="isEdit ? 'Deixe em branco para manter' : ''"
          />
        </div>
        <div class="field">
          <label for="acc-snov-password">Snov Password</label>
          <input
            id="acc-snov-password"
            v-model="form.snov_password"
            type="password"
            autocomplete="new-password"
            :required="!isEdit"
            :placeholder="isEdit ? 'Deixe em branco para manter' : ''"
          />
        </div>
        <div class="field">
          <label for="acc-description">Descrição</label>
          <input id="acc-description" v-model="form.description" type="text" />
        </div>

        <p v-if="props.errorMessage" class="error-text">{{ props.errorMessage }}</p>

        <div class="actions">
          <button type="button" class="btn btn-secondary" @click="emit('close')">Cancelar</button>
          <button type="submit" class="btn btn-primary" :disabled="props.saving">
            {{ props.saving ? "Salvando..." : "Salvar" }}
          </button>
        </div>
      </form>
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
input {
  width: 100%;
}
</style>
