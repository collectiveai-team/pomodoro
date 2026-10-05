"use client";

import { useState } from "react";
import {
  createRowActionApplier,
  deleteTask,
  fetchArchivedTasks,
  type TaskPublic,
  unarchiveTask,
} from "./client";
import { TaskFilter } from "./TaskFilter";
import { useFilteredTaskList } from "./useFilteredTaskList";

/**
 * The Archivadas tab: most-recently-archived-first list, the same
 * text+tag-chip filter as Activas, Unarchive (surfacing a collision error),
 * and permanent Delete gated on the backend's `deletable` flag
 * (stories 24-30).
 */

type TaskRowProps = {
  task: TaskPublic;
  onUnarchive: () => void;
  onDelete: () => void;
  rowError: string | null;
};

function TaskRow({ task, onUnarchive, onDelete, rowError }: TaskRowProps) {
  return (
    <li className="flex flex-col gap-2 rounded-md border border-ink/10 p-3">
      <div className="flex items-center gap-2">
        <span className="flex-1 text-sm font-medium text-ink">{task.text}</span>

        <button
          type="button"
          onClick={onUnarchive}
          className="min-h-11 rounded-md border border-ink/20 px-3 py-2 text-sm text-ink"
        >
          Desarchivar
        </button>

        <button
          type="button"
          disabled={!task.deletable}
          onClick={onDelete}
          aria-label={`Borrar ${task.text}`}
          title={
            task.deletable
              ? undefined
              : "No se puede borrar: tiene Pomodoros registrados."
          }
          className="min-h-11 rounded-md border border-red-600/40 px-3 py-2 text-sm text-red-600 disabled:cursor-not-allowed disabled:opacity-30"
        >
          Borrar
        </button>
      </div>

      {task.tags.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {task.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-ink/20 px-3 py-1 text-xs text-ink"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      {rowError ? (
        <p role="alert" className="text-xs text-red-600">
          {rowError}
        </p>
      ) : null}
    </li>
  );
}

export function ArchivedTab() {
  const {
    tasks,
    setTasks,
    count: archivedCount,
    availableTags,
    textFilter,
    setTextFilter,
    selectedTags,
    toggleTag,
    listError,
    loadCounts,
  } = useFilteredTaskList(fetchArchivedTasks, "archived");
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});

  const applyRowResult = createRowActionApplier(
    setTasks,
    setRowErrors,
    () => void loadCounts(),
  );

  async function handleUnarchive(taskId: number): Promise<void> {
    applyRowResult(taskId, await unarchiveTask(taskId));
  }

  async function handleDelete(taskId: number): Promise<void> {
    applyRowResult(taskId, await deleteTask(taskId));
  }

  return (
    <section className="flex flex-col gap-4 p-4">
      <h2 className="font-olivetta text-xl font-semibold text-ink">
        Archivadas {archivedCount !== null ? `(${archivedCount})` : ""}
      </h2>

      <TaskFilter
        text={textFilter}
        onTextChange={setTextFilter}
        availableTags={availableTags}
        selectedTags={selectedTags}
        onToggleTag={toggleTag}
      />

      {listError ? (
        <p role="alert" className="text-sm text-red-600">
          {listError}
        </p>
      ) : null}

      <ul className="flex flex-col gap-2">
        {tasks.map((task) => (
          <TaskRow
            key={task.id}
            task={task}
            onUnarchive={() => void handleUnarchive(task.id)}
            onDelete={() => void handleDelete(task.id)}
            rowError={rowErrors[task.id] ?? null}
          />
        ))}
      </ul>
    </section>
  );
}
