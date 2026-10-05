"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createAlarmPlayer } from "./alarm";
import { fetchPreferences, updatePreferences } from "./client";
import {
  currentPermission,
  notifyPhaseEnd,
  type PermissionState,
  requestPermission,
} from "./notifications";

/**
 * Owns the Alarm/notifications preferences round-tripped through T14's
 * `/api/settings` (stories 69-71), the Alarm player's unlock/play lifecycle,
 * and the Notification permission flow (story 70). `TimerPanel` calls
 * `unlockAlarm` from a user-gesture handler and `triggerPhaseEndEffects`
 * from the Timer engine's `onAlarm` (fired only for a phase that ended on
 * its own); refs keep both reading the latest enabled flags without forcing
 * the engine to be re-created on every toggle.
 */
export interface SettingsPreferencesState {
  loading: boolean;
  error: string | null;
  alarmEnabled: boolean;
  notificationsEnabled: boolean;
  notificationPermission: PermissionState;
  setAlarmEnabled: (next: boolean) => Promise<void>;
  setNotificationsEnabled: (next: boolean) => Promise<void>;
  unlockAlarm: () => void;
  triggerPhaseEndEffects: (phaseLabel: string) => void;
}

export function useSettingsPreferences(): SettingsPreferencesState {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alarmEnabled, setAlarmEnabledState] = useState(true);
  const [notificationsEnabled, setNotificationsEnabledState] = useState(false);
  const [notificationPermission, setNotificationPermission] =
    useState<PermissionState>(() => currentPermission());

  const alarmEnabledRef = useRef(alarmEnabled);
  alarmEnabledRef.current = alarmEnabled;
  const notificationsEnabledRef = useRef(notificationsEnabled);
  notificationsEnabledRef.current = notificationsEnabled;

  const playerRef = useRef(createAlarmPlayer());

  useEffect(() => {
    let cancelled = false;
    void fetchPreferences().then((result) => {
      if (cancelled) {
        return;
      }
      setLoading(false);
      if (result.ok) {
        setAlarmEnabledState(result.settings.alarm_enabled);
        setNotificationsEnabledState(result.settings.notifications_enabled);
      } else {
        setError(result.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const setAlarmEnabled = useCallback(async (next: boolean) => {
    const previous = alarmEnabledRef.current;
    setAlarmEnabledState(next);
    const result = await updatePreferences({ alarm_enabled: next });
    if (!result.ok) {
      setAlarmEnabledState(previous);
      setError(result.message);
    }
  }, []);

  const setNotificationsEnabled = useCallback(async (next: boolean) => {
    if (!next) {
      const previous = notificationsEnabledRef.current;
      setNotificationsEnabledState(false);
      const result = await updatePreferences({
        notifications_enabled: false,
      });
      if (!result.ok) {
        setNotificationsEnabledState(previous);
        setError(result.message);
      }
      return;
    }

    const permission = currentPermission();
    if (permission === "denied") {
      // Never re-prompt a denied permission; only reflect the state.
      setNotificationPermission("denied");
      return;
    }

    let granted = permission === "granted";
    if (!granted) {
      const result = await requestPermission();
      setNotificationPermission(result);
      granted = result === "granted";
    }
    if (!granted) {
      return;
    }

    setNotificationsEnabledState(true);
    const result = await updatePreferences({ notifications_enabled: true });
    if (!result.ok) {
      setNotificationsEnabledState(false);
      setError(result.message);
    }
  }, []);

  const unlockAlarm = useCallback(() => {
    playerRef.current.unlock();
  }, []);

  const triggerPhaseEndEffects = useCallback((phaseLabel: string) => {
    if (alarmEnabledRef.current) {
      playerRef.current.play();
    }
    if (notificationsEnabledRef.current) {
      notifyPhaseEnd("Pomodoro Collective", phaseLabel);
    }
  }, []);

  return {
    loading,
    error,
    alarmEnabled,
    notificationsEnabled,
    notificationPermission,
    setAlarmEnabled,
    setNotificationsEnabled,
    unlockAlarm,
    triggerPhaseEndEffects,
  };
}
