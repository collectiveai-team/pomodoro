"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  notifyPhaseEnd,
  type PhaseChangeTrigger,
  playAlarm,
  shouldFireOnPhaseEnd,
  unlockAlarm,
} from "@/lib/alarm";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import {
  type ClockSync,
  correctedRemainingSeconds,
  phaseTotalSeconds,
  remainingFraction,
  syncClock,
} from "@/lib/countdown";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { SETTINGS_CHANGED_EVENT, settingsFromEvent } from "@/lib/settings-sync";
import { broadcastTimerChanged, snapshotFromEvent, TIMER_CHANGED_EVENT } from "@/lib/timer-sync";
import { CycleDots } from "./cycle-dots";
import { type TimerActionPath, TimerControls } from "./timer-controls";
import { TimerRing } from "./timer-ring";
import { TimerTaskCard } from "./timer-task-card";

type TimerResponseBody = components["schemas"]["TimerResponse"];
type SettingsResponseBody = components["schemas"]["SettingsResponse"];
type TimerPhase = components["schemas"]["TimerPhase"];

interface TimerView {
  timer: TimerResponseBody;
  sync: ClockSync;
}

function phaseEndMessage(timer: TimerResponseBody): { title: string; body: string } {
  if (timer.phase === "ReadyForNext") {
    return {
      title: "Pomodoro completado",
      body: "Elegí un Break o arrancá otro Pomodoro.",
    };
  }
  return { title: "Break terminado", body: "Volviste a estar en reposo." };
}

export interface TimerPanelProps {
  /** Opens the Task detail from the Task card's ⓘ (wired to the drawer by the home workspace). */
  onOpenDetail?: (taskId: string) => void;
}

