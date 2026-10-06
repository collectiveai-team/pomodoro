"use client";

import { useState } from "react";
import { AccountMenu } from "@/src/account/AccountMenu";
import { HistoryTab } from "@/src/history/HistoryTab";
import { ActiveTab } from "@/src/tasks/ActiveTab";
import { ArchivedTab } from "@/src/tasks/ArchivedTab";
import { TimerEngineProvider } from "@/src/timer/TimerEngineProvider";
import { TimerPanel } from "@/src/timer/TimerPanel";
import { TAB_LABELS, TAB_ORDER, type TabId } from "./tabs";

/**
 * Ties the Timer panel and the Activas/Archivadas/Historial panel together
 * (story 87, layout spec): a fixed two-column split from the `lg` breakpoint
 * up, stacked below it. Only the selected tab is mounted — switching tabs
 * unmounts the previous one, so its own `useEffect` fetch runs again next
 * time it's selected instead of relying on a permanently-mounted sibling
 * to have stayed fresh.
 */
export function AppShell() {
  const [activeTab, setActiveTab] = useState<TabId>("active");

  return (
    <TimerEngineProvider>
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4 lg:grid lg:h-screen lg:grid-cols-[22rem_1fr] lg:gap-6 lg:overflow-hidden lg:p-6">
        <header className="flex items-center justify-between gap-4 lg:col-span-2">
          <h1 className="font-olivetta text-accent text-2xl font-semibold sm:text-3xl">
            Pomodoro Collective
          </h1>
          <AccountMenu />
        </header>

        <div className="rounded-md border border-ink/10 lg:overflow-y-auto">
          <TimerPanel />
        </div>

        <div className="flex flex-col gap-4 lg:overflow-y-auto">
          <nav
            aria-label="Secciones"
            className="flex gap-2 rounded-md border border-ink/10 p-1"
          >
            {TAB_ORDER.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                aria-current={activeTab === tab ? "page" : undefined}
                className={`min-h-11 flex-1 rounded-md px-3 py-2 text-sm font-semibold ${
                  activeTab === tab
                    ? "bg-accent text-white"
                    : "text-ink hover:bg-ink/5"
                }`}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </nav>

          {activeTab === "active" ? <ActiveTab /> : null}
          {activeTab === "archived" ? <ArchivedTab /> : null}
          {activeTab === "history" ? <HistoryTab /> : null}
        </div>
      </main>
    </TimerEngineProvider>
  );
}
