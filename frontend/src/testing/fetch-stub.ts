import { expect, vi } from "vitest";

/**
 * Shared by every area's `client.test.ts`: `src/api/client.ts` captures
 * `globalThis.fetch` once, at module-evaluation time (openapi-fetch's
 * `baseFetch = globalThis.fetch` default). Stubbing the global after that
 * capture has no effect, so callers must stub first and then re-import the
 * client module fresh via `vi.resetModules()`.
 */

/**
 * Node's native `Request` (unlike a browser) refuses a relative URL outright.
 * openapi-fetch's baseUrl is "" by design (same-origin, per ADR-0001) so the
 * real client builds a relative "/api/..." request; this resolves it against
 * a dummy origin the same way a browser would resolve it against the page's
 * own origin.
 */
export class SameOriginRequest extends Request {
  constructor(input: string | URL | Request, init?: RequestInit) {
    super(
      typeof input === "string" ? new URL(input, "http://localhost") : input,
      init,
    );
  }
}

/** Stubs `fetch`/`Request` and resets the module cache so the next `import("./client")` is fresh. */
export function stubSameOriginFetch(fetchMock: typeof fetch): void {
  vi.resetModules();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("Request", SameOriginRequest);
}

/** A JSON `Response` carrying the Content-Type header `apiClient` needs to parse its body. */
export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Asserts the mock was called exactly once with the given method/pathname
 * and returns the captured `Request`, so every area's `client.test.ts` can
 * assert on its own headers/body without re-deriving this boilerplate.
 */
export function expectRequest(
  fetchMock: ReturnType<typeof vi.fn<typeof fetch>>,
  method: string,
  pathname: string,
): Request {
  expect(fetchMock).toHaveBeenCalledOnce();
  const request = fetchMock.mock.calls[0][0] as Request;
  expect(request.method).toBe(method);
  expect(new URL(request.url).pathname).toBe(pathname);
  return request;
}
