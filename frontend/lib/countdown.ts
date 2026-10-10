/**
 * Pure countdown math for the Timer panel (ADR-0001: the frontend projects the server's Timer
 * forward in time, it never re-derives Timer domain rules). Every function here takes the exact
 * fields `TimerResponse` already returns, plus a client clock reading, and nothing else.
 */

/** Client-observed offset between the server's clock and this browser's clock. */
export interface ClockSync {
  readonly offsetMs: number;
}

/** Captures the skew between `serverNowIso` and the client clock at fetch time. */
export function syncClock(serverNowIso: string, clientNowMs: number): ClockSync {
  return { offsetMs: new Date(serverNowIso).getTime() - clientNowMs };
}

/**
 * Projects the server's `remaining_seconds` (as of `serverNowIso`) forward to `clientNowMs`,
 * correcting for clock skew via `sync`. Clamped at zero — a stale local tick never goes negative.
 */
export function correctedRemainingSeconds(params: {
  remainingSecondsAtFetch: number;
  serverNowIso: string;
  sync: ClockSync;
  clientNowMs: number;
}): number {
  const estimatedServerNowMs = params.clientNowMs + params.sync.offsetMs;
  const serverNowAtFetchMs = new Date(params.serverNowIso).getTime();
  const elapsedSeconds = Math.floor((estimatedServerNowMs - serverNowAtFetchMs) / 1000);
  return Math.max(0, params.remainingSecondsAtFetch - elapsedSeconds);
}

/**
 * The phase's total duration, derived from server-given fields rather than a hardcoded
 * 25/5/10-minute constant, so the ring never has to know Pomodoro/Break durations itself.
 */
export function phaseTotalSeconds(params: {
  remainingSecondsAtFetch: number | null;
  accumulatedActiveSeconds: number;
  runningSinceIso: string | null;
  serverNowIso: string;
}): number | null {
  if (params.remainingSecondsAtFetch === null) {
    return null;
  }
  const elapsedWhileRunning = params.runningSinceIso
    ? Math.floor(
        (new Date(params.serverNowIso).getTime() - new Date(params.runningSinceIso).getTime()) /
          1000,
      )
    : 0;
  const activeSecondsAtFetch = params.accumulatedActiveSeconds + elapsedWhileRunning;
  return params.remainingSecondsAtFetch + activeSecondsAtFetch;
}

/** The fraction of the phase still remaining, clamped to `[0, 1]` for ring rendering. */
export function remainingFraction(remainingSeconds: number, totalSeconds: number | null): number {
  if (totalSeconds === null || totalSeconds <= 0) {
    return 0;
  }
  return Math.min(1, Math.max(0, remainingSeconds / totalSeconds));
}

/** Formats whole seconds as `MM:SS` for the ring's remaining-time label. */
export function formatClock(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/** Rounds the Timer's accumulated active time to the whole minutes shown in "¿Registrar N min?". */
export function minutesForLog(accumulatedActiveSeconds: number): number {
  return Math.round(accumulatedActiveSeconds / 60);
}
