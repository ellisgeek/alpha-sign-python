// Shared test helpers. Packets are written as the manual prints them, with
// control characters spelled out: <NUL> = \x00, <SOH> = \x01, <STX> = \x02,
// <ETX> = \x03, <EOT> = \x04.
import {
  type CommandTable,
  createLine,
  model4120C,
  type Readings,
  type ReceivedCommand,
} from "../../src/core";

/** One byte per character; every character must be 0-255. */
export function bytes(text: string): Uint8Array {
  return Uint8Array.from(text, (ch) => ch.charCodeAt(0));
}

/** The inverse of `bytes`, for comparing output with a manual example. */
export function text(data: Uint8Array): string {
  return String.fromCharCode(...data);
}

export const SYNC = "\x00\x00\x00\x00\x00";

/** A Command table whose handlers only record what reached them. */
export function recordingCommands(codes: string): {
  commands: CommandTable;
  received: ReceivedCommand[];
} {
  const received: ReceivedCommand[] = [];
  const commands: CommandTable = {};
  for (const code of codes) {
    commands[code] = (command) => {
      received.push(command);
    };
  }
  return { commands, received };
}

/** 2026-11-07 12:00:00, read as the Sign's local time. */
export const START_CLOCK_MS = Date.UTC(2026, 10, 7, 12, 0, 0);

/** How long `oneSign().send` runs the Line past each Packet. */
export const SEND_SETTLE_MS = 500;

/** A Line with one 4120C (Sign Address 1 by default) and its clock at `START_CLOCK_MS`. */
export function oneSign(readings: Partial<Readings> = {}, signAddress = 1) {
  const line = createLine([{ model: model4120C, signAddress, readings }], {
    startClockMs: START_CLOCK_MS,
  });
  const sign = line.signs()[0];
  if (!sign) throw new Error("no sign");
  let t = 0;
  function send(packet: string): string[] {
    t += 1000;
    line.receive(bytes(packet), t);
    return line.advance(t + SEND_SETTLE_MS).map((o) => text(o.bytes));
  }
  return {
    line,
    sign,
    /**
     * Sends a whole Packet 1 s after the last one, runs the Line
     * `SEND_SETTLE_MS` past it, and returns the Responses as text.
     */
    send,
    /** The Line time the last `send` ran the Line to. */
    now(): number {
      return t + SEND_SETTLE_MS;
    },
    /** Sends `F<label>` and returns the Special Functions Data of the reply. */
    read(label: string): string {
      return specialData(send(`${SYNC}\x01Z00\x02F${label}\x04`)[0], label);
    },
  };
}

/**
 * The Special Functions Data of a Table 18 Response (p. 36) to `F<label>`:
 * 20 NULs, SOH, "000", STX, "E", label; then the data, ETX, a 4-digit
 * Checksum, and EOT.
 */
export function specialData(reply: string | undefined, label: string): string {
  const head = `${"\x00".repeat(20)}\x01000\x02E${label}`;
  if (reply === undefined || !reply.startsWith(head) || !reply.endsWith("\x04")) {
    throw new Error(`not a Table 18 reply to F${label}: ${JSON.stringify(reply)}`);
  }
  return reply.slice(head.length, -6);
}
