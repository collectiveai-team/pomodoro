import type { components } from "@/lib/api/schema";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TimerResponseBody = components["schemas"]["TimerResponse"];

export function makeTask(id: string, text: string, tagIds: string[] = []): TaskResponseBody {
  return {
    id,
    text,
    position: 0,
    tag_ids: tagIds,
    created_at: "2026-01-01T00:00:00Z",
    archived_at: null,
    deletable: true,
  };
}

export const IDLE_TIMER: TimerResponseBody = {
  phase: "Idle",
  task: null,
  break_kind: null,
  phase_started_at: null,
  accumulated_active_seconds: 0,
  running_since: null,
  server_now: "2026-01-01T00:00:00Z",
  remaining_seconds: null,
  pomodoros_completed_today: 0,
  pomodoros_until_long_break: 4,
};
