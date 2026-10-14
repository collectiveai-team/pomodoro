import type { TodayStat } from "@/lib/use-today-by-task";

/** "1h 30m" / "25m" for a dedicated-seconds total. */
function formatDuration(seconds: number): string {
  const totalMinutes = Math.floor(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}

/** Today's stats of one Task: one dot per completed Pomodoro, count and time (Story 16). */
export function TaskRowStats({ stat }: { stat: TodayStat }) {
  if (stat.completedCount === 0 && stat.dedicatedSeconds === 0) {
    return null;
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted tabular">
      <span role="img" aria-label={`${stat.completedCount} Pomodoros hoy`} className="text-accent">
        {"●".repeat(Math.min(stat.completedCount, 12))}
      </span>
      <span>
        {stat.completedCount} hoy · {formatDuration(stat.dedicatedSeconds)}
      </span>
    </span>
  );
}
