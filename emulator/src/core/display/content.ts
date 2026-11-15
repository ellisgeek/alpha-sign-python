// TEXT File content as Frames and Segments (p. 18, Table 12; Appendix G, pp. 81-82).
// Control Codes the Emulator does not draw are kept as "other" Segments with their
// bytes, so nothing is lost.

export type Segment =
  | { kind: "text"; text: string }
  /** 1CH + code: "1"-"8" palette colors, "9" Rainbow 1, "A" Rainbow 2, "B" Color mix, "C" Autocolor. */
  | { kind: "color"; code: string }
  /** 1AH + code (Select character set). */
  | { kind: "font"; code: string }
  /** 12H on / 11H off, or 1DH "0". */
  | { kind: "wide"; on: boolean }
  /** 1DH "1". */
  | { kind: "doubleWide"; on: boolean }
  /** 05H, or 1DH "2". */
  | { kind: "doubleHeight"; on: boolean }
  /** 07H. */
  | { kind: "flash"; on: boolean }
  /** 15H-19H: 1 slowest to 5 fastest. */
  | { kind: "speed"; speed: number }
  /** 09H. */
  | { kind: "noHold" }
  /** 10H + STRING File Label. */
  | { kind: "string"; label: string }
  /** 14H + SMALL DOTS PICTURE File Label. */
  | { kind: "picture"; label: string }
  /** 13H. */
  | { kind: "time" }
  /** 0BH + format "0"-"9". */
  | { kind: "date"; format: string }
  /** 0DH. */
  | { kind: "newLine" }
  /** 0CH. */
  | { kind: "newPage" }
  | { kind: "other"; bytes: string };

export interface Frame {
  /** Display Position character (p. 18), or null when the Message has no Mode Field. */
  position: string | null;
  /** Mode Code (Table 65), or null when the Message has no Mode Field. */
  modeCode: string | null;
  /** Special Specifier after Mode Code "n" (Tables 66, 67). */
  special: string | null;
  segments: Segment[];
}

const ESC = "\x1b";

/** Bytes a Control Code takes, its own byte included (Appendix G). */
function codeLength(data: string, i: number): number {
  switch (data[i]) {
    case "\x05":
    case "\x06":
    case "\x07":
    case "\x08":
    case "\x0b":
    case "\x10":
    case "\x14":
    case "\x1a":
    case "\x1e":
      return 2;
    case "\x1c":
      // "Z"/"Y" + RRGGBB is Alpha 3.0 only; kept whole so it does not leak text.
      return data[i + 1] === "Z" || data[i + 1] === "Y" ? 8 : 2;
    case "\x1d":
      return 3;
    case "\x1f":
      return 15;
    default:
      return 1;
  }
}

function controlSegment(code: string): Segment {
  const arg = code[1] ?? "";
  const on = (c: string | undefined) => c === "1";
  switch (code[0]) {
    case "\x05":
      return { kind: "doubleHeight", on: on(arg) };
    case "\x07":
      return { kind: "flash", on: on(arg) };
    case "\x09":
      return { kind: "noHold" };
    case "\x0b":
      return { kind: "date", format: arg };
    case "\x0c":
      return { kind: "newPage" };
    case "\x0d":
      return { kind: "newLine" };
    case "\x10":
      return { kind: "string", label: arg };
    case "\x11":
      return { kind: "wide", on: false };
    case "\x12":
      return { kind: "wide", on: true };
    case "\x13":
      return { kind: "time" };
    case "\x14":
      return { kind: "picture", label: arg };
    case "\x15":
    case "\x16":
    case "\x17":
    case "\x18":
    case "\x19":
      return { kind: "speed", speed: code.charCodeAt(0) - 0x14 };
    case "\x1a":
      return { kind: "font", code: arg };
    case "\x1c":
      if (code.length === 2) return { kind: "color", code: arg };
      break;
    case "\x1d": {
      const value = on(code[2]);
      if (arg === "0") return { kind: "wide", on: value };
      if (arg === "1") return { kind: "doubleWide", on: value };
      if (arg === "2") return { kind: "doubleHeight", on: value };
      break;
    }
  }
  return { kind: "other", bytes: code };
}

/** Splits Message text (no Mode Fields) into Segments. Also used for STRING File data. */
export function parseSegments(data: string): Segment[] {
  const segments: Segment[] = [];
  let text = "";
  let i = 0;
  while (i < data.length) {
    const code = data.charCodeAt(i);
    if (code >= 0x20) {
      text += data[i];
      i++;
      continue;
    }
    if (text) segments.push({ kind: "text", text });
    text = "";
    const length = codeLength(data, i);
    segments.push(controlSegment(data.slice(i, i + length)));
    i += length;
  }
  if (text) segments.push({ kind: "text", text });
  return segments;
}

/** A TEXT File's content (after the File Label) as Frames, one per Mode Field. */
export function parseMessage(data: string): Frame[] {
  const frames: Frame[] = [];
  const parts = data.split(ESC);
  const lead = parts.shift() ?? "";
  if (lead) {
    frames.push({ position: null, modeCode: null, special: null, segments: parseSegments(lead) });
  }
  for (const part of parts) {
    const position = part[0] ?? null;
    const modeCode = part[1] ?? null;
    const hasSpecial = modeCode === "n";
    const special = hasSpecial ? (part[2] ?? null) : null;
    const body = part.slice(hasSpecial ? 3 : 2);
    frames.push({ position, modeCode, special, segments: parseSegments(body) });
  }
  return frames;
}
