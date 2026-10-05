import { apiClient } from "@/src/api/client";
import type { components } from "@/src/api/schema";
import { extractErrorMessage } from "@/src/auth/messages";

/**
 * Generated-client wrappers for `/api/history/*` (T16): the monthly heatmap
 * counts and a single day's per-Task detail, filterable like the other tabs.
 */

export type MonthDay = components["schemas"]["MonthDayPublic"];
export type DayTaskSummary = components["schemas"]["DayTaskSummaryPublic"];

export type HistoryFilterQuery = {
  text: string;
  tags: string[];
};

export type MonthHeatmapResult =
  | { ok: true; days: MonthDay[] }
  | { ok: false; status: number; message: string };

export type DayDetailResult =
  | { ok: true; summaries: DayTaskSummary[] }
  | { ok: false; status: number; message: string };

export async function fetchMonthHeatmap(
  year: number,
  month: number,
): Promise<MonthHeatmapResult> {
  const { data, error, response } = await apiClient.GET("/api/history/month", {
    params: { query: { year, month } },
  });
  if (data) {
    return { ok: true, days: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, "No se pudo cargar el historial."),
  };
}

export async function fetchDayDetail(
  date: string,
  filter: HistoryFilterQuery,
): Promise<DayDetailResult> {
  const { data, error, response } = await apiClient.GET("/api/history/day", {
    params: { query: { date, text: filter.text, tags: filter.tags } },
  });
  if (data) {
    return { ok: true, summaries: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(
      error,
      "No se pudo cargar el detalle del día.",
    ),
  };
}
