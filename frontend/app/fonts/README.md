# Placeholder font files

`Olivetta-*.ttf` are Lato (SIL OFL) and `Leitura-Italic.otf` is URW Nimbus Roman
(AGPL/GUST), both freely redistributable. They stand in for the real
collectiveai.io Olivetta and Leitura font files, which ADR-0001 assumes are
licensed for web use on this domain. Swap the files in place when the real
fonts are available; the `next/font/local` wiring in `app/fonts.ts` does not
need to change.
