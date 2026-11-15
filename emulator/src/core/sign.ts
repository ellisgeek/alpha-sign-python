// One Emulated Sign: its Packet parser (pp. 10-14) and its state.
//
// Each Sign parses the Line's bytes on its own, so Signs with different
// Readings or input blocks behave independently. Commands run as soon as they
// are complete (after their ETX + Checksum, or at the next STX / EOT);
// Responses wait for the Packet's EOT.
import { checksum, stringToBytes } from "./bytes";
import { clockAt } from "./clock";
import { TABLE_6_COMMAND_CODES } from "./commands/index";
import {
  type CommandContext,
  type CommandTable,
  type ReceivedCommand,
  SerialError,
} from "./commands/types";
import { buildDisplay } from "./display/build-display";
import type { EmulatorModel } from "./model";
import type { Readings } from "./readings";
import { isAddressed, parseRecipients } from "./recipients";
import { encodeResponse } from "./response";
import type { EmulatedSign, IgnoreReason, Outgoing, SignSnapshot, SignState } from "./types";

const SOH = "\x01";
const STX = "\x02";
const ETX = "\x03";
const EOT = "\x04";

/** Silence required after each nested STX (p. 11, Table 4 item E note). */
export const NESTED_STX_PAUSE_MS = 100;

type ParserState =
  | { kind: "idle" }
  | { kind: "header"; buf: string }
  | { kind: "skip" }
  | { kind: "body"; cmd: PendingCommand }
  | { kind: "afterEtx"; cmd: PendingCommand }
  | { kind: "checksum"; cmd: PendingCommand; sum: string }
  | { kind: "afterChecksum" };

interface PendingCommand {
  body: string;
  stxAtMs: number;
  nested: boolean;
  /** Set when the first byte after a nested STX came too soon. */
  missedPause: boolean;
}

export interface SignInternals extends EmulatedSign {
  feed(byte: number, atMs: number): void;
  /** Responses completed since the last call. */
  takeOutgoing(): Outgoing[];
}

