"use client";

import { type FormEvent, useState } from "react";
import type { components } from "@/lib/api/schema";
import { TAG_COLORS } from "@/lib/tag-colors";
import { deleteTag, type TagMutationResult, updateTag } from "@/lib/tag-mutations";

type TagResponseBody = components["schemas"]["TagResponse"];

interface TagEditRowProps {
  tag: TagResponseBody;
  /** Called after any successful change so Task lists reload. */
  onChanged: () => void;
  onDeleted: (tagId: string) => void;
  onDone: () => void;
}

/** Inline editor of one Tag inside the popover: rename (Enter), pick one of 8 colors, delete. */
export function TagEditRow({ tag, onChanged, onDeleted, onDone }: TagEditRowProps) {
  const [draft, setDraft] = useState(tag.name);
  const [error, setError] = useState<string | null>(null);

  async function run(request: () => Promise<TagMutationResult>, after?: () => void) {
    setError(null);
    const { message } = await request();
    if (message !== null) {
      setError(message);
      return;
    }
    after?.();
    onChanged();
  }

  function handleRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(
      () => updateTag(tag.id, { name: draft }),
      () => onDone(),
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-2">
      <form onSubmit={handleRename} className="flex gap-2">
        <input
          type="text"
          aria-label={`Nuevo nombre de la etiqueta ${tag.name}`}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          className="field-input"
        />
        <button type="submit" className="btn-secondary">
          Guardar
        </button>
      </form>
      <fieldset aria-label={`Color de la etiqueta ${tag.name}`} className="flex gap-2">
        {TAG_COLORS.map(({ color, label, dotClass }) => (
          <button
            key={color}
            type="button"
            aria-label={`Color ${label}`}
            aria-pressed={tag.color === color}
            onClick={() => void run(() => updateTag(tag.id, { color }))}
            className={`size-6 rounded-full ${dotClass} aria-pressed:ring-2 aria-pressed:ring-ink aria-pressed:ring-offset-2`}
          />
        ))}
      </fieldset>
      <div className="flex gap-2">
        <button
          type="button"
          aria-label={`Eliminar etiqueta ${tag.name}`}
          onClick={() =>
            void run(
              () => deleteTag(tag.id),
              () => onDeleted(tag.id),
            )
          }
          className="btn-secondary"
        >
          Eliminar
        </button>
        <button type="button" onClick={onDone} className="btn-secondary">
          Cerrar edición
        </button>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
}
