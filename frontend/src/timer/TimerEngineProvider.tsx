"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  createTimerEngine,
  type TimerEngine,
  type TimerSnapshot,
} from "./engine";

/**
 * One `TimerEngine` instance shared by every component that renders Timer
 * state (`TimerPanel`, `ActiveTab`), instead of each creating its own.
 *
 * Before this, `TimerPanel` and `ActiveTab` each called `createTimerEngine()`
 * independently: starting a Pomodoro from a Task row updated only
 * `ActiveTab`'s own engine, leaving the always-mounted `TimerPanel` showing
 * Idle until its next focus/visibility re-fetch (stories 47-49, 64-65 — one
 * Timer, visible everywhere, without the User switching windows). Sharing
 * one engine through context means any action applied through it is
 * immediately visible to every consumer.
 */

interface TimerEngineContextValue {
  snapshot: TimerSnapshot | null;
  remainingSeconds: number | null;
  applyActionResult: (snapshot: TimerSnapshot) => void;
  refetch: () => Promise<void>;
  /** Subscribe to "a phase ended on its own"; returns an unsubscribe function. */
  subscribeAlarm: (callback: () => void) => () => void;
}

const TimerEngineContext = createContext<TimerEngineContextValue | null>(null);

const RUNNING_PHASES = new Set(["pomodoro_running", "break_running"]);

export function TimerEngineProvider({ children }: { children: ReactNode }) {
  const engineRef = useRef<TimerEngine | null>(null);
  const alarmListenersRef = useRef(new Set<() => void>());
  const [snapshot, setSnapshot] = useState<TimerSnapshot | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);

  useEffect(() => {
    const engine = createTimerEngine({
      onSnapshot: (next) => {
        setSnapshot(next);
        setRemainingSeconds(engine.getRemainingSeconds());
      },
      onAlarm: () => {
        for (const listener of alarmListenersRef.current) {
          listener();
        }
      },
    });
    engineRef.current = engine;
    void engine.refetch();
    return () => {
      engine.dispose();
      engineRef.current = null;
    };
  }, []);

  // Only ticks (and locally decays the shared countdown) while a phase is
  // actually running; a paused phase's remaining_seconds is already frozen
  // server-side, so ticking it here would wrongly count paused time.
  useEffect(() => {
    if (!snapshot || !RUNNING_PHASES.has(snapshot.phase)) {
      return;
    }
    const interval = setInterval(() => {
      const engine = engineRef.current;
      if (!engine) {
        return;
      }
      engine.tick();
      setRemainingSeconds(engine.getRemainingSeconds());
    }, 1000);
    return () => clearInterval(interval);
  }, [snapshot]);

  const applyActionResult = useCallback((next: TimerSnapshot): void => {
    engineRef.current?.applyActionResult(next);
  }, []);

  const refetch = useCallback(async (): Promise<void> => {
    await engineRef.current?.refetch();
  }, []);

  const subscribeAlarm = useCallback((callback: () => void): (() => void) => {
    alarmListenersRef.current.add(callback);
    return () => {
      alarmListenersRef.current.delete(callback);
    };
  }, []);

  const value = useMemo<TimerEngineContextValue>(
    () => ({
      snapshot,
      remainingSeconds,
      applyActionResult,
      refetch,
      subscribeAlarm,
    }),
    [snapshot, remainingSeconds, applyActionResult, refetch, subscribeAlarm],
  );

  return (
    <TimerEngineContext.Provider value={value}>
      {children}
    </TimerEngineContext.Provider>
  );
}

export function useTimerEngine(): TimerEngineContextValue {
  const context = useContext(TimerEngineContext);
  if (context === null) {
    throw new Error("useTimerEngine must be used within a TimerEngineProvider");
  }
  return context;
}
