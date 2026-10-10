import { describe, expect, it } from "vitest";
import { intensityBucket } from "./history-intensity";

describe("intensityBucket", () => {
  it("maps zero Pomodoros to the empty level", () => {
    expect(intensityBucket(0)).toBe(0);
  });

  it("maps a negative count to the empty level (never recorded, defensive floor)", () => {
    expect(intensityBucket(-1)).toBe(0);
  });

  it("maps 1-2 completed Pomodoros to level 1", () => {
    expect(intensityBucket(1)).toBe(1);
    expect(intensityBucket(2)).toBe(1);
  });

  it("maps 3-4 completed Pomodoros to level 2", () => {
    expect(intensityBucket(3)).toBe(2);
    expect(intensityBucket(4)).toBe(2);
  });

  it("maps 5-6 completed Pomodoros to level 3", () => {
    expect(intensityBucket(5)).toBe(3);
    expect(intensityBucket(6)).toBe(3);
  });

  it("maps 7 or more completed Pomodoros to the strongest level 4, uncapped", () => {
    expect(intensityBucket(7)).toBe(4);
    expect(intensityBucket(100)).toBe(4);
  });
});
