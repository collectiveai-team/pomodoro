"use client";

import { useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { refreshTagCatalog } from "@/lib/use-tag-catalog";
import { TagRenameForm } from "./tag-rename-form";

type TagResponseBody = components["schemas"]["TagResponse"];

interface TagManagerProps {
  tags: TagResponseBody[];
  /** Called after a rename or delete and the shared catalog refresh, so Task lists reload. */
  onChanged: () => void;
  /** Called with the id of a Tag that no longer exists, so filters can drop it. */
  onDeleted: (tagId: string) => void;
}

/**
 * The "Etiquetas" surface (Stories 36-38): lists the catalog with rename and delete. Delete needs
 * no confirmation; the Tag disappears from every Task, chip and filter selection.
 */
export function TagManager({ tags, onChanged, onDeleted }: TagManagerProps) {
  const [open, setOpen] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleRenamed() {
    setRenamingId(null);
    refreshTagCatalog();
    onChanged();
  }

  async function handleDelete(tagId: string) {
    setPendingId(tagId);
    setError(null);
    const { error: apiError, response } = await apiClient.DELETE("/api/v1/tags/{tag_id}", {
      params: { path: { tag_id: tagId } },
    });
    if (await redirectToLoginOn401(response)) {
      return;
    }
    setPendingId(null);
    if (apiError !== undefined) {
      setError(toApiError(apiError).message);
      return;
    }
    onDeleted(tagId);
    refreshTagCatalog();
    onChanged();
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="tab-button self-start"
      >
        Etiquetas
      </button>
      {open ? (
        <section aria-label="Gestionar etiquetas" className="flex flex-col gap-2">
          {tags.length === 0 ? <p className="text-sm">No hay etiquetas.</p> : null}
          <ul className="flex flex-col gap-1">
            {tags.map((tag) => (
              <li key={tag.id} className="flex items-center gap-2">
                {renamingId === tag.id ? (
                  <TagRenameForm
                    tag={tag}
                    onSaved={handleRenamed}
                    onCancel={() => setRenamingId(null)}
                  />
                ) : (
                  <>
                    <span className="flex-1 text-sm">{tag.name}</span>
                    <button
                      type="button"
                      aria-label={`Renombrar etiqueta ${tag.name}`}
                      onClick={() => setRenamingId(tag.id)}
                      className="min-h-11 min-w-11 rounded px-2 text-sm"
                    >
                      Renombrar
                    </button>
                    <button
                      type="button"
                      aria-label={`Eliminar etiqueta ${tag.name}`}
                      disabled={pendingId === tag.id}
                      onClick={() => void handleDelete(tag.id)}
                      className="min-h-11 min-w-11 rounded px-2 text-sm disabled:opacity-50"
                    >
                      Eliminar
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
          {error ? (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">
              {error}
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
