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

/** The controls for whichever phase the Timer is currently in (Stories 50, 52, 57, 59-63). */
export function TimerControls({
  phase,
  pending,
  breakKind,
  accumulatedActiveSeconds,
  onAction,
}: TimerControlsProps) {
  const dispatch = (path: TimerActionPath) => () => onAction(path);

  switch (phase) {
    case "PomodoroRunning":
      return (
        <>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/pause")}>
            Pausar
          </button>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/stop")}>
            Detener
          </button>
        </>
      );
    case "PomodoroPaused":
      return (
        <>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/resume")}>
            Reanudar
          </button>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/stop")}>
            Detener
          </button>
        </>
      );
    case "BreakRunning":
      return (
        <>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/pause")}>
            Pausar
          </button>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/skip-break")}>
            Saltar Break
          </button>
        </>
      );
    case "BreakPaused":
      return (
        <>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/resume")}>
            Reanudar
          </button>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/skip-break")}>
            Saltar Break
          </button>
        </>
      );
    case "AskingToLog":
      return (
        <>
          <p>¿Registrar {minutesForLog(accumulatedActiveSeconds)} min?</p>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/log")}>
            Registrar
          </button>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/discard")}>
            Descartar
          </button>
        </>
      );
    case "ReadyForNext":
      return (
        <>
          <button
            type="button"
            disabled={pending}
            onClick={dispatch("/api/v1/timer/next-pomodoro")}
          >
            ▶ Otro Pomodoro
          </button>
          <button type="button" disabled={pending} onClick={dispatch("/api/v1/timer/start-break")}>
            Iniciar {breakLabel(breakKind)}
          </button>
        </>
      );
    default:
      return <p className="text-sm">Sin Pomodoro en curso.</p>;
  }
}
