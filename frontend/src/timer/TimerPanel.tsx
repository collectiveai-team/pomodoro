"use client";

import { useEffect, useRef, useState } from "react";
import { SettingsToggles } from "@/src/settings/SettingsToggles";
import { useSettingsPreferences } from "@/src/settings/useSettingsPreferences";
import {
  type DaySummary,
  discardTimer,
  fetchDaySummary,
  logTimer,
  nextPomodoroTimer,
  pauseTimer,
  resumeTimer,
  skipBreakTimer,
  startBreakTimer,
  stopTimer,
  type TimerActionResult,
} from "./client";
import type { TimerSnapshot } from "./engine";
import { useTimerEngine } from "./TimerEngineProvider";

/**
 * The Timer panel: ring + phase + in-progress Task, phase-appropriate
 * controls, and the day summary footer (stories 46-63, 73, 74).
 *
 * All countdown math and server resync (focus/visibility regain, the
 * zero-crossing re-fetch, natural-completion-only alarms) is T21's
 * `createTimerEngine`, shared with `ActiveTab` through one `TimerEngineProvider`
 * instance (`AppShell`) so an action taken from either place is immediately
 * visible in both; this component only renders the shared snapshot and calls
 * the `/api/timer/*` action wrappers in `./client`.
 */

const POMODORO_DURATION_SECONDS = 25 * 60;
const SHORT_BREAK_SECONDS = 5 * 60;
const LONG_BREAK_SECONDS = 10 * 60;

function breakLabel(breakKind: string | null): string {
  if (breakKind === "long") {
    return "Break largo";
  }
  if (breakKind === "short") {
    return "Break corto";
  }
  return "Break";
}

function phaseLabel(snapshot: TimerSnapshot): string {
  switch (snapshot.phase) {
    case "idle":
      return "En reposo";
    case "pomodoro_running":
      return "Pomodoro";
    case "pomodoro_paused":
      return "Pomodoro (en pausa)";
    case "asking_to_log":
      return "¿Registrar?";
    case "break_running":
      return `${breakLabel(snapshot.break_kind)} en curso`;
    case "break_paused":
      return `${breakLabel(snapshot.break_kind)} (en pausa)`;
    case "ready_for_next":
      return "Pomodoro completado";
    default:
      return snapshot.phase;
  }
}

function totalSecondsForPhase(snapshot: TimerSnapshot): number | null {
  if (
    snapshot.phase === "pomodoro_running" ||
    snapshot.phase === "pomodoro_paused"
  ) {
    return POMODORO_DURATION_SECONDS;
  }
  if (snapshot.phase === "break_running" || snapshot.phase === "break_paused") {
    return snapshot.break_kind === "long"
      ? LONG_BREAK_SECONDS
      : SHORT_BREAK_SECONDS;
  }
  return null;
}

