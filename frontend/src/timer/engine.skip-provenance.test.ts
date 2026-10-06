import { describe, expect, it, vi } from "vitest";
import { createTimerEngine, type TimerSnapshot } from "./engine";

/**
 * Story 60: skipping a Break must never sound the Alarm.
 *
 * `applySnapshot` decides "ended on its own" from a phase diff plus a
 * `causedByAction` flag that is only ever set by *this* engine instance's own
 * action. Story 65 promises one shared Timer across tabs and devices, so the
 * Break a User skips in one tab is routinely observed by another tab purely
 * as a `break_running -> idle` re-fetch -- indistinguishable, from the phase
 * diff alone, from a Break that really elapsed. The engine instead checks
 * whether *this* client's own elapsed time since the last snapshot is enough
 * for the previous countdown to have reached zero.
 */

function snapshot(
  phase: string,
  extra: Partial<TimerSnapshot> = {},
): TimerSnapshot {
  return {
    phase,
    task: null,
    break_kind: null,
    remaining_seconds: null,
    server_now: "2026-01-01T00:00:00Z",
    ...extra,
  } as TimerSnapshot;
}

/** An engine already synced to a Break running on the shared server Timer. */
async function duringABreak(remainingSeconds: number) {
  const onAlarm = vi.fn();
  let clientNow = Date.parse("2026-01-01T00:00:00Z");
  const server = {
    current: snapshot("break_running", {
      remaining_seconds: remainingSeconds,
      break_kind: "short",
    }),
  };
  const engine = createTimerEngine({
    fetchTimer: async () => server.current,
    now: () => clientNow,
    subscribeToRefocus: () => () => {},
    onAlarm,
  });
  await engine.refetch();
  return {
    engine,
    server,
    onAlarm,
    advance: (milliseconds: number) => {
      clientNow += milliseconds;
    },
  };
}

describe("the Alarm and a Break that stopped running elsewhere", () => {
  it("stays silent when another tab skipped the Break", async () => {
    const { engine, server, onAlarm } = await duringABreak(300);

    // Another tab (or another device) presses "Saltar Break". No Break ran to
    // completion anywhere; the shared Timer is simply Idle now.
    server.current = snapshot("idle");
    await engine.refetch(); // this tab regains focus and re-syncs

    expect(onAlarm).not.toHaveBeenCalled();
  });

  it("still rings when the Break really did elapse", async () => {
    const { engine, server, onAlarm, advance } = await duringABreak(1);

    advance(1_000);
    server.current = snapshot("idle");
    await engine.refetch();

    expect(onAlarm).toHaveBeenCalledTimes(1);
  });

  it("stays silent for a skip this very engine performed", async () => {
    const { engine, onAlarm } = await duringABreak(300);

    engine.applyActionResult(snapshot("idle"));

    expect(onAlarm).not.toHaveBeenCalled();
  });
});
