// What the display shows at a moment: the Run Sequence and the Priority TEXT File
// pick the TEXT Files (pp. 20, 23), each Frame is laid out at its Display
// Position (p. 18) and drawn in its Mode (Table 65). A pure function of the state
// and the time: the display restarts at `displayRestartedAtMs` (a TEXT write blanks
// it, p. 17) and runs from there; a STRING write changes content without a
// restart, so it does not blank (p. 37).
import { clockAt } from "../clock";
import type { EmulatorModel } from "../model";
import { DEFAULT_READINGS, type Readings } from "../readings";
import type { DisplayState, SignState, StoredFile } from "../types";
import { parseMessage } from "./content";
import { DEFAULT_FONT } from "./fonts";
import {
  type Bitmap,
  blit,
  drawCentered,
  drawLine,
  drawStrip,
  frameText,
  type LayoutContext,
  newBitmap,
  paginate,
  plainRun,
  type StyledRun,
} from "./layout";
import {
  FLASH_HALF_PERIOD_MS,
  HOLD_MS,
  MIN_HOLD_MS,
  type ModeInfo,
  modeInfo,
  positionName,
  stepMs,
  VERTICAL_STEP_FACTOR,
} from "./modes";

/** One Frame page on the timeline. */
interface Step {
  fileLabel: string;
  frameIndex: number;
  info: ModeInfo;
  position: string;
  /** Display rows the Frame uses: [top, bottom). */
  rowStart: number;
  rowEnd: number;
  lines: StyledRun[][];
  /** The page drawn still, region-sized. */
  content: Bitmap;
  /** ROTATE only: the page as one strip; null for a trailing ROTATE with no text. */
  strip: Bitmap | null;
  stepMs: number;
  transitionMs: number;
  durationMs: number;
}

/**
 * Rows a Display Position uses (p. 18, Table 12 item D): Top uses all lines minus
 * one, Bottom the rest; Middle and Fill use the whole display. On a one-line Sign
 * the Display Position is irrelevant.
 */
function regionRows(position: string, model: EmulatorModel): [number, number] {
  if (model.lines <= 1) return [0, model.rows];
  const split = Math.floor(model.rows / model.lines) * (model.lines - 1);
  if (position === "top") return [0, split];
  if (position === "bottom") return [split, model.rows];
  return [0, model.rows];
}

/** TEXT Files in the order they run. Run Times and Run Days are not modelled yet. */
function runningFiles(state: SignState): StoredFile[] {
  // The Priority TEXT File runs by itself until it is written empty (p. 20).
  if (state.priority && state.priority.data !== "") return [state.priority];
  const isText = (label: string) => state.files[label]?.type === "TEXT";
  // An empty Run Sequence runs every TEXT File in Label order. Assumption: the
  // manual does not give the power-up Run Sequence.
  let labels = state.runSequence.labels.length
    ? state.runSequence.labels.filter(isText)
    : Object.keys(state.files).filter(isText).sort();
  const start = state.displayStartLabel === null ? -1 : labels.indexOf(state.displayStartLabel);
  if (start > 0) labels = [...labels.slice(start), ...labels.slice(0, start)];
  return labels.map((label) => state.files[label] as StoredFile);
}

