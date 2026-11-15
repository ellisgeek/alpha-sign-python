// The Memory Pool and the Memory Configuration (p. 21, Table 15 "$"; p. 27, note 1).
import type { EmulatorModel } from "./model";
import type { Readings } from "./readings";
import type { FileEntry, FileType, SignState, StoredFile } from "./types";

/** The Priority TEXT File's label and fixed size, outside the Memory Pool (p. 20; p. 50). */
export const PRIORITY_LABEL = "0";
export const PRIORITY_SIZE = 125;

/** STRING data is buffered, so a STRING File holds at most 125 bytes (p. 37). */
export const STRING_MAX_SIZE = 125;

/** File Labels are 20H through 7EH (Appendix A, p. 50). */
export function isValidFileLabel(label: string): boolean {
  if (label.length !== 1) return false;
  const code = label.charCodeAt(0);
  return code >= 0x20 && code <= 0x7e;
}

/**
 * The single TEXT File "A" every Sign has at power-up (p. 17). The manual gives
 * no size for it; "0000" gives a last TEXT File all remaining memory (p. 27,
 * note 1), and "FF" is the Start Time Always (Appendix B). A real 4120C reported
 * the same free memory for File A alone whatever its size, so the size can't be
 * seen (docs/hardware-results.md).
 */
export function powerUpMemory(): {
  memoryConfiguration: FileEntry[];
  files: Record<string, StoredFile>;
} {
  return {
    memoryConfiguration: [{ label: "A", type: "TEXT", locked: false, size: "0000", extra: "FF00" }],
    files: { A: { label: "A", type: "TEXT", data: "" } },
  };
}

const TYPE_CODES: Record<string, FileType> = { A: "TEXT", B: "STRING", D: "DOTS" };

export function typeCode(type: FileType): string {
  return type === "TEXT" ? "A" : type === "STRING" ? "B" : "D";
}

/** One entry as the Memory Configuration writes and reads it: FTPSIZEQQQQ (pp. 21, 30). */
export function encodeEntry(e: FileEntry): string {
  return `${e.label}${typeCode(e.type)}${e.locked ? "L" : "U"}${e.size}${e.extra}`;
}

const HEX4 = /^[0-9A-Fa-f]{4}$/;

/** Parses Set Memory Configuration data, 11 characters per File; null if malformed. */
export function parseMemoryConfiguration(data: string): FileEntry[] | null {
  if (data.length === 0 || data.length % 11 !== 0) return null;
  const entries: FileEntry[] = [];
  for (let i = 0; i < data.length; i += 11) {
    const chunk = data.slice(i, i + 11);
    const label = chunk[0] ?? "";
    const type = TYPE_CODES[chunk[1] ?? ""];
    const protection = chunk[2];
    const size = chunk.slice(3, 7);
    const extra = chunk.slice(7, 11);
    if (!isValidFileLabel(label) || label === PRIORITY_LABEL || !type) return null;
    if (protection !== "U" && protection !== "L") return null;
    if (!HEX4.test(size) || !HEX4.test(extra)) return null;
    entries.push({ label, type, locked: protection === "L", size, extra });
  }
  return entries;
}

/** A DOTS PICTURE's size field is rows then columns, two hex digits each (p. 21). */
function dotsSize(e: FileEntry): { rows: number; columns: number } {
  return {
    rows: Number.parseInt(e.size.slice(0, 2), 16),
    columns: Number.parseInt(e.size.slice(2), 16),
  };
}

/**
 * Whether this entry takes all memory the other Files leave: a last TEXT File of
 * size "0000" (p. 27, note 1), or a last 0x0 DOTS PICTURE, which a real 4120C
 * treated the same way (docs/hardware-results.md).
 */
function takesTheRest(e: FileEntry, index: number, entries: FileEntry[]): boolean {
  if (index !== entries.length - 1 || e.size !== "0000") return false;
  return e.type === "TEXT" || e.type === "DOTS";
}

/**
 * Bytes an entry takes from the Memory Pool, before overhead. A DOTS PICTURE uses
 * 2 + rows x 2 x ceil(columns / 8) bytes whatever its color depth, as a real 4120C
 * measured (docs/hardware-results.md), unless Reading dotsPictureCounted is false
 * (p. 27, note 1 leaves it out).
 */
function entryBytes(e: FileEntry, readings: Readings): number {
  if (e.type === "DOTS") {
    if (!readings.dotsPictureCounted) return 0;
    const { rows, columns } = dotsSize(e);
    if (rows === 0 && columns === 0) return 0;
    return 2 + rows * 2 * Math.ceil(columns / 8);
  }
  return Number.parseInt(e.size, 16);
}

/**
 * Bytes a Memory Configuration needs: what the model keeps back, plus each File's
 * size and the per-File overhead (p. 27, note 1). A File that takes the rest adds
 * only its overhead. The Sign refuses a table that needs more than its pool.
 */
export function memoryNeeded(
  entries: FileEntry[],
  model: EmulatorModel,
  readings: Readings,
): number {
  return entries.reduce(
    (sum, e) => sum + entryBytes(e, readings) + readings.perFileOverhead,
    model.memoryReserved,
  );
}

/** Memory no File was given. */
function unallocated(entries: FileEntry[], model: EmulatorModel, readings: Readings): number {
  return Math.max(0, model.memoryBytes - memoryNeeded(entries, model, readings));
}

/**
 * Room for content in the File at `index`. Unused memory goes to the first File
 * when it is a TEXT File (p. 29, "#": "assigned to the first TEXT file"), unless a
 * File takes the rest. A real 4120C gave none to a TEXT File listed after a STRING
 * File (docs/hardware-results.md).
 */
function room(
  index: number,
  entries: FileEntry[],
  model: EmulatorModel,
  readings: Readings,
): number {
  const entry = entries[index];
  if (!entry) return 0;
  const left = unallocated(entries, model, readings);
  if (takesTheRest(entry, index, entries)) return left;
  if (entry.type === "DOTS") return 0;
  const size = Number.parseInt(entry.size, 16);
  if (entry.type === "STRING") return Math.min(size, STRING_MAX_SIZE);
  const restTaken = entries.some((e, i) => takesTheRest(e, i, entries));
  return index === 0 && !restTaken ? size + left : size;
}

/**
 * The unused portion of the Memory Pool as General Information reports it (p. 29,
 * "pool"): the room the first TEXT File has, less the model's freeShortfall. That is
 * what a real 4120C reported (docs/hardware-results.md). Never negative.
 */
export function memoryLeft(state: SignState, model: EmulatorModel, readings: Readings): number {
  const entries = state.memoryConfiguration;
  const first = entries.findIndex((e) => e.type === "TEXT");
  if (first === -1) return unallocated(entries, model, readings);
  return Math.max(0, room(first, entries, model, readings) - model.freeShortfall);
}

/** How many content bytes a File can hold. */
export function fileCapacity(
  entry: FileEntry,
  state: SignState,
  model: EmulatorModel,
  readings: Readings,
): number {
  const entries = state.memoryConfiguration;
  return room(entries.indexOf(entry), entries, model, readings);
}
