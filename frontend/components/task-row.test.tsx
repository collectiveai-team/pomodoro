import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { makeTask } from "./task-fixtures";
import { TaskRow, type TaskRowActions } from "./task-row";

const ACTIVE: TaskRowActions = {
  variant: "active",
  startDisabled: false,
  onStart: () => {},
  onArchive: () => {},
  onDelete: () => {},
};
const ARCHIVED: TaskRowActions = { variant: "archived", onUnarchive: () => {}, onDelete: () => {} };

function renderRow(props: Partial<React.ComponentProps<typeof TaskRow>> = {}) {
  return render(
    <ul>
      <TaskRow
        task={makeTask("a", "Write report")}
        tagsById={new Map()}
        pending={false}
        actions={ACTIVE}
        {...props}
      />
    </ul>,
  );
}

describe("TaskRow", () => {
  it("renders one dot per completed Pomodoro today with count and time", () => {
    renderRow({ todayStat: { completedCount: 3, dedicatedSeconds: 5400 } });

    expect(screen.getByRole("img", { name: "3 Pomodoros hoy" }).textContent).toBe("●●●");
    expect(screen.getByText("3 hoy · 1h 30m")).toBeVisible();
  });

  it("renders no stats for an absent entry", () => {
    renderRow();
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByText(/hoy/)).toBeNull();
  });

  it("renders no stats when the entry is zero", () => {
    renderRow({ todayStat: { completedCount: 0, dedicatedSeconds: 0 } });
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByText(/hoy/)).toBeNull();
  });

  it("marks the current row with aria-current", () => {
    renderRow({ isCurrent: true });
    expect(screen.getByRole("listitem")).toHaveAttribute("aria-current", "true");
  });

  it("calls ⓘ, 🏷 and ⋯ callbacks with the task id", async () => {
    const onOpenDetail = vi.fn();
    const onOpenTags = vi.fn();
    const onOpenActions = vi.fn();
    renderRow({ onOpenDetail, onOpenTags, onOpenActions });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Detalle de Write report" }));
    await user.click(screen.getByRole("button", { name: "Etiquetas de Write report" }));
    await user.click(screen.getByRole("button", { name: "Acciones de Write report" }));

    expect(onOpenDetail).toHaveBeenCalledExactlyOnceWith("a");
    expect(onOpenTags).toHaveBeenCalledExactlyOnceWith("a");
    expect(onOpenActions).toHaveBeenCalledExactlyOnceWith("a");
  });

  it("archived row shows ⓘ 🏷 ⋯ and no ▶", () => {
    renderRow({ actions: ARCHIVED });

    for (const name of [
      "Detalle de Write report",
      "Etiquetas de Write report",
      "Acciones de Write report",
    ]) {
      expect(screen.getByRole("button", { name })).toBeVisible();
    }
    expect(screen.queryByRole("button", { name: /Iniciar Pomodoro en/ })).toBeNull();
  });
});
