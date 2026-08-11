<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import type { Account, AccountCreatePayload, AccountStatus } from "../types";
import {
  activateAccount,
  createAccount,
  deactivateAccount,
  deleteAccount,
  listAccounts,
  updateAccount,
} from "../api/accounts";
import { extractErrorMessage } from "../api/client";
import { useAuthStore } from "../stores/auth";
import AccountFormModal from "../components/AccountFormModal.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import CredentialsModal from "../components/CredentialsModal.vue";

const { role } = useAuthStore();

const canWrite = () => role.value === "ADMIN" || role.value === "OPERATOR";
const canDelete = () => role.value === "ADMIN";
const canViewCredentials = () => role.value === "ADMIN";

const accounts = ref<Account[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = ref("");
const statusFilter = ref<AccountStatus | "">("");
const loading = ref(false);
const listError = ref("");

let searchDebounce: ReturnType<typeof setTimeout> | undefined;

async function fetchAccounts() {
  loading.value = true;
  listError.value = "";
  try {
    const result = await listAccounts({
      q: q.value || undefined,
      status: statusFilter.value,
      page: page.value,
      page_size: pageSize.value,
    });
    accounts.value = result.items;
    total.value = result.total;
  } catch (error) {
    listError.value = extractErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

watch([statusFilter, page], fetchAccounts);
watch(q, () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    page.value = 1;
    fetchAccounts();
  }, 300);
});

onMounted(fetchAccounts);

// --- criar / editar ---
const showFormModal = ref(false);
const editingAccount = ref<Account | null>(null);
const formSaving = ref(false);
const formError = ref("");

function openCreateModal() {
  editingAccount.value = null;
  formError.value = "";
  showFormModal.value = true;
}

function openEditModal(account: Account) {
  editingAccount.value = account;
  formError.value = "";
  showFormModal.value = true;
}

async function handleFormSave(payload: AccountCreatePayload) {
  formSaving.value = true;
  formError.value = "";
  try {
    if (editingAccount.value) {
      await updateAccount(editingAccount.value.id, payload);
    } else {
      await createAccount(payload);
    }
    showFormModal.value = false;
    await fetchAccounts();
  } catch (error) {
    formError.value = extractErrorMessage(error);
  } finally {
    formSaving.value = false;
  }
}

// --- ativar / desativar / excluir (com confirmação) ---
type PendingAction = { type: "activate" | "deactivate" | "delete"; account: Account } | null;
const pendingAction = ref<PendingAction>(null);
const actionLoading = ref(false);
const actionError = ref("");

function askActivate(account: Account) {
  actionError.value = "";
  pendingAction.value = { type: "activate", account };
}
function askDeactivate(account: Account) {
  actionError.value = "";
  pendingAction.value = { type: "deactivate", account };
}
function askDelete(account: Account) {
  actionError.value = "";
  pendingAction.value = { type: "delete", account };
}

async function confirmPendingAction() {
  if (!pendingAction.value) return;
  const { type, account } = pendingAction.value;
  actionLoading.value = true;
  actionError.value = "";
  try {
    if (type === "activate") await activateAccount(account.id);
    else if (type === "deactivate") await deactivateAccount(account.id);
    else await deleteAccount(account.id);
    pendingAction.value = null;
    await fetchAccounts();
  } catch (error) {
    actionError.value = extractErrorMessage(error);
  } finally {
    actionLoading.value = false;
  }
}

const confirmCopy = {
  activate: { title: "Ativar conta", message: "Confirma ativar esta conta?", label: "Ativar", danger: false },
  deactivate: {
    title: "Desativar conta",
    message: "Confirma desativar esta conta? Sistemas que dependem dela vão parar de recebê-la.",
    label: "Desativar",
    danger: true,
  },
  delete: {
    title: "Excluir conta",
    message: "Confirma excluir esta conta? Ela deixará de aparecer nas listagens (soft delete).",
    label: "Excluir",
    danger: true,
  },
};

// --- credenciais ---
const credentialsAccount = ref<Account | null>(null);

