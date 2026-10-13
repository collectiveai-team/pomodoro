import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { broadcastTimerChanged } from "@/lib/timer-sync";
import { useTimerPhase } from "@/lib/use-timer-phase";

const getMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: { GET: (...args: unknown[]) => getMock(...args) },
}));

function timerResponse(phase: string, taskId: string | null) {
  return {
    data: { phase, task: taskId ? { id: taskId, text: "t" } : null },
    error: undefined,
    response: { status: 200 } as Response,
  };
}

beforeEach(() => {
  getMock.mockReset();
});

describe("useTimerPhase", () => {
  it("exposes the phase and the Task id from the initial fetch", async () => {
    getMock.mockResolvedValue(timerResponse("PomodoroRunning", "task-7"));

    const { result } = renderHook(() => useTimerPhase());

    await waitFor(() => expect(result.current.phase).toBe("PomodoroRunning"));
    expect(result.current.taskId).toBe("task-7");
  });

  it("applies a broadcast snapshot without requesting the Timer again", async () => {
    getMock.mockResolvedValue(timerResponse("BreakRunning", "task-7"));
    const { result } = renderHook(() => useTimerPhase());
    await waitFor(() => expect(result.current.phase).toBe("BreakRunning"));
    getMock.mockClear();

    act(() => broadcastTimerChanged({ phase: "Idle", taskId: null }));

    expect(result.current.phase).toBe("Idle");
    expect(result.current.taskId).toBeNull();
    expect(getMock).not.toHaveBeenCalled();
  });

  it("refetches on a bare broadcast", async () => {
    getMock.mockResolvedValue(timerResponse("Idle", null));
    const { result } = renderHook(() => useTimerPhase());
    await waitFor(() => expect(result.current.phase).toBe("Idle"));
    getMock.mockResolvedValue(timerResponse("PomodoroRunning", "task-2"));

    act(() => broadcastTimerChanged());

    await waitFor(() => expect(result.current.phase).toBe("PomodoroRunning"));
    expect(result.current.taskId).toBe("task-2");
  });
});
