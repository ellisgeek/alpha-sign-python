// Write and read STRING File (pp. 37-38), with the Appendix F Packets.
import { describe, expect, it } from "vitest";
import { oneSign, SYNC } from "./helpers";

// STRING Files "1" and "2", locked, 10 bytes ("000A"), as Table 55 sets up "l" (p. 71).
const CONFIGURE = `${SYNC}\x01Z00\x02E$AAU0100FF001BL000A00002BL000A0000\x04`;

describe("Write STRING File", () => {
  it("stores the Table 57 data (p. 74)", () => {
    const { sign, send } = oneSign();
    send(CONFIGURE);
    send(`${SYNC}\x01Z00\x02G17,345\x04`);
    expect(sign.snapshot().files["1"]).toEqual({ label: "1", type: "STRING", data: "7,345" });
  });

  it("does not restart the display (p. 37: the display will not blank)", () => {
    const { sign, send } = oneSign();
    send(CONFIGURE);
    const before = sign.snapshot().display;
    send(`${SYNC}\x01Z00\x02G17,345\x04`);
    expect(sign.snapshot().display).toEqual(before);
  });

  it("ignores a write to a File that is not configured (spec story 18)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02G17,345\x04`);
    expect(sign.snapshot().files["1"]).toBeUndefined();
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["unconfigured-file"]);
  });

  it("ignores a write to a TEXT File", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02GAHELLO\x04`);
    expect(sign.snapshot().files.A?.data).toBe("");
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["wrong-file-type"]);
  });

  it("applies Reading oversizedWrite to an 11-byte write into 10 bytes", () => {
    const ignoring = oneSign();
    ignoring.send(CONFIGURE);
    ignoring.send(`${SYNC}\x01Z00\x02G112345678901\x04`);
    expect(ignoring.sign.snapshot().files["1"]?.data).toBe("");
    expect(ignoring.sign.snapshot().ignored.map((i) => i.reason)).toEqual(["oversized-write"]);

    const truncating = oneSign({ oversizedWrite: "truncate" });
    truncating.send(CONFIGURE);
    truncating.send(`${SYNC}\x01Z00\x02G112345678901\x04`);
    expect(truncating.sign.snapshot().files["1"]?.data).toBe("1234567890");
  });

  it("holds at most 125 bytes whatever its configured size (p. 37)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02E$SBL00FF0000\x04`);
    send(`${SYNC}\x01Z00\x02GS${"X".repeat(126)}\x04`);
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["oversized-write"]);
  });
});

describe("Read STRING File", () => {
  it("answers with the Table 59 bytes (p. 75)", () => {
    const { send } = oneSign({}, 8);
    send(CONFIGURE);
    send(`${SYNC}\x01Z00\x02G28,234,000\x04`);
    // Table 58 addresses a 215C ("f08"); this 4120C at address 08 hears "Z08".
    expect(send(`${SYNC}\x01Z08\x02H2\x04`)).toEqual([
      `${"\x00".repeat(20)}\x01000\x02G28,234,000\x030237\x04`,
    ]);
  });

  it("sends nothing for a File that is not configured", () => {
    const { send } = oneSign();
    expect(send(`${SYNC}\x01Z00\x02H2\x04`)).toEqual([]);
  });
});
