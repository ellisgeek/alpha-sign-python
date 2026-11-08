// The Memory Configuration and the Memory Pool (p. 21, p. 27 note 1, pp. 29-30).
import { describe, expect, it } from "vitest";
import { oneSign, SYNC } from "./helpers";

// Table 55, with "073C" as its item I spells it (the printed Packet has a letter "O").
const TABLE_55 = `${SYNC}\x01Z00\x02E$AAU0100FF00mDU073C1000lBL000A0000\x04`;

describe("Memory Configuration", () => {
  it("starts with one TEXT File A (p. 17)", () => {
    const snap = oneSign().sign.snapshot();
    expect(Object.keys(snap.files)).toEqual(["A"]);
    expect(snap.memoryConfiguration.map((e) => [e.label, e.type])).toEqual([["A", "TEXT"]]);
  });

  it("sets up the three Files of Table 55 (p. 71)", () => {
    const { sign, send } = oneSign();
    send(TABLE_55);
    expect(sign.snapshot().memoryConfiguration).toEqual([
      { label: "A", type: "TEXT", locked: false, size: "0100", extra: "FF00" },
      { label: "m", type: "DOTS", locked: false, size: "073C", extra: "1000" },
      { label: "l", type: "STRING", locked: true, size: "000A", extra: "0000" },
    ]);
  });

  it("sets up the eight Files of Table 56 (p. 72)", () => {
    const { sign, send } = oneSign();
    send(
      `${SYNC}\x01Z00\x02E$AAU0100FF00mDU073C1000lBL000A0000` +
        "1AU0064FE002AU0064FE003AU0064FE004AU0064FE005AU0064FE00\x04",
    );
    expect(
      sign
        .snapshot()
        .memoryConfiguration.map((e) => e.label)
        .join(""),
    ).toBe("Aml12345");
    expect(sign.snapshot().memoryConfiguration[7]).toEqual({
      label: "5",
      type: "TEXT",
      locked: false,
      size: "0064",
      extra: "FE00",
    });
  });

  it("replaces every File and erases content (p. 21; spec story 17)", () => {
    const { sign, send } = oneSign();
    send(TABLE_55);
    send(`${SYNC}\x01Z00\x02AAHELLO\x04`);
    send(`${SYNC}\x01Z00\x02E$AAU0100FF00BAU0100FF00\x04`);
    const snap = sign.snapshot();
    expect(Object.keys(snap.files).sort()).toEqual(["A", "B"]);
    expect(snap.files.A?.data).toBe("");
  });

  it("drops a malformed table and sets register bit 5 (p. 31)", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02E$AXU0100FF00\x04`);
    expect(sign.snapshot().memoryConfiguration.map((e) => e.label)).toEqual(["A"]);
    expect(sign.snapshot().serialErrors).toBe(0x60);
  });

  it("reads back with F$ as FTPSIZEQQQQ per File (p. 30)", () => {
    const { send, read } = oneSign();
    send(TABLE_55);
    expect(read("$")).toBe("AAU0100FF00mDU073C1000lBL000A0000");
  });
});

describe("Clear Memory and Soft Reset", () => {
  it('"E$" alone erases every File back to the power-up File A (pp. 21, 17)', () => {
    const { sign, send } = oneSign();
    send(TABLE_55);
    send(`${SYNC}\x01Z00\x02AAHELLO\x04`);
    send(`${SYNC}\x01Z00\x02A0URGENT\x04`);
    send(`${SYNC}\x01Z00\x02E$\x04`);
    const snap = sign.snapshot();
    expect(snap.files).toEqual({ A: { label: "A", type: "TEXT", data: "" } });
    expect(snap.priority).toBeNull();
  });

  it('"E," keeps memory (p. 22: non-destructive)', () => {
    const { sign, send } = oneSign();
    send(TABLE_55);
    send(`${SYNC}\x01Z00\x02AAHELLO\x04`);
    send(`${SYNC}\x01Z00\x02E,\x04`);
    expect(sign.snapshot().files.A?.data).toBe("HELLO");
    expect(sign.snapshot().memoryConfiguration).toHaveLength(3);
  });

  it('"E," restarts the display from the Run Sequence, not the last TEXT File written (pp. 17-18, 22)', () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02E$AAU0100FF00BAU0100FF00\x04`);
    send(`${SYNC}\x01Z00\x02AAHELLO\x04`);
    send(`${SYNC}\x01Z00\x02ABWORLD\x04`);
    expect(sign.snapshot().display.fileLabel).toBe("B");
    send(`${SYNC}\x01Z00\x02E,\x04`);
    expect(sign.snapshot().display.fileLabel).toBe("A");
  });
});

describe("Memory Pool (F#, p. 30; POOL,pool as p. 29)", () => {
  // 4120C pool: 28,000 bytes (brochure p. 2) = 6D60H.
  // Table 55 uses 256 (TEXT A) + 10 (STRING l) + 3 x overhead.
  it("counts 11 bytes of overhead per File and no DOTS PICTURE by default (p. 27, note 1)", () => {
    const { send, read } = oneSign();
    send(TABLE_55);
    // 28000 - 256 - 10 - 3 x 11 = 27701 = 6C35H.
    expect(read("#")).toBe("6D60,6C35");
  });

  it("uses Reading perFileOverhead = 13", () => {
    const { send, read } = oneSign({ perFileOverhead: 13 });
    send(TABLE_55);
    // 28000 - 256 - 10 - 3 x 13 = 27695 = 6C2FH.
    expect(read("#")).toBe("6D60,6C2F");
  });

  it("counts the DOTS PICTURE as rows x columns with Reading dotsPictureCounted (PROVISIONAL)", () => {
    const { send, read } = oneSign({ dotsPictureCounted: true });
    send(TABLE_55);
    // 27701 - 7 x 60 = 27281 = 6A91H.
    expect(read("#")).toBe("6D60,6A91");
  });

  it("gives power-up File A only its overhead (PROVISIONAL: its size is not in the manual)", () => {
    const { read } = oneSign();
    // 28000 - 11 = 27989 = 6D55H.
    expect(read("#")).toBe("6D60,6D55");
  });
});
