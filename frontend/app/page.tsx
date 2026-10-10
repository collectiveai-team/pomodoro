import { TasksPanel } from "@/components/tasks-panel";
import { TimerPanel } from "@/components/timer-panel";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center gap-6 p-6 md:flex-row md:items-start md:justify-center">
      <TimerPanel />
      <TasksPanel />
      <p className="text-sm text-gray-500">The History panel is on its way.</p>
    </main>
  );
}
