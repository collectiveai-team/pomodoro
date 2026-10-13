# Open-license stand-in brand fonts

Issue #12 (Story 85) names collectiveai.io's **Olivetta** (400/600/900) and **Leitura** italic
webfonts, loaded via `next/font/local` (see `frontend/app/fonts.ts`). Per
[ADR-0004](../../../docs/adr/0004-open-license-stand-in-brand-fonts.md), the binaries shipped
here are **open-license stand-ins** under the final filenames, not the brand typefaces:

- `olivetta-400.woff2`, `olivetta-600.woff2`, `olivetta-900.woff2` — subset from
  [Lato](https://fonts.google.com/specimen/Lato) (SIL Open Font License 1.1).
- `leitura-italic.woff2` — subset from
  [Noto Serif Display Italic](https://fonts.google.com/noto/specimen/Noto+Serif+Display)
  (SIL Open Font License 1.1).

Each file was subset to the Latin + Spanish punctuation range with `fonttools`. No licensed
Olivetta or Leitura asset is included or claimed.

**Swap path**: replace these four files with the licensed Olivetta (400/600/900) and Leitura
(italic) webfonts, keeping the same filenames (or update the `src` paths in
`frontend/app/fonts.ts`). No other code should need to change.
