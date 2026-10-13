"use client";

import { type FocusEvent, type FormEvent, type KeyboardEvent, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";

interface TaskTextEditorProps {
  taskId: string;
  text: string;
  onSaved: () => void;
  onCancel: () => void;
}

/**
 * Inline editor for a Task's text (Story 21). Enter saves, Escape cancels, and focus leaving the
 * whole editor cancels (no request). An API error is shown in Spanish and the editor stays open,
 * so the row keeps showing the previous text.
 */
export function TaskTextEditor({ taskId, text, onSaved, onCancel }: TaskTextEditorProps) {
  const [draft, setDraft] = useState(text);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const { error: apiError, response } = await apiClient.PATCH("/api/v1/tasks/{task_id}", {
      params: { path: { task_id: taskId } },
      body: { text: draft },
    });
    if (await redirectToLoginOn401(response)) {
      return;
    }
    setSaving(false);
    if (apiError !== undefined) {
      setError(toApiError(apiError).message);
      return;
    }
    onSaved();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    }
  }

  function handleBlur(event: FocusEvent<HTMLFormElement>) {
    if (!event.currentTarget.contains(event.relatedTarget)) {
      onCancel();
    }
  }

  return (
    <form onSubmit={handleSubmit} onBlur={handleBlur} className="flex flex-1 flex-col gap-1">
      <div className="flex gap-2">
        <input
          type="text"
          // biome-ignore lint/a11y/noAutofocus: the editor opens on an explicit user action.
          autoFocus
          aria-label="Editar texto de la tarea"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={saving}
          className="field-input"
        />
        <button type="submit" disabled={saving} className="btn-primary">
          Guardar
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancelar
        </button>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}
    </form>
  );
}
