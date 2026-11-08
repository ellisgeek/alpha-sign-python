// Bitmap fonts drawn for this project. They are not copies of any Sign's fonts:
// text widths come close to a real Sign's but are not exact (docs/emulator-spec.md,
// "Fonts"). Each glyph is a list of rows, "1" = lit. Blank columns at the sides
// are trimmed, so characters are proportional, as on the Sign (1EH "0" default).

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

// Seven rows, five columns. Characters 20H-7FH (Appendix G, p. 83): 5EH is a
// cent sign, 7EH a half space, 7FH a block.
const SEVEN_HIGH: Record<string, string> = {
  "!": "00100 00100 00100 00100 00100 00000 00100",
  '"': "01010 01010 01010 00000 00000 00000 00000",
  "#": "01010 01010 11111 01010 11111 01010 01010",
  $: "00100 01111 10100 01110 00101 11110 00100",
  "%": "11000 11001 00010 00100 01000 10011 00011",
  "&": "01100 10010 10100 01000 10101 10010 01101",
  "'": "00100 00100 01000 00000 00000 00000 00000",
  "(": "00010 00100 01000 01000 01000 00100 00010",
  ")": "01000 00100 00010 00010 00010 00100 01000",
  "*": "00000 00100 10101 01110 10101 00100 00000",
  "+": "00000 00100 00100 11111 00100 00100 00000",
  ",": "00000 00000 00000 00000 01100 00100 01000",
  "-": "00000 00000 00000 11111 00000 00000 00000",
  ".": "00000 00000 00000 00000 00000 01100 01100",
  "/": "00000 00001 00010 00100 01000 10000 00000",
  "0": "01110 10001 10011 10101 11001 10001 01110",
  "1": "00100 01100 00100 00100 00100 00100 01110",
  "2": "01110 10001 00001 00010 00100 01000 11111",
  "3": "11111 00010 00100 00010 00001 10001 01110",
  "4": "00010 00110 01010 10010 11111 00010 00010",
  "5": "11111 10000 11110 00001 00001 10001 01110",
  "6": "00110 01000 10000 11110 10001 10001 01110",
  "7": "11111 00001 00010 00100 01000 01000 01000",
  "8": "01110 10001 10001 01110 10001 10001 01110",
  "9": "01110 10001 10001 01111 00001 00010 01100",
  ":": "00000 01100 01100 00000 01100 01100 00000",
  ";": "00000 01100 01100 00000 01100 00100 01000",
  "<": "00010 00100 01000 10000 01000 00100 00010",
  "=": "00000 00000 11111 00000 11111 00000 00000",
  ">": "01000 00100 00010 00001 00010 00100 01000",
  "?": "01110 10001 00001 00010 00100 00000 00100",
  "@": "01110 10001 00001 01101 10101 10101 01110",
  A: "01110 10001 10001 11111 10001 10001 10001",
  B: "11110 10001 10001 11110 10001 10001 11110",
  C: "01110 10001 10000 10000 10000 10001 01110",
  D: "11100 10010 10001 10001 10001 10010 11100",
  E: "11111 10000 10000 11110 10000 10000 11111",
  F: "11111 10000 10000 11110 10000 10000 10000",
  G: "01110 10001 10000 10111 10001 10001 01111",
  H: "10001 10001 10001 11111 10001 10001 10001",
  I: "01110 00100 00100 00100 00100 00100 01110",
  J: "00111 00010 00010 00010 00010 10010 01100",
  K: "10001 10010 10100 11000 10100 10010 10001",
  L: "10000 10000 10000 10000 10000 10000 11111",
  M: "10001 11011 10101 10101 10001 10001 10001",
  N: "10001 10001 11001 10101 10011 10001 10001",
  O: "01110 10001 10001 10001 10001 10001 01110",
  P: "11110 10001 10001 11110 10000 10000 10000",
  Q: "01110 10001 10001 10001 10101 10010 01101",
  R: "11110 10001 10001 11110 10100 10010 10001",
  S: "01111 10000 10000 01110 00001 00001 11110",
  T: "11111 00100 00100 00100 00100 00100 00100",
  U: "10001 10001 10001 10001 10001 10001 01110",
  V: "10001 10001 10001 10001 10001 01010 00100",
  W: "10001 10001 10001 10101 10101 10101 01010",
  X: "10001 10001 01010 00100 01010 10001 10001",
  Y: "10001 10001 10001 01010 00100 00100 00100",
  Z: "11111 00001 00010 00100 01000 10000 11111",
  "[": "01110 01000 01000 01000 01000 01000 01110",
  "\\": "00000 10000 01000 00100 00010 00001 00000",
  "]": "01110 00010 00010 00010 00010 00010 01110",
  "^": "00100 01110 10100 10100 10101 01110 00100",
  _: "00000 00000 00000 00000 00000 00000 11111",
  "`": "01000 00100 00010 00000 00000 00000 00000",
  a: "00000 00000 01110 00001 01111 10001 01111",
  b: "10000 10000 10110 11001 10001 10001 11110",
  c: "00000 00000 01110 10000 10000 10001 01110",
  d: "00001 00001 01101 10011 10001 10001 01111",
  e: "00000 00000 01110 10001 11111 10000 01110",
  f: "00110 01001 01000 11100 01000 01000 01000",
  g: "00000 01111 10001 10001 01111 00001 01110",
  h: "10000 10000 10110 11001 10001 10001 10001",
  i: "00100 00000 01100 00100 00100 00100 01110",
  j: "00010 00000 00110 00010 00010 10010 01100",
  k: "10000 10000 10010 10100 11000 10100 10010",
  l: "01100 00100 00100 00100 00100 00100 01110",
  m: "00000 00000 11010 10101 10101 10001 10001",
  n: "00000 00000 10110 11001 10001 10001 10001",
  o: "00000 00000 01110 10001 10001 10001 01110",
  p: "00000 11110 10001 10001 11110 10000 10000",
  q: "00000 01111 10001 10001 01111 00001 00001",
  r: "00000 00000 10110 11001 10000 10000 10000",
  s: "00000 00000 01111 10000 01110 00001 11110",
  t: "01000 01000 11100 01000 01000 01001 00110",
  u: "00000 00000 10001 10001 10001 10011 01101",
  v: "00000 00000 10001 10001 10001 01010 00100",
  w: "00000 00000 10001 10001 10101 10101 01010",
  x: "00000 00000 10001 01010 00100 01010 10001",
  y: "00000 10001 10001 10001 01111 00001 01110",
  z: "00000 00000 11111 00010 00100 01000 11111",
  "{": "00010 00100 00100 01000 00100 00100 00010",
  "|": "00100 00100 00100 00100 00100 00100 00100",
  "}": "01000 00100 00100 00010 00100 00100 01000",
  "\x7f": "11111 11111 11111 11111 11111 11111 11111",
};

