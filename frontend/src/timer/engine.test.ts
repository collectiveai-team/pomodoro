import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createTimerEngine,
  isNaturalCompletion,
  remainingSecondsAt,
  type TimerSnapshot,
} from "./engine";

function snapshot(overrides: Partial<TimerSnapshot> = {}): TimerSnapshot {
  return {
    phase: "pomodoro_running",
    task: { id: 1, text: "Write the engine" },
    break_kind: null,
    remaining_seconds: 1500,
    server_now: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("remainingSecondsAt", () => {
  it("decays by elapsed client time when client and server clocks agree", () => {
    const fetchedAtClientMs = Date.parse("2026-01-01T00:00:00.000Z");
    const result = remainingSecondsAt(
      snapshot({ remaining_seconds: 100 }),
      fetchedAtClientMs,
      fetchedAtClientMs + 10_000,
    );
    expect(result).toBe(90);
  });

  it("corrects for clock skew instead of comparing server_now to the client's uncorrected clock", () => {
    // The client's clock is 5 minutes ahead of the server's. A naive
    // implementation that compared `server_now + remaining_seconds` against
    // the client's own current time (assuming the clocks agree) would read
    // this as already expired. Anchoring on the client's own elapsed time
    // since the fetch (what this function does) is immune to the skew.
    const serverNowMs = Date.parse("2026-01-01T00:00:00.000Z");
    const skewMs = 5 * 60 * 1000;
    const fetchedAtClientMs = serverNowMs + skewMs;
    const tenSecondsLaterClientMs = fetchedAtClientMs + 10_000;

    const result = remainingSecondsAt(
      snapshot({
        remaining_seconds: 100,
        server_now: new Date(serverNowMs).toISOString(),
      }),
      fetchedAtClientMs,
      tenSecondsLaterClientMs,
    );

    expect(result).toBe(90);
  });

  it("never goes below zero", () => {
    const fetchedAtClientMs = Date.parse("2026-01-01T00:00:00.000Z");
    const result = remainingSecondsAt(
      snapshot({ remaining_seconds: 5 }),
      fetchedAtClientMs,
      fetchedAtClientMs + 60_000,
    );
    expect(result).toBe(0);
  });

  it("returns null when the phase has no countdown (e.g. Idle, AskingToLog)", () => {
    const fetchedAtClientMs = Date.parse("2026-01-01T00:00:00.000Z");
    const result = remainingSecondsAt(
      snapshot({ remaining_seconds: null, phase: "idle" }),
      fetchedAtClientMs,
      fetchedAtClientMs + 1000,
    );
    expect(result).toBeNull();
  });
});

describe("isNaturalCompletion", () => {
  it("is true for a Pomodoro that reached 25 minutes on its own", () => {
    expect(isNaturalCompletion("pomodoro_running", "ready_for_next")).toBe(
      true,
    );
  });

  it("is true for a Break that ran out on its own", () => {
    expect(isNaturalCompletion("break_running", "idle")).toBe(true);
  });

  it("is false for a Pomodoro the User stopped themselves", () => {
    expect(isNaturalCompletion("pomodoro_running", "asking_to_log")).toBe(
      false,
    );
  });

  it("is false with no prior known phase", () => {
    expect(isNaturalCompletion(null, "ready_for_next")).toBe(false);
  });

  it("is false for unrelated phase pairs", () => {
    expect(isNaturalCompletion("idle", "pomodoro_running")).toBe(false);
  });
});

describe("createTimerEngine", () => {
  function fakeClock(startMs: number) {
    let currentMs = startMs;
    return {
      now: () => currentMs,
      advance: (deltaMs: number) => {
        currentMs += deltaMs;
      },
    };
  }

  it("fires the alarm when a passive re-fetch reveals a Pomodoro that completed on its own", async () => {
    const onAlarm = vi.fn();
    const clock = fakeClock(Date.parse("2026-01-01T00:00:00.000Z"));
    let nextFetchResult: TimerSnapshot = snapshot({
      phase: "pomodoro_running",
      remaining_seconds: 1500,
    });
    const engine = createTimerEngine({
      now: clock.now,
      onAlarm,
      fetchTimer: async () => nextFetchResult,
      subscribeToRefocus: () => () => {},
    });

    engine.applySnapshot(nextFetchResult);
    expect(onAlarm).not.toHaveBeenCalled();

    // The real elapsed time a re-fetch triggered by the zero-crossing tick
    // (or a focus regain after a long absence) would actually see: without
    // this, the engine can't tell a real natural completion from a Break/
    // Pomodoro another tab ended early (story 65's shared Timer).
    clock.advance(1_500_000);
    nextFetchResult = snapshot({
      phase: "ready_for_next",
      remaining_seconds: null,
      task: null,
    });
    await engine.refetch();

    expect(onAlarm).toHaveBeenCalledOnce();
  });

  it("fires the alarm when a passive re-fetch reveals a Break that ended on its own", async () => {
    const onAlarm = vi.fn();
    const clock = fakeClock(Date.parse("2026-01-01T00:00:00.000Z"));
    const engine = createTimerEngine({
      now: clock.now,
      onAlarm,
      fetchTimer: async () =>
        snapshot({ phase: "idle", remaining_seconds: null, task: null }),
      subscribeToRefocus: () => () => {},
    });

    engine.applySnapshot(
      snapshot({ phase: "break_running", break_kind: "short" }),
    );
    clock.advance(1_500_000);
    await engine.refetch();

    expect(onAlarm).toHaveBeenCalledOnce();
  });

  it("never fires the alarm for a Pomodoro the User stopped themselves", async () => {
    const onAlarm = vi.fn();
    const clock = fakeClock(Date.parse("2026-01-01T00:00:00.000Z"));
    const engine = createTimerEngine({
      now: clock.now,
      onAlarm,
      subscribeToRefocus: () => () => {},
    });

    engine.applySnapshot(snapshot({ phase: "pomodoro_running" }));
    engine.applyActionResult(
      snapshot({ phase: "asking_to_log", remaining_seconds: null }),
    );

    expect(onAlarm).not.toHaveBeenCalled();
  });

  it("never fires the alarm for a Break the User skipped themselves, even though skip lands on the same Idle phase a natural end does", async () => {
    const onAlarm = vi.fn();
    const clock = fakeClock(Date.parse("2026-01-01T00:00:00.000Z"));
    const engine = createTimerEngine({
      now: clock.now,
      onAlarm,
      subscribeToRefocus: () => () => {},
    });

    engine.applySnapshot(
      snapshot({ phase: "break_running", break_kind: "short" }),
    );
    engine.applyActionResult(
      snapshot({
        phase: "idle",
        remaining_seconds: null,
        break_kind: null,
        task: null,
      }),
    );

    expect(onAlarm).not.toHaveBeenCalled();
  });

  it("re-fetches at most once when the local countdown reaches zero, rather than assuming completion locally", async () => {
    const onAlarm = vi.fn();
    const clock = fakeClock(Date.parse("2026-01-01T00:00:00.000Z"));
    const fetchTimer = vi.fn<() => Promise<TimerSnapshot>>(async () =>
      snapshot({
        phase: "ready_for_next",
        remaining_seconds: null,
        task: null,
      }),
    );
    const engine = createTimerEngine({
      now: clock.now,
      onAlarm,
      fetchTimer,
      subscribeToRefocus: () => () => {},
    });

    engine.applySnapshot(
      snapshot({ phase: "pomodoro_running", remaining_seconds: 2 }),
    );
    expect(engine.getRemainingSeconds()).toBe(2);

    clock.advance(2_000);
    expect(engine.getRemainingSeconds()).toBe(0);

    engine.tick();
    engine.tick();
    engine.tick();
    // Let the in-flight refetch's promise microtasks settle.
    await Promise.resolve();
    await Promise.resolve();

    expect(fetchTimer).toHaveBeenCalledOnce();
    expect(onAlarm).toHaveBeenCalledOnce();
  });

  it("re-fetches on focus/visibility regain via the injected subscription", () => {
    let triggerRefocus: () => void = () => {
      throw new Error("not subscribed");
    };
    const fetchTimer = vi.fn<() => Promise<TimerSnapshot>>(async () =>
      snapshot(),
    );
    const clock = fakeClock(Date.parse("2026-01-01T00:00:00.000Z"));
    createTimerEngine({
      now: clock.now,
      fetchTimer,
      subscribeToRefocus: (onRefocus) => {
        triggerRefocus = onRefocus;
        return () => {};
      },
    });

    triggerRefocus();

    expect(fetchTimer).toHaveBeenCalledOnce();
  });

  it("unsubscribes from refocus events on dispose", () => {
    const unsubscribe = vi.fn();
    const engine = createTimerEngine({
      subscribeToRefocus: () => unsubscribe,
    });

    engine.dispose();

    expect(unsubscribe).toHaveBeenCalledOnce();
  });
});

/**
 * `src/api/client.ts` captures `globalThis.fetch` once, at module-evaluation
 * time (openapi-fetch's default). Each test here stubs the global first and
 * re-imports both the client and the engine fresh, following the pattern
 * `src/auth/client.test.ts` established for the same constraint.
 */
class SameOriginRequest extends Request {
  constructor(input: string | URL | Request, init?: RequestInit) {
    super(
      typeof input === "string" ? new URL(input, "http://localhost") : input,
      init,
    );
  }
}

async function importEngineWithFetch(fetchMock: typeof fetch) {
  vi.resetModules();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("Request", SameOriginRequest);
  return import("./engine");
}

describe("createTimerEngine's default fetchTimer (real generated-client wrapper)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("issues a real GET /api/timer request and applies the resulting snapshot", async () => {
    const body: TimerSnapshot = snapshot({
      phase: "idle",
      remaining_seconds: null,
      task: null,
    });
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const { createTimerEngine: createEngine } =
      await importEngineWithFetch(fetchMock);

    const engine = createEngine({ subscribeToRefocus: () => () => {} });
    await engine.refetch();

    expect(fetchMock).toHaveBeenCalledOnce();
    const request = fetchMock.mock.calls[0][0] as Request;
    expect(request.method).toBe("GET");
    expect(new URL(request.url).pathname).toBe("/api/timer");
    expect(engine.getSnapshot()).toEqual(body);
  });

  it("surfaces a thrown error instead of silently applying no snapshot when the server rejects the request", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ detail: "no session" }), { status: 401 }),
    );
    const { createTimerEngine: createEngine } =
      await importEngineWithFetch(fetchMock);

    const engine = createEngine({ subscribeToRefocus: () => () => {} });

    await expect(engine.refetch()).rejects.toThrow("no session");
    expect(engine.getSnapshot()).toBeNull();
  });
});
