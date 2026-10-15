import type { components } from "@/lib/api/schema";
import { formatClock } from "@/lib/countdown";

type TimerPhase = components["schemas"]["TimerPhase"];
type BreakKind = components["schemas"]["BreakKind"];

const RADIUS = 54;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Phase line text in natural case; the line is uppercased by CSS so accessible text stays readable. */
export function phaseLabel(phase: TimerPhase, breakKind: BreakKind | null): string {
  const breakName = breakKind === "long" ? "Break largo" : "Break corto";
  switch (phase) {
    case "Idle":
      return "En reposo";
    case "PomodoroRunning":
      return "Pomodoro";
    case "PomodoroPaused":
      return "Pomodoro en pausa";
    case "AskingToLog":
      return "Pomodoro interrumpido";
    case "BreakRunning":
      return breakName;
    case "BreakPaused":
      return `${breakName} en pausa`;
    case "ReadyForNext":
      return "Pomodoro completado — listo para el próximo";
  }
}

function phaseColorClass(phase: TimerPhase): string {
  if (phase === "BreakRunning" || phase === "BreakPaused") {
    return "text-break";
  }
  return phase === "PomodoroRunning" ? "text-accent" : "text-muted";
}

export interface TimerRingProps {
  phase: TimerPhase;
  breakKind: BreakKind | null;
  remainingSeconds: number | null;
  fraction: number;
}

/** The remaining-time ring: an SVG progress arc, the clock digits and the phase line (Story 49). */
export function TimerRing({ phase, breakKind, remainingSeconds, fraction }: TimerRingProps) {
  const dashOffset = CIRCUMFERENCE * (1 - fraction);
  const clockLabel = remainingSeconds !== null ? formatClock(remainingSeconds) : "--:--";
  const label = phaseLabel(phase, breakKind);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-36 w-36 md:h-[210px] md:w-[210px]">
        <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90" role="img">
          <title>
            {label} — {clockLabel}
          </title>
          <circle
            cx="60"
            cy="60"
            r={RADIUS}
            fill="none"
            stroke="var(--color-border)"
            strokeWidth={8}
          />
          <circle
            cx="60"
            cy="60"
            r={RADIUS}
            fill="none"
            stroke="var(--color-accent)"
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={dashOffset}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span data-testid="clock-digits" className="tabular font-black text-4xl md:text-5xl">
            {clockLabel}
          </span>
        </div>
      </div>
      <p
        data-testid="phase-line"
        className={`tabular text-center text-xs font-black uppercase tracking-wide ${phaseColorClass(phase)}`}
      >
        {label}
      </p>
    </div>
  );
}
