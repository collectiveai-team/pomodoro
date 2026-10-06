import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--color-bg)",
        ink: "var(--color-ink)",
        accent: "var(--color-accent)",
        "accent-pressed": "var(--color-accent-pressed)",
      },
      fontFamily: {
        olivetta: ["var(--font-olivetta)", "sans-serif"],
        leitura: ["var(--font-leitura)", "serif"],
      },
    },
  },
};

export default config;
