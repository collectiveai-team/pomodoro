"use client";

import type { DraggableAttributes, DraggableSyntheticListeners } from "@dnd-kit/core";
import { type CSSProperties, useState } from "react";
import type { components } from "@/lib/api/schema";
import { TaskTagEditor } from "./task-tag-editor";
import { TaskTextEditor } from "./task-text-editor";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TagResponseBody = components["schemas"]["TagResponse"];

export interface DragHandleProps {
  attributes: DraggableAttributes;
  listeners: DraggableSyntheticListeners;
  setNodeRef: (node: HTMLElement | null) => void;
  style: CSSProperties;
}

interface ActiveRowActions {
  variant: "active";
  startDisabled: boolean;
  onStart: (taskId: string) => void;
  onArchive: (taskId: string) => void;
}

interface ArchivedRowActions {
  variant: "archived";
  onUnarchive: (taskId: string) => void;
  onDelete: (taskId: string) => void;
}

export type TaskRowActions = ActiveRowActions | ArchivedRowActions;

export interface TaskRowProps {
  task: TaskResponseBody;
  tagsById: ReadonlyMap<string, TagResponseBody>;
  pending: boolean;
  actions: TaskRowActions;
  /** True while the Timer holds this Task (Story 48): highlighted and `aria-current`. */
  isCurrent?: boolean;
  /** Called after the Task's text was edited successfully (Story 21). */
  onTextSaved?: (taskId: string) => void;
  /** Called after the Task's Tags were saved (Stories 32, 35). */
  onTagsSaved: (taskId: string) => void;
  /** Present only for a draggable (Active-tab) row; the dnd-kit wiring lives in the orchestrator. */
  dragHandle?: DragHandleProps;
}

/** One Task row: handle, text, Tag chips, and the per-tab action set (Stories 22, 24-31, 46-47). */
export function TaskRow({
  task,
  tagsById,
  pending,
  actions,
  isCurrent = false,
  onTextSaved,
  onTagsSaved,
  dragHandle,
}: TaskRowProps) {
  const [editing, setEditing] = useState(false);
  return (
    <li
      ref={dragHandle?.setNodeRef}
      style={dragHandle?.style}
      aria-current={isCurrent ? "true" : undefined}
      className={`flex items-center gap-2 rounded-lg border p-2 ${
        isCurrent
          ? "border-accent bg-accent/10 ring-2 ring-accent dark:bg-accent/20"
          : "border-border"
      }`}
    >
      {dragHandle ? (
        <button
          type="button"
          aria-label={`Reordenar ${task.text}`}
          className="flex min-h-11 min-w-11 cursor-grab touch-none items-center justify-center"
          {...dragHandle.attributes}
          {...dragHandle.listeners}
        >
          ⠿
        </button>
      ) : null}
      {editing ? (
        <TaskTextEditor
          taskId={task.id}
          text={task.text}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            onTextSaved?.(task.id);
          }}
        />
      ) : (
        <>
          <span className="flex-1">{task.text}</span>
          <button
            type="button"
            aria-label={`Editar ${task.text}`}
            disabled={pending}
            onClick={() => setEditing(true)}
            className="btn-secondary"
          >
            ✎
          </button>
        </>
      )}
      <TaskTagEditor task={task} tagsById={tagsById} disabled={pending} onSaved={onTagsSaved} />
      {actions.variant === "active" ? (
        <>
          <button
            type="button"
            aria-label={`Iniciar Pomodoro en ${task.text}`}
            disabled={pending || actions.startDisabled}
            onClick={() => actions.onStart(task.id)}
            className="btn-primary"
          >
            ▶
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => actions.onArchive(task.id)}
            className="btn-secondary"
          >
            Archivar
          </button>
        </>
      ) : (
        <>
          <button
            type="button"
            disabled={pending}
            onClick={() => actions.onUnarchive(task.id)}
            className="btn-secondary"
          >
            Desarchivar
          </button>
          {task.deletable ? (
            <button
              type="button"
              disabled={pending}
              onClick={() => actions.onDelete(task.id)}
              className="btn-secondary"
            >
              Borrar
            </button>
          ) : null}
        </>
      )}
    </li>
  );
}
