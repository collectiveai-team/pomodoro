import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TIMER_CHANGED_EVENT } from "@/lib/timer-sync";
import { makeTimer, okResult } from "./task-fixtures";
import { TimerPanel } from "./timer-panel";

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
  },
}));

let current = makeTimer("Idle");

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  current = makeTimer("Idle");
  getMock.mockImplementation((path: string) => {
    const data = path === "/api/v1/timer" ? current : { alarm_enabled: false };
    return okResult(data);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TimerPanel — phase broadcast", () => {
  it("broadcasts a phase change found by a passive refetch, once, without looping", async () => {
    current = makeTimer("BreakRunning", 1);
    const events: CustomEvent[] = [];
    window.addEventListener(TIMER_CHANGED_EVENT, (e) => events.push(e as CustomEvent));
    render(<TimerPanel />);
    await screen.findAllByText(/Break/);
    expect(events).toHaveLength(0);

    current = makeTimer("Idle");
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
