import type { components } from "@/lib/api/schema";

/**
 * The Account menu edits the User's Settings while the Timer panel reads them for the Alarm and
 * notifications; this same-page broadcast hands the saved Settings across without a shared parent.
 */
export const SETTINGS_CHANGED_EVENT = "pomodoro:settings-changed";

type SettingsResponseBody = components["schemas"]["SettingsResponse"];

export function broadcastSettingsChanged(settings: SettingsResponseBody): void {
  window.dispatchEvent(new CustomEvent(SETTINGS_CHANGED_EVENT, { detail: settings }));
}

export function settingsFromEvent(event: Event): SettingsResponseBody {
  return (event as CustomEvent<SettingsResponseBody>).detail;
}
