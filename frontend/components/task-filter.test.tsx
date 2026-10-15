import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EMPTY_TASK_FILTER, UNTAGGED_FILTER } from "@/lib/task-filter";
import { TaskFilter } from "./task-filter";

const tags = [
  { id: "t1", name: "Trabajo", color: "violet" },
  { id: "t2", name: "Casa", color: "green" },
] as never;

describe("TaskFilter chips", () => {
  it("shows each Tag's color dot and a dashed 'Sin etiqueta' chip without a dot", () => {
    render(
      <TaskFilter
        label="Filtrar Activas"
        tags={tags}
        value={EMPTY_TASK_FILTER}
        onChange={vi.fn()}
      />,
    );

    const work = screen.getByRole("button", { name: "Trabajo" });
    expect(within(work).getByTestId("tag-chip-dot")).toHaveClass("bg-tag-violet");
    const home = screen.getByRole("button", { name: "Casa" });
    expect(within(home).getByTestId("tag-chip-dot")).toHaveClass("bg-tag-green");

    const untagged = screen.getByRole("button", { name: "Sin etiqueta" });
    expect(untagged).toHaveClass("border-dashed");
    expect(within(untagged).queryByTestId("tag-chip-dot")).toBeNull();
  });

  it("still toggles the untagged chip through onChange", async () => {
    const onChange = vi.fn();
    render(
      <TaskFilter
        label="Filtrar Activas"
        tags={tags}
        value={EMPTY_TASK_FILTER}
        onChange={onChange}
      />,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Sin etiqueta" }));
    expect(onChange).toHaveBeenCalledWith({
      ...EMPTY_TASK_FILTER,
      selectedTags: [UNTAGGED_FILTER],
    });
  });
});
