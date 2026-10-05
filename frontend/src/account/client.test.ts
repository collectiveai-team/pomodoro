import { afterEach, describe, expect, it, vi } from "vitest";
import {
  expectRequest,
  jsonResponse,
  stubSameOriginFetch,
} from "@/src/testing/fetch-stub";

async function importAccountClientWithFetch(fetchMock: typeof fetch) {
  stubSameOriginFetch(fetchMock);
  return import("./client");
}

const SETTINGS_BODY = {
  alarm_enabled: true,
  notifications_enabled: true,
  time_zone: "America/Argentina/Buenos_Aires",
};

describe("account client wrappers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("fetches the current Settings via a real GET /api/settings", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(SETTINGS_BODY),
    );
    const { fetchSettings } = await importAccountClientWithFetch(fetchMock);

    const result = await fetchSettings();

    expectRequest(fetchMock, "GET", "/api/settings");
    expect(result).toEqual({ ok: true, settings: SETTINGS_BODY });
  });

  it("updates the time zone via a real PATCH /api/settings carrying only time_zone", async () => {
    const updated = { ...SETTINGS_BODY, time_zone: "UTC" };
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(updated));
    const { updateTimeZone } = await importAccountClientWithFetch(fetchMock);

    const result = await updateTimeZone("UTC");

    const request = expectRequest(fetchMock, "PATCH", "/api/settings");
    expect(request.headers.get("content-type")).toBe("application/json");
    const body = await request.clone().json();
    expect(body).toEqual({ time_zone: "UTC" });
    expect(result).toEqual({ ok: true, settings: updated });
  });

  it("surfaces the server's message when an invalid time zone is rejected", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: "Zona horaria inválida." }, 422),
    );
    const { updateTimeZone } = await importAccountClientWithFetch(fetchMock);

    const result = await updateTimeZone("not/a-zone");

    expect(result).toEqual({
      ok: false,
      status: 422,
      message: "Zona horaria inválida.",
    });
  });

  it("changes the password via a real POST carrying current_password and new_password", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 204 }),
    );
    const { changePassword } = await importAccountClientWithFetch(fetchMock);

    const result = await changePassword("old-secret1", "new-secret1");

    const request = expectRequest(
      fetchMock,
      "POST",
      "/api/auth/change-password",
    );
    expect(request.headers.get("content-type")).toBe("application/json");
    const body = await request.clone().json();
    expect(body).toEqual({
      current_password: "old-secret1",
      new_password: "new-secret1",
    });
    expect(result).toEqual({ ok: true });
  });

  it("surfaces the server's message when the current password is wrong", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: "Contraseña incorrecta." }, 422),
    );
    const { changePassword } = await importAccountClientWithFetch(fetchMock);

    const result = await changePassword("wrong", "new-secret1");

    expect(result).toEqual({
      ok: false,
      status: 422,
      message: "Contraseña incorrecta.",
    });
  });

  it("deletes the account via a real POST carrying the confirmation password", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 204 }),
    );
    const { deleteAccount } = await importAccountClientWithFetch(fetchMock);

    const result = await deleteAccount("my-secret1");

    const request = expectRequest(
      fetchMock,
      "POST",
      "/api/auth/delete-account",
    );
    expect(request.headers.get("content-type")).toBe("application/json");
    const body = await request.clone().json();
    expect(body).toEqual({ password: "my-secret1" });
    expect(result).toEqual({ ok: true });
  });

  it("surfaces the server's message when the delete-account password is wrong", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: "Contraseña incorrecta." }, 422),
    );
    const { deleteAccount } = await importAccountClientWithFetch(fetchMock);

    const result = await deleteAccount("wrong");

    expect(result).toEqual({
      ok: false,
      status: 422,
      message: "Contraseña incorrecta.",
    });
  });
});
