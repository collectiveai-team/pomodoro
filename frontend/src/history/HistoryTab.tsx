"use client";

import { useEffect, useState } from "react";
import { fetchTagCatalog } from "@/src/tasks/client";
import { TaskFilter } from "@/src/tasks/TaskFilter";
import {
  type DayTaskSummary,
  fetchDayDetail,
  fetchMonthHeatmap,
  type MonthDay,
} from "./client";

/**
 * The Historial tab: a monthly heatmap grid (5 brand-violet intensity
 * levels, per-day count, prev/next navigation) and a day-detail strip
 * listing each Task worked that day, filterable like the other tabs
 * (stories 75-82). Backed by T16's `/api/history/month` and `/api/history/day`.
 */

const WEEKDAY_LABELS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

const INTENSITY_BACKGROUND = [
  "transparent",
  "color-mix(in srgb, var(--color-accent) 25%, var(--color-bg))",
  "color-mix(in srgb, var(--color-accent) 50%, var(--color-bg))",
  "color-mix(in srgb, var(--color-accent) 75%, var(--color-bg))",
  "var(--color-accent)",
];

function pad2(value: number): string {
  return value.toString().padStart(2, "0");
}

function dateKey(year: number, month: number, day: number): string {
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function firstWeekday(year: number, month: number): number {
  return new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
}

function intensityLevel(count: number, maxCount: number): number {
  if (count <= 0 || maxCount <= 0) {
    return 0;
  }
  return Math.min(4, Math.max(1, Math.ceil((count / maxCount) * 4)));
}

function formatMonthTitle(year: number, month: number): string {
  const formatted = new Intl.DateTimeFormat("es-AR", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, 1)));
  return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours}h ${minutes}min` : `${minutes} min`;
}

type MonthState = { year: number; month: number };

function shiftMonth({ year, month }: MonthState, delta: number): MonthState {
  const zeroBased = month - 1 + delta;
  const nextYear = year + Math.floor(zeroBased / 12);
  const nextMonth = ((zeroBased % 12) + 12) % 12;
  return { year: nextYear, month: nextMonth + 1 };
}

function todayMonthState(): MonthState {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

type DayDetailRowProps = { summary: DayTaskSummary };

function DayDetailRow({ summary }: DayDetailRowProps) {
  return (
    <li className="flex flex-col gap-1 rounded-md border border-ink/10 p-3">
      <div className="flex items-center gap-2">
        <span className="flex-1 text-sm font-medium text-ink">
          {summary.text}
        </span>
        <span className="text-sm text-ink/70">
          {summary.completed_count} completados ·{" "}
          {formatDuration(summary.dedicated_seconds)}
        </span>
      </div>
      {summary.tags.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {summary.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-ink/20 px-3 py-1 text-xs text-ink"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}
    </li>
  );
}

export function HistoryTab() {
  const [monthState, setMonthState] = useState<MonthState>(todayMonthState);
  const [monthDays, setMonthDays] = useState<MonthDay[]>([]);
  const [monthError, setMonthError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [dayDetail, setDayDetail] = useState<DayTaskSummary[]>([]);
  const [dayError, setDayError] = useState<string | null>(null);
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [textFilter, setTextFilter] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  useEffect(() => {
    void fetchTagCatalog().then((catalog) =>
      setAvailableTags(catalog.map((tag) => tag.name)),
    );
  }, []);

  useEffect(() => {
    setSelectedDate(null);
    let cancelled = false;
    void fetchMonthHeatmap(monthState.year, monthState.month).then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setMonthDays(result.days);
        setMonthError(null);
      } else {
        setMonthDays([]);
        setMonthError(result.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [monthState]);

  useEffect(() => {
    if (!selectedDate) {
      setDayDetail([]);
      setDayError(null);
      return;
    }
    const handle = setTimeout(() => {
      void fetchDayDetail(selectedDate, {
        text: textFilter.trim(),
        tags: selectedTags,
      }).then((result) => {
        if (result.ok) {
          setDayDetail(result.summaries);
          setDayError(null);
        } else {
          setDayDetail([]);
          setDayError(result.message);
        }
      });
    }, 250);
    return () => clearTimeout(handle);
  }, [selectedDate, textFilter, selectedTags]);

  function toggleTag(tag: string): void {
    setSelectedTags((previous) =>
      previous.includes(tag)
        ? previous.filter((existing) => existing !== tag)
        : [...previous, tag],
    );
  }

  const countsByDay = new Map(
    monthDays.map((entry) => [entry.day, entry.completed_count]),
  );
  const maxCount = monthDays.reduce(
    (max, entry) => Math.max(max, entry.completed_count),
    0,
  );
  const totalDays = daysInMonth(monthState.year, monthState.month);
  const leadingBlanks = firstWeekday(monthState.year, monthState.month);
  const cells: Array<{ day: number; key: string } | null> = [
    ...Array.from({ length: leadingBlanks }, () => null),
    ...Array.from({ length: totalDays }, (_, index) => {
      const day = index + 1;
      return { day, key: dateKey(monthState.year, monthState.month, day) };
    }),
  ];

  return (
    <section className="flex flex-col gap-4 p-4">
      <h2 className="font-olivetta text-xl font-semibold text-ink">
        Historial
      </h2>

      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setMonthState((previous) => shiftMonth(previous, -1))}
          aria-label="Mes anterior"
          className="min-h-11 min-w-11 rounded-md border border-ink/20 px-3 py-2 text-sm text-ink"
        >
          ←
        </button>
        <span className="font-leitura text-lg italic text-ink">
          {formatMonthTitle(monthState.year, monthState.month)}
        </span>
        <button
          type="button"
          onClick={() => setMonthState((previous) => shiftMonth(previous, 1))}
          aria-label="Mes siguiente"
          className="min-h-11 min-w-11 rounded-md border border-ink/20 px-3 py-2 text-sm text-ink"
        >
          →
        </button>
      </div>

      {monthError ? (
        <p role="alert" className="text-sm text-red-600">
          {monthError}
        </p>
      ) : null}

      <div className="grid grid-cols-7 gap-1">
        {WEEKDAY_LABELS.map((label) => (
          <span
            key={label}
            className="text-center text-xs font-semibold text-ink/60"
          >
            {label}
          </span>
        ))}
        {cells.map((cell, index) => {
          if (!cell) {
            return (
              // biome-ignore lint/suspicious/noArrayIndexKey: leading blank cells have no identity
              <span key={`blank-${index}`} />
            );
          }
          const count = countsByDay.get(cell.key) ?? 0;
          const level = intensityLevel(count, maxCount);
          const selected = cell.key === selectedDate;
          return (
            <button
              key={cell.key}
              type="button"
              onClick={() => setSelectedDate(cell.key)}
              aria-pressed={selected}
              aria-label={`${cell.day}: ${count} Pomodoros completados`}
              style={{ backgroundColor: INTENSITY_BACKGROUND[level] }}
              className={`relative aspect-square min-h-11 rounded-md border text-xs ${
                selected ? "border-accent ring-2 ring-accent" : "border-ink/10"
              } ${level >= 3 ? "text-white" : "text-ink"}`}
            >
              <span className="absolute left-1 top-1">{cell.day}</span>
              {count > 0 ? (
                <span className="absolute bottom-1 right-1 font-semibold">
                  {count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {selectedDate ? (
        <div className="flex flex-col gap-3 border-t border-ink/10 pt-4">
          <TaskFilter
            text={textFilter}
            onTextChange={setTextFilter}
            availableTags={availableTags}
            selectedTags={selectedTags}
            onToggleTag={toggleTag}
          />

          {dayError ? (
            <p role="alert" className="text-sm text-red-600">
              {dayError}
            </p>
          ) : null}

          {dayDetail.length === 0 && !dayError ? (
            <p className="text-sm text-ink/60">
              Sin Pomodoros registrados ese día.
            </p>
          ) : null}

          <ul className="flex flex-col gap-2">
            {dayDetail.map((summary) => (
              <DayDetailRow key={summary.task_id} summary={summary} />
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
