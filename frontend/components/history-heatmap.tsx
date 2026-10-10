"use client";

import type { components } from "@/lib/api/schema";
import { type IntensityLevel, intensityBucket } from "@/lib/history-intensity";
import { type MonthKey, monthTitle, nextMonth, previousMonth } from "@/lib/history-navigation";

type MonthDaySummaryResponse = components["schemas"]["MonthDaySummaryResponse"];

const INTENSITY_CLASSES: Record<IntensityLevel, string> = {
  0: "bg-violet-50 text-violet-900",
  1: "bg-violet-200 text-violet-900",
  2: "bg-violet-400 text-white",
  3: "bg-violet-600 text-white",
  4: "bg-violet-900 text-white",
};

export interface HistoryHeatmapProps {
  month: MonthKey;
  days: MonthDaySummaryResponse[];
  selectedDay: string | null;
  onSelectDay: (day: string) => void;
  onNavigate: (month: MonthKey) => void;
}

function dayOfMonth(isoDay: string): number {
  return new Date(`${isoDay}T00:00:00Z`).getUTCDate();
}

function leadingBlankCount(days: MonthDaySummaryResponse[]): number {
  if (days.length === 0) {
    return 0;
  }
  const firstDay = days[0];
  if (!firstDay) {
    return 0;
  }
  return new Date(`${firstDay.day}T00:00:00Z`).getUTCDay();
}

/** The month calendar heatmap: 5-level violet intensity per day, with prev/next navigation. */
export function HistoryHeatmap({
  month,
  days,
  selectedDay,
  onSelectDay,
  onNavigate,
}: HistoryHeatmapProps) {
  const leadingBlanks = leadingBlankCount(days);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <button
          type="button"
          aria-label="Mes anterior"
          onClick={() => onNavigate(previousMonth(month))}
        >
          ←
        </button>
        <h2 className="font-serif italic">{monthTitle(month)}</h2>
        <button
          type="button"
          aria-label="Mes siguiente"
          onClick={() => onNavigate(nextMonth(month))}
        >
          →
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: leadingBlanks }, (_, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length leading filler, never reordered
          <div key={`blank-${index}`} aria-hidden="true" />
        ))}
        {days.map((day) => {
          const level = intensityBucket(day.completed_count);
          const isSelected = day.day === selectedDay;
          return (
            <button
              key={day.day}
              type="button"
              aria-label={`Día ${dayOfMonth(day.day)}: ${day.completed_count} Pomodoros`}
              aria-pressed={isSelected}
              onClick={() => onSelectDay(day.day)}
              className={`relative flex aspect-square items-center justify-center rounded text-xs ${INTENSITY_CLASSES[level]} ${isSelected ? "ring-2 ring-violet-700" : ""}`}
            >
              <span>{dayOfMonth(day.day)}</span>
              <span className="absolute right-0.5 bottom-0.5 text-[10px]">
                {day.completed_count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
