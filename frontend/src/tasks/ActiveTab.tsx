"use client";

import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { startTimer } from "@/src/timer/client";
import { useTimerEngine } from "@/src/timer/TimerEngineProvider";
import {
  archiveTask,
  createRowActionApplier,
  createTask,
  editTaskTags,
  editTaskText,
  fetchActiveTasks,
  reorderTasks,
  type TaskPublic,
} from "./client";
import { EditableTaskText } from "./EditableTaskText";
import { TagCatalog } from "./TagCatalog";
import { TaskFilter } from "./TaskFilter";
import { useFilteredTaskList } from "./useFilteredTaskList";

/**
 * The Activas tab: counted list, Enter-to-create, text+tag-chip filtering,
 * drag reorder with a handle, per-row tag editing, start-Pomodoro, and
 * Archive (stories 14-23, 30-32, 35, 40-45, 47, 48).
 *
 * Reorder operates on the *unfiltered* order the backend's `task_ids` list
 * expects (the full Active set); dragging is disabled while a filter narrows
 * the list, since a partial view can't express that full order unambiguously.
 */

function newTagChip(draft: string, existing: string[]): string | null {
  const trimmed = draft.trim();
  if (!trimmed) {
    return null;
  }
  const key = trimmed.toLowerCase();
  if (existing.some((tag) => tag.toLowerCase() === key)) {
    return null;
  }
  return trimmed;
}

type TaskRowProps = {
  task: TaskPublic;
  dragDisabled: boolean;
  isInProgress: boolean;
  startDisabled: boolean;
  onStart: () => void;
  onArchive: () => void;
  onEditText: (text: string) => void;
  onEditTags: (tags: string[]) => void;
  rowError: string | null;
};

function TaskRow({
  task,
  dragDisabled,
  isInProgress,
  startDisabled,
  onStart,
  onArchive,
  onEditText,
  onEditTags,
  rowError,
}: TaskRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: task.id, disabled: dragDisabled });
  const [tagDraft, setTagDraft] = useState("");

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  function addTag(): void {
    const tag = newTagChip(tagDraft, task.tags);
    if (tag) {
      onEditTags([...task.tags, tag]);
    }
    setTagDraft("");
  }

  function removeTag(tag: string): void {
    onEditTags(task.tags.filter((existing) => existing !== tag));
  }

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={`flex flex-col gap-2 rounded-md border border-ink/10 p-3 ${
        isInProgress ? "bg-accent/10 ring-1 ring-accent" : ""
      }`}
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={dragDisabled}
          aria-label="Arrastrar para reordenar"
          className="min-h-11 min-w-11 cursor-grab touch-none rounded-md text-ink/60 disabled:cursor-not-allowed disabled:opacity-30"
          {...attributes}
          {...listeners}
        >
          ⠿
        </button>

        <button
          type="button"
          disabled={startDisabled}
          onClick={onStart}
          aria-label={`Iniciar Pomodoro en ${task.text}`}
          className="min-h-11 min-w-11 rounded-md bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          ▶
        </button>

        <EditableTaskText text={task.text} onSave={onEditText} />

        <button
          type="button"
          onClick={onArchive}
          className="min-h-11 rounded-md border border-ink/20 px-3 py-2 text-sm text-ink"
        >
          Archivar
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 pl-[3.25rem]">
        {task.tags.map((tag) => (
          <span
            key={tag}
            className="flex items-center gap-1 rounded-full border border-ink/20 px-3 py-1 text-xs text-ink"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(tag)}
              aria-label={`Quitar etiqueta ${tag}`}
              className="text-ink/60"
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          value={tagDraft}
          onChange={(event) => setTagDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addTag();
            }
          }}
          onBlur={addTag}
          placeholder="+ etiqueta"
          aria-label={`Agregar etiqueta a ${task.text}`}
          className="min-h-8 w-28 rounded-md border border-ink/20 bg-transparent px-2 py-1 text-xs"
        />
      </div>

      {rowError ? (
        <p role="alert" className="pl-[3.25rem] text-xs text-red-600">
          {rowError}
        </p>
      ) : null}
    </li>
  );
}

