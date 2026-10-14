"use client";

import type { DraggableAttributes, DraggableSyntheticListeners } from "@dnd-kit/core";
import { type CSSProperties, type Ref, useRef, useState } from "react";
import type { components } from "@/lib/api/schema";
import type { TodayStat } from "@/lib/use-today-by-task";
import { type TaskActionItem, TaskActionsMenu } from "./task-actions-menu";
import { TaskRowStats } from "./task-row-stats";
import { TaskTextEditor } from "./task-text-editor";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TagResponseBody = components["schemas"]["TagResponse"];

/** Tenue background + full-color text per Tag color (static class names for Tailwind). */
const TAG_PILL_CLASSES: Record<TagResponseBody["color"], string> = {
  rose: "bg-tag-rose/15 text-tag-rose",
  orange: "bg-tag-orange/15 text-tag-orange",
  amber: "bg-tag-amber/15 text-tag-amber",
  green: "bg-tag-green/15 text-tag-green",
  teal: "bg-tag-teal/15 text-tag-teal",
  sky: "bg-tag-sky/15 text-tag-sky",
  violet: "bg-tag-violet/15 text-tag-violet",
  slate: "bg-tag-slate/15 text-tag-slate",
};

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
  onDelete: (taskId: string) => void;
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
  /** Today's completed count and dedicated time for this Task; absent when none (Story 16). */
  todayStat?: TodayStat;
  /** ⓘ: open the Task's detail (wired in T14). */
  onOpenDetail?: (taskId: string) => void;
  /** 🏷: open the Tag popover (wired in T12). */
  onOpenTags?: (taskId: string) => void;
  /** Called when the ⋯ actions menu is opened. */
  onOpenActions?: (taskId: string) => void;
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
  todayStat,
  onOpenDetail,
  onOpenTags,
  onOpenActions,
  dragHandle,
}: TaskRowProps) {
  const [editing, setEditing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuTriggerRef = useRef<HTMLButtonElement>(null);
  const tags = task.tag_ids.flatMap((tagId) => tagsById.get(tagId) ?? []);
  return (
    <li
      ref={dragHandle?.setNodeRef}
      style={dragHandle?.style}
      aria-current={isCurrent ? "true" : undefined}
      className={`flex items-start gap-2 border-b border-border px-1 py-3 ${
        isCurrent ? "rounded-lg ring-2 ring-accent" : ""
      }`}
    >
      {dragHandle ? (
        <button
          type="button"
          aria-label={`Reordenar ${task.text}`}
          className="flex min-h-11 min-w-8 cursor-grab touch-none items-center justify-center text-muted"
          {...dragHandle.attributes}
          {...dragHandle.listeners}
        >
          ⋮⋮
        </button>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col gap-1 self-center">
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
          <span className="whitespace-pre-wrap break-words">{task.text}</span>
        )}
        {tags.length > 0 || todayStat ? (
          <div className="flex flex-wrap items-center gap-2">
            {tags.map((tag) => (
              <span
                key={tag.id}
                className={`rounded-full px-2 py-0.5 text-xs ${TAG_PILL_CLASSES[tag.color]}`}
              >
                {tag.name}
              </span>
            ))}
            {todayStat ? <TaskRowStats stat={todayStat} /> : null}
          </div>
        ) : null}
      </div>
      {actions.variant === "active" ? (
        <button
          type="button"
          aria-label={`Iniciar Pomodoro en ${task.text}`}
          disabled={pending || actions.startDisabled}
          onClick={() => actions.onStart(task.id)}
          className="btn-primary"
        >
          ▶
        </button>
      ) : null}
      <IconButton label={`Detalle de ${task.text}`} onClick={() => onOpenDetail?.(task.id)}>
        ⓘ
      </IconButton>
      <IconButton
        label={`Etiquetas de ${task.text}`}
        disabled={pending}
        onClick={() => onOpenTags?.(task.id)}
      >
        🏷
      </IconButton>
      <div className="relative">
        <IconButton
          label={`Acciones de ${task.text}`}
          disabled={pending}
          ref={menuTriggerRef}
          onClick={() => {
            if (!menuOpen) onOpenActions?.(task.id);
            setMenuOpen(!menuOpen);
          }}
        >
          ⋯
        </IconButton>
        {menuOpen ? (
          <TaskActionsMenu
            items={menuItems(task, actions, () => setEditing(true))}
            triggerRef={menuTriggerRef}
            onClose={() => setMenuOpen(false)}
          />
        ) : null}
      </div>
    </li>
  );
}

function menuItems(
  task: TaskResponseBody,
  actions: TaskRowActions,
  onEdit: () => void,
): TaskActionItem[] {
  const items: TaskActionItem[] = [{ label: "Editar", onSelect: onEdit }];
  if (actions.variant === "active") {
    items.push({ label: "Archivar", onSelect: () => actions.onArchive(task.id) });
  } else {
    items.push({ label: "Desarchivar", onSelect: () => actions.onUnarchive(task.id) });
  }
  if (task.deletable) {
    items.push({ label: "Eliminar", onSelect: () => actions.onDelete(task.id) });
  }
  return items;
}

interface IconButtonProps {
  ref?: Ref<HTMLButtonElement>;
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: string;
}

function IconButton({ ref, label, disabled, onClick, children }: IconButtonProps) {
  return (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="flex min-h-11 min-w-8 items-center justify-center text-muted hover:text-ink disabled:opacity-50"
    >
      {children}
    </button>
  );
}
