"use client";

import { type FormEvent, type MouseEvent, useEffect, useRef, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { inlineEditHandlers } from "@/lib/inline-edit-handlers";

type TagResponseBody = components["schemas"]["TagResponse"];

interface TagRenameFormProps {
  tag: TagResponseBody;
  onSaved: () => void;
  onCancel: () => void;
}

/** Safari does not focus clicked buttons, so keep focus in the form until the click handler runs. */
function keepFocus(event: MouseEvent<HTMLButtonElement>) {
  event.preventDefault();
}

/**
 * Inline rename of one Tag (Story 36). Enter saves, Escape cancels, focus leaving the form cancels
 * (not while a save is pending). An API error (e.g. duplicate name) is shown in Spanish, the old
 * name stays, and focus returns to the input once it is enabled again.
 */
export function TagRenameForm({ tag, onSaved, onCancel }: TagRenameFormProps) {
  const [draft, setDraft] = useState(tag.name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const savingRef = useRef(false);
  const refocusAfterSave = useRef(true);

  // A disabled input cannot take focus, so (re)focus only once it is enabled and committed.
  useEffect(() => {
    if (inputRef.current && refocusAfterSave.current && !inputRef.current.disabled) {
      refocusAfterSave.current = false;
      inputRef.current.focus();
    }
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingRef.current) {
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError(null);
    const { error: apiError, response } = await apiClient.PATCH("/api/v1/tags/{tag_id}", {
      params: { path: { tag_id: tag.id } },
      body: { name: draft },
    });
    if (await redirectToLoginOn401(response)) {
      return;
    }
    savingRef.current = false;
    refocusAfterSave.current = true;
    setSaving(false);
    if (apiError !== undefined) {
      setError(toApiError(apiError).message);
      return;
    }
    onSaved();
  }

  const { onKeyDown, onBlur } = inlineEditHandlers(onCancel, () => savingRef.current);

  return (
    <form onSubmit={handleSubmit} onBlur={onBlur} className="flex flex-1 flex-col gap-1">
      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          aria-label={`Nuevo nombre de la etiqueta ${tag.name}`}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={saving}
          className="field-input min-h-11 flex-1"
        />
        <button
          type="submit"
          onMouseDown={keepFocus}
          disabled={saving}
          className="min-h-11 min-w-11 rounded px-2 text-sm disabled:opacity-50"
        >
          Guardar
        </button>
        <button
          type="button"
          onMouseDown={keepFocus}
          onClick={onCancel}
          className="min-h-11 min-w-11 rounded px-2 text-sm"
        >
          Cancelar
        </button>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </form>
  );
}
