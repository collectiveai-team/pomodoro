"use client";

import { type KeyboardEvent, type RefObject, useEffect, useRef } from "react";

export interface TaskActionItem {
  label: string;
  onSelect: () => void;
}

interface TaskActionsMenuProps {
  items: TaskActionItem[];
  /** The ⋯ trigger: clicks on it are not "outside", and focus returns to it on close. */
  triggerRef: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
}

/** The 'Acciones' menu opened from a row's ⋯: arrow keys move, Esc / outside click close. */
export function TaskActionsMenu({ items, triggerRef, onClose }: TaskActionsMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
  }, []);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (!menuRef.current?.contains(target) && !triggerRef.current?.contains(target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [onClose, triggerRef]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      triggerRef.current?.focus();
      return;
    }
    const entries = Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
    );
    const current = entries.indexOf(document.activeElement as HTMLElement);
    const target = nextIndex(event.key, current, entries.length);
    if (target !== null) {
      event.preventDefault();
      entries[target]?.focus();
    }
  }

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label="Acciones"
      onKeyDown={handleKeyDown}
      className="absolute right-0 top-full z-10 mt-1 flex min-w-36 flex-col rounded-lg border border-border bg-surface p-1 shadow-lg"
    >
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          role="menuitem"
          onClick={() => {
            onClose();
            item.onSelect();
          }}
          className="rounded px-3 py-2 text-left text-sm hover:bg-border focus:bg-border focus:outline-none"
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function nextIndex(key: string, current: number, count: number): number | null {
  if (key === "ArrowDown") return (current + 1) % count;
  if (key === "ArrowUp") return (current - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}
