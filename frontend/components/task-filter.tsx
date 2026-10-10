"use client";

import type { components } from "@/lib/api/schema";
import { type TaskFilterState, toggleTagFilter, UNTAGGED_FILTER } from "@/lib/task-filter";

type TagResponseBody = components["schemas"]["TagResponse"];

export interface TaskFilterProps {
  label: string;
  tags: TagResponseBody[];
  value: TaskFilterState;
  onChange: (next: TaskFilterState) => void;
}

/**
 * The text-plus-Tag-chip filter shared by Active, Archived, and History day detail (Story 45):
 * text and Tag selection combine with AND, selected Tags combine with OR among themselves, and
 * "Sin etiqueta" is just another chip (Stories 40-43).
 */
export function TaskFilter({ label, tags, value, onChange }: TaskFilterProps) {
  return (
    <div className="flex flex-col gap-2">
      <input
        type="search"
        aria-label={label}
        placeholder="Filtrar por texto"
        value={value.query}
        onChange={(event) => onChange({ ...value, query: event.target.value })}
      />
      <fieldset className="flex flex-wrap gap-1 border-0 p-0">
        <legend className="sr-only">{label} - Tags</legend>
        <button
          type="button"
          aria-pressed={value.selectedTags.includes(UNTAGGED_FILTER)}
          onClick={() => onChange(toggleTagFilter(value, UNTAGGED_FILTER))}
        >
          Sin etiqueta
        </button>
        {tags.map((tag) => (
          <button
            key={tag.id}
            type="button"
            aria-pressed={value.selectedTags.includes(tag.id)}
            onClick={() => onChange(toggleTagFilter(value, tag.id))}
          >
            {tag.name}
          </button>
        ))}
      </fieldset>
    </div>
  );
}
