// Write and read SPECIAL FUNCTION (pp. 21-36), with the Appendix F Packets.
import { describe, expect, it } from "vitest";
import { bytes, oneSign, SYNC } from "./helpers";

const E = (data: string) => `${SYNC}\x01Z00\x02E${data}\x04`;
const W = (data: string) => `${SYNC}\x01Z00\x02A${data}\x04`;

describe("time, date, and day", () => {
  it("sets the time of day with the Table 52 Packet (p. 69)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02E 1430\x04`);
    expect(sign.snapshot().clock).toMatchObject({
      year: 2026,
      month: 11,
      day: 7,
      hour: 14,
      minute: 30,
    });
  });

  it("reads the time of day as HhMm, 24-hour (p. 29)", () => {
    const s = oneSign();
    s.send(E(" 0905"));
    expect(s.read(" ")).toBe("0905");
  });

  it("answers Table 53 with the Table 54 bytes on a Friday (pp. 69-70)", () => {
    const { send } = oneSign({}, 4);
    send(E("&6"));
    expect(send(`${SYNC}\x01Z04\x02F&\x04`)).toEqual([
      `${"\x00".repeat(20)}\x01000\x02E&6\x0300A6\x04`,
    ]);
  });

  it("moves the day set with E& on at midnight (p. 22)", () => {
    const { line, sign, send } = oneSign();
    send(E(" 2359"));
    send(E("&2")); // Monday
    expect(sign.snapshot().clock.dayOfWeek).toBe(2);
    line.advance(2000 + 60_000);
    expect(sign.snapshot().clock).toMatchObject({ hour: 0, dayOfWeek: 3 });
  });

  it("sets the date as mmddyy (p. 26)", () => {
    const { sign, send } = oneSign();
    send(E(";123125"));
    expect(sign.snapshot().clock).toMatchObject({ year: 2025, month: 12, day: 31, hour: 12 });
  });

  it("windows a two-digit year 97-99 to 1997-1999 by default (p. 28, note 15)", () => {
    const { sign, send } = oneSign();
    send(E(";010597"));
    expect(sign.snapshot().clock.year).toBe(1997);
    send(E(";010596"));
    expect(sign.snapshot().clock.year).toBe(2096);
  });

  it("reads every two-digit year as 19xx with Reading twoDigitYear = 19xx", () => {
    const { sign, send } = oneSign({ twoDigitYear: "19xx" });
    send(E(";010505"));
    expect(sign.snapshot().clock.year).toBe(1905);
  });

  it("drops an impossible time and sets register bit 5 (p. 31)", () => {
    const { sign, send } = oneSign();
    send(E(" 2561"));
    expect(sign.snapshot().clock.hour).toBe(12);
    expect(sign.snapshot().serialErrors).toBe(0x60);
  });

  it("sets and reads the time format (pp. 22, 30)", () => {
    const s = oneSign();
    s.send(E("'M"));
    expect(s.sign.snapshot().clock.timeFormat).toBe("M");
    expect(s.read("'")).toBe("M");
  });
});

describe("speaker and tones", () => {
  it('enables the speaker with "00" and reads it back (pp. 21, 29)', () => {
    const s = oneSign();
    expect(s.read("!")).toBe("FF");
    s.send(E("!00"));
    expect(s.sign.snapshot().speakerOn).toBe(true);
    expect(s.read("!")).toBe("00");
    s.send(E("!FF"));
    expect(s.sign.snapshot().speakerOn).toBe(false);
  });

  it('turns the speaker on and off with tone "A" and "B" (p. 22)', () => {
    const { sign, send } = oneSign();
    send(E("(A"));
    expect(sign.snapshot().speakerOn).toBe(true);
    send(E("(B"));
    expect(sign.snapshot().speakerOn).toBe(false);
  });

  it("records a tone and ignores input for 3 s after it (p. 27, note 4; spec story 36)", () => {
    const { line, sign } = oneSign();
    line.receive(bytes(E("(0")), 1000);
    line.receive(bytes(W("AEARLY")), 3999);
    line.receive(bytes(W("AON TIME")), 4000);
    line.advance(5000);
    const snap = sign.snapshot();
    expect(snap.tones).toEqual([{ atMs: 1000, data: "0" }]);
    expect(snap.ignored.map((i) => i.reason)).toEqual(["input-blocked"]);
    expect(snap.files.A?.data).toBe("ON TIME");
  });

  // Checksum per p. 12: STX 02 + "E" 45 + "(" 28 + "0" 30 + ETX 03 = 00A2.
  for (const [form, packet] of [
    ["without a Checksum", E("(0")],
    ["with a Checksum", `${SYNC}\x01Z00\x02E(0\x0300A2\x04`],
  ] as const) {
    it(`accepts the EOT that closes a tone's own Packet ${form} (p. 27, note 4)`, () => {
      const { line, sign } = oneSign();
      line.receive(bytes(packet), 1000);
      line.receive(bytes(W("AEARLY")), 2000);
      line.advance(5000);
      const snap = sign.snapshot();
      expect(snap.tones).toEqual([{ atMs: 1000, data: "0" }]);
      expect(snap.ignored).toMatchObject([{ reason: "input-blocked", atMs: 2000 }]);
      expect(snap.ignored[0]?.bytes).toBe(W("AEARLY"));
    });
  }

  // FFDR = "2F" frequency, D = 5 (0.5 s), R = 3 (p. 22); wait until it ends (note 5).
  for (const [toneRepeats, playMs] of [
    ["R+1", 2000],
    ["R", 1500],
  ] as const) {
    it(`blocks input for a programmable tone's ${playMs} ms with Reading toneRepeats = ${toneRepeats}`, () => {
      const { line, sign } = oneSign({ toneRepeats });
      line.receive(bytes(E("(22F53")), 1000);
      line.receive(bytes(W("AEARLY")), 1000 + playMs - 1);
      line.receive(bytes(W("AON TIME")), 1000 + playMs);
      line.advance(5000);
      expect(sign.snapshot().tones).toEqual([{ atMs: 1000, data: "22F53" }]);
      expect(sign.snapshot().files.A?.data).toBe("ON TIME");
    });
  }

  it("does not model the Alpha 2.0 sound tones 3 and 4 on the 4120C (p. 22; Table 3)", () => {
    const { sign, send } = oneSign();
    send(E("(3"));
    expect(sign.snapshot().tones).toEqual([]);
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["unsupported-special-function"]);
  });
});

