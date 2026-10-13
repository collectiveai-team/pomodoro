import localFont from "next/font/local";

/**
 * Brand typefaces (Story 85): Olivetta weights 400/600/900 for body text, Leitura italic for
 * the History month/year title only (Story 85, `history-heatmap.tsx`). Per ADR-0004 the binaries are
 * open-license stand-ins (Lato / Noto Serif Display Italic) under the final filenames; see `public/fonts/NOTICE.md` for the swap path.
 */
export const olivetta = localFont({
  src: [
    { path: "../public/fonts/olivetta-400.woff2", weight: "400", style: "normal" },
    { path: "../public/fonts/olivetta-600.woff2", weight: "600", style: "normal" },
    { path: "../public/fonts/olivetta-900.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-olivetta",
  display: "swap",
});

export const leitura = localFont({
  src: [{ path: "../public/fonts/leitura-italic.woff2", weight: "400", style: "italic" }],
  variable: "--font-leitura",
  display: "swap",
});
