"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { TIMER_CHANGED_EVENT } from "@/lib/timer-sync";
import { useUserToday } from "@/lib/use-user-today";

export interface TodayStat {
  completedCount: number;
  dedicatedSeconds: number;
}

export type TodayByTask = ReadonlyMap<string, TodayStat>;

const NO_STATS: TodayByTask = new Map();

/**
 * Today's completed count and dedicated time per Task (Story 16), from `GET /history/day`.
 * Refetched on same-page Timer changes, focus, and whenever `refreshKey` changes (the Timer phase
 * moving, e.g. a Pomodoro completing or being logged).
 */
export function useTodayByTask(refreshKey: unknown): TodayByTask {
  const [stats, setStats] = useState<TodayByTask>(NO_STATS);
  const today = useUserToday();

  const load = useCallback(async () => {
    if (today === null) {
      return;
    }
    const { data, response } = await apiClient.GET("/api/v1/history/day", {
      params: { query: { date: today } },
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
  }, [today]);

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
