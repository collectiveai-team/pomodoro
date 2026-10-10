import createClient from "openapi-fetch";
import type { paths } from "./api/schema";

/**
 * Relative base URL: the browser only ever talks to this Next.js origin (ADR-0001). `/api/*`
 * requests are rewritten server-side to the FastAPI backend by `next.config.ts`, so the
 * session cookie travels first-party with no CORS.
 */
export const apiClient = createClient<paths>({ baseUrl: "" });
