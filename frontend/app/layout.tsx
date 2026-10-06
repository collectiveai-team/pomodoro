import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SessionGate } from "@/src/auth/session-gate";
import { leitura, olivetta } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pomodoro Collective",
  description: "Pomodoro timer, Tasks and History for collectiveai.io",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${olivetta.variable} ${leitura.variable}`}>
      <body className="font-olivetta">
        <SessionGate>{children}</SessionGate>
      </body>
    </html>
  );
}
