import createClient from "openapi-fetch";
import type { paths } from "./schema";

/**
 * Typed HTTP client for the backend's `/api/*` surface.
 *
 * Same-origin by design (ADR-0001): the browser only ever talks to Next.js,
 * which rewrites `/api/*` to FastAPI, so no base URL/CORS handling is needed.
 */
export const apiClient = createClient<paths>({ baseUrl: "" });
