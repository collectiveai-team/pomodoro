# T24 visual check

Checked 2026-10-10 against the authenticated local application, using the same-origin
Next.js `/api` proxy and a disposable account. The captures are durable evidence for the
palette and responsive-layout portion of Story 85–87; they are not generic mockups.

| System palette | Viewport | Capture | Verified result |
| --- | ---: | --- | --- |
| Light | 1440 × 900 | [light-wide](t24/light-wide.png) | The Timer is the left fixed column and the Task/History panels form the right column. The open account menu shows password, time-zone, delete-account, and logout actions. |
| Light | 390 × 844 | [light-narrow](t24/light-narrow.png) | Timer, Task panels, and History stack in document order; controls retain touch-sized spacing. |
| Dark | 1440 × 900 | [dark-wide](t24/dark-wide.png) | The same fixed two-column layout renders with the dark palette. |
| Dark | 390 × 844 | [dark-narrow](t24/dark-narrow.png) | The same stacked mobile layout renders with the dark palette. |

The browser's computed values were checked in each color scheme:

| Palette | Base | Ink | Accent |
| --- | --- | --- | --- |
| Light | `#ffffff` | `#1e1e1e` | `#8054ff` |
| Dark | `#16131c` | `#dcd7e6` | `#a98cff` |

## Fonts

The binaries in `frontend/public/fonts/` are open-license stand-ins (Lato for the three
`olivetta-*` weights, Noto Serif Display Italic for `leitura-italic.woff2`), accepted by
[ADR-0004](../adr/0004-open-license-stand-in-brand-fonts.md). The `next/font/local` pipeline,
weights, and filenames are final; swapping in licensed files is a file replacement documented
in `frontend/public/fonts/NOTICE.md`.
