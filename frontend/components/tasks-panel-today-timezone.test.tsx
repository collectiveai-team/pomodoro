import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IDLE_TIMER, makeTask } from "./task-fixtures";
import { TasksPanel } from "./tasks-panel";

const getMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: { GET: (...args: unknown[]) => getMock(...args) },
}));

function result(data: unknown) {
  return Promise.resolve({ data, error: undefined, response: { status: 200 } as Response });
}

beforeEach(() => {
  getMock.mockReset();
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-10-14T12:00:00Z") });
  getMock.mockImplementation((path: string) => {
    if (path === "/api/v1/settings") return result({ time_zone: "Pacific/Kiritimati" });
    if (path === "/api/v1/tags") return result({ tags: [] });
    if (path === "/api/v1/timer") return result({ ...IDLE_TIMER });
    if (path === "/api/v1/history/day") {
      return result({ day: "2026-10-15", completed_count: 0, tasks: [] });
    }
    return result({ tasks: [makeTask("a", "Write report")], active_count: 1, archived_count: 0 });
  });
});

afterEach(() => vi.useRealTimers());

describe("TasksPanel — today in the User's time zone", () => {
  it("queries history/day with the day in the saved zone, not the browser's", async () => {
    render(<TasksPanel />);
    await screen.findByText("Write report");

    await vi.waitFor(() => {
      expect(getMock).toHaveBeenCalledWith("/api/v1/history/day", {
        params: { query: { date: "2026-10-15" } },
      });
    });
  });
});
