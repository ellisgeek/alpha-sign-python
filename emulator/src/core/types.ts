// The core's public shapes (docs/emulator-spec.md, "Architecture").
//
// Byte strings: File content, Command data, and Response bodies are JS strings
// with one character per byte (char codes 0-255), so they print, compare, and
// serialize to JSON easily. Use `bytesToString` / `stringToBytes` at the edges.
import type { EmulatorModel } from "./model";
import type { Readings } from "./readings";

/** The serial network one or more Emulated Signs listen on. */
export interface Line {
  /** Bytes from the library, all stamped with the time they arrived. */
  receive(bytes: Uint8Array, atMs: number): void;
  /**
   * Runs every Sign up to `toMs`: input received at or before `toMs` is
   * processed, and Responses due at or before `toMs` are returned, in time order.
   */
  advance(toMs: number): Outgoing[];
  signs(): EmulatedSign[];
}

/** Bytes to send to the library at `atMs`. */
export interface Outgoing {
  bytes: Uint8Array;
  atMs: number;
}

export interface EmulatedSign {
  readonly model: EmulatorModel;
  readonly settings: Readings;
  /** The Sign's state at the Line's current time (the last `advance`). */
  snapshot(): SignSnapshot;
}

/** File types as the Memory Configuration names them (p. 21, Table 15). */
export type FileType = "TEXT" | "STRING" | "DOTS";

/** One entry of the Memory Configuration (p. 21). */
export interface FileEntry {
  label: string;
  type: FileType;
  locked: boolean;
  /** The 4-character size field exactly as written (hex bytes, or rows+columns for DOTS). */
  size: string;
  /** The 4-character field after the size (Start/Stop Times, "0000", or color status). */
  extra: string;
}

export interface StoredFile {
  label: string;
  type: FileType;
  /** Content as received after the File Label, one char per byte. */
  data: string;
}

/** Day of week as the manual numbers it: 1 = Sunday ... 7 = Saturday (p. 30). */
export type DayOfWeek = 1 | 2 | 3 | 4 | 5 | 6 | 7;

/** Time format (p. 29): "S" standard am/pm, "M" 24-hour. */
export type TimeFormat = "S" | "M";

/** Mutable clock state; read it through `clockAt`. */
export interface ClockState {
  /** Sign wall-clock ms minus Line ms. Wall-clock ms are read as UTC fields = Sign local time. */
  offsetMs: number;
  /** Added to the weekday derived from the date (0-6), so Set Day keeps advancing at midnight. */
  dayOfWeekShift: number;
  timeFormat: TimeFormat;
}

export interface EmulatedClock {
  /** Sign wall-clock ms; its UTC fields are the Sign's local date and time. */
  wallMs: number;
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  dayOfWeek: DayOfWeek;
  timeFormat: TimeFormat;
}

/** The Run Sequence (p. 23): order "T" by times, "S" in sequence, "D" by times then delete. */
export interface RunSequence {
  order: "T" | "S" | "D";
  locked: boolean;
  labels: string[];
}

export interface TonePlayed {
  atMs: number;
  /** The Special Functions Data of the tone Command, one char per byte. */
  data: string;
}

/** Input a real Sign drops without saying so. The Emulator says so here. */
export interface IgnoredInput {
  atMs: number;
  reason: IgnoreReason;
  detail?: string;
  /** The bytes dropped (a Command body, a header, ...), one char per byte. */
  bytes: string;
}

/**
 * Known reasons. Command modules may add their own strings; keep them kebab-case.
 * - bad-checksum: Checksum did not match (p. 12); register bit 4 set.
 * - missing-stx-pause: nested Command's STX not followed by 100 ms (p. 11).
 * - unknown-command: Command Code not in Table 6 (p. 11); register bit 5 set.
 * - unsupported-command: in Table 6 but not modelled by the Emulator.
 * - malformed-packet: framing the parser cannot read (bad header, missing ETX, ...).
 * - input-blocked: bytes arrived while `inputBlockedUntilMs` (tone silence, p. 27 note 4).
 */
export type IgnoreReason =
  | "bad-checksum"
  | "missing-stx-pause"
  | "unknown-command"
  | "unsupported-command"
  | "malformed-packet"
  | "input-blocked"
  | (string & {});

export interface TextRun {
  text: string;
  /** Palette index (see `EmulatorModel.palette`). */
  color: number;
  /** Font name the run is drawn in, e.g. "seven high standard" (Appendix G, 1AH). */
  font: string;
  /** Wide characters on (12H, or 1DH "0"/"1"). */
  wide: boolean;
  /** Character flash on (07H "1"). */
  flash: boolean;
  /** Set when the run is a called SMALL DOTS PICTURE (14H): its File Label. `text` is "". */
  picture?: string;
}

export interface DisplayState {
  fileLabel: string | null;
  frameIndex: number;
  /** The Mode the Frame asked for, by its Table 65-67 name (e.g. "ROTATE", "SNOW"). */
  mode: string;
  /** The Mode actually drawn: `mode`, or "HOLD" for a Mode the Emulator cannot draw yet. */
  drawnAs: string;
  /** Display Position: "top", "middle", "bottom", "fill", "left", "right", or "none". */
  position: string;
  /** The Special Graphic's name (Table 67) when the Frame plays one, else null. */
  specialGraphic: string | null;
  /** Text and color runs per display line. */
  lines: TextRun[][];
  /** Palette index per pixel, row-major, `width * height` entries; 0 = off. */
  pixels: { width: number; height: number; colors: Uint8Array };
}

export interface SignSnapshot {
  signType: string;
  signAddress: number;
  memoryConfiguration: FileEntry[];
  files: Record<string, StoredFile>;
  clock: EmulatedClock;
  runSequence: RunSequence;
  priority: StoredFile | null;
  /** Serial Error Status Register value (p. 31); 0x40 when clear. */
  serialErrors: number;
  speakerOn: boolean;
  tones: TonePlayed[];
  display: DisplayState;
  ignored: IgnoredInput[];
}

/**
 * The mutable state of one Emulated Sign. Command handlers change it; the
 * snapshot is a copy of it plus the clock reading and the display.
 */
export interface SignState {
  signAddress: number;
  memoryConfiguration: FileEntry[];
  files: Record<string, StoredFile>;
  clock: ClockState;
  runSequence: RunSequence;
  priority: StoredFile | null;
  serialErrors: number;
  speakerOn: boolean;
  tones: TonePlayed[];
  ignored: IgnoredInput[];
  /** Line ms before which every received byte is dropped (tone silence, p. 27 note 4). */
  inputBlockedUntilMs: number;
  /** Line ms the display last restarted, e.g. a TEXT File write blanks it (p. 17). */
  displayRestartedAtMs: number;
  /**
   * TEXT File Label the display starts with after a restart: "the unit will begin
   * displaying the last received TEXT file" (p. 18). Null starts at the Run Sequence's
   * first File. The TEXT write handler sets it with `displayRestartedAtMs`.
   */
  displayStartLabel: string | null;
}
