import type { components } from "@/lib/api/schema";
import { minutesForLog } from "@/lib/countdown";

type TimerPhase = components["schemas"]["TimerPhase"];
type BreakKind = components["schemas"]["BreakKind"];

export type TimerActionPath =
  | "/api/v1/timer/start-break"
  | "/api/v1/timer/skip-break"
  | "/api/v1/timer/next-pomodoro"
  | "/api/v1/timer/pause"
  | "/api/v1/timer/resume"
  | "/api/v1/timer/stop"
  | "/api/v1/timer/log"
  | "/api/v1/timer/discard";

export interface TimerControlsProps {
  phase: TimerPhase;
  pending: boolean;
  breakKind: BreakKind | null;
  accumulatedActiveSeconds: number;
  onAction: (path: TimerActionPath) => void;
}

function breakLabel(breakKind: BreakKind | null): string {
  return breakKind === "long" ? "Break largo" : "Break corto";
}

interface ControlSpec {
  primary: { path: TimerActionPath; label: string };
  secondary: { path: TimerActionPath; label: string; icon: string };
  prompt?: string;
}

/** The primary and secondary action of the Timer's current phase (Stories 50, 52, 57, 59-63). */
function controlsFor(
  phase: TimerPhase,
  breakKind: BreakKind | null,
  accumulatedActiveSeconds: number,
): ControlSpec | null {
  const stop = { path: "/api/v1/timer/stop", label: "Detener", icon: "■" } as const;
  const skip = { path: "/api/v1/timer/skip-break", label: "Saltar Break", icon: "⏭" } as const;
  switch (phase) {
    case "PomodoroRunning":
      return { primary: { path: "/api/v1/timer/pause", label: "Pausar" }, secondary: stop };
    case "PomodoroPaused":
      return { primary: { path: "/api/v1/timer/resume", label: "Reanudar" }, secondary: stop };
    case "BreakRunning":
      return { primary: { path: "/api/v1/timer/pause", label: "Pausar" }, secondary: skip };
    case "BreakPaused":
      return { primary: { path: "/api/v1/timer/resume", label: "Reanudar" }, secondary: skip };
    case "AskingToLog":
      return {
        prompt: `¿Registrar ${minutesForLog(accumulatedActiveSeconds)} min?`,
        primary: { path: "/api/v1/timer/log", label: "Registrar" },
        secondary: { path: "/api/v1/timer/discard", label: "Descartar", icon: "✕" },
      };
    case "ReadyForNext":
      return {
        primary: { path: "/api/v1/timer/next-pomodoro", label: "▶ Otro Pomodoro" },
        secondary: {
          path: "/api/v1/timer/start-break",
          label: `Iniciar ${breakLabel(breakKind)}`,
          icon: "☕",
        },
      };
    default:
      return null;
  }
}

/** A large primary action flanked by a round icon-only secondary action (Story 87 touch size). */
export function TimerControls({
  phase,
  pending,
  breakKind,
  accumulatedActiveSeconds,
  onAction,
}: TimerControlsProps) {
  const spec = controlsFor(phase, breakKind, accumulatedActiveSeconds);
  if (!spec) {
    return <p className="text-sm">Sin Pomodoro en curso.</p>;
  }
  const { primary, secondary, prompt } = spec;
  return (
    <div className="flex flex-col items-center gap-2">
      {prompt ? <p>{prompt}</p> : null}
      <div className="flex items-center justify-center gap-3">
        <button
          type="button"
          aria-label={secondary.label}
          disabled={pending}
          onClick={() => onAction(secondary.path)}
          className="btn-secondary h-11 w-11 rounded-full px-0"
        >
          <span aria-hidden="true">{secondary.icon}</span>
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => onAction(primary.path)}
          className="btn-primary min-h-12 min-w-36 px-6 text-base"
        >
          {primary.label}
        </button>
      </div>
    </div>
  );
}
