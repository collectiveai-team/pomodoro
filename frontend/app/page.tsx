import { HistoryPanel } from "@/components/history-panel";
import { TasksPanel } from "@/components/tasks-panel";
import { TimerPanel } from "@/components/timer-panel";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center gap-6 p-6 md:flex-row md:items-start md:justify-center">
      <TimerPanel />
      <TasksPanel />
      <HistoryPanel />
    </main>
  );
}
