"use client";

import { useCallback, useEffect, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { TIMER_CHANGED_EVENT } from "@/lib/timer-sync";

type TimerPhase = components["schemas"]["TimerPhase"];

export interface TimerPhaseState {
  phase: TimerPhase | null;
  setPhase: (phase: TimerPhase) => void;
}

/**
 * The caller's current Timer phase, kept fresh across focus/visibility and same-page Timer
 * actions, for the Task list's ▶ disablement (Story 47) without duplicating the Timer panel's
 * own fetch-and-countdown logic (T21).
 */
export function useTimerPhase(): TimerPhaseState {
  const [phase, setPhase] = useState<TimerPhase | null>(null);

  const refetch = useCallback(async () => {
    const { data, response } = await apiClient.GET("/api/v1/timer");
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (data) {
      setPhase(data.phase);
    }
  }, []);

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
    window.addEventListener(TIMER_CHANGED_EVENT, handleFocus);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener(TIMER_CHANGED_EVENT, handleFocus);
    };
  }, [refetch]);

  return { phase, setPhase };
}
