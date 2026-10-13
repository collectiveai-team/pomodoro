import { describe, expect, it } from "vitest";
import type { components } from "@/lib/api/schema";
import {
  canNotify,
  canPlayAlarm,
  shouldFireOnPhaseEnd,
  shouldRequestNotificationPermission,
} from "./alarm";

type TimerPhase = components["schemas"]["TimerPhase"];

const ALL_PHASES: TimerPhase[] = [
  "Idle",
  "PomodoroRunning",
  "PomodoroPaused",
  "AskingToLog",
  "BreakRunning",
  "BreakPaused",
  "ReadyForNext",
];

describe("shouldFireOnPhaseEnd", () => {
  it("fires when a running Pomodoro completes on its own (Story 51)", () => {
    expect(shouldFireOnPhaseEnd("PomodoroRunning", "ReadyForNext", "passive")).toBe(true);
  });

  it("fires when a running Break ends on its own (Story 61)", () => {
    expect(shouldFireOnPhaseEnd("BreakRunning", "Idle", "passive")).toBe(true);
  });

  it("never fires when the phase changed because this tab called an action", () => {
    expect(shouldFireOnPhaseEnd("PomodoroRunning", "ReadyForNext", "action")).toBe(false);
    expect(shouldFireOnPhaseEnd("BreakRunning", "Idle", "action")).toBe(false);
  });

  it("never fires for a skipped Break, even though it also lands on Idle (Story 60)", () => {
    // Skipping a Break is always observed as an "action" trigger by the caller, not "passive".
    expect(shouldFireOnPhaseEnd("BreakRunning", "Idle", "action")).toBe(false);
  });

  it("never fires for an interrupted-and-logged Pomodoro returning to Idle (Story 55)", () => {
    expect(shouldFireOnPhaseEnd("AskingToLog", "Idle", "passive")).toBe(false);
    expect(shouldFireOnPhaseEnd("AskingToLog", "Idle", "action")).toBe(false);
  });

  it("never fires across every other phase pair, passive or action", () => {
    const naturalEndPairs = new Set(["PomodoroRunning>ReadyForNext", "BreakRunning>Idle"]);
    for (const previousPhase of ALL_PHASES) {
      for (const nextPhase of ALL_PHASES) {
        const isNaturalEndPair = naturalEndPairs.has(`${previousPhase}>${nextPhase}`);
        if (isNaturalEndPair) {
          continue;
        }
        expect(shouldFireOnPhaseEnd(previousPhase, nextPhase, "passive")).toBe(false);
        expect(shouldFireOnPhaseEnd(previousPhase, nextPhase, "action")).toBe(false);
      }
    }
  });
});

describe("canPlayAlarm", () => {
  it("is silent when the Alarm preference is disabled, even if unlocked", () => {
    expect(canPlayAlarm(false, true)).toBe(false);
  });

  it("is silent until the User's first interaction unlocks autoplay", () => {
    expect(canPlayAlarm(true, false)).toBe(false);
  });

  it("plays only when enabled and unlocked", () => {
    expect(canPlayAlarm(true, true)).toBe(true);
  });
});

describe("shouldRequestNotificationPermission", () => {
  it("prompts only when the browser has not yet decided", () => {
    expect(shouldRequestNotificationPermission("default")).toBe(true);
  });

  it("never re-prompts once denied", () => {
    expect(shouldRequestNotificationPermission("denied")).toBe(false);
  });

  it("does not need to prompt again once already granted", () => {
    expect(shouldRequestNotificationPermission("granted")).toBe(false);
  });
});

describe("canNotify", () => {
  it("requires both the preference on and permission already granted", () => {
    expect(canNotify(true, "granted")).toBe(true);
    expect(canNotify(false, "granted")).toBe(false);
    expect(canNotify(true, "denied")).toBe(false);
    expect(canNotify(true, "default")).toBe(false);
  });
});
