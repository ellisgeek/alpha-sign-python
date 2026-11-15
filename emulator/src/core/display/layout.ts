// Segments to styled text lines, and text lines to pixels.
import type { Readings } from "../readings";
import type { EmulatedClock, StoredFile, TextRun } from "../types";
import { parseSegments, type Segment } from "./content";
import {
  DEFAULT_FONT,
  doubleColumns,
  doubleRows,
  embolden,
  type Font,
  fontForCode,
  type Glyph,
} from "./fonts";
import { DEFAULT_SPEED } from "./modes";

export interface StyledRun extends TextRun {
  face: Font;
  doubleWide: boolean;
  doubleHeight: boolean;
  /** A called DOTS PICTURE's pixels, drawn in its own colors. */
  pictureBitmap?: Bitmap;
}

/** A Frame's text as lines, with the speed it asked for. */
export interface FrameText {
  /** Pages of lines (NEW_PAGE splits pages when drawn). */
  pages: StyledRun[][][];
  speed: number;
  noHold: boolean;
}

export interface LayoutContext {
  files: Record<string, StoredFile>;
  clock: EmulatedClock;
  readings: Readings;
  /** Number of palette entries; indexes past the end draw as 1 (red-only models). */
  paletteSize: number;
  /** The palette index for each DOTS PICTURE pixel code, if the model folds them. */
  pictureColors?: readonly number[] | undefined;
  /** Display height in pixels; picks the 15- or 16-high full height font. */
  displayRows: number;
  /**
   * Fonts taller than 7 rows are drawn 7 high, as a two-line Sign does in the Top,
   * Bottom, and Fill positions (p. 96, 7.10.3.2.5).
   */
  sevenHighOnly?: boolean;
  /** Rows of a called picture that show; see PICTURE_ROWS. */
  pictureRows?: number;
}

/**
 * The 7-high font a two-line Sign draws in place of a taller one (p. 96: "15 high
 * fancy characters would be replaced by 7 high fancy characters"). Ten high becoming
 * seven high standard is an assumption; the 4000 Series has no ten high font.
 */
const SIZED_DOWN: Readonly<Record<string, string>> = { "6": "3", "8": "5", "9": "3" };

// Color cycles for the multi-color codes. Approximations: the manual names
// them (Appendix G, 1CH) without saying how they look.
const RAINBOW_1 = [1, 7, 8, 2, 3];
const RAINBOW_2 = [3, 2, 8, 7, 1];
const COLOR_MIX = [1, 2, 3];
/**
 * Autocolor and the color before any 1CH code. Assumption: drawn red; the
 * manual does not say what Autocolor picks.
 */
const AUTOCOLOR = 1;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

const pad = (n: number) => String(n).padStart(2, "0");

/** 13H Call Time. The layout is an approximation: the manual does not show it. */
export function timeText(clock: EmulatedClock): string {
  if (clock.timeFormat === "M") return `${pad(clock.hour)}:${pad(clock.minute)}`;
  const hour = clock.hour % 12 === 0 ? 12 : clock.hour % 12;
  return `${hour}:${pad(clock.minute)}${clock.hour < 12 ? "AM" : "PM"}`;
}

/** 0BH Call date, formats "0"-"9" (Appendix G, p. 81). */
export function dateText(clock: EmulatedClock, format: string): string {
  const mm = pad(clock.month);
  const dd = pad(clock.day);
  const yy = pad(clock.year % 100);
  switch (format) {
    case "0":
      return `${mm}/${dd}/${yy}`;
    case "1":
      return `${dd}/${mm}/${yy}`;
    case "2":
      return `${mm}-${dd}-${yy}`;
    case "3":
      return `${dd}-${mm}-${yy}`;
    case "4":
      return `${mm}.${dd}.${yy}`;
    case "5":
      return `${dd}.${mm}.${yy}`;
    case "6":
      return `${mm} ${dd} ${yy}`;
    case "7":
      return `${dd} ${mm} ${yy}`;
    case "8":
      return `${MONTHS[clock.month - 1]}.${dd}, ${clock.year}`;
    case "9":
      return DAYS[clock.dayOfWeek - 1] ?? "";
    default:
      return "";
  }
}

