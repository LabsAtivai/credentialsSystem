import { computed, reactive } from "vue";
import type { UserRole } from "../types";

interface JwtPayload {
  sub: string;
  role: UserRole;
  exp: number;
}

const STORAGE_KEY = "snov_am_token";

function decodeToken(token: string): JwtPayload | null {
  try {
    const [, payload] = token.split(".");
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

const state = reactive({
  token: sessionStorage.getItem(STORAGE_KEY) as string | null,
});

function isExpired(payload: JwtPayload): boolean {
  return payload.exp * 1000 <= Date.now();
}

export function useAuthStore() {
  const payload = computed(() => (state.token ? decodeToken(state.token) : null));

  const isAuthenticated = computed(() => {
    if (!state.token || !payload.value) return false;
    return !isExpired(payload.value);
  });

  const role = computed<UserRole | null>(() => payload.value?.role ?? null);

  function setToken(token: string) {
    state.token = token;
    sessionStorage.setItem(STORAGE_KEY, token);
  }

  function logout() {
    state.token = null;
    sessionStorage.removeItem(STORAGE_KEY);
  }

  function getToken(): string | null {
    return state.token;
  }

  return { isAuthenticated, role, setToken, logout, getToken };
}
