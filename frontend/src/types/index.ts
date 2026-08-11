export type UserRole = "ADMIN" | "OPERATOR" | "READONLY";

export type AccountStatus = "ACTIVE" | "INACTIVE";

export interface Account {
  id: string;
  email: string;
  status: AccountStatus;
  description: string | null;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedAccounts {
  items: Account[];
  total: number;
  page: number;
  page_size: number;
}

export interface AccountCreatePayload {
  email: string;
  snov_id: string;
  snov_secret: string;
  snov_email: string;
  snov_password: string;
  description?: string | null;
}

export type AccountUpdatePayload = Partial<AccountCreatePayload>;

export interface AccountCredentials {
  account_id: string;
  snov_id: string;
  snov_secret: string;
  snov_email: string;
  snov_password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface ApiError {
  detail: string;
}
