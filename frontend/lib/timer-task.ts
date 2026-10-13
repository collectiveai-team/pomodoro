import type { components } from "@/lib/api/schema";

type TimerPhase = components["schemas"]["TimerPhase"];

/** Whether the Timer currently holds this Task: any phase but Idle, on the Timer's Task id. */
export function isTimerTask(
  phase: TimerPhase | null,
  timerTaskId: string | null,
  taskId: string,
): boolean {
  return phase !== null && phase !== "Idle" && timerTaskId === taskId;
}