interface Style {
  colorCode: string;
  face: Font;
  wide: boolean;
  doubleWide: boolean;
  doubleHeight: boolean;
  flash: boolean;
}

function colorFor(code: string, charIndex: number): number {
  const cycle = (c: number[]) => c[charIndex % c.length] ?? AUTOCOLOR;
  if (code >= "1" && code <= "8") return Number(code);
  if (code === "9") return cycle(RAINBOW_1);
  if (code === "A") return cycle(RAINBOW_2);
  if (code === "B") return cycle(COLOR_MIX);
  return AUTOCOLOR;
}

/**
 * Lays out a Frame's Segments. Styles start at their defaults in each Frame
 * (assumption: the manual does not say whether they carry over). STRING File
 * references insert the STRING File's current content (p. 37).
 */
export function frameText(segments: Segment[], ctx: LayoutContext): FrameText {
  const drawPages = ctx.readings.newPageDoubleHeight === "drawn";
  const style: Style = {
    colorCode: "C",
    face: DEFAULT_FONT,
    wide: false,
    doubleWide: false,
    doubleHeight: false,
    flash: false,
  };
  const pages: StyledRun[][][] = [[[]]];
  let speed = DEFAULT_SPEED;
  let noHold = false;
  let charIndex = 0;

  const currentLine = (): StyledRun[] => {
    const page = pages[pages.length - 1] as StyledRun[][];
    return page[page.length - 1] as StyledRun[];
  };

  const addText = (text: string) => {
    for (const ch of text) {
      const color = colorFor(style.colorCode, charIndex++);
      const run: StyledRun = {
        text: ch,
        color: color < ctx.paletteSize ? color : 1,
        font: style.face.name,
        wide: style.wide,
        flash: style.flash,
        face: style.face,
        doubleWide: style.doubleWide,
        doubleHeight: style.doubleHeight && drawPages,
      };
      const line = currentLine();
      const last = line[line.length - 1];
      if (last && sameStyle(last, run)) last.text += ch;
      else line.push(run);
    }
  };

  const walk = (list: Segment[], depth: number) => {
    for (const seg of list) {
      switch (seg.kind) {
        case "text":
          addText(seg.text);
          break;
        case "color":
          style.colorCode = seg.code;
          break;
        case "font":
          style.face = fontForCode(
            ctx.sevenHighOnly ? (SIZED_DOWN[seg.code] ?? seg.code) : seg.code,
            ctx.displayRows,
          );
          break;
        case "wide":
          style.wide = seg.on;
          break;
        case "doubleWide":
          style.doubleWide = seg.on;
          break;
        case "doubleHeight":
          style.doubleHeight = seg.on;
          break;
        case "flash":
          style.flash = seg.on;
          break;
        case "speed":
          speed = seg.speed;
          break;
        case "noHold":
          noHold = true;
          break;
        case "time":
          addText(timeText(ctx.clock));
          break;
        case "date":
          addText(dateText(ctx.clock, seg.format));
          break;
        case "string": {
          const file = ctx.files[seg.label];
          // A STRING File cannot call another (p. 37 lists no 10H), so depth stays 1.
          if (file?.type === "STRING" && depth === 0) walk(parseSegments(file.data), depth + 1);
          break;
        }
        case "picture": {
          const bitmap = pictureBitmap(ctx.files[seg.label], ctx.paletteSize, ctx.pictureColors);
          if (bitmap) {
            currentLine().push({
              text: "",
              color: 0,
              font: style.face.name,
              wide: false,
              flash: style.flash,
              face: style.face,
              doubleWide: false,
              doubleHeight: false,
              picture: seg.label,
              pictureBitmap: bitmap,
            });
          }
          break;
        }
        case "newLine":
          (pages[pages.length - 1] as StyledRun[][]).push([]);
          break;
        case "newPage":
          // NEW_PAGE on the 4000 Series: the newPageDoubleHeight Reading (Tables 69, 70).
          if (drawPages) pages.push([[]]);
          break;
        case "other":
          break;
      }
    }
  };
  walk(segments, 0);
  return { pages, speed, noHold };
}

