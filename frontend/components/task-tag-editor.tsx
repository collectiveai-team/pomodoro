"use client";

import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { refreshTagCatalog } from "@/lib/use-tag-catalog";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TagResponseBody = components["schemas"]["TagResponse"];

interface TaskTagEditorProps {
  task: TaskResponseBody;
  tagsById: ReadonlyMap<string, TagResponseBody>;
  disabled: boolean;
  /** Called after the Task's Tags were saved and the shared catalog was refreshed. */
  onSaved: (taskId: string) => void;
}

/**
 * Tag chips of one Task with a remove button each, plus an add input suggesting the catalog
 * (Stories 32, 35). The whole name list is sent; the API normalizes case/spacing and creates or
 * reuses each Tag. Errors are shown in Spanish and focus returns to the input, so keyboard use
 * keeps working.
 */
export function TaskTagEditor({ task, tagsById, disabled, onSaved }: TaskTagEditorProps) {
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const refocusAfterSave = useRef(false);
  const listId = useId();

  // A disabled input cannot take focus, so refocus only after the re-enabled render committed.
  useEffect(() => {
    if (inputRef.current && refocusAfterSave.current && !inputRef.current.disabled) {
      refocusAfterSave.current = false;
      inputRef.current?.focus();
    }
  });

  const names = task.tag_ids.map((tagId) => tagsById.get(tagId)?.name ?? tagId);
  const suggestions = [...tagsById.values()].filter((tag) => !task.tag_ids.includes(tag.id));

  async function save(nextNames: string[]): Promise<boolean> {
    setSaving(true);
    setError(null);
    const { error: apiError, response } = await apiClient.PATCH("/api/v1/tasks/{task_id}/tags", {
      params: { path: { task_id: task.id } },
      body: { names: nextNames },
    });
    if (await redirectToLoginOn401(response)) {
      return false;
    }
    // Focus is restored by the effect below, once the input is enabled again.
    refocusAfterSave.current = true;
    setSaving(false);
    if (apiError !== undefined) {
      setError(toApiError(apiError).message);
      return false;
    }
    refreshTagCatalog();
    onSaved(task.id);
    return true;
  }

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = draft.trim();
    if (name === "") {
      return;
    }
    if (await save([...names, name])) {
      setDraft("");
    }
  }

  // Until the catalog resolves every Tag id, names would fall back to ids and be PATCHed as names.
  const catalogPending = task.tag_ids.some((tagId) => !tagsById.has(tagId));
  const busy = disabled || saving || catalogPending;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-1">
        {task.tag_ids.map((tagId, index) => (
          <span
            key={tagId}
            className="inline-flex items-center rounded-full bg-accent/15 pl-2 text-xs"
          >
            {names[index]}
            <button
              type="button"
              aria-label={`Quitar etiqueta ${names[index]}`}
              disabled={busy}
              onClick={() => void save(names.filter((_, other) => other !== index))}
              className="flex min-h-11 min-w-11 items-center justify-center disabled:opacity-50"
            >
              ×
            </button>
          </span>
        ))}
        <form onSubmit={handleAdd} className="flex">
          <input
            ref={inputRef}
            type="text"
            list={listId}
            aria-label={`Agregar etiqueta a ${task.text}`}
            placeholder="＋ Etiqueta"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={busy}
            className="field-input w-32"
          />
          <datalist id={listId}>
            {suggestions.map((tag) => (
              <option key={tag.id} value={tag.name} />
            ))}
          </datalist>
        </form>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
}
