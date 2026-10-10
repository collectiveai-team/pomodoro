"use client";

import {
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { reorderedTaskIds } from "@/lib/task-reorder";

/**
 * `PointerSensor` alone covers both mouse and touch via the browser's unified Pointer Events API
 * (dnd-kit's own recommended combination over separate Mouse+Touch sensors, which can conflict);
 * `KeyboardSensor` keeps the handle operable without a pointer (Space/Enter to pick up and drop,
 * arrow keys to move).
 */
export function useTaskReorderSensors() {
  return useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
}

/**
 * Builds a dnd-kit `onDragEnd` handler that persists a drop as the dragged id's new position
 * among `getTaskIds()`'s current order, or no-ops for a drag with no real move (Story 22).
 */
export function createDragEndHandler(
  getTaskIds: () => string[],
  onReorder: (nextTaskIds: string[]) => void,
): (event: DragEndEvent) => void {
  return (event: DragEndEvent) => {
    const overId = event.over ? String(event.over.id) : null;
    const nextTaskIds = reorderedTaskIds(getTaskIds(), String(event.active.id), overId);
    if (nextTaskIds) {
      onReorder(nextTaskIds);
    }
  };
}
