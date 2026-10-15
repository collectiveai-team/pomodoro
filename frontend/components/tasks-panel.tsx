"use client";

import { closestCenter, DndContext } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { type FormEvent, useCallback, useMemo, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { EMPTY_TASK_FILTER, type TaskFilterState } from "@/lib/task-filter";
import { isTaskStartDisabled } from "@/lib/task-start";
import { broadcastTimerChanged } from "@/lib/timer-sync";
import { isTimerTask } from "@/lib/timer-task";
import { useTagCatalog } from "@/lib/use-tag-catalog";
import { useTaskList } from "@/lib/use-task-list";
import { createDragEndHandler, useTaskReorderSensors } from "@/lib/use-task-reorder";
import { useTimerPhase } from "@/lib/use-timer-phase";
import { useTodayByTask } from "@/lib/use-today-by-task";
import { AccountMenu } from "./account-menu";
import { HistoryPanel } from "./history-panel";
import { TabButton } from "./tab-button";
import { TagPopover } from "./tag-popover";
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

export interface TasksPanelProps {
  /** Opens the Task detail from a row's ⓘ. */
  onOpenDetail?: (taskId: string) => void;
}

/** The Active/Archived Tasks panel: counters, filter, creation, drag-reorder, and row actions. */
export function TasksPanel({ onOpenDetail }: TasksPanelProps = {}) {
  const [tab, setTab] = useState<"active" | "archived" | "history">("active");
  const tags = useTagCatalog();
  const [activeFilter, setActiveFilter] = useState<TaskFilterState>(EMPTY_TASK_FILTER);
  const [archivedFilter, setArchivedFilter] = useState<TaskFilterState>(EMPTY_TASK_FILTER);
  const [newTaskText, setNewTaskText] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [pendingTaskId, setPendingTaskId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [tagTaskId, setTagTaskId] = useState<string | null>(null);
  const closeTagPopover = useCallback(() => setTagTaskId(null), []);
  const toggleTagPopover = useCallback(
    (taskId: string) => setTagTaskId((current) => (current === taskId ? null : taskId)),
    [],
  );

  const [activeState, refetchActive] = useTaskList("active", activeFilter);
  const [archivedState, refetchArchived] = useTaskList("archived", archivedFilter);
  const { phase: timerPhase, taskId: timerTaskId, setPhase: setTimerPhase } = useTimerPhase();

  const todayByTask = useTodayByTask(timerPhase);
  const tagsById = useMemo(() => new Map(tags.map((tag) => [tag.id, tag])), [tags]);

  function refetchBoth() {
    refetchActive();
    refetchArchived();
  }

  function dropDeletedTag(tagId: string) {
    const without = (filter: TaskFilterState) => ({
      ...filter,
      selectedTags: filter.selectedTags.filter((selected) => selected !== tagId),
    });
    setActiveFilter(without);
    setArchivedFilter(without);
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
      const conflict = error as components["schemas"]["TimerResponse"];
      setTimerPhase(conflict.phase, conflict.task?.id ?? null);
      broadcastTimerChanged();
      return;
    }
    if (error || !data) {
      setActionError(toApiError(error).message);
      return;
    }
    setTimerPhase(data.phase, data.task?.id ?? null);
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

  function sharedRowProps(taskId: string) {
    return {
      tagsById,
      pending: pendingTaskId === taskId,
      isCurrent: isTimerTask(timerPhase, timerTaskId, taskId),
      onTextSaved: handleTextSaved,
      onOpenTags: toggleTagPopover,
      tagPopover: tagTask?.id === taskId ? tagPopover : null,
      onOpenDetail,
      todayStat: todayByTask.get(taskId),
    };
  }

  function handleTextSaved(taskId: string) {
    refetchBoth();
    if (isTimerTask(timerPhase, timerTaskId, taskId)) {
      broadcastTimerChanged();
    }
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

  const tagTask = [...activeState.tasks, ...archivedState.tasks].find(
    (task) => task.id === tagTaskId,
  );

  const tagPopover = tagTask ? (
    <TagPopover
      key={tagTask.id}
      task={tagTask}
      tags={tags}
      onChanged={refetchBoth}
      onDeleted={dropDeletedTag}
      onClose={closeTagPopover}
    />
  ) : null;

  return (
    <section className="flex w-full flex-col gap-4">
      <div className="flex items-center gap-4 border-b border-border px-6" role="tablist">
        <TabButton
          selected={tab === "active"}
          count={activeState.activeCount}
          onSelect={() => setTab("active")}
        >
          Activas
        </TabButton>
        <TabButton
          selected={tab === "archived"}
          count={archivedState.archivedCount}
          onSelect={() => setTab("archived")}
        >
          Archivadas
        </TabButton>
        <TabButton selected={tab === "history"} onSelect={() => setTab("history")}>
          Historial
        </TabButton>
        <div className="ml-auto py-1">
          <AccountMenu />
        </div>
      </div>

      <div className="flex flex-col gap-4 px-6 pb-6">
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
                placeholder="+ Nueva tarea (Enter)"
                value={newTaskText}
                onChange={(event) => setNewTaskText(event.target.value)}
                disabled={creating}
                className="field-input border-dashed bg-transparent"
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
                <ul className="flex flex-col">
                  {activeState.tasks.map((task: TaskResponseBody) => (
                    <SortableTaskRow
                      key={task.id}
                      task={task}
                      {...sharedRowProps(task.id)}
                      actions={{
                        variant: "active",
                        startDisabled: isTaskStartDisabled(timerPhase),
                        onStart: handleStart,
                        onArchive: handleArchive,
                        onDelete: handleDelete,
                      }}
                    />
                  ))}
                </ul>
              </SortableContext>
            </DndContext>
          </>
        ) : tab === "history" ? (
          <HistoryPanel />
        ) : (
          <>
            <TaskFilter
              label="Filtrar Archivadas"
              tags={tags}
              value={archivedFilter}
              onChange={setArchivedFilter}
            />

            <ul className="flex flex-col">
              {archivedState.tasks.map((task: TaskResponseBody) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  {...sharedRowProps(task.id)}
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
      </div>
    </section>
  );
}
