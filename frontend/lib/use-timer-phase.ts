"use client";

import { useCallback, useEffect, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { snapshotFromEvent, TIMER_CHANGED_EVENT } from "@/lib/timer-sync";

type TimerPhase = components["schemas"]["TimerPhase"];

export interface TimerPhaseState {
  phase: TimerPhase | null;
  /** Id of the Task the Timer holds, null when none. */
  taskId: string | null;
  setPhase: (phase: TimerPhase, taskId?: string | null) => void;
}

/**
 * The caller's current Timer phase, kept fresh across focus/visibility and same-page Timer
 * actions, for the Task list's ▶ disablement (Story 47) without duplicating the Timer panel's
 * own fetch-and-countdown logic (T21).
 */
export function useTimerPhase(): TimerPhaseState {
  const [phase, setPhaseState] = useState<TimerPhase | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);

  const setPhase = useCallback((nextPhase: TimerPhase, nextTaskId: string | null = null) => {
    setPhaseState(nextPhase);
    setTaskId(nextTaskId);
  }, []);

  const refetch = useCallback(async () => {
    const { data, response } = await apiClient.GET("/api/v1/timer");
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (data) {
      setPhase(data.phase, data.task?.id ?? null);
    }
  }, [setPhase]);

  useEffect(() => {
    void refetch();
    function handleFocus() {
      void refetch();
    }
    function handleVisibility() {
      if (!document.hidden) {
        void refetch();
      }
    }
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    // A broadcast carrying a snapshot is applied directly; a bare one asks for a refetch.
    function handleTimerChanged(event: Event) {
      const snapshot = snapshotFromEvent(event);
      if (snapshot) {
        setPhase(snapshot.phase, snapshot.taskId);
      } else {
        void refetch();
      }
    }
    window.addEventListener(TIMER_CHANGED_EVENT, handleTimerChanged);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener(TIMER_CHANGED_EVENT, handleTimerChanged);
    };
  }, [refetch, setPhase]);

  return { phase, taskId, setPhase };
}
