import type { components } from "@/lib/api/schema";

type TimerPhase = components["schemas"]["TimerPhase"];

/** The Task ▶ starts a Pomodoro only from Idle or ReadyForNext; unknown phase stays disabled until known. */
export function isTaskStartDisabled(phase: TimerPhase | null): boolean {
  return phase !== "Idle" && phase !== "ReadyForNext";
}
