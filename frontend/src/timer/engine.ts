import { apiClient } from "@/src/api/client";
import type { components } from "@/src/api/schema";
import { extractErrorMessage } from "@/src/auth/messages";

/**
 * Client-side Timer countdown engine (infrastructure only, no UI).
 *
 * The server is the sole owner of Timer truth (ADR-0003): it never ticks in
 * the background and only resolves a phase lazily, on read or action. This
 * engine turns one `TimerPublic` snapshot into a locally ticking countdown
 * between server round-trips, re-fetching on focus/visibility regain, after
 * every action, and when the local countdown reaches zero (stories 64-68).
 * No WebSocket/SSE: polling at those three trigger points is the only sync
 * mechanism, per the spec's explicit "Out of Scope".
 */

export type TimerSnapshot = components["schemas"]["TimerPublic"];

const NATURAL_COMPLETION_TRANSITIONS: ReadonlyArray<
  readonly [from: string, to: string]
> = [
  // A Pomodoro that reaches 25 min of active time on its own.
  ["pomodoro_running", "ready_for_next"],
  // A Break that reaches its duration on its own.
  ["break_running", "idle"],
];

/**
 * Whether a phase transition represents a phase that ended "on its own"
 * (story 66, 61) rather than one the User ended themselves via stop/skip.
 *
 * This is a plain phase-diff, deliberately blind to *why* the transition
 * happened: `break_running -> idle` is the destination of both a Break
 * ending naturally and a User-initiated skip, so the caller (`applySnapshot`
 * below) must track provenance (`causedByAction`) separately rather than
 * relying on this function alone to withhold the alarm for a skip.
 */
export function isNaturalCompletion(
  fromPhase: string | null,
  toPhase: string,
): boolean {
  if (fromPhase === null) {
    return false;
  }
  return NATURAL_COMPLETION_TRANSITIONS.some(
    ([from, to]) => from === fromPhase && to === toPhase,
  );
}

/**
 * The remaining seconds at `nowClientMs`, derived from a snapshot fetched at
 * `fetchedAtClientMs`, correcting for clock skew between client and server.
 *
 * The client's own clock may disagree with the server's by any constant
 * offset. Anchoring the countdown on the client's *elapsed* time since the
 * fetch (rather than comparing the server's absolute `server_now` against
 * the client's current absolute time) cancels that offset out: the engine
 * never has to assume the two clocks agree, only that the client's own
 * clock moves at the same rate between one read and the next.
 */
export function remainingSecondsAt(
  snapshot: Pick<TimerSnapshot, "remaining_seconds" | "server_now">,
  fetchedAtClientMs: number,
  nowClientMs: number,
): number | null {
  if (snapshot.remaining_seconds === null) {
    return null;
  }
  const serverNowMs = Date.parse(snapshot.server_now);
  const clockOffsetMs = serverNowMs - fetchedAtClientMs;
  const estimatedServerNowMs = nowClientMs + clockOffsetMs;
  const elapsedServerSeconds = Math.floor(
    (estimatedServerNowMs - serverNowMs) / 1000,
  );
  return Math.max(snapshot.remaining_seconds - elapsedServerSeconds, 0);
}

/**
 * Whether the *previous* snapshot's own countdown would already have reached
 * zero by `nowClientMs`, judged purely from this client's elapsed time.
 *
 * `isNaturalCompletion` is a blind phase-diff: `break_running -> idle` is the
 * destination of both a Break ending on its own and a Break skipped from
 * *another* tab or device (story 65 promises one shared Timer across both).
 * A skip can arrive at any remaining time, so the elapsed-time check below is
 * what actually tells the two apart: if the skip happened well before the
 * Break's own countdown would have hit zero, this client's own clock proves
 * it, and the Alarm must stay silent (story 60).
 */
function previouslyRanOutClientSide(
  previousSnapshot: TimerSnapshot | null,
  previousFetchedAtClientMs: number | null,
  nowClientMs: number,
): boolean {
  if (previousSnapshot === null || previousFetchedAtClientMs === null) {
    return false;
  }
  const projectedRemaining = remainingSecondsAt(
    previousSnapshot,
    previousFetchedAtClientMs,
    nowClientMs,
  );
  return projectedRemaining !== null && projectedRemaining <= 0;
}

async function defaultFetchTimer(): Promise<TimerSnapshot> {
  const { data, error } = await apiClient.GET("/api/timer");
  if (!data) {
    throw new Error(extractErrorMessage(error, "No se pudo obtener el Timer."));
  }
  return data;
}

