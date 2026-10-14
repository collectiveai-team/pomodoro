import { formatDuration } from "@/lib/format-duration";
import type { TodayStat } from "@/lib/use-today-by-task";

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
