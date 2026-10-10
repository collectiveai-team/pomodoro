/** Selects the Tasks with no Tag at all (Story 42); a request-level sibling of a Tag id. */
export const UNTAGGED_FILTER = "sin etiqueta" as const;

export type TagFilterValue = string | typeof UNTAGGED_FILTER;

export interface TaskFilterState {
  query: string;
  selectedTags: TagFilterValue[];
}

export const EMPTY_TASK_FILTER: TaskFilterState = { query: "", selectedTags: [] };

export interface TaskListQuery {
  q?: string;
  tags?: TagFilterValue[];
}

/**
 * Builds the `q`/`tags` list-endpoint query from filter state, shared by Active, Archived, and
 * History day detail (Story 45): text and Tags combine with AND, while the Tags selected within
 * `tags` combine with OR — both rules live server-side in `core.task_filtering` (T9); this only
 * shapes the request, it never re-filters client-side.
 */
export function buildTaskListQuery(state: TaskFilterState): TaskListQuery {
  const query: TaskListQuery = {};
  const trimmedText = state.query.trim();
  if (trimmedText) {
    query.q = trimmedText;
  }
  if (state.selectedTags.length > 0) {
    query.tags = state.selectedTags;
  }
  return query;
}

export function toggleTagFilter(state: TaskFilterState, tag: TagFilterValue): TaskFilterState {
  const isSelected = state.selectedTags.includes(tag);
  return {
    ...state,
    selectedTags: isSelected
      ? state.selectedTags.filter((selected) => selected !== tag)
      : [...state.selectedTags, tag],
  };
}