/** The live Timer panel: ring and phase-specific controls; Alarm settings live in the Account menu. */
export function TimerPanel({ onOpenDetail }: TimerPanelProps = {}) {
  const [view, setView] = useState<TimerView | null>(null);
  const [settings, setSettings] = useState<SettingsResponseBody | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const settingsRef = useRef<SettingsResponseBody | null>(null);
  const previousPhaseRef = useRef<TimerPhase | null>(null);
  const passiveRefetchTriggeredRef = useRef(false);

  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  const applySnapshot = useCallback((timer: TimerResponseBody, trigger: PhaseChangeTrigger) => {
    const sync = syncClock(timer.server_now, Date.now());
    const previousPhase = previousPhaseRef.current;
    if (previousPhase && shouldFireOnPhaseEnd(previousPhase, timer.phase, trigger)) {
      const message = phaseEndMessage(timer);
      playAlarm(settingsRef.current?.alarm_enabled ?? false);
      notifyPhaseEnd(
        settingsRef.current?.notifications_enabled ?? false,
        message.title,
        message.body,
      );
    }
    previousPhaseRef.current = timer.phase;
    if (previousPhase && previousPhase !== timer.phase) {
      broadcastTimerChanged({ phase: timer.phase, taskId: timer.task?.id ?? null });
    }
    passiveRefetchTriggeredRef.current = false;
    setView({ timer, sync });
  }, []);

  const fetchTimer = useCallback(
    async (trigger: PhaseChangeTrigger) => {
      const { data, error: fetchError, response } = await apiClient.GET("/api/v1/timer");
      if (await redirectToLoginOn401(response)) {
        return;
      }
      if (fetchError || !data) {
        setError("No se pudo cargar el Timer.");
        return;
      }
      applySnapshot(data, trigger);
    },
    [applySnapshot],
  );

  const performAction = useCallback(
    async (path: TimerActionPath) => {
      if (!view || pending) {
        return;
      }
      setPending(true);
      setError(null);
      try {
        const {
          data,
          error: actionError,
          response,
        } = await apiClient.POST(path, {
          body: { expected_phase: view.timer.phase },
        });
        if (await redirectToLoginOn401(response)) {
          return;
        }
        if (response.status === 409 && actionError) {
          applySnapshot(actionError as TimerResponseBody, "action");
          return;
        }
        if (actionError || !data) {
          setError("No se pudo completar la acción.");
          return;
        }
        applySnapshot(data, "action");
      } finally {
        setPending(false);
      }
    },
    [view, pending, applySnapshot],
  );

  // Initial load: Timer and settings together, with no previous phase to compare against yet.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [timerResult, settingsResult] = await Promise.all([
        apiClient.GET("/api/v1/timer"),
        apiClient.GET("/api/v1/settings"),
      ]);
      if (cancelled) {
        return;
      }
      if (
        (await redirectToLoginOn401(timerResult.response)) ||
        (await redirectToLoginOn401(settingsResult.response))
      ) {
        return;
      }
      if (settingsResult.data) {
        setSettings(settingsResult.data);
      }
      if (timerResult.data) {
        applySnapshot(timerResult.data, "passive");
      } else {
        setError("No se pudo cargar el Timer.");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [applySnapshot]);

  // Local countdown tick: projects the last fetched Timer forward; a zero countdown refetches
  // once for the settled state instead of guessing completion locally (Story 66).
  useEffect(() => {
    if (!view || view.timer.remaining_seconds === null) {
      setRemainingSeconds(null);
      return;
    }
    const remainingSecondsAtFetch = view.timer.remaining_seconds;
    function tick() {
      const seconds = correctedRemainingSeconds({
        remainingSecondsAtFetch,
        serverNowIso: view ? view.timer.server_now : new Date().toISOString(),
        sync: view ? view.sync : { offsetMs: 0 },
        clientNowMs: Date.now(),
      });
      setRemainingSeconds(seconds);
      if (seconds <= 0 && !passiveRefetchTriggeredRef.current) {
        passiveRefetchTriggeredRef.current = true;
        void fetchTimer("passive");
      }
    }
    tick();
    const intervalId = window.setInterval(tick, 1000);
    return () => window.clearInterval(intervalId);
  }, [view, fetchTimer]);

  // Refetch on focus/visibility so every tab reflects the same settled Timer (Story 65).
  useEffect(() => {
    function handleFocus() {
      void fetchTimer("passive");
    }
    function handleVisibility() {
      if (!document.hidden) {
        void fetchTimer("passive");
      }
    }
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchTimer]);

  // Refetch when another panel on the same page changed the Timer (e.g. ▶ from the Task list).
  useEffect(() => {
    function handleTimerChanged(event: Event) {
      // Events carrying a snapshot are phase announcements (including this panel's own).
      if (snapshotFromEvent(event)) {
        return;
      }
      void fetchTimer("passive");
    }
    window.addEventListener(TIMER_CHANGED_EVENT, handleTimerChanged);
    return () => window.removeEventListener(TIMER_CHANGED_EVENT, handleTimerChanged);
  }, [fetchTimer]);

  // The Account menu saves Alarm/notification Settings; mirror them for the next phase end.
  useEffect(() => {
    function handleSettingsChanged(event: Event) {
      setSettings(settingsFromEvent(event));
    }
    window.addEventListener(SETTINGS_CHANGED_EVENT, handleSettingsChanged);
    return () => window.removeEventListener(SETTINGS_CHANGED_EVENT, handleSettingsChanged);
  }, []);

  // Unlocks Alarm autoplay on the User's first interaction anywhere in the panel.
  useEffect(() => {
    function handleFirstInteraction() {
      unlockAlarm();
    }
    window.addEventListener("pointerdown", handleFirstInteraction);
    window.addEventListener("keydown", handleFirstInteraction);
    return () => {
      window.removeEventListener("pointerdown", handleFirstInteraction);
      window.removeEventListener("keydown", handleFirstInteraction);
    };
  }, []);

  if (!view) {
    return (
      <section className="flex flex-col items-center gap-2 p-6">
        {error ? (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        ) : (
          <p>Cargando…</p>
        )}
      </section>
    );
  }

  const { timer } = view;
  const totalSeconds = phaseTotalSeconds({
    remainingSecondsAtFetch: timer.remaining_seconds,
    accumulatedActiveSeconds: timer.accumulated_active_seconds,
    runningSinceIso: timer.running_since,
    serverNowIso: timer.server_now,
  });
  const fraction = remainingFraction(remainingSeconds ?? 0, totalSeconds);

  return (
    <section className="flex flex-col items-center gap-4 p-4 md:gap-6 md:p-6">
      <h1 className="font-display text-xl italic">Pomodoro Collective</h1>

      <TimerRing
        phase={timer.phase}
        breakKind={timer.break_kind}
        remainingSeconds={remainingSeconds}
        fraction={fraction}
      />

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}

      <div className="flex flex-col items-center gap-3">
        <TimerControls
          phase={timer.phase}
          pending={pending}
          breakKind={timer.break_kind}
          accumulatedActiveSeconds={timer.accumulated_active_seconds}
          onAction={performAction}
        />
        <CycleDots
          phase={timer.phase}
          breakKind={timer.break_kind}
          pomodorosUntilLongBreak={timer.pomodoros_until_long_break}
        />
      </div>

      <TimerTaskCard phase={timer.phase} task={timer.task} onOpenDetail={onOpenDetail} />

      <p className="tabular hidden text-xs text-muted md:block">
        {`Hoy · ${timer.pomodoros_completed_today} ${
          timer.pomodoros_completed_today === 1 ? "Pomodoro" : "Pomodoros"
        }`}
      </p>
    </section>
  );
}