function defaultSubscribeToRefocus(onRefocus: () => void): () => void {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return () => {};
  }
  const handleVisibilityChange = () => {
    if (document.visibilityState === "visible") {
      onRefocus();
    }
  };
  window.addEventListener("focus", onRefocus);
  document.addEventListener("visibilitychange", handleVisibilityChange);
  return () => {
    window.removeEventListener("focus", onRefocus);
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  };
}

export interface TimerEngineOptions {
  /** Generated-client wrapper used for the engine's own re-fetches. */
  fetchTimer?: () => Promise<TimerSnapshot>;
  /** Client clock, injectable so tests can control elapsed time exactly. */
  now?: () => number;
  /** Called with every new snapshot, caused by a fetch or by an action. */
  onSnapshot?: (snapshot: TimerSnapshot) => void;
  /** Called only when a phase is found to have ended on its own. */
  onAlarm?: () => void;
  /** Wires the focus/visibility-regain re-fetch trigger; injectable for tests. */
  subscribeToRefocus?: (onRefocus: () => void) => () => void;
}

export interface TimerEngine {
  /** The last known snapshot, or null before the first fetch/action result. */
  getSnapshot(): TimerSnapshot | null;
  /** Locally computed remaining seconds at the engine's current clock reading. */
  getRemainingSeconds(): number | null;
  /**
   * Feed a snapshot obtained from the engine's own re-fetch (focus/visibility
   * regain, or the zero-reached re-fetch). May fire the alarm if this reveals
   * a phase that ended on its own.
   */
  applySnapshot(snapshot: TimerSnapshot): void;
  /**
   * Feed the snapshot a Timer action's own response already carries (every
   * `/api/timer/*` action returns the resulting, already-settled Timer).
   * Never fires the alarm: a phase the User just ended themselves is, by
   * definition, not one that ended on its own (story requirement).
   */
  applyActionResult(snapshot: TimerSnapshot): void;
  /** Re-fetch the Timer from the server now (focus/visibility regain). */
  refetch(): Promise<void>;
  /**
   * Call on every local countdown tick (e.g. once a second from the UI).
   * Re-fetches, at most once per zero-crossing, once the locally computed
   * remaining time reaches zero (story 66: never assume completion locally).
   */
  tick(): void;
  /** Unsubscribe from focus/visibility-regain events. */
  dispose(): void;
}

export function createTimerEngine(
  options: TimerEngineOptions = {},
): TimerEngine {
  const fetchTimer = options.fetchTimer ?? defaultFetchTimer;
  const now = options.now ?? (() => Date.now());
  const subscribeToRefocus =
    options.subscribeToRefocus ?? defaultSubscribeToRefocus;

  let snapshot: TimerSnapshot | null = null;
  let fetchedAtClientMs: number | null = null;
  let zeroCrossingHandled = false;

  function applySnapshot(
    nextSnapshot: TimerSnapshot,
    causedByAction: boolean,
  ): void {
    const previousPhase = snapshot?.phase ?? null;
    const previousSnapshot = snapshot;
    const previousFetchedAtClientMs = fetchedAtClientMs;
    snapshot = nextSnapshot;
    fetchedAtClientMs = now();
    zeroCrossingHandled = false;
    options.onSnapshot?.(nextSnapshot);
    if (
      !causedByAction &&
      isNaturalCompletion(previousPhase, nextSnapshot.phase) &&
      previouslyRanOutClientSide(
        previousSnapshot,
        previousFetchedAtClientMs,
        fetchedAtClientMs,
      )
    ) {
      options.onAlarm?.();
    }
  }

  async function refetch(): Promise<void> {
    const nextSnapshot = await fetchTimer();
    applySnapshot(nextSnapshot, false);
  }

  const unsubscribeRefocus = subscribeToRefocus(() => {
    void refetch();
  });

  return {
    getSnapshot: () => snapshot,
    getRemainingSeconds: () => {
      if (snapshot === null || fetchedAtClientMs === null) {
        return null;
      }
      return remainingSecondsAt(snapshot, fetchedAtClientMs, now());
    },
    applySnapshot: (nextSnapshot: TimerSnapshot) =>
      applySnapshot(nextSnapshot, false),
    applyActionResult: (nextSnapshot: TimerSnapshot) =>
      applySnapshot(nextSnapshot, true),
    refetch,
    tick: () => {
      if (snapshot === null || fetchedAtClientMs === null) {
        return;
      }
      const remaining = remainingSecondsAt(snapshot, fetchedAtClientMs, now());
      if (remaining === null || remaining > 0) {
        zeroCrossingHandled = false;
        return;
      }
      if (zeroCrossingHandled) {
        return;
      }
      zeroCrossingHandled = true;
      void refetch();
    },
    dispose: unsubscribeRefocus,
  };
}
