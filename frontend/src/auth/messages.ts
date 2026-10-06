/** Pulls a user-facing message out of an `/api/*` error body, falling back when absent. */
export function extractErrorMessage(error: unknown, fallback: string): string {
  if (!error || typeof error !== "object" || !("detail" in error)) {
    return fallback;
  }

  const detail = (error as { detail?: unknown }).detail;

  if (typeof detail === "string" && detail.length > 0) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first && typeof first === "object" && "msg" in first) {
      const msg = (first as { msg?: unknown }).msg;
      if (typeof msg === "string" && msg.length > 0) {
        return msg;
      }
    }
  }

  return fallback;
}