function totalPages() {
  return Math.max(1, Math.ceil(total.value / pageSize.value));
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("pt-BR");
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Contas Snov</h1>
      <button v-if="canWrite()" type="button" class="btn btn-primary" @click="openCreateModal">
        Nova conta
      </button>
    </div>

    <div class="filters card">
      <input v-model="q" type="search" placeholder="Buscar por email..." />
      <select v-model="statusFilter">
        <option value="">Todos os status</option>
        <option value="ACTIVE">Ativo</option>
        <option value="INACTIVE">Inativo</option>
      </select>
    </div>

    <p v-if="listError" class="error-text">{{ listError }}</p>

    <div class="card table-wrap">
      <table>
        <thead>
          <tr>
            <th>Email</th>
            <th>Status</th>
            <th>Descrição</th>
            <th>Última utilização</th>
            <th>Criado em</th>
            <th>Atualizado em</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7">Carregando...</td>
          </tr>
          <tr v-else-if="accounts.length === 0">
            <td colspan="7">Nenhuma conta encontrada.</td>
          </tr>
          <tr v-for="account in accounts" v-else :key="account.id">
            <td>{{ account.email }}</td>
            <td>
              <span :class="['badge', account.status === 'ACTIVE' ? 'badge-active' : 'badge-inactive']">
                {{ account.status === "ACTIVE" ? "Ativo" : "Inativo" }}
              </span>
            </td>
            <td>{{ account.description || "—" }}</td>
            <td>{{ formatDate(account.last_used_at) }}</td>
            <td>{{ formatDate(account.created_at) }}</td>
            <td>{{ formatDate(account.updated_at) }}</td>
            <td class="row-actions">
              <button
                v-if="canViewCredentials()"
                type="button"
                class="btn btn-secondary btn-sm"
                @click="credentialsAccount = account"
              >
                Ver credenciais
              </button>
              <button
                v-if="canWrite()"
                type="button"
                class="btn btn-secondary btn-sm"
                @click="openEditModal(account)"
              >
                Editar
              </button>
              <button
                v-if="canWrite() && account.status === 'INACTIVE'"
                type="button"
                class="btn btn-secondary btn-sm"
                @click="askActivate(account)"
              >
                Ativar
              </button>
              <button
                v-if="canWrite() && account.status === 'ACTIVE'"
                type="button"
                class="btn btn-secondary btn-sm"
                @click="askDeactivate(account)"
              >
                Desativar
              </button>
              <button
                v-if="canDelete()"
                type="button"
                class="btn btn-danger btn-sm"
                @click="askDelete(account)"
              >
                Excluir
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pagination">
      <button type="button" class="btn btn-secondary" :disabled="page <= 1" @click="page--">
        Anterior
      </button>
      <span>Página {{ page }} de {{ totalPages() }} ({{ total }} contas)</span>
      <button type="button" class="btn btn-secondary" :disabled="page >= totalPages()" @click="page++">
        Próxima
      </button>
    </div>

    <AccountFormModal
      v-if="showFormModal"
      :account="editingAccount"
      :saving="formSaving"
      :error-message="formError"
      @save="handleFormSave"
      @close="showFormModal = false"
    />

    <ConfirmDialog
      v-if="pendingAction"
      :title="confirmCopy[pendingAction.type].title"
      :message="actionError || confirmCopy[pendingAction.type].message"
      :confirm-label="confirmCopy[pendingAction.type].label"
      :danger="confirmCopy[pendingAction.type].danger"
      :loading="actionLoading"
      @confirm="confirmPendingAction"
      @cancel="pendingAction = null"
    />

    <CredentialsModal
      v-if="credentialsAccount"
      :account="credentialsAccount"
      @close="credentialsAccount = null"
    />
  </div>
</template>

<style scoped>
.page {
  max-width: 1100px;
  margin: 1.5rem auto;
  padding: 0 1rem;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.filters {
  display: flex;
  gap: 0.75rem;
  padding: 0.9rem;
  margin-bottom: 1rem;
}
.filters input {
  flex: 1;
}
.table-wrap {
  padding: 0.5rem;
  overflow-x: auto;
}
th,
td {
  text-align: left;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid #f0f0f0;
  font-size: 0.9rem;
}
.row-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.btn-sm {
  padding: 0.3rem 0.6rem;
  font-size: 0.78rem;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
}
</style>
