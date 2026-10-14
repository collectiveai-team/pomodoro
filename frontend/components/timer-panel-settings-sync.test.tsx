import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { broadcastSettingsChanged } from "@/lib/settings-sync";
import { makeTimer, okResult } from "./task-fixtures";
import { TimerPanel } from "./timer-panel";

const getMock = vi.fn();
const postMock = vi.fn();
const playAlarmMock = vi.fn();
const notifyPhaseEndMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
  },
}));

vi.mock("@/lib/alarm", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/alarm")>()),
  playAlarm: (...args: unknown[]) => playAlarmMock(...args),
  notifyPhaseEnd: (...args: unknown[]) => notifyPhaseEndMock(...args),
}));

const storedSettings = { alarm_enabled: false, notifications_enabled: false, time_zone: "UTC" };
let current = makeTimer("BreakRunning", 100);

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  playAlarmMock.mockReset();
  notifyPhaseEndMock.mockReset();
  current = makeTimer("BreakRunning", 100);
  getMock.mockImplementation((path: string) => {
    const data = path === "/api/v1/timer" ? current : storedSettings;
    return okResult(data);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function endBreakPassively() {
  current = makeTimer("Idle");
  await act(async () => {
    window.dispatchEvent(new Event("focus"));
  });
}

describe("TimerPanel — Settings broadcast from the Account menu", () => {
  it("uses Settings broadcast as enabled when the phase ends on its own", async () => {
    render(<TimerPanel />);
    await screen.findAllByText(/Break/);
    act(() => {
      broadcastSettingsChanged({
        ...storedSettings,
        alarm_enabled: true,
        notifications_enabled: true,
      });
    });

    await endBreakPassively();

    await waitFor(() => expect(playAlarmMock).toHaveBeenCalledWith(true));
    expect(notifyPhaseEndMock.mock.calls[0]?.[0]).toBe(true);
  });

  it("stays silent when the broadcast Settings turn the Alarm and notifications off", async () => {
    getMock.mockImplementation((path: string) => {
      const data =
        path === "/api/v1/timer"
          ? current
          : { ...storedSettings, alarm_enabled: true, notifications_enabled: true };
      return okResult(data);
    });
    render(<TimerPanel />);
    await screen.findAllByText(/Break/);
    act(() => {
      broadcastSettingsChanged(storedSettings);
    });

    await endBreakPassively();

    await waitFor(() => expect(playAlarmMock).toHaveBeenCalledWith(false));
    expect(notifyPhaseEndMock.mock.calls[0]?.[0]).toBe(false);
  });
});
