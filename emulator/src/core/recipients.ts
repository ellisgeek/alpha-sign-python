// Recipients: which Signs a Packet's header addresses (Table 4 items C, D, I; Table 5).
import type { EmulatorModel } from "./model";
import type { SignState } from "./types";

export interface Recipient {
  /** Type Code (Table 5). */
  signType: string;
  /** Two characters, hex digits or "?" (Table 4 item D). */
  address: string;
}

const ADDRESS_CHAR = /^[0-9A-Fa-f?]$/;

/**
 * Parses "Z00" or "a01,r1?,U26" (Table 4 item I, Table 44 p. 63). Returns null
 * when the header is not a comma-separated list of Type Code + two address characters.
 */
export function parseRecipients(header: string): Recipient[] | null {
  const recipients: Recipient[] = [];
  for (const pair of header.split(",")) {
    const [signType, hi, lo] = pair;
    if (pair.length !== 3 || signType === undefined || hi === undefined || lo === undefined) {
      return null;
    }
    if (!ADDRESS_CHAR.test(hi) || !ADDRESS_CHAR.test(lo)) return null;
    recipients.push({ signType, address: hi + lo });
  }
  return recipients;
}

function typeMatches(signType: string, model: EmulatorModel, state: SignState): boolean {
  switch (signType) {
    case "Z": // All signs
    case "?": // All signs
    case "!": // All signs with Visual Verification (the message itself is not modelled)
      return true;
    case "1": // One-line signs
      return model.lines === 1;
    case "2": // Two-line signs
      return model.lines === 2;
    case "z": // All signs with memory configured for 26 files ("A" - "Z")
      return (
        state.memoryConfiguration.length === 26 &&
        state.memoryConfiguration.every((entry, i) => entry.label === String.fromCharCode(65 + i))
      );
    default:
      return signType === model.signType;
  }
}

/** "00" is broadcast; "?" matches any hex digit in its place, so "0?" is 01H-0FH (p. 11). */
function addressMatches(address: string, signAddress: number): boolean {
  if (address === "00") return true;
  const own = signAddress.toString(16).toUpperCase().padStart(2, "0");
  for (let i = 0; i < 2; i++) {
    const ch = address[i]?.toUpperCase();
    if (ch !== "?" && ch !== own[i]) return false;
  }
  return true;
}

/** Type Codes are cumulative: any matching pair addresses the Sign (p. 63 note). */
export function isAddressed(
  recipients: Recipient[],
  model: EmulatorModel,
  state: SignState,
): boolean {
  return recipients.some(
    (r) => typeMatches(r.signType, model, state) && addressMatches(r.address, state.signAddress),
  );
}
