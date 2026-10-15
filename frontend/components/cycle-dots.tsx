import type { components } from "@/lib/api/schema";

type TimerPhase = components["schemas"]["TimerPhase"];
type BreakKind = components["schemas"]["BreakKind"];

const CYCLE_SIZE = 5;
const DOT_SLOTS = [0, 1, 2, 3, 4];

export interface CycleDotsProps {
  phase: TimerPhase;
  breakKind: BreakKind | null;
  pomodorosUntilLongBreak: number;
}

/** Completed Pomodoros of the cycle; the full cycle stays shown through the long Break. */
function filledCount({ phase, breakKind, pomodorosUntilLongBreak }: CycleDotsProps): number {
  const inBreak = phase === "BreakRunning" || phase === "BreakPaused";
  if (breakKind === "long" && (inBreak || phase === "ReadyForNext")) {
    return CYCLE_SIZE;
  }
  return CYCLE_SIZE - Math.min(CYCLE_SIZE, Math.max(0, pomodorosUntilLongBreak));
}

/** Five dots filling with the Pomodoros completed toward the next long Break. */
export function CycleDots(props: CycleDotsProps) {
  const filled = filledCount(props);
  return (
    <div
      role="img"
      aria-label={`Ciclo: ${filled} de ${CYCLE_SIZE} Pomodoros`}
      className="flex items-center justify-center gap-2"
    >
      {DOT_SLOTS.map((slot) => (
        <span
          key={slot}
          data-filled={slot < filled}
          className={`h-2 w-2 rounded-full border border-accent ${
            slot < filled ? "bg-accent" : "bg-transparent"
          }`}
        />
      ))}
    </div>
  );
}
