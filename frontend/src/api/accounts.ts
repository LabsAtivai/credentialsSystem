import { apiClient } from "./client";
import type {
  Account,
  AccountCreatePayload,
  AccountCredentials,
  AccountStatus,
  AccountUpdatePayload,
  PaginatedAccounts,
} from "../types";

export interface ListAccountsParams {
  q?: string;
  status?: AccountStatus | "";
  page?: number;
  page_size?: number;
}

export async function listAccounts(params: ListAccountsParams): Promise<PaginatedAccounts> {
  const { data } = await apiClient.get<PaginatedAccounts>("/api/accounts", {
    params: { ...params, status: params.status || undefined },
  });
  return data;
}

export async function createAccount(payload: AccountCreatePayload): Promise<Account> {
  const { data } = await apiClient.post<Account>("/api/accounts", payload);
  return data;
}

export async function updateAccount(id: string, payload: AccountUpdatePayload): Promise<Account> {
  const { data } = await apiClient.patch<Account>(`/api/accounts/${id}`, payload);
  return data;
}

export async function deleteAccount(id: string): Promise<void> {
  await apiClient.delete(`/api/accounts/${id}`);
}

export async function activateAccount(id: string): Promise<Account> {
  const { data } = await apiClient.patch<Account>(`/api/accounts/${id}/activate`);
  return data;
}

export async function deactivateAccount(id: string): Promise<Account> {
  const { data } = await apiClient.patch<Account>(`/api/accounts/${id}/deactivate`);
  return data;
}

export async function getAccountCredentials(id: string): Promise<AccountCredentials> {
  const { data } = await apiClient.get<AccountCredentials>(
    `/api/internal/accounts/${id}/credentials`,
  );
  return data;
}
