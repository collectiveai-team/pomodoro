import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/schema";
import { HistoryPanel } from "./history-panel";

type MonthSummaryResponse = components["schemas"]["MonthSummaryResponse"];
type DayDetailResponse = components["schemas"]["DayDetailResponse"];
type DayTaskSummaryResponse = components["schemas"]["DayTaskSummaryResponse"];

const getMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
  },
}));

function ok(status = 200): Response {
  return { status } as Response;
}

function isoDay(year: number, month: number, dayOfMonth: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(dayOfMonth).padStart(2, "0")}`;
}

function makeMonthSummary(
  year: number,
  month: number,
  countsByDay: Record<number, number> = {},
): MonthSummaryResponse {
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return {
    year,
    month,
    days: Array.from({ length: daysInMonth }, (_, index) => {
      const dayOfMonth = index + 1;
      return {
        day: isoDay(year, month, dayOfMonth),
        completed_count: countsByDay[dayOfMonth] ?? 0,
      };
    }),
  };
}

function makeDayDetail(day: string, tasks: DayTaskSummaryResponse[] = []): DayDetailResponse {
  return {
    day,
    completed_count: tasks.reduce((sum, task) => sum + task.completed_count, 0),
    tasks,
  };
}

interface Fixture {
  monthSummaries?: Record<string, MonthSummaryResponse>;
  dayDetails?: Record<string, DayDetailResponse>;
}

function monthKey(year: number, month: number): string {
  return `${year}-${month}`;
}

function setupFixture({ monthSummaries = {}, dayDetails = {} }: Fixture = {}) {
  getMock.mockImplementation(
    (path: string, options?: { params?: { query?: Record<string, unknown> } }) => {
      const query = options?.params?.query ?? {};
      if (path === "/api/v1/tags") {
        return Promise.resolve({ data: { tags: [] }, error: undefined, response: ok() });
      }
      if (path === "/api/v1/history/month") {
        const key = monthKey(query.year as number, query.month as number);
        const data =
          monthSummaries[key] ?? makeMonthSummary(query.year as number, query.month as number);
        return Promise.resolve({ data, error: undefined, response: ok() });
      }
      if (path === "/api/v1/history/day") {
        const data = dayDetails[query.date as string] ?? makeDayDetail(query.date as string);
        return Promise.resolve({ data, error: undefined, response: ok() });
      }
      throw new Error(`Unexpected GET ${path}`);
    },
  );
}

beforeEach(() => {
  getMock.mockReset();
  vi.setSystemTime(new Date("2026-10-15T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("HistoryPanel — month navigation", () => {
  it("opens on the current month's title", async () => {
    setupFixture({ monthSummaries: { [monthKey(2026, 10)]: makeMonthSummary(2026, 10) } });

    render(<HistoryPanel />);

    expect(await screen.findByText("Octubre 2026")).toBeInTheDocument();
  });

  it("requests and displays the next month on the next-arrow click", async () => {
    setupFixture({
      monthSummaries: {
        [monthKey(2026, 10)]: makeMonthSummary(2026, 10),
        [monthKey(2026, 11)]: makeMonthSummary(2026, 11),
      },
    });
    const user = userEvent.setup();

    render(<HistoryPanel />);
    await screen.findByText("Octubre 2026");
    getMock.mockClear();

    await user.click(screen.getByRole("button", { name: "Mes siguiente" }));

    expect(await screen.findByText("Noviembre 2026")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith("/api/v1/history/month", {
        params: { query: { year: 2026, month: 11 } },
      });
    });
  });

  it("requests and displays the previous month on the previous-arrow click, rolling the year back from January", async () => {
    vi.setSystemTime(new Date("2026-01-15T12:00:00Z"));
    setupFixture({
      monthSummaries: {
        [monthKey(2026, 1)]: makeMonthSummary(2026, 1),
        [monthKey(2025, 12)]: makeMonthSummary(2025, 12),
      },
    });
    const user = userEvent.setup();

    render(<HistoryPanel />);
    await screen.findByText("Enero 2026");
    getMock.mockClear();

    await user.click(screen.getByRole("button", { name: "Mes anterior" }));

    expect(await screen.findByText("Diciembre 2025")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith("/api/v1/history/month", {
        params: { query: { year: 2025, month: 12 } },
      });
    });
  });
});

describe("HistoryPanel — day selection", () => {
  it("shows a placeholder before any day is selected", async () => {
    setupFixture({ monthSummaries: { [monthKey(2026, 10)]: makeMonthSummary(2026, 10) } });

    render(<HistoryPanel />);

    expect(await screen.findByText("Seleccioná un día para ver el detalle.")).toBeInTheDocument();
  });

  it("fetches and renders the selected day's per-Task breakdown (Stories 78-79)", async () => {
    const day = isoDay(2026, 10, 5);
    setupFixture({
      monthSummaries: { [monthKey(2026, 10)]: makeMonthSummary(2026, 10, { 5: 3 }) },
      dayDetails: {
        [day]: makeDayDetail(day, [
          {
            task_id: "task-1",
            text: "Write the report",
            completed_count: 2,
            dedicated_seconds: 3000,
          },
        ]),
      },
    });
    const user = userEvent.setup();

    render(<HistoryPanel />);
    await screen.findByText("Octubre 2026");

    await user.click(screen.getByRole("button", { name: "Día 5: 3 Pomodoros" }));

    expect(await screen.findByText("Write the report")).toBeInTheDocument();
    expect(screen.getByText("2 Pomodoros")).toBeInTheDocument();
    expect(screen.getByText("50m")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith("/api/v1/history/day", {
        params: { query: { date: day } },
      });
    });
  });

  it("includes the shared text+Tag filter in the day-detail request (Story 82)", async () => {
    const day = isoDay(2026, 10, 5);
    setupFixture({
      monthSummaries: { [monthKey(2026, 10)]: makeMonthSummary(2026, 10, { 5: 1 }) },
      dayDetails: { [day]: makeDayDetail(day) },
    });
    const user = userEvent.setup();

    render(<HistoryPanel />);
    await screen.findByText("Octubre 2026");
    await user.click(screen.getByRole("button", { name: "Día 5: 1 Pomodoros" }));
    await screen.findByText("Sin Pomodoros ese día.");
    getMock.mockClear();

    await user.type(screen.getByLabelText("Filtrar Historial"), "repo");

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith("/api/v1/history/day", {
        params: { query: { date: day, q: "repo" } },
      });
    });
  });

  it("resets the selected day when navigating to a different month", async () => {
    const day = isoDay(2026, 10, 5);
    setupFixture({
      monthSummaries: {
        [monthKey(2026, 10)]: makeMonthSummary(2026, 10, { 5: 1 }),
        [monthKey(2026, 11)]: makeMonthSummary(2026, 11),
      },
      dayDetails: { [day]: makeDayDetail(day) },
    });
    const user = userEvent.setup();

    render(<HistoryPanel />);
    await screen.findByText("Octubre 2026");
    await user.click(screen.getByRole("button", { name: "Día 5: 1 Pomodoros" }));
    await screen.findByText("Sin Pomodoros ese día.");

    await user.click(screen.getByRole("button", { name: "Mes siguiente" }));

    expect(await screen.findByText("Seleccioná un día para ver el detalle.")).toBeInTheDocument();
  });
});
