"use client";

import type { DraggableAttributes, DraggableSyntheticListeners } from "@dnd-kit/core";
import type { CSSProperties } from "react";
import type { components } from "@/lib/api/schema";

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
  /** Present only for a draggable (Active-tab) row; the dnd-kit wiring lives in the orchestrator. */
  dragHandle?: DragHandleProps;
}

/** One Task row: handle, text, Tag chips, and the per-tab action set (Stories 22, 24-31, 46-47). */
export function TaskRow({ task, tagsById, pending, actions, dragHandle }: TaskRowProps) {
  return (
    <li
      ref={dragHandle?.setNodeRef}
      style={dragHandle?.style}
      className="flex items-center gap-2 rounded-lg border border-ink/15 p-2"
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
      <span className="flex-1">{task.text}</span>
      {task.tag_ids.length > 0 ? (
        <span className="flex flex-wrap gap-1">
          {task.tag_ids.map((tagId) => (
            <span key={tagId} className="rounded-full bg-accent/15 px-2 py-0.5 text-xs">
              {tagsById.get(tagId)?.name ?? tagId}
            </span>
          ))}
        </span>
      ) : null}
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
