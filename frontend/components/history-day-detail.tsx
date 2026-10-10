"use client";

import type { components } from "@/lib/api/schema";

type DayDetailResponse = components["schemas"]["DayDetailResponse"];

export interface HistoryDayDetailProps {
  selectedDay: string | null;
  detail: DayDetailResponse | null;
  loading: boolean;
}

/** Formats dedicated seconds as "1h 15m", or just "15m" under an hour. */
function formatDedicatedSeconds(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}

/** The selected day's per-Task breakdown strip below the heatmap (Stories 78-79, 81-82). */
export function HistoryDayDetail({ selectedDay, detail, loading }: HistoryDayDetailProps) {
  if (!selectedDay) {
    return <p className="text-sm text-gray-500">Seleccioná un día para ver el detalle.</p>;
  }
  if (loading || !detail) {
    return <p>Cargando…</p>;
  }
  if (detail.tasks.length === 0) {
    return <p className="text-sm text-gray-500">Sin Pomodoros ese día.</p>;
  }
  return (
    <ul className="flex flex-col gap-1" aria-label={`Detalle del ${selectedDay}`}>
      {detail.tasks.map((task) => (
        <li key={task.task_id} className="flex items-center justify-between gap-2 text-sm">
          <span className="flex-1">{task.text}</span>
          <span>{task.completed_count} Pomodoros</span>
          <span>{formatDedicatedSeconds(task.dedicated_seconds)}</span>
        </li>
      ))}
    </ul>
  );
}
