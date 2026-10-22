import { api, ApiError } from "@/api/client";

export interface AuthUser {
  username: string;
  name: string;
  email: string;
}

export interface AuthState {
  authEnabled: boolean;
  user: AuthUser | null;
}

export const AUTH_ME_KEY = ["auth", "me"] as const;
export const SIGNED_OUT: AuthState = { authEnabled: true, user: null };

export async function fetchMe(): Promise<AuthState> {
  try {
    return await api<AuthState>("/api/v1/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return SIGNED_OUT;
    throw error;
  }
}

export function login(email: string, password: string) {
  return api<AuthState>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}

export function logout() {
  return api<void>("/api/v1/auth/logout", { method: "POST" });
}
