/** Routes that never require a session; every other route must gate on one. */
export const PUBLIC_PATHS: ReadonlySet<string> = new Set([
  "/login",
  "/register",
]);

export type SessionChecker = () => Promise<{ ok: boolean }>;

export type SessionGateOutcome = "public" | "authenticated" | "redirected";

/**
 * Pure gating decision behind the client-side session gate: bypass public
 * routes, otherwise ask `checkSession` (a GET /api/auth/me call in practice)
 * and redirect to /login on any non-ok (401) result.
 */
export async function requireSession(options: {
  pathname: string;
  checkSession: SessionChecker;
  redirectToLogin: () => void;
}): Promise<SessionGateOutcome> {
  if (PUBLIC_PATHS.has(options.pathname)) {
    return "public";
  }

  const result = await options.checkSession();
  if (!result.ok) {
    options.redirectToLogin();
    return "redirected";
  }

  return "authenticated";
}
