/**
 * The Timer panel and the Tasks panel both read and mutate the one Timer, but each polls it
 * independently (no WebSocket/SSE, per the spec). This same-page broadcast lets either one tell
 * the other "the Timer just changed, refetch" without lifting their state into a shared parent.
 */
export const TIMER_CHANGED_EVENT = "pomodoro:timer-changed";

export function broadcastTimerChanged(): void {
  window.dispatchEvent(new Event(TIMER_CHANGED_EVENT));
}
