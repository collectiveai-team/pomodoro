import type { components } from "@/lib/api/schema";

type TimerPhase = components["schemas"]["TimerPhase"];

const WORKING_PHASES: readonly TimerPhase[] = ["PomodoroRunning", "PomodoroPaused", "AskingToLog"];

export interface TimerTaskCardProps {
  phase: TimerPhase;
  task: { id: string; text: string } | null;
  onOpenDetail?: (taskId: string) => void;
}

/** 'Trabajando en: {Task} ⓘ' during a Pomodoro, 'Última tarea: {Task} ⓘ' in a Break or ReadyForNext. */
export function TimerTaskCard({ phase, task, onOpenDetail }: TimerTaskCardProps) {
  if (!task || phase === "Idle") {
    return null;
  }
  const prefix = WORKING_PHASES.includes(phase) ? "Trabajando en" : "Última tarea";
  return (
    <div className="flex w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
      <p className="min-w-0 flex-1 break-words">{`${prefix}: ${task.text}`}</p>
      <button
        type="button"
        aria-label={`Ver detalle de ${task.text}`}
        onClick={() => onOpenDetail?.(task.id)}
        className="shrink-0 text-muted hover:text-ink"
      >
        ⓘ
      </button>
    </div>
  );
}
