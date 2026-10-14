import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useUserToday } from "./use-user-today";

const getMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: { GET: (...args: unknown[]) => getMock(...args) },
}));

beforeEach(() => {
  getMock.mockReset();
  getMock.mockResolvedValue({ data: { time_zone: "UTC" }, response: { status: 200 } });
  vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
  vi.setSystemTime(new Date("2026-10-14T23:59:30Z"));
});

afterEach(() => vi.useRealTimers());

describe("useUserToday", () => {
  it("rolls over to the next day at midnight in the saved zone while the page stays open", async () => {
    const { result } = renderHook(() => useUserToday());
    await act(async () => {});
    expect(result.current).toBe("2026-10-14");

    act(() => {
      vi.advanceTimersByTime(60_000);
    });

    expect(result.current).toBe("2026-10-15");
  });

  it("re-reads the day when the window regains focus after the machine slept past midnight", async () => {
    const { result } = renderHook(() => useUserToday());
    await act(async () => {});
    expect(result.current).toBe("2026-10-14");

    vi.setSystemTime(new Date("2026-10-15T08:00:00Z"));
    act(() => {
      window.dispatchEvent(new Event("focus"));
    });

    expect(result.current).toBe("2026-10-15");
  });
});
