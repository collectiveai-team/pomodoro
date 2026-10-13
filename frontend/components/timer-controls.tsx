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
interface ActionButtonProps {
  path: TimerActionPath;
  label: string;
  pending: boolean;
  onAction: (path: TimerActionPath) => void;
  variant?: "primary" | "secondary";
}

/** One touch-sized Timer action button (Story 87), styled by primary/secondary variant. */
function ActionButton({
  path,
  label,
  pending,
  onAction,
  variant = "secondary",
}: ActionButtonProps) {
  return (
    <button
      type="button"
      disabled={pending}
      onClick={() => onAction(path)}
      className={variant === "primary" ? "btn-primary" : "btn-secondary"}
    >
      {label}
    </button>
  );
}

export function TimerControls({
  phase,
  pending,
  breakKind,
  accumulatedActiveSeconds,
  onAction,
}: TimerControlsProps) {
  switch (phase) {
    case "PomodoroRunning":
      return (
        <>
          <ActionButton
            path="/api/v1/timer/pause"
            label="Pausar"
            pending={pending}
            onAction={onAction}
            variant="primary"
          />
          <ActionButton
            path="/api/v1/timer/stop"
            label="Detener"
            pending={pending}
            onAction={onAction}
          />
        </>
      );
    case "PomodoroPaused":
      return (
        <>
          <ActionButton
            path="/api/v1/timer/resume"
            label="Reanudar"
            pending={pending}
            onAction={onAction}
            variant="primary"
          />
          <ActionButton
            path="/api/v1/timer/stop"
            label="Detener"
            pending={pending}
            onAction={onAction}
          />
        </>
      );
    case "BreakRunning":
      return (
        <>
          <ActionButton
            path="/api/v1/timer/pause"
            label="Pausar"
            pending={pending}
            onAction={onAction}
            variant="primary"
          />
          <ActionButton
            path="/api/v1/timer/skip-break"
            label="Saltar Break"
            pending={pending}
            onAction={onAction}
          />
        </>
      );
    case "BreakPaused":
      return (
        <>
          <ActionButton
            path="/api/v1/timer/resume"
            label="Reanudar"
            pending={pending}
            onAction={onAction}
            variant="primary"
          />
          <ActionButton
            path="/api/v1/timer/skip-break"
            label="Saltar Break"
            pending={pending}
            onAction={onAction}
          />
        </>
      );
    case "AskingToLog":
      return (
        <>
          <p>¿Registrar {minutesForLog(accumulatedActiveSeconds)} min?</p>
          <ActionButton
            path="/api/v1/timer/log"
            label="Registrar"
            pending={pending}
            onAction={onAction}
            variant="primary"
          />
          <ActionButton
            path="/api/v1/timer/discard"
            label="Descartar"
            pending={pending}
            onAction={onAction}
          />
        </>
      );
    case "ReadyForNext":
      return (
        <>
          <ActionButton
            path="/api/v1/timer/next-pomodoro"
            label="▶ Otro Pomodoro"
            pending={pending}
            onAction={onAction}
            variant="primary"
          />
          <ActionButton
            path="/api/v1/timer/start-break"
            label={`Iniciar ${breakLabel(breakKind)}`}
            pending={pending}
            onAction={onAction}
          />
        </>
      );
    default:
      return <p className="text-sm">Sin Pomodoro en curso.</p>;
  }
}