/**
 * A stored SMALL DOTS PICTURE as pixels: Height and Width, then rows of p. 40 codes,
 * each ended by <CR> (see commands/dots-picture.ts). Null if `file` is not a written
 * DOTS PICTURE File. A color past the palette draws as red, as text does.
 */
function pictureBitmap(
  file: StoredFile | undefined,
  paletteSize: number,
  pictureColors?: readonly number[],
): Bitmap | null {
  if (file?.type !== "DOTS" || file.data.length < 4) return null;
  const height = Number.parseInt(file.data.slice(0, 2), 16);
  const width = Number.parseInt(file.data.slice(2, 4), 16);
  if (!(height > 0 && width > 0)) return null;
  const rows = file.data.slice(4).split("\r");
  const out = newBitmap(width, height);
  for (let y = 0; y < height; y++) {
    const row = rows[y] ?? "";
    for (let x = 0; x < width; x++) {
      const code = Number(row[x] ?? "0");
      const folded = Number.isInteger(code) ? (pictureColors?.[code] ?? code) : 1;
      out.colors[y * width + x] = folded < paletteSize ? folded : 1;
    }
  }
  return out;
}

function sameStyle(a: StyledRun, b: StyledRun): boolean {
  if (a.picture !== undefined || b.picture !== undefined) return false;
  return (
    a.color === b.color &&
    a.face === b.face &&
    a.wide === b.wide &&
    a.flash === b.flash &&
    a.doubleWide === b.doubleWide &&
    a.doubleHeight === b.doubleHeight
  );
}

/** The public part of a run. */
export function plainRun(run: StyledRun): TextRun {
  const plain: TextRun = {
    text: run.text,
    color: run.color,
    font: run.font,
    wide: run.wide,
    flash: run.flash,
  };
  if (run.picture !== undefined) plain.picture = run.picture;
  return plain;
}

// --- Pixels ---

export interface Bitmap {
  width: number;
  height: number;
  colors: Uint8Array;
  /** 1 where the pixel belongs to flashing characters (07H). */
  flash: Uint8Array;
}

export function newBitmap(width: number, height: number): Bitmap {
  return {
    width,
    height,
    colors: new Uint8Array(width * height),
    flash: new Uint8Array(width * height),
  };
}

function styledGlyph(run: StyledRun, ch: string) {
  let g = run.face.glyph(ch);
  if (run.wide) g = embolden(g);
  if (run.doubleWide) g = doubleColumns(g);
  if (run.doubleHeight) g = doubleRows(g);
  return g;
}

/** Characters are one column apart. */
const CHAR_GAP = 1;
/** Lines are one row apart. */
const LINE_GAP = 1;
/**
 * In the Fill position a called DOTS PICTURE shows at most its top 8 rows, from the
 * top of its line. On a real 4120C the line was 8 rows, with five and seven high text
 * ending one row above its bottom (docs/hardware-results.md). p. 96 says 7 rows.
 */
export const PICTURE_ROWS = 8;

/**
 * One line drawn on its own, glyphs sitting on a common bottom row. A called picture
 * shows its top `pictureRows` rows.
 */
