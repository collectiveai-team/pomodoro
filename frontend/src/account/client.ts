import { apiClient } from "@/src/api/client";
import type { components } from "@/src/api/schema";
import { extractErrorMessage } from "@/src/auth/messages";

/**
 * Generated-client wrappers `AccountMenu` (T27) depends on: reading/updating
 * the current User's Settings (time_zone) and the password-confirmed
 * change-password/delete-account actions. Logout is deliberately not
 * re-wrapped here; `AccountMenu` reuses `logoutUser` from `@/src/auth/client`.
 */

export type SettingsPublic = components["schemas"]["SettingsPublic"];

export type SettingsResult =
  | { ok: true; settings: SettingsPublic }
  | { ok: false; status: number; message: string };

export type ActionResult =
  | { ok: true }
  | { ok: false; status: number; message: string };

export async function fetchSettings(): Promise<SettingsResult> {
  const { data, error, response } = await apiClient.GET("/api/settings");
  if (data) {
    return { ok: true, settings: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, "No se pudo cargar la configuración."),
  };
}

export async function updateTimeZone(
  timeZone: string,
): Promise<SettingsResult> {
  const { data, error, response } = await apiClient.PATCH("/api/settings", {
    body: { time_zone: timeZone },
  });
  if (data) {
    return { ok: true, settings: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(
      error,
      "No se pudo actualizar la zona horaria.",
    ),
  };
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<ActionResult> {
  const { error, response } = await apiClient.POST(
    "/api/auth/change-password",
    {
      body: { current_password: currentPassword, new_password: newPassword },
    },
  );
  if (response.ok) {
    return { ok: true };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, "No se pudo cambiar la contraseña."),
  };
}

export async function deleteAccount(password: string): Promise<ActionResult> {
  const { error, response } = await apiClient.POST("/api/auth/delete-account", {
    body: { password },
  });
  if (response.ok) {
    return { ok: true };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, "No se pudo eliminar la cuenta."),
  };
}
