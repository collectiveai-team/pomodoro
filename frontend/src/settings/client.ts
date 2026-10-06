import { apiClient } from "@/src/api/client";
import type { components } from "@/src/api/schema";
import { extractErrorMessage } from "@/src/auth/messages";

/**
 * Generated-client wrapper for `alarm_enabled`/`notifications_enabled`
 * (stories 69-71). Reads/writes the same `/api/settings` endpoint T14's
 * backend and T27's `src/account/client.ts` already use for `time_zone`;
 * this wrapper is kept separate because its callers (the Timer panel's
 * Alarm/notifications toggles) only ever touch these two fields.
 */

export type SettingsPublic = components["schemas"]["SettingsPublic"];

export type SettingsResult =
  | { ok: true; settings: SettingsPublic }
  | { ok: false; status: number; message: string };

export interface PreferencesPatch {
  alarm_enabled?: boolean;
  notifications_enabled?: boolean;
}

export async function fetchPreferences(): Promise<SettingsResult> {
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

export async function updatePreferences(
  patch: PreferencesPatch,
): Promise<SettingsResult> {
  const { data, error, response } = await apiClient.PATCH("/api/settings", {
    body: patch,
  });
  if (data) {
    return { ok: true, settings: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(
      error,
      "No se pudo actualizar la configuración.",
    ),
  };
}
