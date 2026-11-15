// The Line: every Emulated Sign hears every byte; their Responses are merged
// in time order. Responses that overlap on the wire garble each other.
import { defaultCommands } from "./commands/index";
import type { CommandTable } from "./commands/types";
import type { EmulatorModel } from "./model";
import { DEFAULT_READINGS, type Readings } from "./readings";
import { createSign, type SignInternals } from "./sign";
import { powerUpState } from "./state";
import type { EmulatedSign, Line, Outgoing } from "./types";

export interface SignSetup {
  model: EmulatorModel;
  /** 1-255; 0 is the broadcast address (p. 11). */
  signAddress: number;
  /** Overrides of `DEFAULT_READINGS`. */
  readings?: Partial<Readings>;
}

export interface LineOptions {
  /** The Sign clocks' wall-clock ms at `startMs`; UTC fields are read as local time. */
  startClockMs: number;
  /** Line time at creation. Default 0. */
  startMs?: number;
  /** The Command dispatch table. Default: every registered Command family. */
  commands?: CommandTable;
}

export function createLine(setups: SignSetup[], options: LineOptions): Line {
  let nowMs = options.startMs ?? 0;
  const commands = options.commands ?? defaultCommands;
  const signs: SignInternals[] = setups.map((setup) =>
    createSign(
      setup.model,
      { ...DEFAULT_READINGS, ...setup.readings },
      powerUpState(setup.signAddress, options.startClockMs, nowMs),
      commands,
      () => nowMs,
    ),
  );
  let input: { bytes: Uint8Array; atMs: number; seq: number }[] = [];
  let pending: Outgoing[] = [];
  let seq = 0;

  return {
    receive(bytes, atMs) {
      input.push({ bytes: bytes.slice(), atMs, seq: seq++ });
    },
    advance(toMs) {
      nowMs = Math.max(nowMs, toMs);
      const due = input
        .filter((c) => c.atMs <= toMs)
        .sort((a, b) => a.atMs - b.atMs || a.seq - b.seq);
      input = input.filter((c) => c.atMs > toMs);
      for (const chunk of due) {
        for (const byte of chunk.bytes) for (const sign of signs) sign.feed(byte, chunk.atMs);
      }
      for (const sign of signs) pending.push(...sign.takeOutgoing());
      pending = collide(pending);
      const out = pending.filter((o) => o.atMs <= toMs);
      pending = pending.filter((o) => o.atMs > toMs);
      return out;
    },
    signs(): EmulatedSign[] {
      return [...signs];
    },
  };
}

/** Milliseconds one byte takes at 9600 baud, 8N1: ten bits (Table 3, p. 8). */
export const BYTE_MS = 10_000 / 9600;

/**
 * Sorts Responses by time and combines any that overlap on the wire. The serial line
 * idles high and a 0 bit drives it low, so bytes sent at once combine as a bitwise
 * AND. Two Signs at one Sign Address answering a Network Query garble each other
 * this way (p. 32).
 */
function collide(responses: Outgoing[]): Outgoing[] {
  const sorted = [...responses].sort((a, b) => a.atMs - b.atMs);
  const out: Outgoing[] = [];
  for (const next of sorted) {
    const last = out.at(-1);
    if (!last || next.atMs >= last.atMs + last.bytes.length * BYTE_MS) {
      out.push(next);
      continue;
    }
    const offset = Math.round((next.atMs - last.atMs) / BYTE_MS);
    const merged = new Uint8Array(Math.max(last.bytes.length, offset + next.bytes.length));
    merged.fill(0xff);
    merged.set(last.bytes);
    next.bytes.forEach((byte, i) => {
      const at = offset + i;
      merged[at] = (at < last.bytes.length ? (merged[at] ?? 0xff) : 0xff) & byte;
    });
    out[out.length - 1] = { bytes: merged, atMs: last.atMs };
  }
  return out;
}
