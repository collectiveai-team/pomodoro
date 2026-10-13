import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TimerPanel } from "./timer-panel";

const getMock = vi.fn();
const postMock = vi.fn();
const patchMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
    PATCH: (...args: unknown[]) => patchMock(...args),
  },
}));

const idleTimer = {
  phase: "Idle",
  task: null,
  break_kind: null,
  phase_started_at: null,
  accumulated_active_seconds: 0,
  running_since: null,
  server_now: new Date().toISOString(),
  remaining_seconds: null,
  pomodoros_completed_today: 0,
  pomodoros_until_long_break: 4,
};

beforeEach(() => {
  getMock.mockReset();
  patchMock.mockReset();
  getMock.mockImplementation((path: string) => {
    const data =
      path === "/api/v1/timer"
        ? idleTimer
        : { alarm_enabled: false, notifications_enabled: false, time_zone: "UTC" };
    return Promise.resolve({ data, error: undefined, response: { status: 200 } as Response });
  });
  patchMock.mockResolvedValue({
    data: { alarm_enabled: true, notifications_enabled: false, time_zone: "America/Bogota" },
    error: undefined,
    response: { status: 200 } as Response,
  });
});

describe("TimerPanel — settings PATCH", () => {
  it("sends only the toggled field so a stored time zone is not overwritten", async () => {
    render(<TimerPanel />);
    fireEvent.click(await screen.findByLabelText("Alarm"));

    await waitFor(() => expect(patchMock).toHaveBeenCalled());
    expect(patchMock).toHaveBeenCalledWith("/api/v1/settings", {
      body: { alarm_enabled: true },
    });
  });
});
