import { render, screen } from "@testing-library/react";
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
