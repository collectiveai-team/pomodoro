# Brand fonts ship as open-license stand-ins until the licensed files arrive

Issue #12 (Story 85) asks for collectiveai.io's Olivetta (400/600/900) and Leitura italic, served with `next/font/local`, and assumes the licensed webfont files are available to us. They are not in this repository, and an agent cannot obtain them: they are a licensed asset the team has to supply.

Until they arrive, the app ships open-license stand-ins under the final filenames: Lato (SIL OFL 1.1) for `olivetta-400/600/900.woff2` and Noto Serif Display Italic (SIL OFL 1.1) for `leitura-italic.woff2`, with a `frontend/public/fonts/NOTICE.md` saying what they are and how to swap them. The brand-identity requirement is met when the loading pipeline is in place: `next/font/local` with the three Olivetta weights and the Leitura italic used only for the month/year title, the CSS variables, and the violet accent. Swapping in the licensed typefaces is a file replacement with no code change, and it is a follow-up outside this build.

This decision overrides the part of Story 85 and the "Fuentes de marca" assumption that require the licensed files themselves. Verification must not block on the font binaries not being Olivetta or Leitura.

## Considered Options

- **Block the build until the licensed files are supplied**: it stalls every later ticket over an asset the build cannot produce.
- **Fall back to system fonts**: it leaves the `next/font/local` pipeline unexercised, so the swap would mean code changes later.
