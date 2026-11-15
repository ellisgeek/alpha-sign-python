// Network Query ("F-", p. 32) and Signs answering on one Line.
import { describe, expect, it } from "vitest";
import { createLine, model4120C, type Readings } from "../../src/core";
import { bytes, START_CLOCK_MS, SYNC, text } from "./helpers";

// Answers captured from a real 4120C (firmware 10184403 rev O (1206)) on 2026-11-15,
// at Sign Address 1 and then 2 (tests/test_discovery.py in the library).
const NULS = "\x00".repeat(26);
const FOUND_AT_01 = `${NULS}\x01000\x02E-a01@\x030179\x04`;
const FOUND_AT_02 = `${NULS}\x01000\x02E-a02@\x03017A\x04`;

// The library's discovery Packet: Read SPECIAL FUNCTION "-" to every Sign (p. 32).
const QUERY = `${SYNC}\x01Z00\x02F-\x030078\x04`;

function lineOf(addresses: number[], readings: Partial<Readings> = {}) {
  return createLine(
    addresses.map((signAddress) => ({ model: model4120C, signAddress, readings })),
    { startClockMs: START_CLOCK_MS },
  );
}

describe("Network Query (p. 32)", () => {
  it("answers as a real 4120C did, 1 s + 0.5 s x its Sign Address after the query", () => {
    for (const [address, answer] of [
      [1, FOUND_AT_01],
      [2, FOUND_AT_02],
    ] as const) {
      const line = lineOf([address]);
      line.receive(bytes(QUERY), 0);
      const due = 1000 + 500 * address;
      expect(line.advance(due - 1)).toEqual([]);
      expect(line.advance(due).map((o) => ({ text: text(o.bytes), atMs: o.atMs }))).toEqual([
        { text: answer, atMs: due },
      ]);
    }
  });

  it("reports the Serial Error Status Register in Z (p. 32)", () => {
    const line = lineOf([1]);
    line.receive(bytes(`${SYNC}\x01Z00\x02AAHI\x030000\x04`), 0); // bad Checksum: 10H (p. 31)
    line.receive(bytes(QUERY), 1000);
    const [answer] = line.advance(5000);
    expect(text(answer?.bytes ?? new Uint8Array())).toContain("E-a01P"); // 40H + 10H = "P"
  });

  it("answers with only the UAAZ data with Reading networkQueryFraming = bare", () => {
    const line = lineOf([1], { networkQueryFraming: "bare" });
    line.receive(bytes(QUERY), 0);
    expect(line.advance(5000).map((o) => text(o.bytes))).toEqual(["a01@"]);
  });
});

describe("Signs answering on one Line", () => {
  it("lets Signs at different Sign Addresses answer in turn", () => {
    const line = lineOf([2, 1]);
    line.receive(bytes(QUERY), 0);
    expect(line.advance(5000).map((o) => ({ text: text(o.bytes), atMs: o.atMs }))).toEqual([
      { text: FOUND_AT_01, atMs: 1500 },
      { text: FOUND_AT_02, atMs: 2000 },
    ]);
  });

  it("sends one answer when two Signs at one Sign Address answer at once (p. 32)", () => {
    const line = lineOf([1, 1]);
    line.receive(bytes(QUERY), 0);
    const out = line.advance(5000);
    expect(out).toHaveLength(1);
    // Identical answers sent together combine into themselves.
    expect(text(out[0]?.bytes ?? new Uint8Array())).toBe(FOUND_AT_01);
  });

  it("garbles answers that overlap: a 0 bit wins, as on an idle-high line", () => {
    // A stand-in read each Sign answers at once with its own Sign Address.
    const line = createLine(
      [1, 2].map((signAddress) => ({ model: model4120C, signAddress })),
      {
        startClockMs: START_CLOCK_MS,
        commands: { B: (_cmd, ctx) => ctx.respond(`AC${ctx.state.signAddress}`) },
      },
    );
    line.receive(bytes(`${SYNC}\x01Z00\x02BC\x04`), 0);
    const out = line.advance(1000);
    expect(out).toHaveLength(1);
    const garbled = text(out[0]?.bytes ?? new Uint8Array());
    // "1" (31H) AND "2" (32H) = "0" (30H). The Checksums are 00BA and 00BB (02H + 41H +
    // 43H + 31H or 32H + 03H), and "A" (41H) AND "B" (42H) = "@" (40H).
    expect(garbled).toBe(`${NULS}\x01000\x02AC0\x0300B@\x04`);
  });
});

describe("Response leading NULs", () => {
  it("sends 26 NULs before SOH, as every capture from a real 4120C shows", () => {
    const line = lineOf([1]);
    line.receive(bytes(`${SYNC}\x01Z00\x02F*\x04`), 0);
    const [reply] = line.advance(1000);
    // Captured Serial Error Status Response (tests/test_sign.py in the library).
    expect(text(reply?.bytes ?? new Uint8Array())).toBe(`${NULS}\x01000\x02E*@\x0300B4\x04`);
  });
});
