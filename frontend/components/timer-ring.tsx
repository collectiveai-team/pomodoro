import type { components } from "@/lib/api/schema";
import { formatClock } from "@/lib/countdown";

type TimerPhase = components["schemas"]["TimerPhase"];

const RADIUS = 54;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export const PHASE_LABELS: Record<TimerPhase, string> = {
  Idle: "En reposo",
  PomodoroRunning: "Pomodoro",
  PomodoroPaused: "Pomodoro (pausado)",
  AskingToLog: "Pomodoro interrumpido",
  BreakRunning: "Break",
  BreakPaused: "Break (pausado)",
  ReadyForNext: "Pomodoro completado",
};

export interface TimerRingProps {
  phase: TimerPhase;
  remainingSeconds: number | null;
  fraction: number;
}

/** The remaining-time ring: an SVG progress circle plus the phase label (Story 49). */
export function TimerRing({ phase, remainingSeconds, fraction }: TimerRingProps) {
  const dashOffset = CIRCUMFERENCE * (1 - fraction);
  const clockLabel = remainingSeconds !== null ? formatClock(remainingSeconds) : "--:--";

  return (
    <div className="relative h-36 w-36">
      <svg viewBox="0 0 120 120" className="h-36 w-36 -rotate-90" role="img">
        <title>
          {PHASE_LABELS[phase]} — {clockLabel}
        </title>
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.15}
          strokeWidth={8}
        />
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          fill="none"
          stroke="currentColor"
          className="text-accent"
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tabular-nums">{clockLabel}</span>
        <span className="text-xs">{PHASE_LABELS[phase]}</span>
      </div>
    </div>
  );
}
