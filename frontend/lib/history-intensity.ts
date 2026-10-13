/** The heatmap's 5-level violet intensity scale, keyed by a day's completed-Pomodoro count. */
export type IntensityLevel = 0 | 1 | 2 | 3 | 4;

/**
 * Buckets a day's completed-Pomodoro count into one of 5 fixed intensity levels (Story 76).
 * Level 0 is empty; each further level covers two more completed Pomodoros, so a heavy day (7+)
 * tops out at the strongest violet rather than growing unbounded.
 */
export function intensityBucket(completedCount: number): IntensityLevel {
  if (completedCount <= 0) {
    return 0;
  }
  if (completedCount <= 2) {
    return 1;
  }
  if (completedCount <= 4) {
    return 2;
  }
  if (completedCount <= 6) {
    return 3;
  }
  return 4;
}
