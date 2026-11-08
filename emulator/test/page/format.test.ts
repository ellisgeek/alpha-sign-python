// How the page prints bytes and the Serial Error Status Register.
import { describe, expect, it } from "vitest";
import { printBytes, registerErrors } from "../../src/page/format";

describe("printBytes", () => {
  it("spells control characters the way the manual prints them (Table 38, p. 58)", () => {
    expect(printBytes("\x00\x00\x01Z00\x02AAHELLO\x04")).toBe(
      "<NUL><NUL><SOH>Z00<STX>AAHELLO<EOT>",
    );
  });

  it("prints other bytes outside printable ASCII as hex with an H, as the manual does", () => {
    // <ESC> starts the Mode Field (Table 12, p. 18); 1CH selects a color (p. 37).
    expect(printBytes("\x1b0a\x1c1\xff")).toBe("<ESC>0a<1CH>1<FFH>");
  });
});

describe("registerErrors", () => {
  it("is empty for the default value 40H (p. 31)", () => {
    expect(registerErrors(0x40)).toEqual([]);
  });

  it("names each bit that is set, high bit first (p. 31)", () => {
    expect(registerErrors(0x40 | 0x20 | 0x10 | 0x01)).toEqual([
      "illegal Command Code, File Label, or SPECIAL FUNCTION",
      "Checksum",
      "parity",
    ]);
    expect(registerErrors(0x40 | 0x08 | 0x04 | 0x02)).toEqual([
      "serial buffer overflow",
      "serial timeout",
      "bit framing (baud rate)",
    ]);
  });
});