function formatClock(totalSeconds: number | null): string {
  if (totalSeconds === null) {
    return "--:--";
  }
  const clamped = Math.max(totalSeconds, 0);
  const minutes = Math.floor(clamped / 60);
  const seconds = clamped % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

export function TimerPanel() {
  const { snapshot, remainingSeconds, applyActionResult, subscribeAlarm } =
    useTimerEngine();
  const settings = useSettingsPreferences();
  const latestSnapshotRef = useRef<TimerSnapshot | null>(null);
  const [summary, setSummary] = useState<DaySummary | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Captured client-side at the moment Stop is pressed (the server's 409/200
  // response carries no elapsed-time field for AskingToLog), so "¿Registrar N
  // min?" can show the real figure without widening the backend contract.
  const [pendingLogSeconds, setPendingLogSeconds] = useState<number | null>(
    null,
  );

  useEffect(() => {
    latestSnapshotRef.current = snapshot;
    void fetchDaySummary().then((next) => {
      if (next) {
        setSummary(next);
      }
    });
  }, [snapshot]);

  useEffect(
    () =>
      subscribeAlarm(() => {
        const phase = latestSnapshotRef.current
          ? phaseLabel(latestSnapshotRef.current)
          : "Pomodoro";
        settings.triggerPhaseEndEffects(phase);
      }),
    [subscribeAlarm, settings.triggerPhaseEndEffects],
  );

  // Unlocks the Alarm's autoplay on the first real user gesture anywhere in
  // the panel, per the browser's autoplay policy (story 72).
  useEffect(() => {
    function handleFirstInteraction(): void {
      settings.unlockAlarm();
      window.removeEventListener("pointerdown", handleFirstInteraction);
      window.removeEventListener("keydown", handleFirstInteraction);
    }
    window.addEventListener("pointerdown", handleFirstInteraction);
    window.addEventListener("keydown", handleFirstInteraction);
    return () => {
      window.removeEventListener("pointerdown", handleFirstInteraction);
      window.removeEventListener("keydown", handleFirstInteraction);
    };
  }, [settings.unlockAlarm]);

  async function runAction(
    action: () => Promise<TimerActionResult>,
  ): Promise<void> {
    setPending(true);
    setError(null);
    const result = await action();
    setPending(false);
    if (result.ok) {
      applyActionResult(result.timer);
      return;
    }
    if (result.timer) {
      // A 409 from a stale tab carries the already-current Timer: resync
      // silently instead of showing an error (story 68).
      applyActionResult(result.timer);
      return;
    }
    setError(result.message);
  }

  function handleStop(): void {
    const elapsed =
      remainingSeconds === null
        ? null
        : Math.max(POMODORO_DURATION_SECONDS - remainingSeconds, 0);
    void runAction(stopTimer).then(() => setPendingLogSeconds(elapsed));
  }

  function handleLog(): void {
    void runAction(logTimer).then(() => setPendingLogSeconds(null));
  }

  function handleDiscard(): void {
    void runAction(discardTimer).then(() => setPendingLogSeconds(null));
  }

  if (!snapshot) {
    return (
      <section className="flex min-h-[20rem] flex-col items-center justify-center gap-4 p-6">
        <p className="text-sm text-ink/60">Cargando el Timer…</p>
      </section>
    );
  }

  const total = totalSecondsForPhase(snapshot);
  const displaySeconds = total === null ? null : (remainingSeconds ?? total);
  const progress =
    total && displaySeconds !== null ? 1 - displaySeconds / total : 0;

  return (
    <section className="flex flex-col items-center gap-6 p-6">
      <div
        className="flex h-48 w-48 items-center justify-center rounded-full"
        style={{
          background: `conic-gradient(var(--color-accent) ${progress * 360}deg, color-mix(in srgb, var(--color-ink) 15%, transparent) 0deg)`,
        }}
      >
        <div className="flex h-40 w-40 flex-col items-center justify-center gap-1 rounded-full bg-bg text-center">
          <span className="font-olivetta text-3xl font-semibold text-ink">
            {formatClock(displaySeconds)}
          </span>
          <span className="text-sm text-ink/70">{phaseLabel(snapshot)}</span>
        </div>
      </div>

      <p className="text-center text-base font-semibold text-ink">
        {snapshot.task ? snapshot.task.text : "Sin Task en curso"}
      </p>

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}

      <div className="flex min-h-11 flex-wrap items-center justify-center gap-3">
        {snapshot.phase === "pomodoro_running" ||
        snapshot.phase === "pomodoro_paused" ? (
          <>
            <button
              type="button"
              disabled={pending}
              onClick={() =>
                runAction(
                  snapshot.phase === "pomodoro_running"
                    ? pauseTimer
                    : resumeTimer,
                )
              }
              className="min-h-11 min-w-11 rounded-md border border-accent px-4 py-2 text-sm font-semibold text-accent disabled:opacity-60"
            >
              {snapshot.phase === "pomodoro_running" ? "Pausar" : "Reanudar"}
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={handleStop}
              className="min-h-11 min-w-11 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              Detener
            </button>
          </>
        ) : null}

        {snapshot.phase === "break_running" ||
        snapshot.phase === "break_paused" ? (
          <>
            <button
              type="button"
              disabled={pending}
              onClick={() =>
                runAction(
                  snapshot.phase === "break_running" ? pauseTimer : resumeTimer,
                )
              }
              className="min-h-11 min-w-11 rounded-md border border-accent px-4 py-2 text-sm font-semibold text-accent disabled:opacity-60"
            >
              {snapshot.phase === "break_running" ? "Pausar" : "Reanudar"}
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={() => runAction(skipBreakTimer)}
              className="min-h-11 min-w-11 rounded-md border border-accent px-4 py-2 text-sm font-semibold text-accent disabled:opacity-60"
            >
              Saltar Break
            </button>
          </>
        ) : null}

        {snapshot.phase === "asking_to_log" ? (
          <div className="flex flex-col items-center gap-3">
            <p className="text-sm text-ink">
              {pendingLogSeconds !== null
                ? `¿Registrar ${Math.round(pendingLogSeconds / 60)} min?`
                : "¿Registrar este Pomodoro?"}
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                disabled={pending}
                onClick={handleLog}
                className="min-h-11 min-w-11 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                Registrar
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={handleDiscard}
                className="min-h-11 min-w-11 rounded-md border border-accent px-4 py-2 text-sm font-semibold text-accent disabled:opacity-60"
              >
                Descartar
              </button>
            </div>
          </div>
        ) : null}

        {snapshot.phase === "ready_for_next" ? (
          <>
            <button
              type="button"
              disabled={pending}
              onClick={() => runAction(nextPomodoroTimer)}
              className="min-h-11 min-w-11 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              ▶ Otro Pomodoro
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={() => runAction(startBreakTimer)}
              className="min-h-11 min-w-11 rounded-md border border-accent px-4 py-2 text-sm font-semibold text-accent disabled:opacity-60"
            >
              Iniciar Break
            </button>
          </>
        ) : null}

        {snapshot.phase === "idle" ? (
          <p className="text-sm text-ink/60">
            Elegí una Task en Activas para empezar.
          </p>
        ) : null}
      </div>

      <SettingsToggles
        loading={settings.loading}
        alarmEnabled={settings.alarmEnabled}
        notificationsEnabled={settings.notificationsEnabled}
        notificationPermission={settings.notificationPermission}
        onToggleAlarm={(next) => void settings.setAlarmEnabled(next)}
        onToggleNotifications={(next) =>
          void settings.setNotificationsEnabled(next)
        }
      />

      <footer className="flex w-full justify-between text-sm text-ink/70">
        <span>Hoy: {summary ? summary.completed_today : "–"} completados</span>
        <span>
          Para el próximo Break largo:{" "}
          {summary ? summary.until_long_break : "–"}
        </span>
      </footer>
    </section>
  );
}
