import { apiClient } from "@/src/api/client";
import type { components } from "@/src/api/schema";
import { extractErrorMessage } from "@/src/auth/messages";
import type { TimerSnapshot } from "./engine";

/**
 * Generated-client wrappers for every `/api/timer/*` action plus the day
 * summary read. `TimerPanel` (T22) calls every action except `start`, which
 * `ActiveTab` (T24) calls instead. All actions are body-less `POST`s except
 * `start`, so each of those needs the explicit `Content-Type` header the
 * backend's `csrf_guard` middleware requires on every mutating request
 * (see `src/auth/client.ts`'s `logoutUser`, which hit the same 415 originally).
 */

export type DaySummary = components["schemas"]["DaySummaryPublic"];

export type TimerActionResult =
  | { ok: true; timer: TimerSnapshot }
  | { ok: false; status: number; message: string; timer: TimerSnapshot | null };

const JSON_HEADERS = { "Content-Type": "application/json" } as const;

/**
 * A 409 conflict's body is `{ detail: <TimerPublic> }` (see `_conflict` in
 * `pomodoro/api/timer.py`): the current, already-resynced Timer, not just an
 * error string. Extracting it lets the caller silently resync (story 68)
 * instead of surfacing a confusing error for an ordinary stale-tab race.
 */
function conflictTimer(error: unknown): TimerSnapshot | null {
  if (!error || typeof error !== "object" || !("detail" in error)) {
    return null;
  }
  const detail = (error as { detail?: unknown }).detail;
  if (
    !detail ||
    typeof detail !== "object" ||
    !("phase" in detail) ||
    !("server_now" in detail)
  ) {
    return null;
  }
  return detail as TimerSnapshot;
}

async function runTimerAction(
  call: () => Promise<{
    data?: TimerSnapshot;
    error?: unknown;
    response: Response;
  }>,
  fallbackMessage: string,
): Promise<TimerActionResult> {
  const { data, error, response } = await call();
  if (data) {
    return { ok: true, timer: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, fallbackMessage),
    timer: conflictTimer(error),
  };
}

export function startTimer(taskId: number): Promise<TimerActionResult> {
  // Unlike every other action here, `start` carries a body, so openapi-fetch
  // already sets `Content-Type: application/json` on its own.
  return runTimerAction(
    () => apiClient.POST("/api/timer/start", { body: { task_id: taskId } }),
    "No se pudo iniciar el Pomodoro.",
  );
}

export function pauseTimer(): Promise<TimerActionResult> {
  return runTimerAction(
    () => apiClient.POST("/api/timer/pause", { headers: JSON_HEADERS }),
    "No se pudo pausar.",
  );
}

export function resumeTimer(): Promise<TimerActionResult> {
  return runTimerAction(
    () => apiClient.POST("/api/timer/resume", { headers: JSON_HEADERS }),
    "No se pudo reanudar.",
  );
}

export function stopTimer(): Promise<TimerActionResult> {
  return runTimerAction(
    () => apiClient.POST("/api/timer/stop", { headers: JSON_HEADERS }),
    "No se pudo detener.",
  );
}

export function logTimer(): Promise<TimerActionResult> {
  return runTimerAction(
    () => apiClient.POST("/api/timer/log", { headers: JSON_HEADERS }),
    "No se pudo registrar el Pomodoro.",
  );
}

export function discardTimer(): Promise<TimerActionResult> {
  return runTimerAction(
    () => apiClient.POST("/api/timer/discard", { headers: JSON_HEADERS }),
    "No se pudo descartar el Pomodoro.",
  );
}

export function startBreakTimer(): Promise<TimerActionResult> {
  return runTimerAction(
    () => apiClient.POST("/api/timer/start-break", { headers: JSON_HEADERS }),
    "No se pudo iniciar el Break.",
  );
}

export function skipBreakTimer(): Promise<TimerActionResult> {
  return runTimerAction(
    () => apiClient.POST("/api/timer/skip-break", { headers: JSON_HEADERS }),
    "No se pudo saltear el Break.",
  );
}

export function nextPomodoroTimer(): Promise<TimerActionResult> {
  return runTimerAction(
    () => apiClient.POST("/api/timer/next-pomodoro", { headers: JSON_HEADERS }),
    "No se pudo iniciar otro Pomodoro.",
  );
}

export async function fetchDaySummary(): Promise<DaySummary | null> {
  const { data } = await apiClient.GET("/api/timer/summary");
  return data ?? null;
}
