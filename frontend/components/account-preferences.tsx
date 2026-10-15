"use client";

import { useState } from "react";
import { requestNotificationPermission } from "@/lib/alarm";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { broadcastSettingsChanged } from "@/lib/settings-sync";

type SettingsResponseBody = components["schemas"]["SettingsResponse"];
type TogglePatch = Partial<Pick<SettingsResponseBody, "alarm_enabled" | "notifications_enabled">>;

interface AccountPreferencesProps {
  settings: SettingsResponseBody;
  onSaved: (settings: SettingsResponseBody) => void;
  onError: (message: string) => void;
}

/** Alarm and notification toggles, each saving a partial Settings PATCH (Timer panel reads them). */
export function AccountPreferences({ settings, onSaved, onError }: AccountPreferencesProps) {
  const [permissionDenied, setPermissionDenied] = useState(false);

  async function save(partial: TogglePatch) {
    const { data, error, response } = await apiClient.PATCH("/api/v1/settings", {
      body: partial,
    });
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (error !== undefined || !data) {
      onError(toApiError(error).message);
      return;
    }
    onSaved(data);
    broadcastSettingsChanged(data);
  }

  async function toggleNotifications() {
    const enable = !settings.notifications_enabled;
    if (enable) {
      const denied = (await requestNotificationPermission()) === "denied";
      setPermissionDenied(denied);
      if (denied) {
        return;
      }
    } else {
      setPermissionDenied(false);
    }
    await save({ notifications_enabled: enable });
  }

  return (
    <div className="flex flex-col gap-1 text-sm">
      <label className="flex min-h-8 items-center gap-2">
        <input
          type="checkbox"
          checked={settings.alarm_enabled}
          onChange={() => save({ alarm_enabled: !settings.alarm_enabled })}
        />
        Alarm
      </label>
      <label className="flex min-h-8 items-center gap-2">
        <input
          type="checkbox"
          checked={settings.notifications_enabled}
          onChange={toggleNotifications}
        />
        Notificaciones
      </label>
      {permissionDenied ? (
        <p className="text-muted">Permiso de notificaciones denegado por el navegador.</p>
      ) : null}
    </div>
  );
}
