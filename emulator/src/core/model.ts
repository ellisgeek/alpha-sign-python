// A Sign Model is data, never a subclass (docs/emulator-spec.md, "Sign Models").
// Entered from the manual (Tables 3 and 5) and the Alpha 4000 Series brochure,
// not from any other program's data.

/** One palette entry: what a pixel of this index looks like. Index 0 is off. */
export interface PaletteColor {
  name: string;
  /** Approximate on-screen color, "#rrggbb". Not a measured LED color. */
  rgb: string;
}

export type ProtocolVersion = "EZKEY II" | "Alpha 1.0" | "Alpha 2.0" | "Alpha 3.0";

export interface EmulatorModel {
  name: string;
  /** Type Code the Sign answers to (Table 5, p. 10). */
  signType: string;
  /** Display size in pixels. */
  columns: number;
  rows: number;
  /** Text lines the Sign shows; decides the "1" / "2" group Type Codes (Table 5). */
  lines: number;
  /**
   * Palette indexed by the DOTS PICTURE pixel codes (p. 40): 0 off, 1 red,
   * 2 green, 3 amber, 4 dim red, 5 dim green, 6 brown, 7 orange, 8 yellow.
   * A red-only model lists only the colors it can show.
   */
  palette: PaletteColor[];
  /** Memory Pool size in bytes. */
  memoryBytes: number;
  maxMessages: number;
  protocolVersions: ProtocolVersion[];
  /** General Information firmware fields (p. 29): FFFFFFFF, f, MmYy. */
  firmware: { name: string; revision: string; date: string };
}

const OFF: PaletteColor = { name: "off", rgb: "#1a0d0a" };

/** Tricolor palette (p. 40 pixel codes "0"-"8"). RGB values are approximations. */
export const TRICOLOR_PALETTE: PaletteColor[] = [
  OFF,
  { name: "red", rgb: "#ff2a1a" },
  { name: "green", rgb: "#2aff3a" },
  { name: "amber", rgb: "#ffb000" },
  { name: "dim red", rgb: "#8a160e" },
  { name: "dim green", rgb: "#168a20" },
  { name: "brown", rgb: "#8a5a10" },
  { name: "orange", rgb: "#ff7010" },
  { name: "yellow", rgb: "#ffe830" },
];

/** Red-only palette for "R" models (Table 3 note 4, p. 8: "R" = red LEDs). */
export const RED_PALETTE: PaletteColor[] = [OFF, { name: "red", rgb: "#ff2a1a" }];

/**
 * Alpha 4120C.
 * - Type Code "a" (Table 5, p. 10).
 * - 120 x 16 pixels, 28,000 bytes display memory, 81 messages, tricolor,
 *   one- or two-line messages (brochure, p. 2 "4120C/R" column and p. 1).
 * - EZKEY II and Alpha 1.0, not 2.0 or 3.0 (Table 3, p. 8, "4000 Series").
 * - Firmware fields are invented for the Emulator: no 4120C General Information
 *   capture exists yet (docs/hardware-results.md). PROVISIONAL.
 */
export const model4120C: EmulatorModel = {
  name: "4120C",
  signType: "a",
  columns: 120,
  rows: 16,
  lines: 2,
  palette: TRICOLOR_PALETTE,
  memoryBytes: 28000,
  maxMessages: 81,
  protocolVersions: ["EZKEY II", "Alpha 1.0"],
  firmware: { name: "EMU4120C", revision: "A", date: "1126" },
};

/** Sign Models the hosts and the page can name. Add a model here as data. */
export const MODELS: Readonly<Record<string, EmulatorModel>> = { [model4120C.name]: model4120C };

/** The Sign Model with this name; throws an Error naming the known ones if there is none. */
export function findModel(name: string): EmulatorModel {
  const model = Object.hasOwn(MODELS, name) ? MODELS[name] : undefined;
  if (!model) {
    const known = Object.keys(MODELS).join(", ");
    throw new Error(`unknown Sign Model ${JSON.stringify(name)}; known: ${known}`);
  }
  return model;
}
