import { describe, expect, it } from "vitest";
import { isTimerTask } from "./timer-task";

describe("isTimerTask", () => {
  it("is true only for the Timer's Task while the phase is not Idle", () => {
    expect(isTimerTask("PomodoroRunning", "a", "a")).toBe(true);
    expect(isTimerTask("ReadyForNext", "a", "a")).toBe(true);
    expect(isTimerTask("PomodoroRunning", "a", "b")).toBe(false);
    expect(isTimerTask("Idle", "a", "a")).toBe(false);
    expect(isTimerTask(null, "a", "a")).toBe(false);
    expect(isTimerTask("PomodoroRunning", null, "a")).toBe(false);
  });
});
