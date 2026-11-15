// What TEXT and STRING File writes and reads share: finding the File in the
// Memory Configuration, and the oversized-write Reading.
import { fileCapacity, isValidFileLabel } from "../memory";
import type { FileEntry, FileType } from "../types";
import { type CommandContext, SerialError } from "./types";

/**
 * The Memory Configuration entry a write or read of `label` goes to, or null
 * after recording why the Command was dropped. A label outside Appendix A
 * (p. 50) is an illegal File Label and sets register bit 5 (p. 31).
 */
export function configuredFile(
  ctx: CommandContext,
  label: string,
  type: FileType,
  body: string,
): FileEntry | null {
  if (!isValidFileLabel(label)) {
    ctx.flagSerialError(SerialError.illegalCommand);
    ctx.ignore("illegal-file-label", `File Label ${JSON.stringify(label)}`, body);
    return null;
  }
  const entry = ctx.state.memoryConfiguration.find((e) => e.label === label);
  if (!entry) {
    ctx.ignore("unconfigured-file", `File ${label} is not in the Memory Configuration`, body);
    return null;
  }
  if (entry.type !== type) {
    ctx.ignore("wrong-file-type", `File ${label} is a ${entry.type} File`, body);
    return null;
  }
  return entry;
}

/**
 * Applies the oversized-write Reading: the content to store, or null when the
 * write is dropped. "measured" does what a real 4120C did (docs/hardware-results.md):
 * a TEXT File keeps the first capacity + 1 bytes and sets the buffer overflow bit; a
 * STRING File is emptied and the illegal command bit is set (p. 31). The Priority
 * TEXT File was not measured: there "measured" drops the write, as "ignore" does.
 */
export function fitContent(
  ctx: CommandContext,
  type: FileType | "PRIORITY",
  content: string,
  capacity: number,
  label: string,
  body: string,
): string | null {
  if (content.length <= capacity) return content;
  const reading = ctx.readings.oversizedWrite;
  if (reading === "measured" && type === "TEXT") {
    ctx.flagSerialError(SerialError.bufferOverflow);
    return content.slice(0, capacity + 1);
  }
  if (reading === "measured" && type === "STRING") {
    ctx.flagSerialError(SerialError.illegalCommand);
    ctx.ignore(
      "oversized-write",
      `${content.length} bytes into File ${label} of ${capacity}`,
      body,
    );
    return "";
  }
  if (reading === "truncate") return content.slice(0, capacity);
  ctx.ignore("oversized-write", `${content.length} bytes into File ${label} of ${capacity}`, body);
  return null;
}

/** Writes `content` to a configured File of `type`; returns false if dropped. */
export function writeFile(
  ctx: CommandContext,
  type: FileType,
  label: string,
  content: string,
  body: string,
): boolean {
  const entry = configuredFile(ctx, label, type, body);
  if (!entry) return false;
  const capacity = fileCapacity(entry, ctx.state, ctx.model, ctx.readings);
  const fitted = fitContent(ctx, type, content, capacity, label, body);
  if (fitted === null) return false;
  ctx.state.files[label] = { label, type, data: fitted };
  return true;
}
