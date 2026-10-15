import type { ReactNode } from "react";

interface TabButtonProps {
  selected: boolean;
  onSelect: () => void;
  count?: number;
  children: ReactNode;
}

/** An underlined tab with an optional small gray count ("Activas 3"). */
export function TabButton({ selected, onSelect, count, children }: TabButtonProps) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      onClick={onSelect}
      className="-mb-px flex min-h-11 items-center gap-1.5 border-b-2 border-transparent px-1 text-sm font-medium text-muted transition-colors hover:text-ink aria-selected:border-accent aria-selected:text-ink"
    >
      {children}
      {count === undefined ? null : <span className="tabular text-xs text-muted">{count}</span>}
    </button>
  );
}
