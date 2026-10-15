import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { makeTask } from "./task-fixtures";
import { TaskRow, type TaskRowActions } from "./task-row";

function activeActions(onArchive = vi.fn(), onDelete = vi.fn()): TaskRowActions {
  return { variant: "active", startDisabled: false, onStart: () => {}, onArchive, onDelete };
}

function archivedActions(onUnarchive = vi.fn(), onDelete = vi.fn()): TaskRowActions {
  return { variant: "archived", onUnarchive, onDelete };
}

function renderRow(actions: TaskRowActions, deletable = true) {
  return render(
    <div>
      <button type="button">outside</button>
      <ul>
        <TaskRow
          task={{ ...makeTask("a", "Write report"), deletable }}
          tagsById={new Map()}
          pending={false}
          actions={actions}
        />
      </ul>
    </div>,
  );
}

const trigger = () => screen.getByRole("button", { name: "Acciones de Write report" });

describe("Task actions menu", () => {
  it("opens an 'Acciones' menu from ⋯ with Editar, Archivar and Eliminar for a deletable Task", async () => {
    renderRow(activeActions());
    const user = userEvent.setup();
    await user.click(trigger());

    expect(screen.getByRole("menu", { name: "Acciones" })).toBeVisible();
    expect(screen.getAllByRole("menuitem").map((item) => item.textContent)).toEqual([
      "Editar",
      "Archivar",
      "Eliminar",
    ]);
  });

  it("Eliminar on an Active deletable row calls the delete handler with the task id", async () => {
    const onDelete = vi.fn();
    renderRow(activeActions(vi.fn(), onDelete));
    const user = userEvent.setup();
    await user.click(trigger());
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));

    expect(onDelete).toHaveBeenCalledExactlyOnceWith("a");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("an Active Task with Pomodoros offers only Editar and Archivar", async () => {
    renderRow(activeActions(), false);
    const user = userEvent.setup();
    await user.click(trigger());

    expect(screen.getAllByRole("menuitem").map((item) => item.textContent)).toEqual([
      "Editar",
      "Archivar",
    ]);
  });

  it("Archivar calls the archive handler and closes the menu", async () => {
    const onArchive = vi.fn();
    renderRow(activeActions(onArchive));
    const user = userEvent.setup();
    await user.click(trigger());
    await user.click(screen.getByRole("menuitem", { name: "Archivar" }));

    expect(onArchive).toHaveBeenCalledExactlyOnceWith("a");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("Editar opens the text editor", async () => {
    renderRow(activeActions());
    const user = userEvent.setup();
    await user.click(trigger());
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));

    expect(screen.getByRole("textbox", { name: "Editar texto de la tarea" })).toBeVisible();
  });

  it("archived variant offers Desarchivar and Eliminar", async () => {
    const onUnarchive = vi.fn();
    const onDelete = vi.fn();
    renderRow(archivedActions(onUnarchive, onDelete));
    const user = userEvent.setup();
    await user.click(trigger());
    expect(screen.getAllByRole("menuitem").map((item) => item.textContent)).toEqual([
      "Editar",
      "Desarchivar",
      "Eliminar",
    ]);
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    expect(onDelete).toHaveBeenCalledExactlyOnceWith("a");

    await user.click(trigger());
    await user.click(screen.getByRole("menuitem", { name: "Desarchivar" }));
    expect(onUnarchive).toHaveBeenCalledExactlyOnceWith("a");
  });

  it("hides Eliminar when the Task has Pomodoros", async () => {
    renderRow(archivedActions(), false);
    const user = userEvent.setup();
    await user.click(trigger());

    expect(screen.queryByRole("menuitem", { name: "Eliminar" })).toBeNull();
  });

  it("moves with arrow keys, wrapping around", async () => {
    renderRow(activeActions(), false);
    const user = userEvent.setup();
    await user.click(trigger());
    expect(screen.getByRole("menuitem", { name: "Editar" })).toHaveFocus();

    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Archivar" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Editar" })).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(screen.getByRole("menuitem", { name: "Archivar" })).toHaveFocus();
  });

  it("Esc closes and returns focus to the trigger", async () => {
    renderRow(activeActions());
    const user = userEvent.setup();
    await user.click(trigger());
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("menu")).toBeNull();
    expect(trigger()).toHaveFocus();
  });

  it("an outside click closes it, and ⋯ toggles it", async () => {
    renderRow(activeActions());
    const user = userEvent.setup();
    await user.click(trigger());
    await user.click(screen.getByRole("button", { name: "outside" }));
    expect(screen.queryByRole("menu")).toBeNull();

    await user.click(trigger());
    await user.click(trigger());
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
