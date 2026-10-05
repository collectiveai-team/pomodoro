import { apiClient } from "@/src/api/client";
import type { components } from "@/src/api/schema";
import { extractErrorMessage } from "./messages";

export type UserPublic = components["schemas"]["UserPublic"];

export type AuthResult =
  | { ok: true; user: UserPublic }
  | { ok: false; status: number; message: string };

export type SessionCheck =
  | { ok: true; user: UserPublic }
  | { ok: false; status: number };

export async function registerUser(input: {
  email: string;
  password: string;
  time_zone: string;
}): Promise<AuthResult> {
  const { data, error, response } = await apiClient.POST("/api/auth/register", {
    body: input,
  });
  if (data) {
    return { ok: true, user: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, "No se pudo completar el registro."),
  };
}

export async function loginUser(input: {
  email: string;
  password: string;
}): Promise<AuthResult> {
  const { data, error, response } = await apiClient.POST("/api/auth/login", {
    body: input,
  });
  if (data) {
    return { ok: true, user: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, "No se pudo iniciar sesión."),
  };
}

export async function logoutUser(): Promise<{ ok: boolean }> {
  // The backend's csrf_guard middleware rejects any mutating request that
  // lacks Content-Type: application/json, including this body-less one.
  const { response } = await apiClient.POST("/api/auth/logout", {
    headers: { "Content-Type": "application/json" },
  });
  return { ok: response.ok };
}

export async function fetchCurrentUser(): Promise<SessionCheck> {
  const { data, response } = await apiClient.GET("/api/auth/me");
  if (data) {
    return { ok: true, user: data };
  }
  return { ok: false, status: response.status };
}
