# T17 visual verification against Variante B

Checked 2026-10-14 in Chrome (Playwright, `channel: chrome`) against a local stack (SQLite backend
plus `next dev`, same-origin `/api` proxy) seeded with six Tasks, eight Tags, one archived Task and
159 Pomodoros over 45 days (time zone `America/Bogota`). References: the prototype
`.scratch/prototype-main-window-B/index.html?variant=B` and `.scratch/issue-19-references/*.png`.
Captures live in [`t17/`](t17/): `app-*` (idle, light/dark x wide 1440x900 / narrow 390x844),
`proto-*` (the prototype at the same sizes) and `state-*` (interaction states).

## Result per area

| Area | Result |
| --- | --- |
| Layout (T7) | 300px timer column on wide, stacked on narrow; underlined tabs with gray counts; `Cuenta` sits in the tab row. Matches Variante B. |
| Timer panel (T8, T9) | Phase line is accent while a Pomodoro runs, green in Break, gray otherwise; ring arc follows the phase; compact ring on narrow; serif italic wordmark; large primary button with 44px round secondary (■ ✕ ⏭ ☕ glyphs); AskingToLog shows "Registrar"; cycle dots fill correctly. |
| Task rows (T10) | Two-line rows, tinted Tag pills, divider rows, accent ring on the current Task, dots and `N hoy · time` line, ⓘ 🏷 ⋯ aligned on narrow. |
| Acciones menu (T11) | Opens under the ⋯; Active deletable row: Editar, Archivar, Eliminar; Active row with Pomodoros: Editar, Archivar; Archived row: Editar, Desarchivar. Fits on narrow. |
| Tag popover (T12) | Color dots, ✓ on assigned Tags, ✎ editor with the 8-color palette, Guardar, Eliminar. **Fixed** (see below): it was a centered overlay far from the 🏷; it now anchors under the 🏷 from `md` and stays a centered overlay below `md`. |
| Filter chips and create row (T13) | Color dots, dashed "Sin etiqueta" chip, dashed "+ Nueva tarea (Enter)" row. |
| Drawer (T14) | Right slide-in (420px), full width on narrow, Tag colors, month sections with totals (October 11 · 4h 35m matches the seeded days), "Hoy" row, Esc closes. |
| Heatmap (T15) | heat-1..4 read as increasing intensity in light and dark, numbers readable on heat-3/4, italic serif month title. |
| Notification denial (T7) | With permission denied the toggle stays off and the message "Permiso de notificaciones denegado por el navegador." shows (`state-notifications-denied-light-wide.png`). |

Out-of-scope items (◯, ↺, list counters, tomato logo, theme selector) are absent. The round
bottom-left "N" in the captures is the Next.js dev indicator, not app UI.

## Token review (T6)

- `--color-muted` `#6f6f6f` (prototype `#8C8C8C`): kept. It is visibly darker than the prototype but
  keeps small text (counts, "Hoy · N Pomodoros", filter placeholder) readable on the `#f5f5f5` base.
- `tag-*` colors: all eight are distinguishable as dots and as pill text on a 15% tint in both
  schemes. `slate` (lectura) and `salud` (violet) are the closest pair; acceptable.

## Fixes made during this ticket

1. The Tag popover is rendered inside its row's anchor wrapper (`TaskRow` `tagPopover` slot,
   positioned `md:absolute md:right-0 md:top-full`) instead of a fixed screen-center overlay. Test:
   `tag-popover.test.tsx` "anchors the popover inside the row of the Task whose 🏷 opened it".
2. Clicking the same row's 🏷 while the popover is open now closes it. Before, the outside-click
   (mousedown) closed it and the click reopened it, so it could not be toggled shut. Test:
   "closes the popover when its own 🏷 is clicked again" (red first); confirmed in Chrome.

## Deviations recorded, not changed

- Idle timer shows `--:--` with a gray ring and "EN REPOSO"; the prototype shows `25:00`, an accent
  ring and "LISTO PARA EMPEZAR". The spec asks for a gray idle phase line and the `--:--` display
  predates this issue, so it was left alone.
- On wide the "Hoy · N Pomodoros" line sits under the Task card, not pinned to the panel bottom as
  in the prototype footer.
- Heatmap day cells stretch to the full panel width (about 150px squares on a 1440px viewport).
- The drawer's "Hoy" used the browser-local date when captured. Since fixed: the drawer and the
  row stats read the day in the User's saved time zone (`useUserToday`) and roll over at that
  zone's midnight while the page stays open.
- Fonts remain the ADR-0004 open-license stand-ins.
