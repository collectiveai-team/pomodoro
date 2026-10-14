import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TimerControls } from "./timer-controls";

function renderReady(breakKind: "short" | "long" | null) {
  render(
    <TimerControls
      phase="ReadyForNext"
      pending={false}
      breakKind={breakKind}
      accumulatedActiveSeconds={0}
      onAction={vi.fn()}
    />,
  );
}

describe("TimerControls — ReadyForNext Break label", () => {
  it("offers a long Break when the Timer's break_kind is long", () => {
    renderReady("long");
    expect(screen.getByRole("button", { name: "Iniciar Break largo" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Iniciar Break corto" })).not.toBeInTheDocument();
  });

  it("offers a short Break when the Timer's break_kind is short", () => {
    renderReady("short");
    expect(screen.getByRole("button", { name: "Iniciar Break corto" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Iniciar Break largo" })).not.toBeInTheDocument();
  });

  it("falls back to a short Break label when break_kind is null", () => {
    renderReady(null);
    expect(screen.getByRole("button", { name: "Iniciar Break corto" })).toBeInTheDocument();
  });
});

describe("TimerControls — primary and round secondary actions per phase", () => {
  const cases = [
    ["PomodoroRunning", "Pausar", "/api/v1/timer/pause", "Detener", "/api/v1/timer/stop"],
    ["PomodoroPaused", "Reanudar", "/api/v1/timer/resume", "Detener", "/api/v1/timer/stop"],
    ["BreakRunning", "Pausar", "/api/v1/timer/pause", "Saltar Break", "/api/v1/timer/skip-break"],
    ["BreakPaused", "Reanudar", "/api/v1/timer/resume", "Saltar Break", "/api/v1/timer/skip-break"],
    ["AskingToLog", "Registrar", "/api/v1/timer/log", "Descartar", "/api/v1/timer/discard"],
    [
      "ReadyForNext",
      "▶ Otro Pomodoro",
      "/api/v1/timer/next-pomodoro",
      "Iniciar Break corto",
      "/api/v1/timer/start-break",
    ],
  ] as const;

  it.each(cases)(
    "%s exposes %s and %s",
    async (phase, primary, primaryPath, secondary, secondaryPath) => {
      const onAction = vi.fn();
      const user = userEvent.setup();
      render(
        <TimerControls
          phase={phase}
          pending={false}
          breakKind="short"
          accumulatedActiveSeconds={600}
          onAction={onAction}
        />,
      );
      await user.click(screen.getByRole("button", { name: primary }));
      await user.click(screen.getByRole("button", { name: secondary }));
      expect(onAction.mock.calls).toEqual([[primaryPath], [secondaryPath]]);
    },
  );

  it("asks how many minutes to log when AskingToLog", () => {
    render(
      <TimerControls
        phase="AskingToLog"
        pending={false}
        breakKind={null}
        accumulatedActiveSeconds={600}
        onAction={vi.fn()}
      />,
    );
    expect(screen.getByText(/¿Registrar \d+ min\?/)).toBeInTheDocument();
  });

  it("disables both actions while pending", () => {
    render(
      <TimerControls
        phase="PomodoroRunning"
        pending
        breakKind={null}
        accumulatedActiveSeconds={0}
        onAction={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Pausar" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Detener" })).toBeDisabled();
  });

  it("shows a placeholder when no Pomodoro is in progress", () => {
    render(
      <TimerControls
        phase="Idle"
        pending={false}
        breakKind={null}
        accumulatedActiveSeconds={0}
        onAction={vi.fn()}
      />,
    );
    expect(screen.getByText("Sin Pomodoro en curso.")).toBeInTheDocument();
  });
});
