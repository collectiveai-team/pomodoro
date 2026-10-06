import { useState } from "react";

interface EditableTaskTextProps {
  text: string;
  onSave: (text: string) => void;
}

/** A Task's text with an inline editor: Enter saves, Escape cancels. */
export function EditableTaskText({ text, onSave }: EditableTaskTextProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);

  return (
    <>
      {editing ? (
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              onSave(draft);
              setEditing(false);
            }
            if (event.key === "Escape") {
              setDraft(text);
              setEditing(false);
            }
          }}
          aria-label={`Editar tarea ${text}`}
          className="min-h-11 flex-1 rounded-md border border-ink/20 bg-transparent px-2 text-sm font-medium text-ink"
        />
      ) : (
        <span className="flex-1 text-sm font-medium text-ink">{text}</span>
      )}

      <button
        type="button"
        onClick={() => {
          setDraft(text);
          setEditing((current) => !current);
        }}
        className="min-h-11 rounded-md border border-ink/20 px-3 py-2 text-sm text-ink"
      >
        {editing ? "Cancelar" : "Editar"}
      </button>
    </>
  );
}
