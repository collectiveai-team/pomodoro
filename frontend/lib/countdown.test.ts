import { describe, expect, it } from "vitest";
import {
  correctedRemainingSeconds,
  formatClock,
  minutesForLog,
  phaseTotalSeconds,
  remainingFraction,
  syncClock,
} from "./countdown";

describe("syncClock", () => {
  it("is zero when the client and server clocks agree", () => {
    const serverNowIso = "2026-01-01T12:00:00.000Z";
    const clientNowMs = new Date(serverNowIso).getTime();
    expect(syncClock(serverNowIso, clientNowMs).offsetMs).toBe(0);
  });

  it("captures a positive offset when the client clock runs behind the server", () => {
    const serverNowIso = "2026-01-01T12:00:10.000Z";
    const clientNowMs = new Date("2026-01-01T12:00:00.000Z").getTime();
    expect(syncClock(serverNowIso, clientNowMs).offsetMs).toBe(10_000);
  });

  it("captures a negative offset when the client clock runs ahead of the server", () => {
    const serverNowIso = "2026-01-01T12:00:00.000Z";
    const clientNowMs = new Date("2026-01-01T12:00:10.000Z").getTime();
    expect(syncClock(serverNowIso, clientNowMs).offsetMs).toBe(-10_000);
  });
});

describe("correctedRemainingSeconds", () => {
  const serverNowIso = "2026-01-01T12:00:00.000Z";

  it("counts down one second per elapsed real second when clocks agree", () => {
    const clientFetchMs = new Date(serverNowIso).getTime();
    const sync = syncClock(serverNowIso, clientFetchMs);

    const remaining = correctedRemainingSeconds({
      remainingSecondsAtFetch: 1500,
      serverNowIso,
      sync,
      clientNowMs: clientFetchMs + 7_000,
    });

    expect(remaining).toBe(1493);
  });

  it("is unaffected by a client clock that is skewed but not drifting", () => {
    // The client clock reads 1 hour ahead of the server at every instant.
    const clientFetchMs = new Date(serverNowIso).getTime() + 3_600_000;
    const sync = syncClock(serverNowIso, clientFetchMs);

    const remaining = correctedRemainingSeconds({
      remainingSecondsAtFetch: 1500,
      serverNowIso,
      sync,
      clientNowMs: clientFetchMs + 7_000,
    });

    expect(remaining).toBe(1493);
  });

  it("is unaffected by a client clock that is skewed behind the server", () => {
    const clientFetchMs = new Date(serverNowIso).getTime() - 3_600_000;
    const sync = syncClock(serverNowIso, clientFetchMs);

    const remaining = correctedRemainingSeconds({
      remainingSecondsAtFetch: 1500,
      serverNowIso,
      sync,
      clientNowMs: clientFetchMs + 7_000,
    });

    expect(remaining).toBe(1493);
  });

  it("clamps at zero instead of going negative past the end of the phase", () => {
    const clientFetchMs = new Date(serverNowIso).getTime();
    const sync = syncClock(serverNowIso, clientFetchMs);

    const remaining = correctedRemainingSeconds({
      remainingSecondsAtFetch: 5,
      serverNowIso,
      sync,
      clientNowMs: clientFetchMs + 30_000,
    });

    expect(remaining).toBe(0);
  });
});

describe("phaseTotalSeconds", () => {
  it("is null when the phase has no countdown (Idle, AskingToLog, ReadyForNext)", () => {
    expect(
      phaseTotalSeconds({
        remainingSecondsAtFetch: null,
        accumulatedActiveSeconds: 400,
        runningSinceIso: null,
        serverNowIso: "2026-01-01T12:00:00.000Z",
      }),
    ).toBeNull();
  });

  it("derives the total from remaining plus accumulated active time while paused", () => {
    const total = phaseTotalSeconds({
      remainingSecondsAtFetch: 1100,
      accumulatedActiveSeconds: 400,
      runningSinceIso: null,
      serverNowIso: "2026-01-01T12:00:00.000Z",
    });

    expect(total).toBe(1500);
  });

  it("derives the total from remaining plus active time elapsed while running", () => {
    const total = phaseTotalSeconds({
      remainingSecondsAtFetch: 1090,
      accumulatedActiveSeconds: 400,
      runningSinceIso: "2026-01-01T11:59:50.000Z",
      serverNowIso: "2026-01-01T12:00:00.000Z",
    });

    expect(total).toBe(1500);
  });
});

describe("remainingFraction", () => {
  it("is 1 at the start of a phase and 0 at the end", () => {
    expect(remainingFraction(1500, 1500)).toBe(1);
    expect(remainingFraction(0, 1500)).toBe(0);
  });

  it("is 0 when there is no total (no active countdown)", () => {
    expect(remainingFraction(0, null)).toBe(0);
  });

  it("clamps outside [0, 1] for stale or inconsistent inputs", () => {
    expect(remainingFraction(-10, 1500)).toBe(0);
    expect(remainingFraction(2000, 1500)).toBe(1);
  });
});

describe("formatClock", () => {
  it("formats whole minutes and seconds as MM:SS", () => {
    expect(formatClock(1500)).toBe("25:00");
    expect(formatClock(65)).toBe("1:05");
    expect(formatClock(0)).toBe("0:00");
  });

  it("never renders a negative clock", () => {
    expect(formatClock(-5)).toBe("0:00");
  });
});

describe("minutesForLog", () => {
  it("rounds active seconds to the nearest whole minute", () => {
    expect(minutesForLog(0)).toBe(0);
    expect(minutesForLog(29)).toBe(0);
    expect(minutesForLog(30)).toBe(1);
    expect(minutesForLog(90)).toBe(2);
  });
});
