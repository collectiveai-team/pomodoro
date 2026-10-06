"use client";

import { useState } from "react";
import { deleteTag, renameTag, type TagPublic } from "./client";

type TagCatalogProps = {
  tags: TagPublic[];
  onRenamed: (previousName: string, nextName: string) => void;
  onDeleted: (tagName: string) => void;
};

/** Global Tag management: rename or delete catalog entries without a confirmation. */
export function TagCatalog({ tags, onRenamed, onDeleted }: TagCatalogProps) {
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  async function handleRename(tag: TagPublic): Promise<void> {
    const result = await renameTag(tag.id, drafts[tag.id] ?? tag.name);
    if (result.ok) {
      setError(null);
      onRenamed(tag.name, result.tag.name);
      return;
    }
    setError(result.message);
  }

  async function handleDelete(tag: TagPublic): Promise<void> {
    const result = await deleteTag(tag.id);
    if (result.ok) {
      setError(null);
      onDeleted(tag.name);
      return;
    }
    setError(result.message);
  }

  if (tags.length === 0) {
    return null;
  }

  return (
    <section aria-label="Gestionar etiquetas" className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-ink">Etiquetas</h3>
      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}
      <ul className="flex flex-col gap-2">
        {tags.map((tag) => (
          <li key={tag.id} className="flex items-center gap-2">
            <input
              type="text"
              value={drafts[tag.id] ?? tag.name}
              onChange={(event) =>
                setDrafts((previous) => ({
                  ...previous,
                  [tag.id]: event.target.value,
                }))
              }
              aria-label={`Renombrar etiqueta ${tag.name}`}
              className="min-h-11 flex-1 rounded-md border border-ink/20 bg-transparent px-2 text-sm text-ink"
            />
            <button
              type="button"
              onClick={() => void handleRename(tag)}
              className="min-h-11 rounded-md border border-ink/20 px-3 py-2 text-sm text-ink"
            >
              Renombrar
            </button>
            <button
              type="button"
              onClick={() => void handleDelete(tag)}
              className="min-h-11 rounded-md border border-red-600/40 px-3 py-2 text-sm text-red-600"
            >
              Borrar
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
