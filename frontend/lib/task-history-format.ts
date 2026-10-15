import type { components } from "@/lib/api/schema";

type TaskHistoryDay = components["schemas"]["TaskHistoryDayResponse"];

export interface MonthGroup {
  /** `YYYY-MM`. */
  key: string;
  completedCount: number;
  dedicatedSeconds: number;
  days: TaskHistoryDay[];
}

/**
 * Groups the API's per-day rows (already local days, newest first) by month, preserving order.
 * The days arrive as the User's-timezone calendar days, so no timezone math happens here.
 */
export function groupByMonth(days: TaskHistoryDay[]): MonthGroup[] {
  const groups = new Map<string, MonthGroup>();
  for (const entry of days) {
    const key = entry.day.slice(0, 7);
    const group = groups.get(key) ?? { key, completedCount: 0, dedicatedSeconds: 0, days: [] };
    group.completedCount += entry.completed_count;
    group.dedicatedSeconds += entry.dedicated_seconds;
    group.days.push(entry);
    groups.set(key, group);
  }
  return [...groups.values()];
}

/** `YYYY-MM-DD` as d/m/aaaa. */
export function formatDay(day: string): string {
  const [year, month, date] = day.split("-").map(Number);
  return `${date}/${month}/${year}`;
}

export function dayLabel(day: string, today: string): string {
  return day === today ? "Hoy" : formatDay(day);
}

export function rangeLabel(firstDay: string, lastDay: string, activeDays: number): string {
  const noun = activeDays === 1 ? "día" : "días";
  return `${formatDay(firstDay)} – ${formatDay(lastDay)} · ${activeDays} ${noun}`;
}