describe("Run Sequence (p. 23; read p. 32)", () => {
  it("stores and reads back KPF", () => {
    const s = oneSign();
    s.send(E(".SLAB"));
    expect(s.sign.snapshot().runSequence).toEqual({ order: "S", locked: true, labels: ["A", "B"] });
    expect(s.read(".")).toBe("SLAB");
  });

  it("drops an order other than T, S, or D", () => {
    const { sign, send } = oneSign();
    send(E(".XUA"));
    expect(sign.snapshot().runSequence.order).toBe("T");
    expect(sign.snapshot().serialErrors).toBe(0x60);
  });
});

describe("Serial Error Status Register (pp. 24, 31)", () => {
  it("reads one bitmapped character and resets to 40H on the read", () => {
    const s = oneSign();
    // A bad Checksum sets bit 4: 50H = "P".
    s.send(`${SYNC}\x01Z00\x02AAHELLO\x030000\x04`);
    expect(s.read("*")).toBe("P");
    expect(s.sign.snapshot().serialErrors).toBe(0x40);
    expect(s.read("*")).toBe("@");
  });

  it('clears to 40H with "E4"', () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02AAHELLO\x030000\x04`);
    send(E("4"));
    expect(sign.snapshot().serialErrors).toBe(0x40);
  });
});

describe("Read General Information (p. 29)", () => {
  // PROVISIONAL: no manual example and no capture. Checked field by field
  // against <NUL>FFFFFFFFfMmYyHhNnRSSPOOL,pool.
  it("returns the 29 field-list characters by default", () => {
    const s = oneSign();
    s.send(E(" 1430"));
    const data = s.read('"');
    expect(data).toHaveLength(29);
    expect(data?.slice(0, 8)).toBe("EMU4120C"); // FFFFFFFF firmware (model data)
    expect(data?.slice(8, 9)).toBe("A"); // f revision
    expect(data?.slice(9, 13)).toBe("1126"); // MmYy release date
    expect(data?.slice(13, 17)).toBe("1430"); // HhNn time of day, 24-hour
    expect(data?.slice(17, 18)).toBe("S"); // R time format (default)
    expect(data?.slice(18, 20)).toBe("FF"); // SS speaker disabled (default)
    // POOL,pool: 28,000 = 6D60H; power-up File A's 11 bytes of overhead leave 6D55H.
    expect(data?.slice(20)).toBe("6D60,6D55");
  });

  it("leads with a NUL under Reading generalInfoLength = 29+NUL", () => {
    const data = oneSign({ generalInfoLength: "29+NUL" }).read('"');
    expect(data).toHaveLength(30);
    expect(data?.slice(0, 9)).toBe("\x00EMU4120C");
  });

  it("drops the revision letter under Reading generalInfoLength = 28 (PROVISIONAL)", () => {
    const data = oneSign({ generalInfoLength: "28" }).read('"');
    expect(data).toHaveLength(28);
    expect(data?.slice(0, 12)).toBe("EMU4120C1126");
  });
});

describe("Sign Address (p. 26)", () => {
  it("answers at the address written with E7 and no longer at the old one", () => {
    const { sign, send } = oneSign();
    send(E("71A"));
    expect(sign.snapshot().signAddress).toBe(0x1a);
    send(`${SYNC}\x01a01\x02AAOLD\x04`);
    expect(sign.snapshot().files.A?.data).toBe("");
    send(`${SYNC}\x01a1A\x02AANEW\x04`);
    expect(sign.snapshot().files.A?.data).toBe("NEW");
  });
});

describe("special functions the Emulator does not model", () => {
  it("ignores them without setting the register", () => {
    const { sign, send } = oneSign();
    send(E("/0000"));
    expect(sign.snapshot().ignored.map((i) => i.reason)).toEqual(["unsupported-special-function"]);
    expect(sign.snapshot().serialErrors).toBe(0x40);
  });
});
