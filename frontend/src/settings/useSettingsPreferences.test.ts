// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  expectRequest,
  jsonResponse,
  stubSameOriginFetch,
} from "@/src/testing/fetch-stub";

/**
 * Exercises the real orchestration hook (not just the pure `alarm.ts` /
 * `notifications.ts` modules it composes), per the T23 finding that
 * reverting its disable-gate or permission branches passed every other
 * test. `fetch` is stubbed the same way `client.test.ts` does; `Audio` and
 * `Notification` are stubbed globals so the hook's own `createAlarmPlayer()`
 * and `currentPermission()`/`requestPermission()` calls (which take no
 * injected fakes here, unlike their own unit tests) never touch real
 * browser APIs jsdom doesn't implement.
 */

class FakeAudio {
  currentTime = 0;
  src: string;
  play = vi.fn(() => Promise.resolve());
  pause = vi.fn();
  constructor(src: string) {
    this.src = src;
  }
}

function installFakeNotification(
  permission: NotificationPermission,
  requestResult: NotificationPermission = permission,
) {
  const requestPermissionMock = vi.fn(async () => requestResult);
  function FakeNotification(
    this: unknown,
    _title: string,
    _options?: NotificationOptions,
  ) {}
  Object.defineProperty(FakeNotification, "permission", {
    get: () => permission,
    configurable: true,
  });
  (
    FakeNotification as unknown as {
      requestPermission: typeof requestPermissionMock;
    }
  ).requestPermission = requestPermissionMock;
  Object.defineProperty(window, "Notification", {
    value: FakeNotification,
    configurable: true,
    writable: true,
  });
  return requestPermissionMock;
}

function settingsBody(overrides: {
  alarm_enabled: boolean;
  notifications_enabled: boolean;
}) {
  return {
    alarm_enabled: overrides.alarm_enabled,
    notifications_enabled: overrides.notifications_enabled,
    time_zone: "America/Argentina/Buenos_Aires",
  };
}

async function renderSettingsHook(fetchMock: typeof fetch) {
  stubSameOriginFetch(fetchMock);
  const { useSettingsPreferences } = await import("./useSettingsPreferences");
  const view = renderHook(() => useSettingsPreferences());
  await waitFor(() => expect(view.result.current.loading).toBe(false));
  return view;
}

describe("useSettingsPreferences", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
    vi.doUnmock("./notifications");
    Object.defineProperty(window, "Notification", {
      value: undefined,
      configurable: true,
      writable: true,
    });
  });

  it("populates alarmEnabled/notificationsEnabled from the fetched settings on mount", async () => {
    vi.stubGlobal("Audio", FakeAudio);
    installFakeNotification("default");
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(
        settingsBody({ alarm_enabled: false, notifications_enabled: true }),
      ),
    );

    const { result } = await renderSettingsHook(fetchMock);

    expectRequest(fetchMock, "GET", "/api/settings");
    expect(result.current.alarmEnabled).toBe(false);
    expect(result.current.notificationsEnabled).toBe(true);
  });

  it("never plays the Alarm when disabled, but plays it when enabled (story 69)", async () => {
    installFakeNotification("default");
    const audioInstances: FakeAudio[] = [];
    class TrackedAudio extends FakeAudio {
      constructor(src: string) {
        super(src);
        audioInstances.push(this);
      }
    }
    vi.stubGlobal("Audio", TrackedAudio);

    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(
        settingsBody({ alarm_enabled: false, notifications_enabled: false }),
      ),
    );
    const { result } = await renderSettingsHook(fetchMock);
    expect(result.current.alarmEnabled).toBe(false);

    act(() => {
      result.current.triggerPhaseEndEffects("Foco");
    });
    expect(audioInstances).toHaveLength(0);

    await act(async () => {
      await result.current.setAlarmEnabled(true);
    });
    expect(result.current.alarmEnabled).toBe(true);

    act(() => {
      result.current.triggerPhaseEndEffects("Foco");
    });
    expect(audioInstances).toHaveLength(1);
    expect(audioInstances[0]?.play).toHaveBeenCalledOnce();
  });

  it("never re-prompts a denied Notification permission (story 70)", async () => {
    // Mocks the "./notifications" module directly (not just the global
    // Notification object) so this exercises the hook's own denied-permission
    // short-circuit in `setNotificationsEnabled`, isolated from the fact
    // that `notifications.ts`'s own `requestPermission()` independently
    // refuses to re-prompt once already denied. The mocked
    // `requestPermission` resolves to "granted" -- a different outcome than
    // the denied short-circuit -- so if the hook's branch were deleted, it
    // would call through to this mock, get "granted", and fail the
    // assertions below instead of accidentally passing via the lower
    // layer's own guard.
    vi.stubGlobal("Audio", FakeAudio);
    const requestPermissionMock = vi.fn(
      async (): Promise<"granted"> => "granted",
    );
    const currentPermissionMock = vi.fn((): "denied" => "denied");
    vi.doMock("./notifications", () => ({
      currentPermission: currentPermissionMock,
      requestPermission: requestPermissionMock,
      notifyPhaseEnd: vi.fn(),
    }));
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(
        settingsBody({ alarm_enabled: true, notifications_enabled: false }),
      ),
    );
    const { result } = await renderSettingsHook(fetchMock);

    await act(async () => {
      await result.current.setNotificationsEnabled(true);
    });

    expect(requestPermissionMock).not.toHaveBeenCalled();
    expect(result.current.notificationPermission).toBe("denied");
    expect(result.current.notificationsEnabled).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("requests permission and PATCHes notifications_enabled true once granted (story 70, 71)", async () => {
    vi.stubGlobal("Audio", FakeAudio);
    const requestPermissionMock = installFakeNotification("default", "granted");
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const request = input as Request;
      if (request.method === "PATCH") {
        return jsonResponse(
          settingsBody({ alarm_enabled: true, notifications_enabled: true }),
        );
      }
      return jsonResponse(
        settingsBody({ alarm_enabled: true, notifications_enabled: false }),
      );
    });
    const { result } = await renderSettingsHook(fetchMock);
    fetchMock.mockClear();

    await act(async () => {
      await result.current.setNotificationsEnabled(true);
    });

    expect(requestPermissionMock).toHaveBeenCalledOnce();
    expect(result.current.notificationPermission).toBe("granted");
    expect(result.current.notificationsEnabled).toBe(true);
    const request = expectRequest(fetchMock, "PATCH", "/api/settings");
    const body = await request.clone().json();
    expect(body).toEqual({ notifications_enabled: true });
  });
});
