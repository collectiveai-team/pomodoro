import { afterEach, describe, expect, it, vi } from "vitest";
import { jsonResponse, stubSameOriginFetch } from "@/src/testing/fetch-stub";

async function importTimerClientWithFetch(fetchMock: typeof fetch) {
  stubSameOriginFetch(fetchMock);
  return import("./client");
}

const TIMER_BODY = {
  phase: "pomodoro_paused",
  task: { id: 1, text: "Write the panel" },
  break_kind: null,
  remaining_seconds: 1200,
  server_now: "2026-01-01T00:00:00.000Z",
};

describe("timer action wrappers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("sends Content-Type: application/json on a body-less pause request so csrf_guard accepts it", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(TIMER_BODY));
    const { pauseTimer } = await importTimerClientWithFetch(fetchMock);

    const result = await pauseTimer();

    expect(fetchMock).toHaveBeenCalledOnce();
    const request = fetchMock.mock.calls[0][0] as Request;
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/timer/pause");
    expect(request.headers.get("content-type")).toBe("application/json");
    expect(result).toEqual({ ok: true, timer: TIMER_BODY });
  });

  it("starts a Pomodoro via a real POST carrying the task id in the body", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(TIMER_BODY));
    const { startTimer } = await importTimerClientWithFetch(fetchMock);

    const result = await startTimer(42);

    expect(fetchMock).toHaveBeenCalledOnce();
    const request = fetchMock.mock.calls[0][0] as Request;
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/timer/start");
    expect(request.headers.get("content-type")).toBe("application/json");
    const body = await request.clone().json();
    expect(body).toEqual({ task_id: 42 });
    expect(result).toEqual({ ok: true, timer: TIMER_BODY });
  });

  it("issues a real POST to the matching endpoint for every body-less Timer action", async () => {
    const actions: Array<[string, string]> = [
      ["resumeTimer", "/api/timer/resume"],
      ["stopTimer", "/api/timer/stop"],
      ["logTimer", "/api/timer/log"],
      ["discardTimer", "/api/timer/discard"],
      ["startBreakTimer", "/api/timer/start-break"],
      ["skipBreakTimer", "/api/timer/skip-break"],
      ["nextPomodoroTimer", "/api/timer/next-pomodoro"],
    ];

    for (const [exportName, path] of actions) {
      const fetchMock = vi.fn<typeof fetch>(async () =>
        jsonResponse(TIMER_BODY),
      );
      const client = await importTimerClientWithFetch(fetchMock);
      const action = client[
        exportName as keyof typeof client
      ] as () => Promise<unknown>;

      await action();

      expect(fetchMock).toHaveBeenCalledOnce();
      const request = fetchMock.mock.calls[0][0] as Request;
      expect(request.method).toBe("POST");
      expect(new URL(request.url).pathname).toBe(path);
      expect(request.headers.get("content-type")).toBe("application/json");
    }
  });

  it("extracts the resynced Timer from a 409 conflict body instead of only reporting an error", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: TIMER_BODY }, 409),
    );
    const { stopTimer } = await importTimerClientWithFetch(fetchMock);

    const result = await stopTimer();

    expect(result).toEqual({
      ok: false,
      status: 409,
      message: expect.any(String),
      timer: TIMER_BODY,
    });
  });

  it("reports failure with no Timer to resync when the error body isn't Timer-shaped", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ detail: "no session" }), {
          status: 401,
        }),
    );
    const { pauseTimer } = await importTimerClientWithFetch(fetchMock);

    const result = await pauseTimer();

    expect(result).toEqual({
      ok: false,
      status: 401,
      message: "no session",
      timer: null,
    });
  });

  it("fetches the day summary via a real GET request", async () => {
    const summaryBody = { completed_today: 3, until_long_break: 2 };
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(summaryBody),
    );
    const { fetchDaySummary } = await importTimerClientWithFetch(fetchMock);

    const result = await fetchDaySummary();

    expect(fetchMock).toHaveBeenCalledOnce();
    const request = fetchMock.mock.calls[0][0] as Request;
    expect(request.method).toBe("GET");
    expect(new URL(request.url).pathname).toBe("/api/timer/summary");
    expect(result).toEqual(summaryBody);
  });
});