export function ActiveTab() {
  const {
    tasks,
    setTasks,
    count: activeCount,
    availableTags,
    textFilter,
    setTextFilter,
    selectedTags,
    toggleTag,
    listError,
    setListError,
    loadCounts,
    refreshTagCatalog,
    tagCatalog,
  } = useFilteredTaskList(fetchActiveTasks, "active");
  const [newTaskText, setNewTaskText] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const { snapshot: timerSnapshot, applyActionResult } = useTimerEngine();
  const timerPhase = timerSnapshot?.phase ?? null;
  const inProgressTaskId = timerSnapshot?.task?.id ?? null;

  const hasActiveFilter =
    textFilter.trim().length > 0 || selectedTags.length > 0;

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 150, tolerance: 5 },
    }),
  );

  const applyRowResult = createRowActionApplier(
    setTasks,
    setRowErrors,
    () => void loadCounts(),
  );

  async function handleCreate(): Promise<void> {
    const trimmed = newTaskText.trim();
    if (!trimmed) {
      setCreateError("El texto de la tarea no puede estar vacío.");
      return;
    }
    if (trimmed.length > 200) {
      setCreateError(
        "El texto de la tarea no puede superar los 200 caracteres.",
      );
      return;
    }
    setCreating(true);
    const result = await createTask(trimmed);
    setCreating(false);
    if (result.ok) {
      setNewTaskText("");
      setCreateError(null);
      setTasks((previous) => [result.task, ...previous]);
      void loadCounts();
      return;
    }
    setCreateError(result.message);
  }

  async function handleEditTags(taskId: number, tags: string[]): Promise<void> {
    const result = await editTaskTags(taskId, tags);
    if (result.ok) {
      setTasks((previous) =>
        previous.map((task) => (task.id === taskId ? result.task : task)),
      );
      void refreshTagCatalog();
    } else {
      setRowErrors((previous) => ({ ...previous, [taskId]: result.message }));
    }
  }

  async function handleEditText(taskId: number, text: string): Promise<void> {
    const result = await editTaskText(taskId, text);
    if (result.ok) {
      setTasks((previous) =>
        previous.map((task) => (task.id === taskId ? result.task : task)),
      );
    } else {
      setRowErrors((previous) => ({ ...previous, [taskId]: result.message }));
    }
  }

  async function handleStart(taskId: number): Promise<void> {
    const result = await startTimer(taskId);
    if (result.ok) {
      applyActionResult(result.timer);
      return;
    }
    if (result.timer) {
      applyActionResult(result.timer);
      return;
    }
    setRowErrors((previous) => ({ ...previous, [taskId]: result.message }));
  }

  async function handleArchive(taskId: number): Promise<void> {
    applyRowResult(taskId, await archiveTask(taskId));
  }

  function handleDragEnd(event: DragEndEvent): void {
    const { active, over } = event;
    if (hasActiveFilter || !over || active.id === over.id) {
      return;
    }
    const oldIndex = tasks.findIndex((task) => task.id === active.id);
    const newIndex = tasks.findIndex((task) => task.id === over.id);
    if (oldIndex === -1 || newIndex === -1) {
      return;
    }
    const previousOrder = tasks;
    const reordered = arrayMove(tasks, oldIndex, newIndex);
    setTasks(reordered);
    void reorderTasks(reordered.map((task) => task.id)).then((result) => {
      if (result.ok) {
        setTasks(result.tasks);
      } else {
        setTasks(previousOrder);
        setListError(result.message);
      }
    });
  }

  return (
    <section className="flex flex-col gap-4 p-4">
      <h2 className="font-olivetta text-xl font-semibold text-ink">
        Activas {activeCount !== null ? `(${activeCount})` : ""}
      </h2>

      <input
        type="text"
        value={newTaskText}
        onChange={(event) => setNewTaskText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void handleCreate();
          }
        }}
        placeholder="＋ Nueva tarea"
        aria-label="Nueva tarea"
        disabled={creating}
        className="min-h-11 rounded-md border border-ink/20 bg-transparent px-3 py-2 text-sm disabled:opacity-60"
      />
      {createError ? (
        <p role="alert" className="text-sm text-red-600">
          {createError}
        </p>
      ) : null}

      <TaskFilter
        text={textFilter}
        onTextChange={setTextFilter}
        availableTags={availableTags}
        selectedTags={selectedTags}
        onToggleTag={toggleTag}
      />
      <TagCatalog
        tags={tagCatalog}
        onRenamed={(previousName, nextName) => {
          setTasks((previous) =>
            previous.map((task) => ({
              ...task,
              tags: task.tags.map((tag) =>
                tag === previousName ? nextName : tag,
              ),
            })),
          );
          void refreshTagCatalog();
        }}
        onDeleted={(tagName) => {
          setTasks((previous) =>
            previous.map((task) => ({
              ...task,
              tags: task.tags.filter((tag) => tag !== tagName),
            })),
          );
          void refreshTagCatalog();
        }}
      />
      {hasActiveFilter ? (
        <p className="text-xs text-ink/60">
          Limpiá el filtro para reordenar arrastrando.
        </p>
      ) : null}

      {listError ? (
        <p role="alert" className="text-sm text-red-600">
          {listError}
        </p>
      ) : null}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={tasks.map((task) => task.id)}
          strategy={verticalListSortingStrategy}
        >
          <ul className="flex flex-col gap-2">
            {tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                dragDisabled={hasActiveFilter}
                isInProgress={task.id === inProgressTaskId}
                startDisabled={timerPhase !== "idle"}
                onStart={() => void handleStart(task.id)}
                onArchive={() => void handleArchive(task.id)}
                onEditText={(text) => void handleEditText(task.id, text)}
                onEditTags={(tags) => void handleEditTags(task.id, tags)}
                rowError={rowErrors[task.id] ?? null}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>
    </section>
  );
}
