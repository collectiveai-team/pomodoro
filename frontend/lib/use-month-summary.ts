"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import type { MonthKey } from "@/lib/history-navigation";
import { redirectToLoginOn401 } from "@/lib/http-session";

type MonthDaySummaryResponse = components["schemas"]["MonthDaySummaryResponse"];

export interface MonthSummaryState {
  days: MonthDaySummaryResponse[];
  loading: boolean;
  error: string | null;
}

const INITIAL_STATE: MonthSummaryState = { days: [], loading: true, error: null };

/** Fetches one month's per-day completed-Pomodoro counts for the heatmap (Stories 75-77). */
export function useMonthSummary({ year, month }: MonthKey): MonthSummaryState {
  const [state, setState] = useState<MonthSummaryState>(INITIAL_STATE);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setState((previous) => ({ ...previous, loading: true }));
    const { data, response } = await apiClient.GET("/api/v1/history/month", {
      params: { query: { year, month } },
    });
    if (requestIdRef.current !== requestId) {
      return;
    }
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (!data) {
      setState({ days: [], loading: false, error: "No se pudo cargar el Historial." });
      return;
    }
    setState({ days: data.days, loading: false, error: null });
  }, [year, month]);

  useEffect(() => {
    void load();
  }, [load]);

  return state;
}
