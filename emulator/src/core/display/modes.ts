// Mode names (Tables 65-67, pp. 89-90) and the Modes the Emulator draws.
// Timings are approximations: the manual gives speeds but no durations
// (docs/emulator-spec.md, "Open questions").
import type { Readings } from "../readings";

/** Table 65, Standard Modes. */
const STANDARD_MODES: Record<string, string> = {
  a: "ROTATE",
  b: "HOLD",
  c: "FLASH",
  e: "ROLL UP",
  f: "ROLL DOWN",
  g: "ROLL LEFT",
  h: "ROLL RIGHT",
  i: "WIPE UP",
  j: "WIPE DOWN",
  k: "WIPE LEFT",
  l: "WIPE RIGHT",
  m: "SCROLL",
  o: "AUTOMODE",
  p: "ROLL IN",
  q: "ROLL OUT",
  r: "WIPE IN",
  s: "WIPE OUT",
  t: "COMPRESSED ROTATE",
  u: "EXPLODE",
  v: "CLOCK",
};

/** Table 66, Special Modes. */
const SPECIAL_MODES: Record<string, string> = {
  "0": "TWINKLE",
  "1": "SPARKLE",
  "2": "SNOW",
  "3": "INTERLOCK",
  "4": "SWITCH",
  "5": "SLIDE",
  "6": "SPRAY",
  "7": "STARBURST",
  C: "CYCLE COLORS",
};

/**
 * Special Graphics: Table 67, plus the Table 66 entries the manual calls
 * animations that show no message (WELCOME, SLOT MACHINE; Table 48 note on "8").
 */
const SPECIAL_GRAPHICS: Record<string, string> = {
  "8": "WELCOME",
  "9": "SLOT MACHINE",
  S: "THANK YOU",
  U: "NO SMOKING",
  V: "DON'T DRINK & DRIVE",
  W: "RUNNING ANIMAL",
  X: "FIREWORKS",
  Y: "TURBO CAR",
  Z: "CHERRY BOMB",
};

/** Modes this Emulator draws. Any other Mode is drawn as HOLD. */
export const DRAWN_MODES = new Set([
  "HOLD",
  "ROTATE",
  "FLASH",
  "ROLL UP",
  "ROLL DOWN",
  "ROLL LEFT",
  "ROLL RIGHT",
  "WIPE UP",
  "WIPE DOWN",
  "WIPE LEFT",
  "WIPE RIGHT",
]);

export interface ModeInfo {
  mode: string;
  drawnAs: string;
  specialGraphic: string | null;
}

/**
 * NEWS FLASH and TRUMPET: Table 66 prints both "A"/"B" and 3AH/3BH; the
 * `newsFlashTrumpetForm` Reading picks which the Sign accepts.
 */
function newsFlashTrumpet(special: string, readings: Readings): string | null {
  const form = readings.newsFlashTrumpetForm;
  const letters = form === "letters" || form === "both";
  const hex = form === "hex" || form === "both";
  if ((letters && special === "A") || (hex && special === ":")) return "NEWS FLASH";
  if ((letters && special === "B") || (hex && special === ";")) return "TRUMPET";
  return null;
}

/**
 * A Frame with no Mode Field is drawn as AUTOMODE. Assumption: p. 18 makes the
 * Mode Field optional but does not say which Mode is used without one.
 */
export function modeInfo(
  modeCode: string | null,
  special: string | null,
  readings: Readings,
): ModeInfo {
  let mode: string;
  let graphic: string | null = null;
  if (modeCode === null) mode = "AUTOMODE";
  else if (modeCode === "n") {
    const s = special ?? "";
    graphic = SPECIAL_GRAPHICS[s] ?? newsFlashTrumpet(s, readings);
    mode = graphic ?? SPECIAL_MODES[s] ?? `SPECIAL ${JSON.stringify(s)}`;
  } else mode = STANDARD_MODES[modeCode] ?? `UNKNOWN MODE ${JSON.stringify(modeCode)}`;
  return { mode, drawnAs: DRAWN_MODES.has(mode) ? mode : "HOLD", specialGraphic: graphic };
}

/** Display Position names (p. 18, Table 12 item D). */
export function positionName(position: string | null): string {
  switch (position) {
    case " ":
      return "middle";
    case '"':
      return "top";
    case "&":
      return "bottom";
    case "0":
      return "fill";
    case "1":
      return "left";
    case "2":
      return "right";
    case null:
      return "fill";
    default:
      return "fill";
  }
}

// --- Timing (approximations, not from the manual) ---

/** Default speed: Speed 4 (p. 37, "18H = Speed 4 (default)"). */
export const DEFAULT_SPEED = 4;

/** ms per pixel of horizontal movement, by speed 1 (slowest) to 5 (fastest). */
const STEP_MS = [0, 50, 40, 30, 20, 12];

export function stepMs(speed: number): number {
  return STEP_MS[speed] ?? 20;
}

/** Vertical movement is slower per pixel: fewer pixels to cross. */
export const VERTICAL_STEP_FACTOR = 4;

/** How long a Frame stays still after its Mode's presentation. */
export const HOLD_MS = 3000;

/** HOLD with No Hold speed (09H) still shows for this long. */
export const MIN_HOLD_MS = 500;

/** FLASH and character flash: on for this long, then off for this long. */
export const FLASH_HALF_PERIOD_MS = 500;
