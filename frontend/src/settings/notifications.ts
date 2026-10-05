/**
 * Browser notifications for a phase that ended on its own (story 70, 61,
 * 57). The Notification API's permission is a one-way ratchet once denied:
 * browsers themselves refuse to re-prompt, and this module mirrors that by
 * never calling `requestPermission()` again once `permission === "denied"`,
 * so the UI only ever needs to reflect the current state.
 */

export type PermissionState = "granted" | "denied" | "default" | "unsupported";

export interface NotificationApi {
  permission: NotificationPermission;
  requestPermission(): Promise<NotificationPermission>;
}

export type NotificationConstructorApi = NotificationApi &
  (new (
    title: string,
    options?: NotificationOptions,
  ) => unknown);

function defaultApi(): NotificationConstructorApi | undefined {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return undefined;
  }
  return window.Notification as unknown as NotificationConstructorApi;
}

export function currentPermission(
  api: NotificationApi | undefined = defaultApi(),
): PermissionState {
  if (!api) {
    return "unsupported";
  }
  return api.permission;
}

/** Requests permission unless it is already `denied`, which is never re-prompted. */
export async function requestPermission(
  api: NotificationApi | undefined = defaultApi(),
): Promise<PermissionState> {
  if (!api) {
    return "unsupported";
  }
  if (api.permission === "denied") {
    return "denied";
  }
  return await api.requestPermission();
}

/** Fires a Notification only if permission is currently granted; a no-op otherwise. */
export function notifyPhaseEnd(
  title: string,
  body: string,
  api: NotificationConstructorApi | undefined = defaultApi(),
): void {
  if (!api || api.permission !== "granted") {
    return;
  }
  new api(title, { body });
}
