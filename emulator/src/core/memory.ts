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
 * note 1), and "FF" is the Start Time Always (Appendix B). PROVISIONAL.
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

/**
 * Bytes an entry takes from the Memory Pool, before overhead. A DOTS PICTURE's
 * size field is rows then columns (p. 21); counted as one byte per pixel when
 * the Reading says it counts (PROVISIONAL: the manual gives no byte size).
 */
function entryBytes(e: FileEntry, readings: Readings): number {
  if (e.type === "DOTS") {
    if (!readings.dotsPictureCounted) return 0;
    return Number.parseInt(e.size.slice(0, 2), 16) * Number.parseInt(e.size.slice(2), 16);
  }
  return Number.parseInt(e.size, 16);
}

/**
 * Bytes used: each File's size plus the per-File overhead (p. 27, note 1). A
 * TEXT File of size "0000" takes whatever is left, so it adds only overhead.
 */
export function memoryUsed(entries: FileEntry[], readings: Readings): number {
  return entries.reduce((sum, e) => sum + entryBytes(e, readings) + readings.perFileOverhead, 0);
}

/** The unused portion of the Memory Pool (p. 29, "pool"). Never negative. */
export function memoryLeft(state: SignState, model: EmulatorModel, readings: Readings): number {
  return Math.max(0, model.memoryBytes - memoryUsed(state.memoryConfiguration, readings));
}

/** How many content bytes a File can hold. */
export function fileCapacity(
  entry: FileEntry,
  state: SignState,
  model: EmulatorModel,
  readings: Readings,
): number {
  if (entry.type === "TEXT" && entry.size === "0000") return memoryLeft(state, model, readings);
  const size = Number.parseInt(entry.size, 16);
  return entry.type === "STRING" ? Math.min(size, STRING_MAX_SIZE) : size;
}
