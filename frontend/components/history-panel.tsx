"use client";

import { useState } from "react";
import type { MonthKey } from "@/lib/history-navigation";
import { EMPTY_TASK_FILTER, type TaskFilterState } from "@/lib/task-filter";
import { useDayDetail } from "@/lib/use-day-detail";
import { useMonthSummary } from "@/lib/use-month-summary";
import { useTagCatalog } from "@/lib/use-tag-catalog";
import { HistoryDayDetail } from "./history-day-detail";
import { HistoryHeatmap } from "./history-heatmap";
import { TaskFilter } from "./task-filter";

function currentMonthKey(): MonthKey {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

/** The History panel: month heatmap plus the selected day's filtered Task breakdown (T23). */
export function HistoryPanel() {
  const [month, setMonth] = useState<MonthKey>(currentMonthKey);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [filter, setFilter] = useState<TaskFilterState>(EMPTY_TASK_FILTER);
  const tags = useTagCatalog();

  const monthSummary = useMonthSummary(month);
  const dayDetail = useDayDetail(selectedDay, filter);

  function handleNavigate(nextMonth: MonthKey) {
    setMonth(nextMonth);
    setSelectedDay(null);
  }

  return (
    <section className="flex w-full max-w-md flex-col gap-4 p-6">
      {monthSummary.error ? (
        <p role="alert" className="text-sm text-red-600">
          {monthSummary.error}
        </p>
      ) : null}

      <HistoryHeatmap
        month={month}
        days={monthSummary.days}
        selectedDay={selectedDay}
        onSelectDay={setSelectedDay}
        onNavigate={handleNavigate}
      />

      <TaskFilter label="Filtrar Historial" tags={tags} value={filter} onChange={setFilter} />

      {dayDetail.error ? (
        <p role="alert" className="text-sm text-red-600">
          {dayDetail.error}
        </p>
      ) : null}

      <HistoryDayDetail
        selectedDay={selectedDay}
        detail={dayDetail.detail}
        loading={dayDetail.loading}
      />
    </section>
  );
}
