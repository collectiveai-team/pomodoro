import type { Metadata } from "next";
import type { ReactNode } from "react";
import { leitura, olivetta } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pomodoro Collective",
  description: "Pomodoro timer, Tasks, and History — in one place.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${olivetta.variable} ${leitura.variable}`}>
      <body className="min-h-screen bg-base font-sans text-ink antialiased">{children}</body>
    </html>
  );
}