export function drawLine(line: StyledRun[], pictureRows = PICTURE_ROWS): Bitmap {
  const items = line.flatMap((run): { run: StyledRun; g: Glyph | Bitmap }[] =>
    run.pictureBitmap
      ? [{ run, g: run.pictureBitmap }]
      : [...run.text].map((ch) => ({ run, g: styledGlyph(run, ch) })),
  );
  const text = items.filter(({ g }) => !("colors" in g));
  const textHeight = Math.max(DEFAULT_FONT.height, ...text.map(({ g }) => g.height));
  const pictureHeight = Math.max(
    0,
    ...items.flatMap(({ g }) => ("colors" in g ? [Math.min(g.height, pictureRows)] : [])),
  );
  const height = Math.max(textHeight, pictureHeight);
  const width = Math.max(0, items.reduce((w, { g }) => w + g.width + CHAR_GAP, 0) - CHAR_GAP);
  const out = newBitmap(width, height);
  let x0 = 0;
  for (const { run, g } of items) {
    if ("colors" in g) {
      // A called picture sits at the top of the line, in its own colors, cut to
      // pictureRows.
      const picture = newBitmap(g.width, g.height);
      picture.colors.set(g.colors);
      if (run.flash) picture.flash.fill(1);
      blit(out, picture, x0, 0, pictureRows);
      x0 += g.width + CHAR_GAP;
      continue;
    }
    const y0 = textHeight - g.height;
    for (let y = 0; y < g.height; y++) {
      for (let x = 0; x < g.width; x++) {
        if (!g.bits[y * g.width + x]) continue;
        const i = (y0 + y) * width + x0 + x;
        out.colors[i] = run.color;
        out.flash[i] = run.flash ? 1 : 0;
      }
    }
    x0 += g.width + CHAR_GAP;
  }
  return out;
}

/** Copies the top `rows` of `src` into `dst` at (x, y), clipped; only lit pixels are copied. */
export function blit(dst: Bitmap, src: Bitmap, x: number, y: number, rows = src.height): void {
  for (let sy = 0; sy < Math.min(rows, src.height); sy++) {
    const dy = y + sy;
    if (dy < 0 || dy >= dst.height) continue;
    for (let sx = 0; sx < src.width; sx++) {
      const dx = x + sx;
      if (dx < 0 || dx >= dst.width) continue;
      const s = sy * src.width + sx;
      const color = src.colors[s] ?? 0;
      if (!color) continue;
      const d = dy * dst.width + dx;
      dst.colors[d] = color;
      dst.flash[d] = src.flash[s] ?? 0;
    }
  }
}

/** Splits lines into pages that fit `height` rows; every page has at least one line. */
export function paginate<T extends { height: number }>(lines: T[], height: number): T[][] {
  const pages: T[][] = [];
  let page: T[] = [];
  let used = 0;
  for (const line of lines) {
    const need = (page.length ? LINE_GAP : 0) + line.height;
    if (page.length && used + need > height) {
      pages.push(page);
      page = [];
      used = 0;
    }
    used += (page.length ? LINE_GAP : 0) + line.height;
    page.push(line);
  }
  if (page.length) pages.push(page);
  return pages;
}

function blockHeight(lines: Bitmap[]): number {
  return lines.reduce((h, l) => h + l.height, 0) + LINE_GAP * Math.max(0, lines.length - 1);
}

/** A page centered in a `width` x `height` area, each line centered across. */
export function drawCentered(lines: Bitmap[], width: number, height: number): Bitmap {
  const out = newBitmap(width, height);
  let y = Math.floor((height - blockHeight(lines)) / 2);
  for (const line of lines) {
    const x = line.width > width ? 0 : Math.floor((width - line.width) / 2);
    blit(out, line, x, y);
    y += line.height + LINE_GAP;
  }
  return out;
}

/** A page as one strip for ROTATE: lines left-aligned, as wide as the widest. */
export function drawStrip(lines: Bitmap[], height: number): Bitmap {
  const width = Math.max(0, ...lines.map((l) => l.width));
  const out = newBitmap(width, height);
  let y = Math.floor((height - blockHeight(lines)) / 2);
  for (const line of lines) {
    blit(out, line, 0, y);
    y += line.height + LINE_GAP;
  }
  return out;
}
