import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { proxy, SESSION_COOKIE_NAME } from "./proxy";

function makeRequest(pathname: string, { withSession = false } = {}): NextRequest {
  const request = new NextRequest(new URL(pathname, "https://app.example.com"));
  if (withSession) {
    request.cookies.set(SESSION_COOKIE_NAME, "a-session-token");
  }
  return request;
}

describe("proxy", () => {
  it("redirects an unauthenticated visitor away from a protected route to /login", () => {
    const response = proxy(makeRequest("/"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://app.example.com/login");
  });

  it("lets an authenticated visitor reach a protected route", () => {
    const response = proxy(makeRequest("/", { withSession: true }));

    expect(response.status).toBe(200);
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("lets an unauthenticated visitor reach /login without redirecting", () => {
    const response = proxy(makeRequest("/login"));

    expect(response.status).toBe(200);
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("lets an unauthenticated visitor reach /register without redirecting", () => {
    const response = proxy(makeRequest("/register"));

    expect(response.status).toBe(200);
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });
});
