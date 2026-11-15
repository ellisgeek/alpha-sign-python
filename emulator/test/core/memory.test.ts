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
  // Every expected figure here is what a real 4120C reported (docs/hardware-results.md,
  // "Memory Configuration limit"). Pool: 28,872 bytes = 70C8H. The Sign keeps 9 bytes
  // back, gives unused memory to a first-listed TEXT File (p. 29, "#"), and reports
  // as free the room that File has, less 5 bytes.
  const hex = (n: number, width: number) => n.toString(16).toUpperCase().padStart(width, "0");
  const text = (label: string, size: number) => `${label}AU${hex(size, 4)}FF00`;
  const string = (label: string, size: number) => `${label}BL${hex(size, 4)}0000`;
  const dots = (label: string, rows: number, columns: number) =>
    `${label}DU${hex(rows, 2)}${hex(columns, 2)}1000`;
  const configure = (send: (packet: string) => void, entries: string) =>
    send(`${SYNC}\x01Z00\x02E$${entries}\x04`);
  const free = (read: (label: string) => string) => Number.parseInt(read("#").slice(5), 16);

  it("reports 28,847 free with File A alone, whatever its size", () => {
    for (const size of [0, 1, 256, 28_852]) {
      const { send, read } = oneSign();
      configure(send, text("A", size));
      expect(free(read)).toBe(28_847);
    }
  });

  it("reports 28,847 free at power-up", () => {
    const { read } = oneSign();
    expect(read("#")).toBe("70C8,70AF");
  });

  it("counts another File's size and 11 bytes of overhead, but not the first TEXT File's size", () => {
    for (const entries of [
      text("A", 100) + text("B", 100),
      text("A", 1000) + text("B", 100),
      text("B", 100) + text("A", 100),
      text("B", 1000) + text("A", 100),
    ]) {
      const { send, read } = oneSign();
      configure(send, entries);
      expect(free(read)).toBe(28_736);
    }
  });

  it("gives a last TEXT File of size 0 the unused memory instead (p. 27, note 1)", () => {
    const { send, read } = oneSign();
    configure(send, text("A", 256) + text("B", 0));
    expect(free(read)).toBe(251);
    configure(send, text("A", 100) + text("B", 100) + text("C", 0));
    expect(free(read)).toBe(95);
  });

  it("gives unused memory to no File when the first File listed is not a TEXT File", () => {
    const { send, read } = oneSign();
    configure(send, string("T", 100) + text("A", 100));
    expect(free(read)).toBe(95);
  });

  it("counts a DOTS PICTURE as 2 + rows x 2 x ceil(columns / 8) bytes plus overhead", () => {
    const sizes: [number, number, number][] = [
      [16, 16, 77],
      [8, 8, 29],
      [16, 120, 493],
      [1, 1, 15],
      [3, 3, 19],
      [1, 17, 19],
    ];
    for (const [rows, columns, bytes] of sizes) {
      const { send, read } = oneSign();
      configure(send, text("A", 256) + dots("P", rows, columns));
      expect(free(read)).toBe(28_847 - bytes);
    }
  });

  it("gives a 0x0 DOTS PICTURE the unused memory, like a last TEXT File of size 0", () => {
    const { send, read } = oneSign();
    configure(send, text("A", 256) + dots("P", 0, 0));
    expect(free(read)).toBe(251);
  });

  it("counts only overhead for a DOTS PICTURE with Reading dotsPictureCounted false (p. 27, note 1)", () => {
    const { send, read } = oneSign({ dotsPictureCounted: false });
    configure(send, text("A", 256) + dots("P", 16, 16));
    expect(free(read)).toBe(28_847 - 11);
  });

  it("uses Reading perFileOverhead = 13", () => {
    const { send, read } = oneSign({ perFileOverhead: 13 });
    configure(send, text("A", 100) + text("B", 100));
    expect(free(read)).toBe(28_872 - 9 - 2 * 13 - 100 - 5);
  });
});

describe("Memory Configuration limit", () => {
  // The largest File A a real 4120C took beside one other File (docs/hardware-results.md).
  const cases: [string, number, string][] = [
    ["TEXT B of 100", 28_741, "BAU0064FF00"],
    ["STRING T of 100", 28_741, "TBL00640000"],
    ["a 16x16 DOTS PICTURE", 28_775, "PDU10101000"],
    ["a 16x120 DOTS PICTURE", 28_359, "PDU10781000"],
  ];
  const fileA = (size: number) => `AAU${size.toString(16).toUpperCase().padStart(4, "0")}FF00`;

  for (const [other, largest, entry] of cases) {
    it(`takes File A of ${largest} bytes beside ${other}, and refuses one more`, () => {
      const { sign, send } = oneSign();
      send(`${SYNC}\x01Z00\x02E$${fileA(largest)}${entry}\x04`);
      expect(sign.snapshot().memoryConfiguration).toHaveLength(2);

      send(`${SYNC}\x01Z00\x02E$\x04`);
      send(`${SYNC}\x01Z00\x02E$${fileA(largest + 1)}${entry}\x04`);
      expect(sign.snapshot().memoryConfiguration).toHaveLength(1);
    });
  }

  it("keeps the old Files and their content when it refuses a Memory Configuration", () => {
    const { sign, send } = oneSign();
    send(`${SYNC}\x01Z00\x02AAHELLO\x04`);
    send(`${SYNC}\x01Z00\x02E$${fileA(28_742)}BAU0064FF00\x04`);
    expect(sign.snapshot().files).toEqual({ A: { label: "A", type: "TEXT", data: "HELLO" } });
  });
});
