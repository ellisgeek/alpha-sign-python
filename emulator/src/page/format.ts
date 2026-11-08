// Text the page prints for bytes and registers. Pure, no DOM.

/** Control characters the manual names (Table 38, p. 58; Table 12, p. 18). */
const NAMES: Record<number, string> = {
  0: "NUL",
  1: "SOH",
  2: "STX",
  3: "ETX",
  4: "EOT",
  27: "ESC",
};

/** A byte string (one char per byte) as the manual prints it: <STX>, <1CH>, ... */
export function printBytes(data: string): string {
  let out = "";
  for (const ch of data) {
    const code = ch.charCodeAt(0);
    if (code >= 0x20 && code < 0x7f) out += ch;
    else out += `<${NAMES[code] ?? `${code.toString(16).toUpperCase().padStart(2, "0")}H`}>`;
  }
  return out;
}

/** Serial Error Status Register bits 5-0 (p. 31), high bit first. */
const REGISTER_BITS: [number, string][] = [
  [0x20, "illegal Command Code, File Label, or SPECIAL FUNCTION"],
  [0x10, "Checksum"],
  [0x08, "serial buffer overflow"],
  [0x04, "serial timeout"],
  [0x02, "bit framing (baud rate)"],
  [0x01, "parity"],
];

/** The errors the register records, by name; empty for the default 40H. */
export function registerErrors(value: number): string[] {
  return REGISTER_BITS.filter(([bit]) => (value & bit) !== 0).map(([, name]) => name);
}
