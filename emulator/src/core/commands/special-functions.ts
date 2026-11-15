// Write and read SPECIAL FUNCTION, "E" and "F" (pp. 21-36).
//
// Each Command sub-dispatches on its Special Functions Label (the first data
// byte). A label the Emulator does not model is ignored as
// "unsupported-special-function" (no register bit); malformed data for a
// modelled label is an illegal write or read and sets register bit 5 (p. 31).
// To model another label, add one entry to `writes` or `reads`.
import { clockAt, setDate, setDayOfWeek, setTimeOfDay } from "../clock";
import {
  encodeEntry,
  memoryLeft,
  memoryNeeded,
  parseMemoryConfiguration,
  powerUpMemory,
} from "../memory";
import type { CommandContext, CommandHandler, CommandTable, ReceivedCommand } from "./types";
import { SERIAL_ERRORS_CLEAR, SerialError } from "./types";

type LabelHandler = (data: string, cmd: ReceivedCommand, ctx: CommandContext) => void;

/** Silence after tone "0" or "1": "Wait a minimum of 3 seconds" (p. 27, note 4). */
export const FIXED_TONE_SILENCE_MS = 3000;

function illegal(ctx: CommandContext, cmd: ReceivedCommand, detail: string): void {
  ctx.flagSerialError(SerialError.illegalCommand);
  ctx.ignore("illegal-special-function", detail, `${cmd.code}${cmd.data}`);
}

function unsupported(ctx: CommandContext, cmd: ReceivedCommand, detail: string): void {
  ctx.ignore("unsupported-special-function", detail, `${cmd.code}${cmd.data}`);
}

const pad2 = (n: number) => n.toString().padStart(2, "0");
const hex4 = (n: number) => n.toString(16).toUpperCase().padStart(4, "0");
const hex2 = (n: number) => n.toString(16).toUpperCase().padStart(2, "0");

/** A Sign answers a Network Query 1 s + 0.5 s x its Sign Address after it (p. 32). */
export const NETWORK_QUERY_FIRST_MS = 1000;
export const NETWORK_QUERY_STEP_MS = 500;

/** Two decimal digits, or NaN. */
function digits2(s: string): number {
  return /^\d\d$/.test(s) ? Number(s) : Number.NaN;
}

function timeOfDay(ctx: CommandContext, atMs: number): string {
  const c = clockAt(ctx.state.clock, atMs);
  return `${pad2(c.hour)}${pad2(c.minute)}`;
}

/** POOL,pool (p. 29): total and unused Memory Pool, four hex digits each. */
function memoryPool(ctx: CommandContext): string {
  return `${hex4(ctx.model.memoryBytes)},${hex4(memoryLeft(ctx.state, ctx.model, ctx.readings))}`;
}

