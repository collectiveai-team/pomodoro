import { describe, expect, it, vi } from "vitest";
import { requireSession } from "./require-session";

describe("requireSession", () => {
  it("skips the session check entirely on a public route", async () => {
    const checkSession = vi.fn();
    const redirectToLogin = vi.fn();

    const outcome = await requireSession({
      pathname: "/login",
      checkSession,
      redirectToLogin,
    });

    expect(outcome).toBe("public");
    expect(checkSession).not.toHaveBeenCalled();
    expect(redirectToLogin).not.toHaveBeenCalled();
  });

  it("lets the route render when the session check succeeds", async () => {
    const redirectToLogin = vi.fn();

    const outcome = await requireSession({
      pathname: "/",
      checkSession: async () => ({ ok: true }),
      redirectToLogin,
    });

    expect(outcome).toBe("authenticated");
    expect(redirectToLogin).not.toHaveBeenCalled();
  });

  it("redirects to /login when GET /api/auth/me comes back 401", async () => {
    const redirectToLogin = vi.fn();

    const outcome = await requireSession({
      pathname: "/",
      checkSession: async () => ({ ok: false }),
      redirectToLogin,
    });

    expect(outcome).toBe("redirected");
    expect(redirectToLogin).toHaveBeenCalledOnce();
  });

  it("gates any protected route, not just a hardcoded one", async () => {
    const redirectToLogin = vi.fn();

    const outcome = await requireSession({
      pathname: "/some/deep/route",
      checkSession: async () => ({ ok: false }),
      redirectToLogin,
    });

    expect(outcome).toBe("redirected");
    expect(redirectToLogin).toHaveBeenCalledOnce();
  });
});
