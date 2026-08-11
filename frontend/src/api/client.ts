import axios from "axios";
import { useAuthStore } from "../stores/auth";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});

apiClient.interceptors.request.use((config) => {
  const { getToken } = useAuthStore();
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const { logout } = useAuthStore();
      logout();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (error.response?.status === 403) return "Você não tem permissão para esta ação.";
    if (error.response?.status === 404) return "Registro não encontrado.";
  }
  return "Erro inesperado. Tente novamente.";
}
