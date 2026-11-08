// Reads the control channel's JSON description of a Line: the Signs on it,
// their Readings, and the time their clocks start at.
import { DEFAULT_READINGS, findModel, model4120C, type Readings } from "../core/index";

export interface SignSpec {
  model: string;
  signAddress: number;
  readings: Readings;
}

export const DEFAULT_SIGNS: SignSpec[] = [
  { model: model4120C.name, signAddress: 1, readings: DEFAULT_READINGS },
];

export class SetupError extends Error {}

export function parseSigns(value: unknown): SignSpec[] {
  if (!Array.isArray(value) || value.length === 0) {
    throw new SetupError("signs must be a non-empty array");
  }
  return value.map((entry: unknown, i) => {
    if (typeof entry !== "object" || entry === null) {
      throw new SetupError(`signs[${i}] must be an object`);
    }
    const {
      model = model4120C.name,
      signAddress,
      readings = {},
    } = entry as Record<string, unknown>;
    if (typeof model !== "string") throw new SetupError(`signs[${i}].model must be a string`);
    try {
      findModel(model);
    } catch (e) {
      throw new SetupError(`signs[${i}].model: ${(e as Error).message}`);
    }
    // 1-255; 0 is the broadcast address (p. 11).
    if (typeof signAddress !== "number" || !Number.isInteger(signAddress)) {
      throw new SetupError(`signs[${i}].signAddress must be an integer 1-255`);
    }
    if (signAddress < 1 || signAddress > 255) {
      throw new SetupError(`signs[${i}].signAddress must be an integer 1-255`);
    }
    return { model, signAddress, readings: parseReadings(readings, `signs[${i}].readings`) };
  });
}

function parseReadings(value: unknown, where: string): Readings {
  if (typeof value !== "object" || value === null)
    throw new SetupError(`${where} must be an object`);
  const readings: Record<string, unknown> = { ...DEFAULT_READINGS };
  for (const [key, v] of Object.entries(value)) {
    if (!(key in DEFAULT_READINGS)) throw new SetupError(`${where}.${key} is not a Reading`);
    if (typeof v !== typeof readings[key]) {
      throw new SetupError(`${where}.${key} must be a ${typeof readings[key]}`);
    }
    readings[key] = v;
  }
  return readings as unknown as Readings;
}

/**
 * The Sign clocks' start: "YYYY-MM-DDTHH:MM[:SS]" with no zone, read as the
 * Sign's local time. Returns ms whose UTC fields are that time (the core's
 * convention).
 */
export function parseClock(value: unknown): number {
  const pattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,3})?)?$/;
  if (typeof value !== "string" || !pattern.test(value)) {
    throw new SetupError('clock must look like "2026-11-07T12:00:00" (no zone)');
  }
  const ms = Date.parse(`${value}Z`);
  if (Number.isNaN(ms)) throw new SetupError(`clock ${value} is not a date`);
  return ms;
}
