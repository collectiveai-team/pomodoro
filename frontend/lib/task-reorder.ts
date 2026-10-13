/**
 * Computes the full reordered id list for a drag-end, framework-free so it is testable without
 * simulating dnd-kit's pointer/keyboard sensors (Story 22). Returns `null` for a no-op drag: no
 * drop target, or dropped back on itself.
 */
export function reorderedTaskIds(
  ids: readonly string[],
  activeId: string,
  overId: string | null,
): string[] | null {
  if (overId === null || activeId === overId) {
    return null;
  }
  const fromIndex = ids.indexOf(activeId);
  const toIndex = ids.indexOf(overId);
  if (fromIndex === -1 || toIndex === -1) {
    return null;
  }
  const next = [...ids];
  next.splice(fromIndex, 1);
  next.splice(toIndex, 0, activeId);
  return next;
}
