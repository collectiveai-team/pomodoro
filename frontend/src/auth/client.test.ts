import { afterEach, describe, expect, it, vi } from "vitest";
import { stubSameOriginFetch } from "@/src/testing/fetch-stub";

async function importLogoutUserWithFetch(fetchMock: typeof fetch) {
  stubSameOriginFetch(fetchMock);
  const { logoutUser } = await import("./client");
  return logoutUser;
}

describe("logoutUser", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("sends Content-Type: application/json so the backend's csrf_guard middleware accepts the body-less POST", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 204 }),
    );
    const logoutUser = await importLogoutUserWithFetch(fetchMock);

    const result = await logoutUser();

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledOnce();
    const request = fetchMock.mock.calls[0][0] as Request;
    expect(request.method).toBe("POST");
    expect(request.headers.get("content-type")).toBe("application/json");
  });

  it("reports failure instead of claiming success when the server rejects the request", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(
          JSON.stringify({ detail: "Content-Type must be application/json" }),
          {
            status: 415,
          },
        ),
    );
    const logoutUser = await importLogoutUserWithFetch(fetchMock);

    const result = await logoutUser();

    expect(result.ok).toBe(false);
  });
});