function buildSteps(state: SignState, model: EmulatorModel, ctx: LayoutContext): Step[] {
  const steps: Step[] = [];
  for (const file of runningFiles(state)) {
    parseMessage(file.data).forEach((frame, frameIndex) => {
      const info = modeInfo(frame.modeCode, frame.special, ctx.readings);
      const position = positionName(frame.position);
      const [rowStart, rowEnd] = regionRows(position, model);
      const height = rowEnd - rowStart;
      const base = { fileLabel: file.label, frameIndex, info, position, rowStart, rowEnd };
      if (info.specialGraphic) {
        // A placeholder: the Special Graphic's name, held (no animation yet).
        const color = model.palette.length > 3 ? 3 : 1;
        const label = drawLine([
          {
            text: info.specialGraphic,
            color,
            font: DEFAULT_FONT.name,
            wide: false,
            flash: false,
            face: DEFAULT_FONT,
            doubleWide: false,
            doubleHeight: false,
          },
        ]);
        steps.push({
          ...base,
          lines: [],
          content: drawCentered([label], model.columns, height),
          strip: null,
          stepMs: 0,
          transitionMs: 0,
          durationMs: HOLD_MS,
        });
        return;
      }
      const text = frameText(frame.segments, ctx);
      const step = stepMs(text.speed);
      const holdMs = text.noHold ? 0 : HOLD_MS;
      for (const page of text.pages) {
        const drawn = page.map((runs) => ({ runs, bitmap: drawLine(runs), height: 0 }));
        for (const d of drawn) d.height = d.bitmap.height;
        for (const sub of paginate(drawn, height)) {
          const bitmaps = sub.map((d) => d.bitmap);
          const hasText = sub.some((d) => d.runs.length > 0);
          const content = drawCentered(bitmaps, model.columns, height);
          const strip = hasText ? drawStrip(bitmaps, height) : null;
          let transitionMs = 0;
          let durationMs: number;
          switch (info.drawnAs) {
            case "ROTATE":
              transitionMs = (model.columns + (strip?.width ?? 0)) * step;
              durationMs = transitionMs;
              break;
            case "ROLL UP":
            case "ROLL DOWN":
            case "WIPE UP":
            case "WIPE DOWN":
              transitionMs = height * step * VERTICAL_STEP_FACTOR;
              durationMs = transitionMs + holdMs;
              break;
            case "ROLL LEFT":
            case "ROLL RIGHT":
            case "WIPE LEFT":
            case "WIPE RIGHT":
              transitionMs = model.columns * step;
              durationMs = transitionMs + holdMs;
              break;
            default:
              durationMs = text.noHold ? MIN_HOLD_MS : HOLD_MS;
          }
          steps.push({
            ...base,
            lines: hasText ? sub.map((d) => d.runs) : [],
            content,
            strip,
            stepMs: step,
            transitionMs,
            durationMs,
          });
        }
      }
    });
  }
  return steps;
}

function regionOf(screen: Bitmap, step: Step): Bitmap {
  const out = newBitmap(screen.width, step.rowEnd - step.rowStart);
  const from = step.rowStart * screen.width;
  out.colors.set(screen.colors.subarray(from, from + out.colors.length));
  out.flash.set(screen.flash.subarray(from, from + out.flash.length));
  return out;
}

function putRegion(screen: Bitmap, step: Step, region: Bitmap): void {
  screen.colors.set(region.colors, step.rowStart * screen.width);
  screen.flash.set(region.flash, step.rowStart * screen.width);
}

/** What a step leaves on its rows when it ends. */
function finalRegion(step: Step, prev: Bitmap): Bitmap {
  if (step.info.drawnAs === "ROTATE") return newBitmap(prev.width, prev.height);
  return step.content;
}

/** Copies rows (or columns) of `src` where `take(x, y)` holds. */
function mask(dst: Bitmap, src: Bitmap, take: (x: number, y: number) => boolean): void {
  for (let y = 0; y < dst.height; y++) {
    for (let x = 0; x < dst.width; x++) {
      if (!take(x, y)) continue;
      const i = y * dst.width + x;
      dst.colors[i] = src.colors[i] ?? 0;
      dst.flash[i] = src.flash[i] ?? 0;
    }
  }
}

