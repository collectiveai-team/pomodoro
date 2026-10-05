import type { NextConfig } from "next";

// /api/* proxying to the backend is handled by proxy.ts, not here: a
// `rewrites()` destination is resolved once by `next build` and frozen into
// .next/routes-manifest.json, so in the standalone Docker image it would bake
// in whatever BACKEND_ORIGIN happened to be set at build time instead of
// reading it per-request from the running container's environment.
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
