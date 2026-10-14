"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { SETTINGS_CHANGED_EVENT, settingsFromEvent } from "@/lib/settings-sync";

/** The calendar day of `now` in `timeZone` as `YYYY-MM-DD`; the browser zone when it is unknown. */
export function todayInZone(timeZone: string | undefined, now: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(now);
  } catch {
    return todayInZone(undefined, now);
  }
}

/**
 * The User's current calendar day (their saved `time_zone`, not the browser's), or `null` until
 * their Settings have loaded. Follows Settings saved from the Account menu.
 */
export function useUserToday(): string | null {
  const [today, setToday] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void apiClient.GET("/api/v1/settings").then(({ data }) => {
      if (!cancelled) {
        setToday(todayInZone((data as { time_zone?: string } | undefined)?.time_zone));
      }
    });
    const onChanged = (event: Event) => setToday(todayInZone(settingsFromEvent(event).time_zone));
    window.addEventListener(SETTINGS_CHANGED_EVENT, onChanged);
    return () => {
      cancelled = true;
      window.removeEventListener(SETTINGS_CHANGED_EVENT, onChanged);
    };
  }, []);

  return today;
}
