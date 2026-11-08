// The state an Emulated Sign starts with.
import { startClock } from "./clock";
import { SERIAL_ERRORS_CLEAR } from "./commands/types";
import { powerUpMemory } from "./memory";
import type { SignState } from "./types";

/**
 * Power-up state; keep every default here with its citation.
 */
export function powerUpState(
  signAddress: number,
  startClockMs: number,
  atLineMs: number,
): SignState {
  return {
    signAddress,
    // One TEXT File "A" (p. 17).
    ...powerUpMemory(),
    clock: startClock(startClockMs, atLineMs),
    // Order "T" and unlocked are the defaults (p. 23).
    runSequence: { order: "T", locked: false, labels: [] },
    priority: null,
    serialErrors: SERIAL_ERRORS_CLEAR,
    // "FF" speaker disabled (default) (p. 29, Read Speaker Status).
    speakerOn: false,
    tones: [],
    ignored: [],
    inputBlockedUntilMs: Number.NEGATIVE_INFINITY,
    displayRestartedAtMs: atLineMs,
    displayStartLabel: null,
  };
}
