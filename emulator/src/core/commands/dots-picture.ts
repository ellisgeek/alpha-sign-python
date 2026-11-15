// Write and read SMALL DOTS PICTURE File, "I" and "J" (pp. 39-41).
//
// A picture is stored as its Height and Width, then each row padded or cut to the
// Width and followed by <CR>, which is how p. 40 says the Sign reads a write. A read
// answers with that, so LFs sent in a write are not sent back (p. 40).
import { configuredFile } from "./files";
import type { CommandTable } from "./types";

/** Silence p. 40 asks for between the Width and the first row. */
export const DOTS_ROWS_PAUSE_MS = 100;

const SIZE = /^[0-9A-Fa-f]{4}$/;

/** Index in the Data Field of the first row byte: File Label, Height, Width. */
const ROWS_START = 5;

/**
 * The rows as the Sign keeps them (p. 40): LF is optional and dropped; a row longer
 * than the Width is cut, a shorter one padded with "0"; rows never sent are off,
 * because the Sign clears the picture once it has the Width.
 */
export function normalizeRows(rows: string, height: number, width: number): string {
  const lines = rows.replaceAll("\n", "").split("\r");
  let out = "";
  for (let y = 0; y < height; y++) {
    out += `${(lines[y] ?? "").slice(0, width).padEnd(width, "0")}\r`;
  }
  return out;
}

export const dotsPictureCommands: CommandTable = {
  I(cmd, ctx) {
    const label = cmd.data.slice(0, 1);
    const size = cmd.data.slice(1, ROWS_START);
    const body = `I${cmd.data}`;
    const entry = configuredFile(ctx, label, "DOTS", body);
    if (!entry) return;
    if (!SIZE.test(size)) {
      ctx.ignore("malformed-dots-picture", `size ${JSON.stringify(size)}`, body);
      return;
    }
    const widthAt = cmd.dataAtMs[ROWS_START - 1];
    const rowsAt = cmd.dataAtMs[ROWS_START];
    if (
      widthAt !== undefined &&
      rowsAt !== undefined &&
      rowsAt - widthAt < DOTS_ROWS_PAUSE_MS &&
      ctx.readings.missingDotsPause === "drop"
    ) {
      ctx.ignore("missing-dots-pause", `need ${DOTS_ROWS_PAUSE_MS} ms after the Width`, body);
      return;
    }
    if (
      size.toUpperCase() !== entry.size.toUpperCase() &&
      ctx.readings.dotsPictureSize === "drop"
    ) {
      ctx.ignore("dots-size-mismatch", `size ${size} into File ${label} of ${entry.size}`, body);
      return;
    }
    const height = Number.parseInt(size.slice(0, 2), 16);
    const width = Number.parseInt(size.slice(2, 4), 16);
    const rows = normalizeRows(cmd.data.slice(ROWS_START), height, width);
    ctx.state.files[label] = { label, type: "DOTS", data: `${size}${rows}` };
    // "the sign will go blank until the transmission is complete" (p. 39).
    ctx.state.displayRestartedAtMs = cmd.atMs;
  },

  // The Response returns Command Code "I", the File Label, and the data (Table 24, p. 41).
  // Before any write, it holds the configured size and no rows (an assumption).
  J(cmd, ctx) {
    const label = cmd.data.slice(0, 1);
    const entry = configuredFile(ctx, label, "DOTS", `J${cmd.data}`);
    if (!entry) return;
    ctx.respond(`I${label}${ctx.state.files[label]?.data || entry.size}`);
  },
};
