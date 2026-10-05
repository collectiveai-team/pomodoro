import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `src/api/client.ts` captures `globalThis.fetch` once, at module-evaluation
 * time (openapi-fetch's `baseFetch = globalThis.fetch` default). Stubbing
 * the global after that capture has no effect, so each test stubs first and
 * then re-imports the module fresh via `vi.resetModules()`.
 */
/**
 * Node's native `Request` (unlike a browser) refuses a relative URL outright.
 * openapi-fetch's baseUrl is "" by design (same-origin, per ADR-0001) so the
 * real client builds a relative "/api/..." request; this resolves it against
 * a dummy origin the same way a browser would resolve it against the page's
 * own origin.
 */
class SameOriginRequest extends Request {
  constructor(input: string | URL | Request, init?: RequestInit) {
    super(
      typeof input === "string" ? new URL(input, "http://localhost") : input,
      init,
    );
  }
}

async function importLogoutUserWithFetch(fetchMock: typeof fetch) {
  vi.resetModules();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("Request", SameOriginRequest);
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
