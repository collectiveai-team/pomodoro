"use client";

import { closestCenter, DndContext } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { type FormEvent, useMemo, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { EMPTY_TASK_FILTER, type TaskFilterState } from "@/lib/task-filter";
import { broadcastTimerChanged } from "@/lib/timer-sync";
import { useTagCatalog } from "@/lib/use-tag-catalog";
import { useTaskList } from "@/lib/use-task-list";
import { createDragEndHandler, useTaskReorderSensors } from "@/lib/use-task-reorder";
import { useTimerPhase } from "@/lib/use-timer-phase";
import { TaskFilter } from "./task-filter";
import { TaskRow, type TaskRowProps } from "./task-row";

type TaskResponseBody = components["schemas"]["TaskResponse"];

interface TaskMutationResponse {
  error?: unknown;
  response: Response;
}

type SortableTaskRowProps = Omit<TaskRowProps, "dragHandle">;

/** Wires one Active row into dnd-kit's sortable context; `TaskRow` stays drag-library-agnostic. */
function SortableTaskRow(props: SortableTaskRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: props.task.id,
  });
  return (
    <TaskRow
      {...props}
      dragHandle={{
        attributes,
        listeners,
        setNodeRef,
        style: {
          transform: CSS.Transform.toString(transform),
          transition: transition ?? undefined,
        },
      }}
    />
  );
}

/** The Active/Archived Tasks panel: counters, filter, creation, drag-reorder, and row actions. */
export function TasksPanel() {
  const [tab, setTab] = useState<"active" | "archived">("active");
  const tags = useTagCatalog();
  const [activeFilter, setActiveFilter] = useState<TaskFilterState>(EMPTY_TASK_FILTER);
  const [archivedFilter, setArchivedFilter] = useState<TaskFilterState>(EMPTY_TASK_FILTER);
  const [newTaskText, setNewTaskText] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [pendingTaskId, setPendingTaskId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [activeState, refetchActive] = useTaskList("active", activeFilter);
  const [archivedState, refetchArchived] = useTaskList("archived", archivedFilter);
  const { phase: timerPhase, setPhase: setTimerPhase } = useTimerPhase();

  const tagsById = useMemo(() => new Map(tags.map((tag) => [tag.id, tag])), [tags]);

  function refetchBoth() {
    refetchActive();
    refetchArchived();
  }

  async function handleCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    const { data, error, response } = await apiClient.POST("/api/v1/tasks", {
      body: { text: newTaskText },
    });
    if (await redirectToLoginOn401(response)) {
      return;
    }
    setCreating(false);
    if (error || !data) {
      setCreateError(toApiError(error).message);
      return;
    }
    setNewTaskText("");
    refetchActive();
  }

  async function handleStart(taskId: string) {
    setPendingTaskId(taskId);
    setActionError(null);
    const { data, error, response } = await apiClient.POST("/api/v1/timer/start", {
      body: { task_id: taskId, expected_phase: timerPhase ?? "Idle" },
    });
    setPendingTaskId(null);
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (response.status === 409 && error) {
      setTimerPhase((error as components["schemas"]["TimerResponse"]).phase);
      broadcastTimerChanged();
      return;
    }
    if (error || !data) {
      setActionError(toApiError(error).message);
      return;
    }
    setTimerPhase(data.phase);
    broadcastTimerChanged();
  }

  async function runTaskMutation(taskId: string, request: () => Promise<TaskMutationResponse>) {
    setPendingTaskId(taskId);
    setActionError(null);
    try {
      const { error, response } = await request();
      if (await redirectToLoginOn401(response)) {
        return;
      }
      if (error !== undefined) {
        setActionError(toApiError(error).message);
        return;
      }
      refetchBoth();
    } finally {
      setPendingTaskId(null);
    }
  }

  function handleArchive(taskId: string) {
    return runTaskMutation(taskId, () =>
      apiClient.POST("/api/v1/tasks/{task_id}/archive", {
        params: { path: { task_id: taskId } },
      }),
    );
  }

  function handleUnarchive(taskId: string) {
    return runTaskMutation(taskId, () =>
      apiClient.POST("/api/v1/tasks/{task_id}/unarchive", {
        params: { path: { task_id: taskId } },
      }),
    );
  }

  function handleDelete(taskId: string) {
    return runTaskMutation(taskId, () =>
      apiClient.DELETE("/api/v1/tasks/{task_id}", {
        params: { path: { task_id: taskId } },
      }),
    );
  }

  const sensors = useTaskReorderSensors();

  async function persistReorder(nextTaskIds: string[]) {
    const { data, response } = await apiClient.PUT("/api/v1/tasks/reorder", {
      body: { task_ids: nextTaskIds },
    });
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (data) {
      refetchActive();
    }
  }

  const handleDragEnd = createDragEndHandler(
    () => activeState.tasks.map((task) => task.id),
    persistReorder,
  );

  return (
    <section className="flex w-full max-w-md flex-col gap-4 p-6">
      <div className="flex gap-2" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "active"}
          onClick={() => setTab("active")}
        >
          Activas ({activeState.activeCount})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "archived"}
          onClick={() => setTab("archived")}
        >
          Archivadas ({archivedState.archivedCount})
        </button>
      </div>

      {actionError ? (
        <p role="alert" className="text-sm text-red-600">
          {actionError}
        </p>
      ) : null}

      {tab === "active" ? (
        <>
          <TaskFilter
            label="Filtrar Activas"
            tags={tags}
            value={activeFilter}
            onChange={setActiveFilter}
          />

          <form onSubmit={handleCreateTask} className="flex flex-col gap-1">
            <input
              type="text"
              aria-label="Nueva tarea"
              placeholder="＋ Nueva tarea"
              value={newTaskText}
              onChange={(event) => setNewTaskText(event.target.value)}
              disabled={creating}
            />
            {createError ? (
              <p role="alert" className="text-sm text-red-600">
                {createError}
              </p>
            ) : null}
          </form>

          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={activeState.tasks.map((task) => task.id)}
              strategy={verticalListSortingStrategy}
            >
              <ul className="flex flex-col gap-2">
                {activeState.tasks.map((task: TaskResponseBody) => (
                  <SortableTaskRow
                    key={task.id}
                    task={task}
                    tagsById={tagsById}
                    pending={pendingTaskId === task.id}
                    actions={{
                      variant: "active",
                      startDisabled: timerPhase !== "Idle",
                      onStart: handleStart,
                      onArchive: handleArchive,
                    }}
                  />
                ))}
              </ul>
            </SortableContext>
          </DndContext>
        </>
      ) : (
        <>
          <TaskFilter
            label="Filtrar Archivadas"
            tags={tags}
            value={archivedFilter}
            onChange={setArchivedFilter}
          />

          <ul className="flex flex-col gap-2">
            {archivedState.tasks.map((task: TaskResponseBody) => (
              <TaskRow
                key={task.id}
                task={task}
                tagsById={tagsById}
                pending={pendingTaskId === task.id}
                actions={{
                  variant: "archived",
                  onUnarchive: handleUnarchive,
                  onDelete: handleDelete,
                }}
              />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
