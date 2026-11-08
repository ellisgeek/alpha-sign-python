// Write and read TEXT File (pp. 17-20), with the Appendix F Packets.
import { describe, expect, it } from "vitest";
import { createLine, model4120C } from "../../src/core";
import { bytes, oneSign, START_CLOCK_MS, SYNC } from "./helpers";

describe("Write TEXT File", () => {
  it("writes TEXT File A at power-up with Table 38 (p. 58, and p. 17: File A at power-up)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02AAHELLO\x04`);
    expect(sign.snapshot().files.A).toEqual({ label: "A", type: "TEXT", data: "HELLO" });
  });
});

describe("Appendix F Packets that write TEXT File A", () => {
  it("accepts the Table 41 Packet with its Checksum 01FB (p. 60)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02AAHELLO\x0301FB\x04`);
    expect(sign.snapshot().files.A?.data).toBe("HELLO");
  });

  for (const [table, page, packet] of [
    ["Table 42", "p. 61", ["\x02E'S\x0300C4", "\x02AAHELLO\x0301FB\x04"]],
    ["Table 43", "p. 62", ["\x02E'S\x03", "\x02AAHELLO\x03\x04"]],
  ] as const) {
    it(`runs both nested Commands of ${table} (${page}) with 100 ms after each STX`, () => {
      const line = createLine([{ model: model4120C, signAddress: 1 }], {
        startClockMs: START_CLOCK_MS,
      });
      // Set 24-hour time first, so Set Time Format "S" visibly changes it.
      line.receive(bytes(`${SYNC}\x01Z00\x02E'M\x04`), 0);
      line.receive(bytes(`${SYNC}\x01Z00`), 1000);
      // Each STX, then the 100 ms of silence p. 11 asks for, then the rest.
      let t = 1010;
      for (const part of packet) {
        line.receive(bytes("\x02"), t);
        line.receive(bytes(part.slice(1)), t + 100);
        t += 200;
      }
      line.advance(t);
      const snap = line.signs()[0]?.snapshot();
      expect(snap?.files.A?.data).toBe("HELLO");
      expect(snap?.clock.timeFormat).toBe("S");
      expect(snap?.ignored).toEqual([]);
    });
  }

  it("is heard by a 4120C at address 01 in Table 44's list of pairs (p. 63)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01a01,r1?,U26\x02AAHELLO\x04`);
    expect(sign.snapshot().files.A?.data).toBe("HELLO");
  });
});

describe("Read TEXT File", () => {
  it("answers Table 45 with the Table 46 bytes (p. 64)", () => {
    const { send } = oneSign();
    send(`${SYNC}\x01Z00\x02E$CAU0100FF00\x04`);
    send(`${SYNC}\x01Z00\x02ACFILE C\x04`);
    // Table 45: <SOH>"Z00"<STX>"BC"<EOT>; Table 46 printed below.
    expect(send(`${SYNC}\x01Z00\x02BC\x04`)).toEqual([
      `${"\x00".repeat(20)}\x01000\x02ACFILE C\x03020C\x04`,
    ]);
  });

  it("reads back Control Codes it does not model unchanged (spec story 32)", () => {
    const { send } = oneSign();
    // A Mode Field (Table 12), a character set (<SUB>"9"), then 7FH, 1FH, and 10H.
    const content = "\x1b a\x1a9\x7f\x1fHI\x10";
    send(`${SYNC}\x01Z00\x02AA${content}\x04`);
    const [reply] = send(`${SYNC}\x01Z00\x02BA\x04`);
    // Table 14: twenty NULs, SOH, "000", STX, "A", File Label, the content, ETX.
    expect(reply?.slice(0, 26)).toBe(`${"\x00".repeat(20)}\x01000\x02A`);
    expect(reply?.slice(26, 27 + content.length)).toBe(`A${content}`);
    expect(reply?.charAt(27 + content.length)).toBe("\x03");
  });

  it("sends nothing for a File that is not configured", () => {
    const { sign, send } = oneSign();
    expect(send(`${SYNC}\x01Z00\x02BQ\x04`)).toEqual([]);
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["unconfigured-file"]);
  });
});

describe("TEXT File writes the Memory Configuration does not allow", () => {
  it("ignores a write to a File that is not configured (p. 21; spec story 18)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02AQHELLO\x04`);
    const snap = sign.snapshot();
    expect(snap.files.Q).toBeUndefined();
    expect(snap.ignored.map((i) => i.reason)).toEqual(["unconfigured-file"]);
    expect(snap.serialErrors).toBe(0x40);
  });

  it("ignores a write to a STRING File with the TEXT Command", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02E$AAU0100FF00lBL000A0000\x04`);
    send(`${SYNC}\x01Z00\x02AlHELLO\x04`);
    expect(sign.snapshot().files.l?.data).toBe("");
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["wrong-file-type"]);
  });

  it("sets register bit 5 for a File Label outside 20H-7EH (Appendix A, p. 50; p. 31)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02A\x7fHELLO\x04`);
    expect(sign.snapshot().serialErrors).toBe(0x60);
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["illegal-file-label"]);
  });

  // A 4-byte TEXT File "B" ("0004", p. 21) and a 6-byte write.
  it("ignores a write larger than its File by default (Reading oversizedWrite)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02E$BAU0004FF00\x04`);
    send(`${SYNC}\x01Z00\x02ABHELLO!\x04`);
    expect(sign.snapshot().files.B?.data).toBe("");
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["oversized-write"]);
  });

  it("keeps the first bytes with Reading oversizedWrite = truncate", () => {
    const { sign, send } = oneSign({ oversizedWrite: "truncate" });
    send(`${SYNC}\x01Z00\x02E$BAU0004FF00\x04`);
    send(`${SYNC}\x01Z00\x02ABHELLO!\x04`);
    expect(sign.snapshot().files.B?.data).toBe("HELL");
    expect(sign.snapshot().ignored).toEqual([]);
  });
});

describe("Priority TEXT File (p. 20)", () => {
  it("stores the Table 50 Packet without a Memory Configuration (p. 68)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02A0\x1b c\x1a9EMERGENCY\x04`);
    expect(sign.snapshot().priority).toEqual({
      label: "0",
      type: "TEXT",
      data: "\x1b c\x1a9EMERGENCY",
    });
  });

  it("clears it with the Table 51 Packet (p. 68)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02A0\x1b c\x1a9EMERGENCY\x04`);
    send(`${SYNC}\x01Z00\x02A0\x04`);
    expect(sign.snapshot().priority).toBeNull();
  });

  it("holds at most 125 bytes (p. 20)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02A0${"X".repeat(126)}\x04`);
    expect(sign.snapshot().priority).toBeNull();
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["oversized-write"]);
    send(`${SYNC}\x01Z00\x02A0${"X".repeat(125)}\x04`);
    expect(sign.snapshot().priority?.data).toHaveLength(125);
  });

  it("reads back with File Label 0 (p. 19, Table 13)", () => {
    const { send } = oneSign();
    send(`${SYNC}\x01Z00\x02A0URGENT\x04`);
    const [reply] = send(`${SYNC}\x01Z00\x02B0\x04`);
    expect(reply?.slice(24, 33)).toBe("\x02A0URGENT");
  });
});