/** Write SPECIAL FUNCTION labels (Table 15, pp. 21-28). */
const writes: Record<string, LabelHandler> = {
  // Set Time of Day: HhMm, 24-hour (p. 21).
  " "(data, cmd, ctx) {
    const hour = digits2(data.slice(0, 2));
    const minute = digits2(data.slice(2));
    if (!(hour < 24 && minute < 60)) return illegal(ctx, cmd, "time of day is HhMm");
    setTimeOfDay(ctx.state.clock, cmd.atMs, hour, minute);
  },

  // Enable ("00") or disable ("FF") the speaker (p. 21).
  "!"(data, cmd, ctx) {
    if (data !== "00" && data !== "FF") return illegal(ctx, cmd, 'speaker is "00" or "FF"');
    ctx.state.speakerOn = data === "00";
  },

  // Clear Memory ("E$" alone) or Set Memory Configuration (p. 21): a new table
  // replaces the old one and every File starts empty. A real 4120C kept its old
  // Files when a table needed more than its pool (docs/hardware-results.md);
  // whether it sets a register bit is not known, so none is set.
  $(data, cmd, ctx) {
    const { state } = ctx;
    if (data === "") {
      Object.assign(state, powerUpMemory());
      state.priority = null;
      state.runSequence = { order: "T", locked: false, labels: [] };
      state.displayRestartedAtMs = cmd.atMs;
      return;
    }
    const entries = parseMemoryConfiguration(data);
    if (!entries) return illegal(ctx, cmd, "Memory Configuration is FTPSIZEQQQQ per File");
    const needed = memoryNeeded(entries, ctx.model, ctx.readings);
    if (needed > ctx.model.memoryBytes) {
      return ctx.ignore(
        "memory-configuration-too-big",
        `needs ${needed} bytes; the pool has ${ctx.model.memoryBytes}`,
        `${cmd.code}${cmd.data}`,
      );
    }
    state.memoryConfiguration = entries;
    state.files = Object.fromEntries(
      entries.map((e) => [e.label, { label: e.label, type: e.type, data: "" }]),
    );
    state.displayRestartedAtMs = cmd.atMs;
  },

  // Set Day of Week: "1" Sunday ... "7" Saturday (p. 22).
  "&"(data, cmd, ctx) {
    if (!/^[1-7]$/.test(data)) return illegal(ctx, cmd, "day of week is 1-7");
    setDayOfWeek(ctx.state.clock, cmd.atMs, Number(data));
  },

  // Set Time Format: "S" am/pm, "M" 24-hour (p. 22).
  "'"(data, cmd, ctx) {
    if (data !== "S" && data !== "M") return illegal(ctx, cmd, "time format is S or M");
    ctx.state.clock.timeFormat = data;
  },

  // Generate Speaker Tone (p. 22). No sound: the tone is recorded, and input is
  // dropped for the silence the Sign needs (p. 27, notes 2, 4, and 5).
  "("(data, cmd, ctx) {
    const { state } = ctx;
    if (data === "A" || data === "B") {
      state.speakerOn = data === "A";
      return;
    }
    let silenceMs: number;
    if (data === "0" || data === "1") {
      silenceMs = FIXED_TONE_SILENCE_MS;
    } else if (/^2[0-9A-Fa-f]{2}[1-9A-Fa-f][0-9A-Fa-f]$/.test(data)) {
      // FFDR: D tenths of a second, repeated R times (Reading toneRepeats).
      const tenths = Number.parseInt(data.charAt(3), 16);
      const repeats = Number.parseInt(data.charAt(4), 16);
      const plays = ctx.readings.toneRepeats === "R+1" ? repeats + 1 : Math.max(repeats, 1);
      silenceMs = tenths * 100 * plays;
    } else if (data.startsWith("3") || data.startsWith("4")) {
      // Programmable sounds are Alpha 2.0 and 3.0 only (p. 22, p. 109).
      return unsupported(ctx, cmd, "programmable sounds need Alpha 2.0");
    } else {
      return illegal(ctx, cmd, "tone is A, B, 0, 1, or 2FFDR");
    }
    state.tones.push({ atMs: cmd.atMs, data });
    state.inputBlockedUntilMs = Math.max(state.inputBlockedUntilMs, cmd.atMs + silenceMs);
  },

  // Soft Reset: power-up diagnostics, memory kept (p. 22). The display restarts.
  ","(data, cmd, ctx) {
    if (data !== "") return illegal(ctx, cmd, "soft reset takes no data");
    ctx.state.displayRestartedAtMs = cmd.atMs;
    // Assumption until a real Sign shows otherwise: like power-up (p. 17), the
    // display restarts from the Run Sequence, not the last TEXT File written.
    ctx.state.displayStartLabel = null;
  },

  // Set Run Sequence: KPF..., 1-128 labels (p. 23). Labels are kept as sent;
  // one that is invalid or missing is skipped when the sequence runs.
  "."(data, cmd, ctx) {
    const order = data.charAt(0);
    const protection = data.charAt(1);
    const labels = [...data.slice(2)];
    if (order !== "T" && order !== "S" && order !== "D") {
      return illegal(ctx, cmd, "Run Sequence order is T, S, or D");
    }
    if (protection !== "U" && protection !== "L") {
      return illegal(ctx, cmd, "Run Sequence protection is U or L");
    }
    if (labels.length < 1 || labels.length > 128) {
      return illegal(ctx, cmd, "Run Sequence holds 1-128 File Labels");
    }
    ctx.state.runSequence = { order, locked: protection === "L", labels };
  },

  // Clear Serial Error Status Register to 40H (p. 24).
  "4"(_data, _cmd, ctx) {
    ctx.state.serialErrors = SERIAL_ERRORS_CLEAR;
  },

  // Set Serial Address: two hex characters "00"-"FF" (p. 26).
  "7"(data, cmd, ctx) {
    if (!/^[0-9A-Fa-f]{2}$/.test(data)) return illegal(ctx, cmd, "Sign Address is two hex digits");
    ctx.state.signAddress = Number.parseInt(data, 16);
  },

  // Set Date: mmddyy (p. 26). The year is read per Reading twoDigitYear (p. 28, note 15).
  ";"(data, cmd, ctx) {
    const month = digits2(data.slice(0, 2));
    const day = digits2(data.slice(2, 4));
    const yy = digits2(data.slice(4));
    if (data.length !== 6 || Number.isNaN(yy)) return illegal(ctx, cmd, "date is mmddyy");
    const year = ctx.readings.twoDigitYear === "19xx" || yy >= 97 ? 1900 + yy : 2000 + yy;
    const check = new Date(Date.UTC(year, month - 1, day));
    if (check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) {
      return illegal(ctx, cmd, "no such date");
    }
    setDate(ctx.state.clock, cmd.atMs, year, month, day);
  },
};

