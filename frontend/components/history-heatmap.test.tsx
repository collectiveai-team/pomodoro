import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HistoryHeatmap } from "./history-heatmap";

const MONTH = { year: 2026, month: 9 };

function renderHeatmap(counts: Record<number, number>) {
  const days = Array.from({ length: 30 }, (_, index) => ({
    day: `2026-09-${String(index + 1).padStart(2, "0")}`,
    completed_count: counts[index + 1] ?? 0,
  }));
  return render(
    <HistoryHeatmap
      month={MONTH}
      days={days}
      selectedDay={null}
      onSelectDay={vi.fn()}
      onNavigate={vi.fn()}
    />,
  );
}

describe("HistoryHeatmap", () => {
  it("renders the month title in the italic display font", () => {
    renderHeatmap({});
    const title = screen.getByRole("heading", { level: 2 });
    expect(title).toHaveClass("font-display", "italic");
  });

  it("keeps the accessible day and navigation labels", () => {
    renderHeatmap({ 3: 2 });
    expect(screen.getByRole("button", { name: "Día 3: 2 Pomodoros" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mes anterior" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mes siguiente" })).toBeInTheDocument();
  });

  it("colors each day from the heat tokens, with ink for the dark levels", () => {
    renderHeatmap({ 1: 1, 2: 3, 3: 5, 4: 9 });
    expect(screen.getByRole("button", { name: "Día 1: 1 Pomodoros" })).toHaveClass("bg-heat-1");
    expect(screen.getByRole("button", { name: "Día 2: 3 Pomodoros" })).toHaveClass("bg-heat-2");
    expect(screen.getByRole("button", { name: "Día 3: 5 Pomodoros" })).toHaveClass(
      "bg-heat-3",
      "text-heat-3-ink",
    );
    expect(screen.getByRole("button", { name: "Día 4: 9 Pomodoros" })).toHaveClass(
      "bg-heat-4",
      "text-heat-4-ink",
    );
  });

  it("uses no fixed palette colors", () => {
    const { container } = renderHeatmap({ 1: 1, 2: 3, 3: 5, 4: 9 });
    expect(container.innerHTML).not.toMatch(/violet|purple|#[0-9a-f]{3,6}/i);
  });
});