// Five rows, capitals only; small letters are drawn as capitals.
const FIVE_HIGH: Record<string, string> = {
  "!": "1 1 1 0 1",
  '"': "101 101 000 000 000",
  "'": "1 1 0 0 0",
  "(": "01 10 10 10 01",
  ")": "10 01 01 01 10",
  "%": "101 001 010 100 101",
  "+": "000 010 111 010 000",
  ",": "00 00 00 01 10",
  "-": "000 000 111 000 000",
  ".": "0 0 0 0 1",
  "/": "001 001 010 100 100",
  ":": "0 1 0 1 0",
  "=": "000 111 000 111 000",
  "?": "110 001 010 000 010",
  "0": "111 101 101 101 111",
  "1": "010 110 010 010 111",
  "2": "110 001 010 100 111",
  "3": "110 001 010 001 110",
  "4": "101 101 111 001 001",
  "5": "111 100 110 001 110",
  "6": "011 100 111 101 111",
  "7": "111 001 010 010 010",
  "8": "111 101 111 101 111",
  "9": "111 101 111 001 110",
  A: "010 101 111 101 101",
  B: "110 101 110 101 110",
  C: "011 100 100 100 011",
  D: "110 101 101 101 110",
  E: "111 100 110 100 111",
  F: "111 100 110 100 100",
  G: "011 100 101 101 011",
  H: "101 101 111 101 101",
  I: "111 010 010 010 111",
  J: "001 001 001 101 010",
  K: "101 101 110 101 101",
  L: "100 100 100 100 111",
  M: "10001 11011 10101 10001 10001",
  N: "1001 1101 1011 1001 1001",
  O: "010 101 101 101 010",
  P: "110 101 110 100 100",
  Q: "0110 1001 1001 1010 0101",
  R: "110 101 110 101 101",
  S: "011 100 010 001 110",
  T: "111 010 010 010 010",
  U: "101 101 101 101 111",
  V: "101 101 101 101 010",
  W: "10001 10001 10101 10101 01010",
  X: "101 101 010 101 101",
  Y: "101 101 010 010 010",
  Z: "111 001 010 100 111",
  "\x7f": "111 111 111 111 111",
};

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
  table: Record<string, string>,
  height: number,
  spaceWidth: number,
  fallback: (ch: string) => string,
  shape: (g: Glyph) => Glyph = (g) => g,
): Font {
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
        g = art ? shape(parseGlyph(art)) : blank(spaceWidth, height);
      }
      cache.set(ch, g);
      return g;
    },
  };
}

const same = (ch: string) => ch;

export const sevenHigh = makeFont("seven high standard", SEVEN_HIGH, 7, 3, same);
export const fiveHigh = makeFont("five high standard", FIVE_HIGH, 5, 2, (ch) => ch.toUpperCase());
export const tenHigh = makeFont("ten high standard", SEVEN_HIGH, 10, 4, same, (g) =>
  embolden(stretchRows(g, [0, 1, 1, 2, 3, 3, 4, 5, 5, 6])),
);
export const fullHeight = makeFont("full height standard", SEVEN_HIGH, 14, 5, same, (g) =>
  embolden(doubleRows(g)),
);

export const DEFAULT_FONT = sevenHigh;

/**
 * Font for a 1AH Select character set code (Appendix G, p. 82). Fancy, stroke,
 * slim, shadow, and wide sets fall back to the nearest drawn font, or the default.
 */
export function fontForCode(code: string): Font {
  switch (code) {
    case "1":
      return fiveHigh;
    case "6":
      return tenHigh;
    case "8":
    case "9":
      return fullHeight;
    default:
      return DEFAULT_FONT;
  }
}
