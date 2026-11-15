// Bitmap fonts from Appendix O of the protocol manual (pp. 141-216), extracted by
// docs/reference/extract_fonts.py into manual-glyphs.ts. Each glyph is the manual's
// fixed-width cell with its blank columns trimmed, so characters are proportional, as
// on the Sign (1EH "0" default). Space widths are not in the manual: the cells for 20H
// and 7EH (half space, Appendix G) are blank, so their widths are assumptions.
import { MANUAL_GLYPHS } from "./manual-glyphs";

export interface Glyph {
  width: number;
  height: number;
  /** Row-major, `width * height`, 1 = lit. */
  bits: Uint8Array;
}

export interface Font {
  name: string;
  height: number;
  glyph(ch: string): Glyph;
}

function blank(width: number, height: number): Glyph {
  return { width, height, bits: new Uint8Array(width * height) };
}

function parseGlyph(art: string): Glyph {
  const rows = art.split(" ");
  const height = rows.length;
  const full = Math.max(...rows.map((r) => r.length));
  let left = full;
  let right = -1;
  for (const row of rows) {
    for (let x = 0; x < row.length; x++) {
      if (row[x] === "1") {
        left = Math.min(left, x);
        right = Math.max(right, x);
      }
    }
  }
  if (right < 0) return blank(1, height);
  const width = right - left + 1;
  const bits = new Uint8Array(width * height);
  rows.forEach((row, y) => {
    for (let x = 0; x < width; x++) bits[y * width + x] = row[left + x] === "1" ? 1 : 0;
  });
  return { width, height, bits };
}

/** Each row of `g` repeated per `rowMap` (source row index per output row). */
function stretchRows(g: Glyph, rowMap: number[]): Glyph {
  const out = blank(g.width, rowMap.length);
  rowMap.forEach((src, y) => {
    out.bits.set(g.bits.subarray(src * g.width, (src + 1) * g.width), y * g.width);
  });
  return out;
}

/** A heavier stroke: every lit pixel also lights its right neighbour. */
export function embolden(g: Glyph): Glyph {
  const width = g.width + 1;
  const out = blank(width, g.height);
  for (let y = 0; y < g.height; y++) {
    for (let x = 0; x < g.width; x++) {
      if (g.bits[y * g.width + x]) {
        out.bits[y * width + x] = 1;
        out.bits[y * width + x + 1] = 1;
      }
    }
  }
  return out;
}

/** Every column twice as wide. */
export function doubleColumns(g: Glyph): Glyph {
  const width = g.width * 2;
  const out = blank(width, g.height);
  for (let i = 0; i < out.bits.length; i++) {
    const y = Math.floor(i / width);
    out.bits[i] = g.bits[y * g.width + Math.floor((i % width) / 2)] ?? 0;
  }
  return out;
}

/** Every row twice as tall. */
export function doubleRows(g: Glyph): Glyph {
  return stretchRows(
    g,
    Array.from({ length: g.height * 2 }, (_, y) => Math.floor(y / 2)),
  );
}

function makeFont(
  name: string,
  set: keyof typeof MANUAL_GLYPHS,
  spaceWidth: number,
  fallback: (ch: string) => string = (ch) => ch,
): Font {
  const table = MANUAL_GLYPHS[set] ?? {};
  const height = (table.A ?? "").split(" ").length;
  const cache = new Map<string, Glyph>();
  return {
    name,
    height,
    glyph(ch) {
      const hit = cache.get(ch);
      if (hit) return hit;
      let g: Glyph;
      if (ch === " ") g = blank(spaceWidth, height);
      else if (ch === "~") g = blank(Math.max(1, Math.floor(spaceWidth / 2)), height);
      else {
        const art = table[ch] ?? table[fallback(ch)];
        g = art ? parseGlyph(art) : blank(spaceWidth, height);
      }
      cache.set(ch, g);
      return g;
    },
  };
}

// Appendix O, 7.15.1: the five high set has no lowercase; assumption: the Sign shows
// capitals for it.
export const fiveHigh = makeFont("five high standard", "SS5", 2, (ch) => ch.toUpperCase());
export const sevenHigh = makeFont("seven high standard", "SS7", 3);
export const sevenHighFancy = makeFont("seven high fancy", "SF7", 3);
// Appendix O has one ten high set, 7.15.9 "10-High Fancy (SF10)".
export const tenHigh = makeFont("ten high standard", "SF10", 4);
export const fifteenHigh = makeFont("full height standard", "SS15", 5);
export const fifteenHighFancy = makeFont("full height fancy", "SF15", 5);
export const sixteenHigh = makeFont("full height standard", "SS16", 5);
export const sixteenHighFancy = makeFont("full height fancy", "SF16", 5);

export const DEFAULT_FONT = sevenHigh;

/**
 * Font for a 1AH Select character set code (Appendix G, p. 82) on a display `rows`
 * pixels high. Full height is the 16-high set on a 16-row Sign and the 15-high set
 * otherwise (Table 69 names one "15/16 row" font). The BetaBrite 1036 sets (stroke,
 * shadow, wide) use the default font.
 */
export function fontForCode(code: string, rows = 16): Font {
  switch (code) {
    case "1":
      return fiveHigh;
    case "5":
      return sevenHighFancy;
    case "6":
      return tenHigh;
    case "8":
      return rows >= 16 ? sixteenHighFancy : fifteenHighFancy;
    case "9":
      return rows >= 16 ? sixteenHigh : fifteenHigh;
    default:
      return DEFAULT_FONT;
  }
}
