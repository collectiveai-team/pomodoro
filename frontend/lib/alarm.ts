import type { components } from "@/lib/api/schema";

type TimerPhase = components["schemas"]["TimerPhase"];

/**
 * Whether a phase change was caused by this tab calling a Timer action, or observed passively
 * (a focus/visibility refetch, or the local countdown reaching zero). Only a passive observation
 * of one of the two natural-end transitions below counts as "the phase ended on its own"
 * (Stories 51, 60, 61): a skip is always an action, so it never fires the Alarm even though it
 * also lands on `Idle`.
 */
export type PhaseChangeTrigger = "action" | "passive";

const NATURAL_PHASE_END_TRANSITIONS: ReadonlyArray<readonly [TimerPhase, TimerPhase]> = [
  ["PomodoroRunning", "ReadyForNext"],
  ["BreakRunning", "Idle"],
];

/** True only when a phase ended on its own: observed passively, matching a natural-end pair. */
export function shouldFireOnPhaseEnd(
  previousPhase: TimerPhase,
  nextPhase: TimerPhase,
  trigger: PhaseChangeTrigger,
): boolean {
  if (trigger !== "passive") {
    return false;
  }
  return NATURAL_PHASE_END_TRANSITIONS.some(
    ([from, to]) => from === previousPhase && to === nextPhase,
  );
}

/** Disabled means silent, and the Alarm stays silent until the User's first interaction. */
export function canPlayAlarm(alarmEnabled: boolean, unlocked: boolean): boolean {
  return alarmEnabled && unlocked;
}

/** Only prompt when the User is turning notifications on and the browser hasn't decided yet. */
export function shouldRequestNotificationPermission(permission: NotificationPermission): boolean {
  return permission === "default";
}

/** Never notify without both the preference on and the browser's permission already granted. */
export function canNotify(
  notificationsEnabled: boolean,
  permission: NotificationPermission,
): boolean {
  return notificationsEnabled && permission === "granted";
}

const ALARM_SOURCE = "/sounds/alarm.wav";

let unlocked = false;
let audioElement: HTMLAudioElement | null = null;

function getAudioElement(): HTMLAudioElement | null {
  if (typeof Audio === "undefined") {
    return null;
  }
  if (!audioElement) {
    audioElement = new Audio(ALARM_SOURCE);
  }
  return audioElement;
}

export function isAlarmUnlocked(): boolean {
  return unlocked;
}

/**
 * Unlocks Alarm autoplay by playing (and immediately rewinding) on the User's first interaction,
 * per the browser autoplay policy. Safe to call repeatedly — a no-op once already unlocked.
 */
export function unlockAlarm(): void {
  if (unlocked) {
    return;
  }
  const audio = getAudioElement();
  if (!audio) {
    return;
  }
  audio
    .play()
    .then(() => {
      audio.pause();
      audio.currentTime = 0;
      unlocked = true;
    })
    .catch(() => {
      // Still locked without a User gesture; the next interaction tries again.
    });
}

/** Plays the bundled Alarm asset, unless the preference is off or it is still autoplay-locked. */
export function playAlarm(alarmEnabled: boolean): void {
  if (!canPlayAlarm(alarmEnabled, unlocked)) {
    return;
  }
  const audio = getAudioElement();
  audio?.play().catch(() => {
    // Autoplay was blocked after all; nothing actionable for the User here.
  });
}

/** Requests the browser Notification permission, but never re-prompts once denied. */
export async function requestNotificationPermission(): Promise<NotificationPermission> {
  if (typeof Notification === "undefined") {
    return "denied";
  }
  if (!shouldRequestNotificationPermission(Notification.permission)) {
    return Notification.permission;
  }
  return Notification.requestPermission();
}

export function currentNotificationPermission(): NotificationPermission {
  return typeof Notification === "undefined" ? "denied" : Notification.permission;
}

/** Shows a phase-end Notification, gated by the same preference-plus-permission rule as `canNotify`. */
export function notifyPhaseEnd(notificationsEnabled: boolean, title: string, body: string): void {
  if (typeof Notification === "undefined") {
    return;
  }
  if (!canNotify(notificationsEnabled, Notification.permission)) {
    return;
  }
  new Notification(title, { body });
}
