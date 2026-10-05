import type { Metadata } from "next";
import type { ReactNode } from "react";
import { leitura, olivetta } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pomodoro Collective",
  description: "Pomodoro timer, Tasks and History for collectiveai.io",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${olivetta.variable} ${leitura.variable}`}>
      <body className="font-olivetta">{children}</body>
    </html>
  );
}
