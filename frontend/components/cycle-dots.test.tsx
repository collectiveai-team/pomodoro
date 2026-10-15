import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CycleDots } from "./cycle-dots";

type Phase = Parameters<typeof CycleDots>[0]["phase"];
type BreakKind = Parameters<typeof CycleDots>[0]["breakKind"];

function renderDots(phase: Phase, untilLongBreak: number, breakKind: BreakKind = null) {
  render(
    <CycleDots phase={phase} breakKind={breakKind} pomodorosUntilLongBreak={untilLongBreak} />,
  );
  const group = screen.getByRole("img");
  return {
    group,
    filled: group.querySelectorAll("[data-filled='true']").length,
    total: group.querySelectorAll("[data-filled]").length,
  };
}

describe("CycleDots", () => {
  it("shows 5 empty dots at the start of a cycle", () => {
    const { filled, total, group } = renderDots("Idle", 5);
    expect(total).toBe(5);
    expect(filled).toBe(0);
    expect(group).toHaveAccessibleName("Ciclo: 0 de 5 Pomodoros");
  });

  it("fills one dot after the first Pomodoro of the cycle", () => {
    const { filled, group } = renderDots("ReadyForNext", 4, "short");
    expect(filled).toBe(1);
    expect(group).toHaveAccessibleName("Ciclo: 1 de 5 Pomodoros");
  });

  it("fills four dots while the fifth Pomodoro runs", () => {
    expect(renderDots("PomodoroRunning", 1).filled).toBe(4);
  });

  it("fills all five dots once the fifth Pomodoro completes", () => {
    expect(renderDots("ReadyForNext", 0, "long").filled).toBe(5);
  });

  it.each(["BreakRunning", "BreakPaused"] as const)(
    "keeps all five dots filled during the long Break (%s)",
    (phase) => {
      expect(renderDots(phase, 5, "long").filled).toBe(5);
    },
  );

  it("empties the dots when the long Break is over", () => {
    expect(renderDots("Idle", 5, "long").filled).toBe(0);
  });

  it("does not fill extra dots during a short Break", () => {
    expect(renderDots("BreakRunning", 3, "short").filled).toBe(2);
  });
});