/** The step's rows `t` ms after it started. */
function drawStep(step: Step, prev: Bitmap, t: number): Bitmap {
  const { width: w, height: h } = prev;
  const out = newBitmap(w, h);
  const moved = (pixels: number, perPixelMs: number) =>
    Math.min(pixels, Math.floor(t / perPixelMs));
  const v = step.stepMs * VERTICAL_STEP_FACTOR;
  const flashOff = Math.floor(t / FLASH_HALF_PERIOD_MS) % 2 === 1;
  switch (step.info.drawnAs) {
    case "ROTATE": {
      const k = Math.floor(t / step.stepMs);
      if (step.strip) blit(out, step.strip, w - k, 0);
      else blit(out, prev, -k, 0); // trailing ROTATE moves the old text off (Table 48)
      break;
    }
    case "FLASH":
      if (!flashOff) blit(out, step.content, 0, 0);
      break;
    case "ROLL UP": {
      const k = moved(h, v);
      blit(out, prev, 0, -k);
      blit(out, step.content, 0, h - k);
      break;
    }
    case "ROLL DOWN": {
      const k = moved(h, v);
      blit(out, prev, 0, k);
      blit(out, step.content, 0, k - h);
      break;
    }
    case "ROLL LEFT": {
      const k = moved(w, step.stepMs);
      blit(out, prev, -k, 0);
      blit(out, step.content, w - k, 0);
      break;
    }
    case "ROLL RIGHT": {
      const k = moved(w, step.stepMs);
      blit(out, prev, k, 0);
      blit(out, step.content, k - w, 0);
      break;
    }
    case "WIPE UP": {
      const k = moved(h, v);
      blit(out, prev, 0, 0);
      mask(out, step.content, (_x, y) => y >= h - k);
      break;
    }
    case "WIPE DOWN": {
      const k = moved(h, v);
      blit(out, prev, 0, 0);
      mask(out, step.content, (_x, y) => y < k);
      break;
    }
    case "WIPE LEFT": {
      const k = moved(w, step.stepMs);
      blit(out, prev, 0, 0);
      mask(out, step.content, (x) => x >= w - k);
      break;
    }
    case "WIPE RIGHT": {
      const k = moved(w, step.stepMs);
      blit(out, prev, 0, 0);
      mask(out, step.content, (x) => x < k);
      break;
    }
    default:
      blit(out, step.content, 0, 0);
  }
  // Character flash (07H): flashing pixels go dark every other half period.
  if (flashOff) {
    for (let i = 0; i < out.colors.length; i++) if (out.flash[i]) out.colors[i] = 0;
  }
  return out;
}

function blankDisplay(model: EmulatorModel): DisplayState {
  return {
    fileLabel: null,
    frameIndex: 0,
    mode: "none",
    drawnAs: "none",
    position: "none",
    specialGraphic: null,
    lines: [],
    pixels: {
      width: model.columns,
      height: model.rows,
      colors: new Uint8Array(model.columns * model.rows),
    },
  };
}

export function buildDisplay(
  state: SignState,
  model: EmulatorModel,
  nowMs: number,
  readings: Readings = DEFAULT_READINGS,
): DisplayState {
  const ctx: LayoutContext = {
    files: state.files,
    clock: clockAt(state.clock, nowMs),
    readings,
    paletteSize: model.palette.length,
  };
  const steps = buildSteps(state, model, ctx);
  const cycleMs = steps.reduce((sum, s) => sum + s.durationMs, 0);
  if (cycleMs <= 0) return blankDisplay(model);

  const elapsed = Math.max(0, nowMs - state.displayRestartedAtMs);
  const cycle = Math.floor(elapsed / cycleMs);
  let t = elapsed - cycle * cycleMs;

  const screen = newBitmap(model.columns, model.rows);
  const finish = (step: Step) => putRegion(screen, step, finalRegion(step, regionOf(screen, step)));
  // After the first cycle, every cycle starts from what the last one left.
  if (cycle > 0) for (const step of steps) finish(step);

  for (const step of steps) {
    if (t >= step.durationMs) {
      finish(step);
      t -= step.durationMs;
      continue;
    }
    putRegion(screen, step, drawStep(step, regionOf(screen, step), t));
    return {
      fileLabel: step.fileLabel,
      frameIndex: step.frameIndex,
      mode: step.info.mode,
      drawnAs: step.info.drawnAs,
      position: step.position,
      specialGraphic: step.info.specialGraphic,
      lines: step.lines.map((line) => line.map(plainRun)),
      pixels: { width: screen.width, height: screen.height, colors: screen.colors },
    };
  }
  return blankDisplay(model);
}
