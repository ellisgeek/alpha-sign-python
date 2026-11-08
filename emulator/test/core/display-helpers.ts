// Builds Sign states for display tests directly, without Commands.
import type { DisplayState, SignState, StoredFile } from "../../src/core";
import { powerUpState } from "../../src/core/state";
import { START_CLOCK_MS } from "./helpers";

/** Line ms the display restarts at in these tests. */
export const RESTART_MS = 10_000;

export interface StateOptions {
  text?: Record<string, string>;
  strings?: Record<string, string>;
  runSequence?: string[];
  priority?: string;
  startLabel?: string;
}

/** A powered-up Sign holding the given TEXT and STRING Files, restarted at RESTART_MS. */
export function stateWith(options: StateOptions): SignState {
  const state = powerUpState(0, START_CLOCK_MS, 0);
  state.files = {};
  const add = (type: StoredFile["type"], files: Record<string, string> = {}) => {
    for (const [label, data] of Object.entries(files)) state.files[label] = { label, type, data };
  };
  add("TEXT", options.text);
  add("STRING", options.strings);
  if (options.runSequence) state.runSequence.labels = options.runSequence;
  if (options.priority !== undefined) {
    state.priority = { label: "0", type: "TEXT", data: options.priority };
  }
  state.displayRestartedAtMs = RESTART_MS;
  state.displayStartLabel = options.startLabel ?? null;
  return state;
}

const ART = ".RGArgboy";

/** Pixels as text art, one character per pixel: "." off, then p. 40 codes 1-8. */
export function art(pixels: { width: number; height: number; colors: Uint8Array }): string {
  const rows: string[] = [];
  for (let y = 0; y < pixels.height; y++) {
    let row = "";
    for (let x = 0; x < pixels.width; x++) row += ART[pixels.colors[y * pixels.width + x] ?? 0];
    rows.push(row);
  }
  return `${rows.join("\n")}\n`;
}

/** Line text of a display, one string per line. */
export function lineTexts(display: { lines: { text: string }[][] }): string[] {
  return display.lines.map((line) => line.map((run) => run.text).join(""));
}

export interface Shown {
  atMs: number;
  display: DisplayState;
}

/**
 * Every distinct Frame page shown from RESTART_MS for `forMs`, sampled each
 * 10 ms: the order Frames appear in, without depending on Mode timings.
 */
export function sequence(show: (atMs: number) => DisplayState, forMs: number): Shown[] {
  const seen: Shown[] = [];
  let key = "";
  for (let t = RESTART_MS; t <= RESTART_MS + forMs; t += 10) {
    const display = show(t);
    const next = JSON.stringify([display.fileLabel, display.frameIndex, display.lines]);
    if (next !== key) seen.push({ atMs: t, display });
    key = next;
  }
  return seen;
}
