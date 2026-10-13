import type { components } from "@/lib/api/schema";

/**
 * The Timer panel and the Tasks panel both read and mutate the one Timer, but each polls it
 * independently (no WebSocket/SSE, per the spec). This same-page broadcast lets either one tell
 * the other "the Timer just changed" without lifting their state into a shared parent.
 */
export const TIMER_CHANGED_EVENT = "pomodoro:timer-changed";

type TimerPhase = components["schemas"]["TimerPhase"];

/** The slice of a Timer snapshot other panels need, carried so they skip an extra request. */
export interface TimerSyncSnapshot {
  phase: TimerPhase;
  taskId: string | null;
}

export function broadcastTimerChanged(snapshot?: TimerSyncSnapshot): void {
  window.dispatchEvent(new CustomEvent(TIMER_CHANGED_EVENT, { detail: snapshot }));
}

/** The snapshot an event carries, or null when the sender wants listeners to refetch. */
export function snapshotFromEvent(event: Event): TimerSyncSnapshot | null {
  return (event as CustomEvent<TimerSyncSnapshot | undefined>).detail ?? null;
}
