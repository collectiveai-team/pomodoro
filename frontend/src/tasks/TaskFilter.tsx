"use client";

/**
 * Text + Tag-chip filter shared by the Activas tab (stories 40-44), reusing
 * the backend's `filter_tasks` semantics verbatim: substring text AND a set
 * of chips that OR together, where `SIN_ETIQUETA` selects untagged Tasks.
 * Purely presentational; `ActiveTab` owns the filter state and re-fetches.
 */

/** Must match `pomodoro.core.filtering.SIN_ETIQUETA` exactly: it's sent as a query value. */
export const SIN_ETIQUETA = "sin etiqueta";

export type TaskFilterProps = {
  text: string;
  onTextChange: (value: string) => void;
  availableTags: string[];
  selectedTags: string[];
  onToggleTag: (tag: string) => void;
};

function chipClassName(selected: boolean): string {
  const base =
    "min-h-11 rounded-full border px-4 py-2 text-sm font-medium transition-colors";
  return selected
    ? `${base} border-accent bg-accent text-white`
    : `${base} border-ink/20 text-ink`;
}

export function TaskFilter({
  text,
  onTextChange,
  availableTags,
  selectedTags,
  onToggleTag,
}: TaskFilterProps) {
  const chips = [SIN_ETIQUETA, ...availableTags];

  return (
    <div className="flex flex-col gap-3">
      <input
        type="search"
        value={text}
        onChange={(event) => onTextChange(event.target.value)}
        placeholder="Filtrar por texto…"
        aria-label="Filtrar por texto"
        className="min-h-11 rounded-md border border-ink/20 bg-transparent px-3 py-2 text-sm"
      />
      <div className="flex flex-wrap gap-2">
        {chips.map((tag) => (
          <button
            key={tag}
            type="button"
            onClick={() => onToggleTag(tag)}
            aria-pressed={selectedTags.includes(tag)}
            className={chipClassName(selectedTags.includes(tag))}
          >
            {tag === SIN_ETIQUETA ? "Sin etiqueta" : tag}
          </button>
        ))}
      </div>
    </div>
  );
}
