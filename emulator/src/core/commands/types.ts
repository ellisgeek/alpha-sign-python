// The contract between the Packet parser and the Command modules.
import type { EmulatorModel } from "../model";
import type { Readings } from "../readings";
import type { IgnoreReason, SignState } from "../types";

/** One complete Command from a Packet, after its Checksum (if any) passed. */
export interface ReceivedCommand {
  /** The Command Code (Table 6, p. 11), e.g. "A". */
  code: string;
  /** The Data Field, one char per byte. */
  data: string;
  /** Line ms the Command's last byte (ETX, Checksum, or EOT) arrived. */
  atMs: number;
}

/** Serial Error Status Register bits (p. 31). Bit 7 is always 0, bit 6 always 1. */
export const SerialError = {
  illegalCommand: 0x20,
  checksum: 0x10,
  bufferOverflow: 0x08,
  timeout: 0x04,
  framing: 0x02,
  parity: 0x01,
} as const;

/** The register's value after a read, a Network Query, or a clear (p. 31). */
export const SERIAL_ERRORS_CLEAR = 0x40;

export interface CommandContext {
  /** The Sign's state; handlers change it in place. */
  readonly state: SignState;
  readonly model: EmulatorModel;
  readonly readings: Readings;
  /**
   * Queues a Response Packet. `body` is everything between STX and ETX: the
   * Command Code the Sign returns and its data, e.g. "A" + label + content for a
   * TEXT File read (Table 14, p. 19) or "E" + label + data for a special
   * function read (Table 18, p. 36). The framing (20 NULs, SOH, "000", STX, ETX,
   * Checksum, EOT) is added for you. The Response leaves `delayMs` after the
   * Packet's EOT; if the Packet never ends with EOT, it is never sent.
   */
  respond(body: string, options?: { delayMs?: number }): void;
  /** Records dropped input in the snapshot's `ignored`. */
  ignore(reason: IgnoreReason, detail?: string, bytes?: string): void;
  /** ORs a `SerialError` bit into the Serial Error Status Register. */
  flagSerialError(bit: number): void;
}

export type CommandHandler = (command: ReceivedCommand, ctx: CommandContext) => void;

/** Handlers by Command Code. */
export type CommandTable = Record<string, CommandHandler>;
