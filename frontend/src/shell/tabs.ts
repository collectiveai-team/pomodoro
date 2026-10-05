export type TabId = "active" | "archived" | "history";

export const TAB_ORDER: readonly TabId[] = ["active", "archived", "history"];

export const TAB_LABELS: Record<TabId, string> = {
  active: "Activas",
  archived: "Archivadas",
  history: "Historial",
};

export function isTabId(value: string): value is TabId {
  return (TAB_ORDER as readonly string[]).includes(value);
}
