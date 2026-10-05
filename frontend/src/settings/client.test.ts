import { afterEach, describe, expect, it, vi } from "vitest";
import {
  expectRequest,
  jsonResponse,
  stubSameOriginFetch,
} from "@/src/testing/fetch-stub";

async function importSettingsClientWithFetch(fetchMock: typeof fetch) {
  stubSameOriginFetch(fetchMock);
  return import("./client");
}

const SETTINGS_BODY = {
  alarm_enabled: true,
  notifications_enabled: false,
  time_zone: "America/Argentina/Buenos_Aires",
};

describe("settings client wrappers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("fetches the current preferences via a real GET /api/settings", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(SETTINGS_BODY),
    );
    const { fetchPreferences } = await importSettingsClientWithFetch(fetchMock);

    const result = await fetchPreferences();

    expectRequest(fetchMock, "GET", "/api/settings");
    expect(result).toEqual({ ok: true, settings: SETTINGS_BODY });
  });

  it("updates only alarm_enabled via a real PATCH /api/settings", async () => {
    const updated = { ...SETTINGS_BODY, alarm_enabled: false };
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(updated));
    const { updatePreferences } =
      await importSettingsClientWithFetch(fetchMock);

    const result = await updatePreferences({ alarm_enabled: false });

    const request = expectRequest(fetchMock, "PATCH", "/api/settings");
    expect(request.headers.get("content-type")).toBe("application/json");
    const body = await request.clone().json();
    expect(body).toEqual({ alarm_enabled: false });
    expect(result).toEqual({ ok: true, settings: updated });
  });

  it("updates only notifications_enabled via a real PATCH /api/settings", async () => {
    const updated = { ...SETTINGS_BODY, notifications_enabled: true };
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(updated));
    const { updatePreferences } =
      await importSettingsClientWithFetch(fetchMock);

    const result = await updatePreferences({ notifications_enabled: true });

    const request = expectRequest(fetchMock, "PATCH", "/api/settings");
    const body = await request.clone().json();
    expect(body).toEqual({ notifications_enabled: true });
    expect(result).toEqual({ ok: true, settings: updated });
  });

  it("surfaces the server's message when the update is rejected", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: "No se pudo actualizar." }, 422),
    );
    const { updatePreferences } =
      await importSettingsClientWithFetch(fetchMock);

    const result = await updatePreferences({ alarm_enabled: true });

    expect(result).toEqual({
      ok: false,
      status: 422,
      message: "No se pudo actualizar.",
    });
  });
});
