import { describe, expect, it, vi } from "vitest";
import { type AlarmAudio, createAlarmPlayer } from "./alarm";

function fakeAudio(
  overrides: Partial<AlarmAudio> & { playImpl?: () => Promise<void> } = {},
): AlarmAudio & { pause: ReturnType<typeof vi.fn> } {
  const playImpl = overrides.playImpl ?? (() => Promise.resolve());
  return {
    currentTime: 0,
    play: vi.fn(playImpl),
    pause: vi.fn(),
    ...overrides,
  } as AlarmAudio & { pause: ReturnType<typeof vi.fn> };
}

describe("createAlarmPlayer", () => {
  it("plays and immediately pauses/resets on unlock, satisfying the autoplay-unlock gesture without audible sound", async () => {
    const audio = fakeAudio();
    const player = createAlarmPlayer({ createAudio: () => audio });

    player.unlock();
    await Promise.resolve();
    await Promise.resolve();

    expect(audio.play).toHaveBeenCalledOnce();
    expect(audio.pause).toHaveBeenCalledOnce();
    expect(audio.currentTime).toBe(0);
  });

  it("only creates and unlocks the audio element once across repeated calls", () => {
    let createCount = 0;
    const audio = fakeAudio();
    const player = createAlarmPlayer({
      createAudio: () => {
        createCount += 1;
        return audio;
      },
    });

    player.unlock();
    player.unlock();
    player.unlock();

    expect(createCount).toBe(1);
    expect(audio.play).toHaveBeenCalledOnce();
  });

  it("plays the Alarm from the start when play() is called", () => {
    const audio = fakeAudio();
    audio.currentTime = 5;
    const player = createAlarmPlayer({ createAudio: () => audio });

    player.play();

    expect(audio.currentTime).toBe(0);
    expect(audio.play).toHaveBeenCalledOnce();
  });

  it("allows a retry on the next gesture if the browser blocks the unlock attempt", async () => {
    let attempt = 0;
    const audio = fakeAudio({
      playImpl: () => {
        attempt += 1;
        return attempt === 1
          ? Promise.reject(new Error("blocked"))
          : Promise.resolve();
      },
    });
    const player = createAlarmPlayer({ createAudio: () => audio });

    player.unlock();
    await Promise.resolve();
    await Promise.resolve();
    expect(audio.pause).not.toHaveBeenCalled();

    player.unlock();
    await Promise.resolve();
    await Promise.resolve();

    expect(audio.play).toHaveBeenCalledTimes(2);
    expect(audio.pause).toHaveBeenCalledOnce();
  });

  it("never throws when play() rejects outside of unlock (e.g. a disabled Alarm the caller still called play on)", () => {
    const audio = fakeAudio({
      playImpl: () => Promise.reject(new Error("blocked")),
    });
    const player = createAlarmPlayer({ createAudio: () => audio });

    expect(() => player.play()).not.toThrow();
  });
});
