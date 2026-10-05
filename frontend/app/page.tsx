import { LogoutButton } from "@/src/auth/logout-button";
import { HistoryTab } from "@/src/history/HistoryTab";
import { ActiveTab } from "@/src/tasks/ActiveTab";
import { ArchivedTab } from "@/src/tasks/ArchivedTab";
import { TimerPanel } from "@/src/timer/TimerPanel";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center gap-4 py-8">
      <h1 className="font-olivetta text-accent text-3xl font-semibold">
        Pomodoro Collective
      </h1>
      <TimerPanel />
      <div className="w-full max-w-xl">
        <ActiveTab />
      </div>
      <div className="w-full max-w-xl">
        <ArchivedTab />
      </div>
      <div className="w-full max-w-xl">
        <HistoryTab />
      </div>
      <LogoutButton />
    </main>
  );
}
