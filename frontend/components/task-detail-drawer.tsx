"use client";

import { useEffect, useMemo, useRef } from "react";
import { formatDuration } from "@/lib/format-duration";
import { monthTitle } from "@/lib/history-navigation";
import { tagDotClass } from "@/lib/tag-colors";
import { EMPTY_TASK_FILTER } from "@/lib/task-filter";
import { dayLabel, groupByMonth, rangeLabel } from "@/lib/task-history-format";
import { isTimerTask } from "@/lib/timer-task";
import { useTagCatalog } from "@/lib/use-tag-catalog";
import { useTaskHistory } from "@/lib/use-task-history";
import { useTaskList } from "@/lib/use-task-list";
import { useTimerPhase } from "@/lib/use-timer-phase";

export interface TaskDetailDrawerProps {
  taskId: string;
  onClose: () => void;
}

function localToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/** Right-sliding Task detail (Stories 30-36); full screen below `md`. */
export function TaskDetailDrawer({ taskId, onClose }: TaskDetailDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const [active] = useTaskList("active", EMPTY_TASK_FILTER);
  const [archived] = useTaskList("archived", EMPTY_TASK_FILTER);
  const tags = useTagCatalog();
  const { phase, taskId: timerTaskId } = useTimerPhase();
  const { history, loading, error } = useTaskHistory(taskId);

  const task = [...active.tasks, ...archived.tasks].find((candidate) => candidate.id === taskId);
  const months = useMemo(() => groupByMonth(history?.days ?? []), [history]);
  const today = localToday();
  const taskTags = task ? tags.filter((tag) => task.tag_ids.includes(tag.id)) : [];
  const status = isTimerTask(phase, timerTaskId, taskId)
    ? "En curso"
    : task?.archived_at
      ? "Archivada"
      : "Activa";

  useEffect(() => {
    closeRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        data-testid="drawer-backdrop"
        onClick={onClose}
        className="absolute inset-0 bg-black/30"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Detalle de ${task?.text ?? "la tarea"}`}
        className="drawer-slide-in relative flex h-full w-full flex-col gap-4 overflow-y-auto bg-paper p-6 shadow-xl md:w-[420px]"
      >
        <div className="flex items-start gap-2">
          <h2 className="min-w-0 flex-1 break-words font-display text-xl italic">
            {task?.text ?? ""}
          </h2>
          <button
            ref={closeRef}
            type="button"
            aria-label="Cerrar detalle"
            onClick={onClose}
            className="flex min-h-11 min-w-11 items-center justify-center text-muted hover:text-ink"
          >
            ✕
          </button>
        </div>
        <p className="text-sm text-muted">{status}</p>
        {taskTags.length > 0 ? (
          <ul className="flex flex-wrap gap-2">
            {taskTags.map((tag) => (
              <li key={tag.id} className="chip-button">
                <span
                  aria-hidden="true"
                  data-testid="drawer-tag-dot"
                  className={`inline-block h-2 w-2 rounded-full ${tagDotClass(tag.color)}`}
                />
                {tag.name}
              </li>
            ))}
          </ul>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        ) : loading || !history ? null : history.days.length === 0 ? (
          <p className="text-sm text-muted">Todavía sin Pomodoros</p>
        ) : (
          <>
            <section className="flex flex-col gap-1">
              <h3 className="text-xs uppercase text-muted">Dedicación total</h3>
              <p className="tabular">
                {history.completed_count} Pomodoros · {formatDuration(history.dedicated_seconds)}
              </p>
              {history.first_day && history.last_day ? (
                <p className="text-sm text-muted tabular">
                  {rangeLabel(history.first_day, history.last_day, history.active_days)}
                </p>
              ) : null}
            </section>
            {months.map((month) => (
              <section key={month.key} className="flex flex-col gap-1">
                <h3 className="flex justify-between font-display text-lg italic">
                  <span>
                    {monthTitle({
                      year: Number(month.key.slice(0, 4)),
                      month: Number(month.key.slice(5)),
                    })}
                  </span>
                  <span className="tabular text-sm">
                    {month.completedCount} · {formatDuration(month.dedicatedSeconds)}
                  </span>
                </h3>
                <ul className="flex flex-col">
                  {month.days.map((entry) => (
                    <li
                      key={entry.day}
                      className="flex justify-between border-b border-border py-1 text-sm tabular"
                    >
                      <span>{dayLabel(entry.day, today)}</span>
                      <span>
                        {entry.completed_count} pomodoros ·{" "}
                        {formatDuration(entry.dedicated_seconds)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </>
        )}
      </aside>
    </div>
  );
}
