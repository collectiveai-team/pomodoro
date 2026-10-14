"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { TIMER_CHANGED_EVENT } from "@/lib/timer-sync";

export interface TodayStat {
  completedCount: number;
  dedicatedSeconds: number;
}

export type TodayByTask = ReadonlyMap<string, TodayStat>;

const NO_STATS: TodayByTask = new Map();

/** The browser's local calendar day as `YYYY-MM-DD` (the API's `date` query parameter). */
function localToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * Today's completed count and dedicated time per Task (Story 16), from `GET /history/day`.
 * Refetched on same-page Timer changes, focus, and whenever `refreshKey` changes (the Timer phase
 * moving, e.g. a Pomodoro completing or being logged).
 */
export function useTodayByTask(refreshKey: unknown): TodayByTask {
  const [stats, setStats] = useState<TodayByTask>(NO_STATS);

  const load = useCallback(async () => {
    const { data, response } = await apiClient.GET("/api/v1/history/day", {
      params: { query: { date: localToday() } },
    });
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (data && Array.isArray(data.tasks)) {
      setStats(
        new Map(
          data.tasks.map((entry) => [
            entry.task_id,
            { completedCount: entry.completed_count, dedicatedSeconds: entry.dedicated_seconds },
          ]),
        ),
      );
    }
  }, []);

  // biome-ignore lint/correctness/useExhaustiveDependencies: refreshKey is the refetch trigger.
  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    const refetch = () => void load();
    window.addEventListener(TIMER_CHANGED_EVENT, refetch);
    window.addEventListener("focus", refetch);
    return () => {
      window.removeEventListener(TIMER_CHANGED_EVENT, refetch);
      window.removeEventListener("focus", refetch);
    };
  }, [load]);

  return stats;
}
