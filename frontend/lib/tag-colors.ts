import type { components } from "@/lib/api/schema";

export type TagColor = components["schemas"]["TagColor"];

/** The fixed 8-color Tag palette, with the Spanish name used as the swatch label. */
export const TAG_COLORS: ReadonlyArray<{ color: TagColor; label: string; dotClass: string }> = [
  { color: "rose", label: "Rosa", dotClass: "bg-tag-rose" },
  { color: "orange", label: "Naranja", dotClass: "bg-tag-orange" },
  { color: "amber", label: "Ámbar", dotClass: "bg-tag-amber" },
  { color: "green", label: "Verde", dotClass: "bg-tag-green" },
  { color: "teal", label: "Turquesa", dotClass: "bg-tag-teal" },
  { color: "sky", label: "Celeste", dotClass: "bg-tag-sky" },
  { color: "violet", label: "Violeta", dotClass: "bg-tag-violet" },
  { color: "slate", label: "Gris", dotClass: "bg-tag-slate" },
];

const DOT_CLASS_BY_COLOR = new Map(TAG_COLORS.map((entry) => [entry.color, entry.dotClass]));

export function tagDotClass(color: TagColor): string {
  return DOT_CLASS_BY_COLOR.get(color) ?? "bg-tag-slate";
}
