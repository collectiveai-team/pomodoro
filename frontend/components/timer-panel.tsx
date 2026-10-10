"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  currentNotificationPermission,
  notifyPhaseEnd,
  type PhaseChangeTrigger,
  playAlarm,
  requestNotificationPermission,
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
import { type TimerActionPath, TimerControls } from "./timer-controls";
import { TimerRing } from "./timer-ring";

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

async function redirectToLoginOn401(response: Response): Promise<boolean> {
  if (response.status === 401) {
    window.location.assign("/login");
    return true;
  }
  return false;
}

/** The live Timer panel: ring, phase-specific controls, Alarm/notification toggles (T21). */
export function TimerPanel() {
  const [view, setView] = useState<TimerView | null>(null);
  const [settings, setSettings] = useState<SettingsResponseBody | null>(null);
  const [notificationPermission, setNotificationPermission] =
    useState<NotificationPermission>("default");
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

  const updateSettings = useCallback(
    async (
      partial: Partial<Pick<SettingsResponseBody, "alarm_enabled" | "notifications_enabled">>,
    ) => {
      const current = settingsRef.current;
      if (!current) {
        return;
      }
      const {
        data,
        error: settingsError,
        response,
      } = await apiClient.PATCH("/api/v1/settings", {
        body: { ...current, ...partial },
      });
      if (await redirectToLoginOn401(response)) {
        return;
      }
      if (settingsError || !data) {
        setError("No se pudieron guardar las preferencias.");
        return;
      }
      setSettings(data);
    },
    [],
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
      setNotificationPermission(currentNotificationPermission());
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

  async function handleToggleAlarm() {
    if (!settings) {
      return;
    }
    await updateSettings({ alarm_enabled: !settings.alarm_enabled });
  }

  async function handleToggleNotifications() {
    if (!settings) {
      return;
    }
    const nextEnabled = !settings.notifications_enabled;
    if (nextEnabled) {
      setNotificationPermission(await requestNotificationPermission());
    }
    await updateSettings({ notifications_enabled: nextEnabled });
  }

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
    <section className="flex flex-col items-center gap-6 p-6">
      <TimerRing phase={timer.phase} remainingSeconds={remainingSeconds} fraction={fraction} />

      {timer.task ? <p className="text-sm font-medium">{timer.task.text}</p> : null}

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-center gap-2">
        <TimerControls
          phase={timer.phase}
          pending={pending}
          breakKind={timer.break_kind}
          accumulatedActiveSeconds={timer.accumulated_active_seconds}
          onAction={performAction}
        />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 text-center text-xs">
        <div>
          <dt>Hoy</dt>
          <dd className="font-semibold">{timer.pomodoros_completed_today}</dd>
        </div>
        <div>
          <dt>Para el Break largo</dt>
          <dd className="font-semibold">{timer.pomodoros_until_long_break}</dd>
        </div>
      </dl>

      {settings ? (
        <div className="flex flex-col items-center gap-1 text-xs">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={settings.alarm_enabled} onChange={handleToggleAlarm} />
            Alarm
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.notifications_enabled}
              onChange={handleToggleNotifications}
            />
            Notificaciones
          </label>
          {settings.notifications_enabled && notificationPermission === "denied" ? (
            <p>Permiso de notificaciones denegado por el navegador.</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
