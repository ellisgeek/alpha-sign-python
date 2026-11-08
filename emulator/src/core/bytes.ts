// Byte strings: one JS character per byte (char codes 0-255).

export function bytesToString(bytes: Uint8Array): string {
  let out = "";
  for (const b of bytes) out += String.fromCharCode(b);
  return out;
}

export function stringToBytes(text: string): Uint8Array {
  const out = new Uint8Array(text.length);
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code > 0xff) throw new RangeError(`not a byte string: char ${code} at ${i}`);
    out[i] = code;
  }
  return out;
}

/**
 * The Checksum (p. 12): 16-bit sum of every byte from STX through ETX
 * inclusive, as four uppercase hex digits, most significant first.
 */
export function checksum(fromStxThroughEtx: string): string {
  let sum = 0;
  for (let i = 0; i < fromStxThroughEtx.length; i++) sum += fromStxThroughEtx.charCodeAt(i);
  return (sum & 0xffff).toString(16).toUpperCase().padStart(4, "0");
}