/** Read SPECIAL FUNCTION labels (Table 16, pp. 29-35); replies per Table 18 (p. 36). */
const reads: Record<string, LabelHandler> = {
  // Read Time of Day: HhMm, 24-hour (p. 29).
  " "(_data, cmd, ctx) {
    ctx.respond(`E ${timeOfDay(ctx, cmd.atMs)}`);
  },

  // Read Speaker Status: "00" enabled, "FF" disabled (p. 29).
  "!"(_data, _cmd, ctx) {
    ctx.respond(`E!${ctx.state.speakerOn ? "00" : "FF"}`);
  },

  // Read General Information: [<NUL>]FFFFFFFFfMmYyHhNnRSSPOOL,pool (p. 29),
  // shaped by Reading generalInfoLength. "28" leaves out the revision letter
  // f: the manual never says which character is missing (PROVISIONAL).
  '"'(_data, cmd, ctx) {
    const { firmware } = ctx.model;
    const length = ctx.readings.generalInfoLength;
    const revision = length === "28" ? "" : firmware.revision;
    const lead = length === "29+NUL" ? "\x00" : "";
    const time = timeOfDay(ctx, cmd.atMs);
    const speaker = ctx.state.speakerOn ? "00" : "FF";
    ctx.respond(
      `E"${lead}${firmware.name}${revision}${firmware.date}${time}` +
        `${ctx.state.clock.timeFormat}${speaker}${memoryPool(ctx)}`,
    );
  },

  // Read Memory Pool Size: POOL,pool (p. 30).
  "#"(_data, _cmd, ctx) {
    ctx.respond(`E#${memoryPool(ctx)}`);
  },

  // Read Memory Configuration: FTPSIZEQQQQ per File (p. 30).
  $(_data, _cmd, ctx) {
    ctx.respond(`E$${ctx.state.memoryConfiguration.map(encodeEntry).join("")}`);
  },

  // Read Day of Week: "1" Sunday ... "7" Saturday (p. 30).
  "&"(_data, cmd, ctx) {
    ctx.respond(`E&${clockAt(ctx.state.clock, cmd.atMs).dayOfWeek}`);
  },

  // Read Time Format (p. 30).
  "'"(_data, _cmd, ctx) {
    ctx.respond(`E'${ctx.state.clock.timeFormat}`);
  },

  // Read Serial Error Status Register: one bitmapped character, then the
  // register returns to 40H (p. 31).
  "*"(_data, _cmd, ctx) {
    ctx.respond(`E*${String.fromCharCode(ctx.state.serialErrors)}`);
    ctx.state.serialErrors = SERIAL_ERRORS_CLEAR;
  },

  // Network Query: UAAZ (p. 32), U Sign Type, AA Sign Address, Z the Serial Error
  // Status Register, sent 1 s + 0.5 s x the Sign Address after the query. A real
  // 4120C answered with a Response Packet "E-UAAZ" (docs/hardware-results.md); Reading
  // networkQueryFraming = "bare" sends UAAZ alone. Whether the answer clears the
  // register is not known, so it is kept.
  "-"(_data, _cmd, ctx) {
    const { signAddress, serialErrors } = ctx.state;
    const data = `${ctx.model.signType}${hex2(signAddress)}${String.fromCharCode(serialErrors)}`;
    const delayMs = NETWORK_QUERY_FIRST_MS + NETWORK_QUERY_STEP_MS * signAddress;
    if (ctx.readings.networkQueryFraming === "bare") ctx.respond(data, { delayMs, bare: true });
    else ctx.respond(`E-${data}`, { delayMs });
  },

  // Read Run Sequence: KPF... (p. 32).
  "."(_data, _cmd, ctx) {
    const { order, locked, labels } = ctx.state.runSequence;
    ctx.respond(`E.${order}${locked ? "L" : "U"}${labels.join("")}`);
  },
};

function subDispatch(table: Record<string, LabelHandler>): CommandHandler {
  return (cmd, ctx) => {
    const label = cmd.data.slice(0, 1);
    const handler = table[label];
    if (!handler) return unsupported(ctx, cmd, `${cmd.code} label ${JSON.stringify(label)}`);
    handler(cmd.data.slice(1), cmd, ctx);
  };
}

export const specialFunctionCommands: CommandTable = {
  E: subDispatch(writes),
  F: subDispatch(reads),
};
