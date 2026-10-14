import { TasksPanel } from "@/components/tasks-panel";
import { TimerPanel } from "@/components/timer-panel";

/**
 * Edge-to-edge split: a 300px paper Timer column and a fluid tabbed-panels column. Below `md`
 * everything stacks with the Timer on top (Story 87).
 */
export default function HomePage() {
  return (
    <main className="grid min-h-screen grid-cols-1 md:grid-cols-[300px_1fr]">
      <aside className="border-b border-border bg-paper md:sticky md:top-0 md:h-screen md:border-b-0 md:border-r">
        <TimerPanel />
      </aside>
      <div className="min-w-0 pt-2">
        <TasksPanel />
      </div>
    </main>
  );
}
