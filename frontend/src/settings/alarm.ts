/**
 * The Alarm: a short audio asset (`/alarm.mp3`) played via `HTMLAudioElement`
 * (story 72). Modern autoplay policies block any `play()` that isn't
 * triggered by (or doesn't follow) a user gesture, so `unlock()` must be
 * called once from a real interaction handler before `play()` is ever
 * expected to produce sound; `play()` itself stays a no-op-on-failure since
 * the only other caller is a passive, non-user-initiated Timer re-fetch.
 */

export interface AlarmAudio {
  play(): Promise<void> | void;
  pause(): void;
  currentTime: number;
}

export interface AlarmPlayer {
  /** Call from a real user-gesture handler (click/keydown) to unlock autoplay. */
  unlock(): void;
  /** Play the Alarm from the start; silently does nothing if playback fails. */
  play(): void;
}

export interface AlarmPlayerOptions {
  /** Injectable so tests never touch a real `<audio>` element. */
  createAudio?: () => AlarmAudio;
}

function defaultCreateAudio(): AlarmAudio {
  return new Audio("/alarm.mp3");
}

export function createAlarmPlayer(
  options: AlarmPlayerOptions = {},
): AlarmPlayer {
  const createAudio = options.createAudio ?? defaultCreateAudio;
  let audio: AlarmAudio | null = null;
  let unlocked = false;

  function ensureAudio(): AlarmAudio {
    if (!audio) {
      audio = createAudio();
    }
    return audio;
  }

  return {
    unlock() {
      if (unlocked) {
        return;
      }
      unlocked = true;
      const element = ensureAudio();
      const result = element.play();
      if (result && typeof (result as Promise<void>).then === "function") {
        (result as Promise<void>)
          .then(() => {
            element.pause();
            element.currentTime = 0;
          })
          .catch(() => {
            // Autoplay was still blocked; allow another unlock attempt on
            // the next user gesture instead of silently wedging forever.
            unlocked = false;
          });
      } else {
        element.pause();
        element.currentTime = 0;
      }
    },
    play() {
      const element = ensureAudio();
      element.currentTime = 0;
      const result = element.play();
      if (result && typeof (result as Promise<void>).catch === "function") {
        void (result as Promise<void>).catch(() => {});
      }
    },
  };
}
