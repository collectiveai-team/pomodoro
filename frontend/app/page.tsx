import { AccountMenu } from "@/components/account-menu";
import { HistoryPanel } from "@/components/history-panel";
import { TasksPanel } from "@/components/tasks-panel";
import { TimerPanel } from "@/components/timer-panel";

/**
 * Wide screens show a fixed split (Timer column | tabbed-panels column); narrow screens stack
 * everything in document order (Story 87).
 */
export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 p-4 md:p-8">
      <div className="flex justify-end">
        <AccountMenu />
      </div>
      <div className="flex flex-col items-center gap-6 md:flex-row md:items-start md:justify-center">
        <div className="w-full md:sticky md:top-8 md:w-auto md:flex-shrink-0">
          <TimerPanel />
        </div>
        <div className="flex w-full flex-col gap-6 md:max-w-xl">
          <TasksPanel />
          <HistoryPanel />
        </div>
      </div>
    </main>
  );
}
