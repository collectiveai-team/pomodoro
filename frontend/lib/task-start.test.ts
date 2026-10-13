import { describe, expect, it } from "vitest";
import { isTaskStartDisabled } from "./task-start";

describe("isTaskStartDisabled", () => {
  it.each(["Idle", "ReadyForNext"] as const)("is enabled in %s", (phase) => {
    expect(isTaskStartDisabled(phase)).toBe(false);
  });

  it.each([
    "PomodoroRunning",
    "PomodoroPaused",
    "BreakRunning",
    "BreakPaused",
    "AskingToLog",
  ] as const)("is disabled in %s", (phase) => {
    expect(isTaskStartDisabled(phase)).toBe(true);
  });

  it("is disabled while the phase is still unknown", () => {
    expect(isTaskStartDisabled(null)).toBe(true);
  });
});
