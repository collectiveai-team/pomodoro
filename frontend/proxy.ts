import { type NextRequest, NextResponse } from "next/server";

/**
 * Must match `SESSION_COOKIE_NAME` in `backend/pomodoro/core/auth_sessions.py` — the two
 * cannot share a single source of truth across languages, so keep them in sync by hand.
 */
export const SESSION_COOKIE_NAME = "session";

const PUBLIC_PATHS = ["/login", "/register"];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

/**
 * User Story 11: any route without a session cookie redirects to `/login`. This only checks
 * that the cookie is present — the backend is the sole authority on whether it is still valid
 * (ADR-0001); a stale cookie reaches a 401 from the API instead, which the client handles.
 */
export function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  if (!request.cookies.has(SESSION_COOKIE_NAME)) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
