"use client";

import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import type { components } from "@/lib/api/schema";
import { tagDotClass } from "@/lib/tag-colors";
import { setTaskTagNames } from "@/lib/tag-mutations";
import { TagEditRow } from "./tag-edit-row";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TagResponseBody = components["schemas"]["TagResponse"];

interface TagPopoverProps {
  task: TaskResponseBody;
  tags: TagResponseBody[];
  /** Called after any Tag change (assignment, rename, color, delete) so Task lists reload. */
  onChanged: () => void;
  onDeleted: (tagId: string) => void;
  onClose: () => void;
}

/**
 * 'Etiquetas de {Task}' popover opened from a row's 🏷: filter/create input (Enter creates and
 * assigns a missing Tag), the catalog with ✓ on assigned Tags (click toggles) and a per-Tag ✎
 * editor. Esc or a click outside closes it.
 */
export function TagPopover({ task, tags, onChanged, onDeleted, onClose }: TagPopoverProps) {
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [filter, setFilter] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!ref.current?.contains(event.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [onClose]);

  const assignedNames = task.tag_ids.flatMap((id) => tags.find((tag) => tag.id === id)?.name ?? []);
  const query = filter.trim().toLowerCase();
  const visible = tags.filter((tag) => tag.name.toLowerCase().includes(query));

  async function saveNames(names: string[]) {
    setSaving(true);
    setError(null);
    const { message } = await setTaskTagNames(task.id, names);
    setSaving(false);
    if (message !== null) {
      setError(message);
      return false;
    }
    onChanged();
    return true;
  }

  function toggle(tag: TagResponseBody) {
    const assigned = task.tag_ids.includes(tag.id);
    void saveNames(
      assigned ? assignedNames.filter((n) => n !== tag.name) : [...assignedNames, tag.name],
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = filter.trim();
    if (name === "" || saving) {
      return;
    }
    const existing = tags.find((tag) => tag.name.toLowerCase() === name.toLowerCase());
    if (existing?.id && task.tag_ids.includes(existing.id)) {
      setFilter("");
      return;
    }
    const names = [...assignedNames, existing?.name ?? name];
    if (await saveNames(names)) {
      setFilter("");
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Escape") {
      return;
    }
    event.stopPropagation();
    if (editingId === null) {
      onClose();
    } else {
      setEditingId(null);
    }
  }

  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={`Etiquetas de ${task.text}`}
      onKeyDown={handleKeyDown}
      className="fixed left-1/2 top-24 z-20 flex max-h-[70vh] w-[min(22rem,92vw)] -translate-x-1/2 flex-col gap-2 overflow-y-auto rounded-lg border border-border bg-surface p-3 shadow-lg"
    >
      <h2 className="text-sm font-medium">Etiquetas de {task.text}</h2>
      <form onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          aria-label="Filtrar o crear etiqueta"
          placeholder="Filtrar o crear etiqueta (Enter)"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          disabled={saving}
          className="field-input"
        />
      </form>
      <ul className="flex flex-col gap-1">
        {visible.map((tag) => {
          const assigned = task.tag_ids.includes(tag.id);
          return (
            <li key={tag.id} className="flex flex-col gap-1">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  aria-label={`Etiqueta ${tag.name}`}
                  aria-pressed={assigned}
                  disabled={saving}
                  onClick={() => toggle(tag)}
                  className="flex min-h-11 flex-1 items-center gap-2 rounded px-1 text-left text-sm hover:bg-paper disabled:opacity-50"
                >
                  <span
                    aria-hidden="true"
                    className={`size-3 rounded-full ${tagDotClass(tag.color)}`}
                  />
                  <span className="flex-1">{tag.name}</span>
                  {assigned ? <span aria-hidden="true">✓</span> : null}
                </button>
                <button
                  type="button"
                  aria-label={`Editar etiqueta ${tag.name}`}
                  onClick={() => setEditingId(editingId === tag.id ? null : tag.id)}
                  className="flex min-h-11 min-w-8 items-center justify-center text-muted hover:text-ink"
                >
                  ✎
                </button>
              </div>
              {editingId === tag.id ? (
                <TagEditRow
                  tag={tag}
                  onChanged={onChanged}
                  onDeleted={onDeleted}
                  onDone={() => setEditingId(null)}
                />
              ) : null}
            </li>
          );
        })}
      </ul>
      {error ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
}
