import type { NextConfig } from "next";

/**
 * ADR-0001: the browser only ever talks to this Next.js origin. `/api/*` is rewritten
 * server-side to the FastAPI backend, so the session cookie stays first-party and no CORS is
 * needed. `BACKEND_INTERNAL_URL` is a server-only env var — never exposed to the browser.
 */
const BACKEND_INTERNAL_URL = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_INTERNAL_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
