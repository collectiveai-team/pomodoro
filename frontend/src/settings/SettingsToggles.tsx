"use client";

/**
 * Alarm/notifications preference toggles shown in the Timer panel (stories
 * 69-71, layout spec). Purely presentational: `TimerPanel` owns the state
 * via `useSettingsPreferences` and passes it down, so this component has no
 * data fetching of its own to mock in tests.
 */
export interface SettingsTogglesProps {
  loading: boolean;
  alarmEnabled: boolean;
  notificationsEnabled: boolean;
  notificationPermission: "granted" | "denied" | "default" | "unsupported";
  onToggleAlarm: (next: boolean) => void;
  onToggleNotifications: (next: boolean) => void;
}

export function SettingsToggles({
  loading,
  alarmEnabled,
  notificationsEnabled,
  notificationPermission,
  onToggleAlarm,
  onToggleNotifications,
}: SettingsTogglesProps) {
  if (loading) {
    return <p className="text-sm text-ink/60">Cargando preferencias…</p>;
  }

  const notificationsBlocked = notificationPermission === "denied";

  return (
    <div className="flex flex-wrap items-center gap-4 text-sm text-ink">
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          checked={alarmEnabled}
          onChange={(event) => onToggleAlarm(event.target.checked)}
          aria-label="Alarm"
        />
        Alarm
      </label>

      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          checked={notificationsEnabled}
          disabled={notificationsBlocked && !notificationsEnabled}
          onChange={(event) => onToggleNotifications(event.target.checked)}
          aria-label="Notificaciones"
        />
        Notificaciones
        {notificationsBlocked ? (
          <span className="text-ink/60">(bloqueadas por el navegador)</span>
        ) : null}
      </label>
    </div>
  );
}
