import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TIMER_CHANGED_EVENT } from "@/lib/timer-sync";
import { TimerPanel } from "./timer-panel";

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
  },
}));

function timer(phase: string, remaining: number | null = null) {
  return {
    phase,
    task: null,
    break_kind: phase === "BreakRunning" ? "short" : null,
    phase_started_at: null,
    accumulated_active_seconds: 0,
    running_since: null,
    server_now: new Date().toISOString(),
    remaining_seconds: remaining,
    pomodoros_completed_today: 0,
    pomodoros_until_long_break: 4,
  };
}

let current = timer("Idle");

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  current = timer("Idle");
  getMock.mockImplementation((path: string) => {
    const data = path === "/api/v1/timer" ? current : { alarm_enabled: false };
    return Promise.resolve({ data, error: undefined, response: { status: 200 } as Response });
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TimerPanel — phase broadcast", () => {
  it("broadcasts a phase change found by a passive refetch, once, without looping", async () => {
    current = timer("BreakRunning", 1);
    const events: CustomEvent[] = [];
    window.addEventListener(TIMER_CHANGED_EVENT, (e) => events.push(e as CustomEvent));
    render(<TimerPanel />);
    await screen.findAllByText(/Break/);
    expect(events).toHaveLength(0);

    current = timer("Idle");
    await waitFor(() => expect(events).toHaveLength(1), { timeout: 4000 });

    expect(events[0]?.detail).toEqual({ phase: "Idle", taskId: null });
    await new Promise((resolve) => setTimeout(resolve, 200));
    expect(events).toHaveLength(1);
  });

  it("does not broadcast when a refetch finds the same phase", async () => {
    const events: Event[] = [];
    window.addEventListener(TIMER_CHANGED_EVENT, (e) => events.push(e));
    render(<TimerPanel />);
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    window.dispatchEvent(new Event("focus"));
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(events).toHaveLength(0);
  });
});
