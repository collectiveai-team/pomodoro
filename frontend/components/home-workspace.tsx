"use client";

import { useCallback, useState } from "react";
import { TaskDetailDrawer } from "./task-detail-drawer";
import { TasksPanel } from "./tasks-panel";
import { TimerPanel } from "./timer-panel";

/**
 * Edge-to-edge split: a 300px paper Timer column and a fluid tabbed-panels column. Below `md`
 * everything stacks with the Timer on top (Story 87). Owns the Task detail drawer, opened from
 * either column's ⓘ (Story 30).
 */
export function HomeWorkspace() {
  const [detailTaskId, setDetailTaskId] = useState<string | null>(null);
  const closeDetail = useCallback(() => setDetailTaskId(null), []);
  return (
    <main className="grid min-h-screen grid-cols-1 md:grid-cols-[300px_1fr]">
      <aside className="border-b border-border bg-paper md:sticky md:top-0 md:h-screen md:border-b-0 md:border-r">
        <TimerPanel onOpenDetail={setDetailTaskId} />
      </aside>
      <div className="min-w-0 pt-2">
        <TasksPanel onOpenDetail={setDetailTaskId} />
      </div>
      {detailTaskId ? (
        <TaskDetailDrawer key={detailTaskId} taskId={detailTaskId} onClose={closeDetail} />
      ) : null}
    </main>
  );
}
