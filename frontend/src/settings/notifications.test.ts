import { describe, expect, it, vi } from "vitest";
import {
  currentPermission,
  type NotificationConstructorApi,
  notifyPhaseEnd,
  requestPermission,
} from "./notifications";

function fakeNotificationApi(
  permission: NotificationPermission,
  requestResult: NotificationPermission = permission,
): NotificationConstructorApi {
  const requestPermissionMock = vi.fn(async () => requestResult);
  function FakeNotification(
    this: unknown,
    _title: string,
    _options?: NotificationOptions,
  ) {}
  Object.defineProperty(FakeNotification, "permission", {
    get: () => permission,
  });
  (
    FakeNotification as unknown as {
      requestPermission: typeof requestPermissionMock;
    }
  ).requestPermission = requestPermissionMock;
  return FakeNotification as unknown as NotificationConstructorApi;
}

describe("currentPermission", () => {
  it("reports unsupported when there is no Notification API", () => {
    expect(currentPermission(undefined)).toBe("unsupported");
  });

  it("reports the API's current permission", () => {
    expect(currentPermission(fakeNotificationApi("granted"))).toBe("granted");
    expect(currentPermission(fakeNotificationApi("default"))).toBe("default");
    expect(currentPermission(fakeNotificationApi("denied"))).toBe("denied");
  });
});

describe("requestPermission", () => {
  it("is unsupported with no Notification API", async () => {
    await expect(requestPermission(undefined)).resolves.toBe("unsupported");
  });

  it("requests permission and returns the browser's answer", async () => {
    const api = fakeNotificationApi("default", "granted");

    const result = await requestPermission(api);

    expect(result).toBe("granted");
    expect(api.requestPermission).toHaveBeenCalledOnce();
  });

  it("never re-prompts once denied; it just reports the denied state (story 70)", async () => {
    const api = fakeNotificationApi("denied");

    const result = await requestPermission(api);

    expect(result).toBe("denied");
    expect(api.requestPermission).not.toHaveBeenCalled();
  });
});

describe("notifyPhaseEnd", () => {
  it("does nothing when unsupported", () => {
    expect(() => notifyPhaseEnd("Pomodoro", "done", undefined)).not.toThrow();
  });

  it("does nothing when permission is not granted", () => {
    const api = fakeNotificationApi("default");
    const ctor = vi.fn();
    const Spyable = new Proxy(api, {
      construct: (_target, args) => {
        ctor(...args);
        return {};
      },
    });

    notifyPhaseEnd("Pomodoro", "done", Spyable as NotificationConstructorApi);

    expect(ctor).not.toHaveBeenCalled();
  });

  it("constructs a real Notification when permission is granted", () => {
    const api = fakeNotificationApi("granted");
    const ctor = vi.fn();
    const Spyable = new Proxy(api, {
      construct: (_target, args) => {
        ctor(...args);
        return {};
      },
    });

    notifyPhaseEnd(
      "Pomodoro Collective",
      "Pomodoro completado",
      Spyable as NotificationConstructorApi,
    );

    expect(ctor).toHaveBeenCalledWith("Pomodoro Collective", {
      body: "Pomodoro completado",
    });
  });
});