export function createSign(
  model: EmulatorModel,
  settings: Readings,
  state: SignState,
  commands: CommandTable,
  now: () => number,
): SignInternals {
  let parser: ParserState = { kind: "idle" };
  let queuedResponses: { body: string; delayMs: number; bare: boolean }[] = [];
  let outgoing: Outgoing[] = [];
  let blockedRunOpen = false;
  /** Set when a Command in the open Packet started a tone's silence. */
  let packetStartedSilence = false;

  function ignore(atMs: number, reason: IgnoreReason, detail?: string, bytes = ""): void {
    state.ignored.push(
      detail === undefined ? { atMs, reason, bytes } : { atMs, reason, detail, bytes },
    );
  }

  function context(atMs: number): CommandContext {
    return {
      state,
      model,
      readings: settings,
      respond(body, options) {
        queuedResponses.push({
          body,
          delayMs: options?.delayMs ?? 0,
          bare: options?.bare ?? false,
        });
      },
      ignore(reason, detail, bytes) {
        ignore(atMs, reason, detail, bytes);
      },
      flagSerialError(bit) {
        state.serialErrors |= bit;
      },
    };
  }

  function startCommand(atMs: number, nested: boolean): void {
    parser = {
      kind: "body",
      cmd: { body: "", stxAtMs: atMs, nested, missedPause: false },
    };
  }

  function complete(cmd: PendingCommand, sum: string | null, atMs: number): void {
    if (sum !== null) {
      const expected = checksum(`${STX}${cmd.body}${ETX}`);
      if (sum.toUpperCase() !== expected) {
        state.serialErrors |= SerialError.checksum;
        ignore(atMs, "bad-checksum", `got ${sum}, expected ${expected}`, cmd.body);
        return;
      }
    }
    if (cmd.missedPause && settings.missingStxPause === "drop") {
      ignore(
        atMs,
        "missing-stx-pause",
        `need ${NESTED_STX_PAUSE_MS} ms after a nested STX`,
        cmd.body,
      );
      return;
    }
    const code = cmd.body[0];
    if (code === undefined) {
      ignore(atMs, "malformed-packet", "STX with no Command Code");
      return;
    }
    const handler = commands[code];
    if (!handler) {
      if (TABLE_6_COMMAND_CODES.has(code)) {
        ignore(atMs, "unsupported-command", `Command Code ${code}`, cmd.body);
      } else {
        state.serialErrors |= SerialError.illegalCommand;
        ignore(atMs, "unknown-command", `Command Code ${code}`, cmd.body);
      }
      return;
    }
    const received: ReceivedCommand = { code, data: cmd.body.slice(1), atMs };
    const blockedUntil = state.inputBlockedUntilMs;
    handler(received, context(atMs));
    if (state.inputBlockedUntilMs > blockedUntil) packetStartedSilence = true;
  }

  function endPacket(atMs: number): void {
    for (const r of queuedResponses) {
      const bytes = r.bare ? stringToBytes(r.body) : encodeResponse(r.body, model.responseNuls);
      outgoing.push({ bytes, atMs: atMs + r.delayMs });
    }
    queuedResponses = [];
    parser = { kind: "idle" };
    packetStartedSilence = false;
  }

  function abandonPacket(): void {
    queuedResponses = [];
    packetStartedSilence = false;
  }

  function step(ch: string, atMs: number): void {
    switch (parser.kind) {
      case "idle":
        if (ch === SOH) parser = { kind: "header", buf: "" };
        return;
      case "skip":
        if (ch === EOT) parser = { kind: "idle" };
        else if (ch === SOH) parser = { kind: "header", buf: "" };
        return;
      case "header": {
        if (ch === SOH) {
          // Five SOHs may stand in for the sync NULs (Table 4 item A).
          if (parser.buf !== "") ignore(atMs, "malformed-packet", "header restarted", parser.buf);
          parser = { kind: "header", buf: "" };
        } else if (ch === EOT) {
          parser = { kind: "idle" };
        } else if (ch === STX) {
          const recipients = parseRecipients(parser.buf);
          if (recipients === null) {
            ignore(atMs, "malformed-packet", "unreadable Type Code / Sign Address", parser.buf);
            parser = { kind: "skip" };
          } else if (!isAddressed(recipients, model, state)) {
            parser = { kind: "skip" };
          } else {
            startCommand(atMs, false);
          }
        } else if (ch !== "\x00") {
          parser.buf += ch;
        }
        return;
      }
      case "body": {
        const cmd = parser.cmd;
        if (cmd.nested && cmd.body === "" && atMs - cmd.stxAtMs < NESTED_STX_PAUSE_MS) {
          cmd.missedPause = true;
        }
        if (ch === ETX) parser = { kind: "afterEtx", cmd };
        else if (ch === EOT) {
          complete(cmd, null, atMs);
          endPacket(atMs);
        } else if (ch === SOH || ch === STX) {
          ignore(atMs, "malformed-packet", "Command not ended by ETX before STX/SOH", cmd.body);
          abandonPacket();
          parser = ch === SOH ? { kind: "header", buf: "" } : { kind: "skip" };
        } else cmd.body += ch;
        return;
      }
      case "afterEtx": {
        const cmd = parser.cmd;
        if (ch === STX) {
          // Nesting without Checksums (p. 14).
          complete(cmd, null, atMs);
          startCommand(atMs, true);
        } else if (ch === EOT) {
          complete(cmd, null, atMs);
          endPacket(atMs);
        } else parser = { kind: "checksum", cmd, sum: ch };
        return;
      }
      case "checksum": {
        if (ch === STX || ch === EOT || ch === SOH) {
          state.serialErrors |= SerialError.checksum;
          ignore(atMs, "bad-checksum", `short Checksum "${parser.sum}"`, parser.cmd.body);
          if (ch === STX) startCommand(atMs, true);
          else if (ch === EOT) endPacket(atMs);
          else parser = { kind: "header", buf: "" };
          return;
        }
        parser.sum += ch;
        if (parser.sum.length === 4) {
          complete(parser.cmd, parser.sum, atMs);
          parser = { kind: "afterChecksum" };
        }
        return;
      }
      case "afterChecksum":
        if (ch === STX) startCommand(atMs, true);
        else if (ch === EOT) endPacket(atMs);
        else if (ch === SOH) {
          abandonPacket();
          parser = { kind: "header", buf: "" };
        } else ignore(atMs, "malformed-packet", "byte after Checksum", ch);
        return;
    }
  }

  return {
    model,
    settings,
    feed(byte, atMs) {
      const ch = String.fromCharCode(byte);
      // The silence is for data sent after the tone (p. 27, note 4): the EOT
      // that closes the tone's own Packet still ends it, Checksum or not.
      const closesTonePacket =
        ch === EOT && packetStartedSilence && parser.kind === "afterChecksum";
      if (atMs < state.inputBlockedUntilMs && !closesTonePacket) {
        const last = state.ignored.at(-1);
        if (blockedRunOpen && last?.reason === "input-blocked") last.bytes += ch;
        else ignore(atMs, "input-blocked", "input during a tone's silence (p. 27, note 4)", ch);
        blockedRunOpen = true;
        return;
      }
      blockedRunOpen = false;
      step(ch, atMs);
    },
    takeOutgoing() {
      const out = outgoing;
      outgoing = [];
      return out;
    },
    snapshot(): SignSnapshot {
      const nowMs = now();
      return {
        signType: model.signType,
        signAddress: state.signAddress,
        memoryConfiguration: state.memoryConfiguration.map((e) => ({ ...e })),
        files: Object.fromEntries(Object.entries(state.files).map(([k, f]) => [k, { ...f }])),
        clock: clockAt(state.clock, nowMs),
        runSequence: { ...state.runSequence, labels: [...state.runSequence.labels] },
        priority: state.priority ? { ...state.priority } : null,
        serialErrors: state.serialErrors,
        speakerOn: state.speakerOn,
        tones: state.tones.map((t) => ({ ...t })),
        display: buildDisplay(state, model, nowMs, settings),
        ignored: state.ignored.map((i) => ({ ...i })),
      };
    },
  };
}
