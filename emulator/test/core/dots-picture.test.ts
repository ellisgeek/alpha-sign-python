// Write and read SMALL DOTS PICTURE File, "I" and "J" (pp. 39-41), with Table 60's
// arrow (p. 76), and calling a picture from a TEXT File (14H, p. 81).
import { describe, expect, it } from "vitest";
import { buildDisplay, model4120C } from "../../src/core";
import { art, lineTexts, RESTART_MS, stateWith } from "./display-helpers";
import { bytes, NULS_4120C, oneSign, SYNC, text } from "./helpers";

// TEXT File "A" and DOTS PICTURE File "P", 15 rows x 9 columns ("0F09"), 3-color
// ("2000"), as Table 15 lays out a Memory Configuration (p. 21).
const CONFIGURE = `${SYNC}\x01Z00\x02E$AAU0100FF00PDU0F092000\x04`;

// Table 60 (p. 76): the rows of the arrow, each followed by <CR>.
const ARROW_ROWS = [
  "000000000",
  "000000000",
  "000100000",
  "000110000",
  "000111000",
  "000111100",
  "111111110",
  "111111112",
  "111111110",
  "000111100",
  "000111000",
  "000110000",
  "000100000",
  "000000000",
  "000000000",
];
const ARROW = ARROW_ROWS.map((row) => `${row}\r`).join("");

/**
 * Sends `head` (up to and including the Width), waits `pauseMs`, then sends `rows`
 * and EOT, as p. 40 asks: at least 100 ms after the Width. Table 60 addresses a
 * 4160C ("b00"); this 4120C hears "Z00".
 */
function writePicture(
  sign: ReturnType<typeof oneSign>,
  label: string,
  size: string,
  rows: string,
  pauseMs = 100,
): string[] {
  const t = sign.now() + 1000;
  sign.line.receive(bytes(`${SYNC}\x01Z00\x02I${label}${size}`), t);
  sign.line.receive(bytes(`${rows}\x04`), t + pauseMs);
  return sign.line.advance(t + pauseMs + 500).map((o) => text(o.bytes));
}

describe("Write SMALL DOTS PICTURE File", () => {
  it("stores Table 60's arrow (p. 76)", () => {
    const sign = oneSign();
    sign.send(CONFIGURE);
    writePicture(sign, "P", "0F09", ARROW);
    expect(sign.sign.snapshot().files.P).toEqual({
      label: "P",
      type: "DOTS",
      data: `0F09${ARROW}`,
    });
  });

  it("reads rows the way p. 40 says: LF dropped, short rows padded, long rows cut", () => {
    const sign = oneSign();
    sign.send(`${SYNC}\x01Z00\x02E$AAU0100FF00PDU03032000\x04`);
    // No last <CR>, and the third row never sent: the picture was cleared after the Width.
    writePicture(sign, "P", "0303", "12\r\n3456\r\n");
    expect(sign.sign.snapshot().files.P?.data).toBe("0303120\r345\r000\r");
  });

  it("keeps rows sent sooner than 100 ms after the Width, as a real 4120C did", () => {
    // docs/hardware-results.md, "DOTS PICTURE pause": p. 40 asks for 100 ms, but the
    // 4120C read back a picture written without it intact.
    const sign = oneSign();
    sign.send(CONFIGURE);
    writePicture(sign, "P", "0F09", ARROW, 20);
    expect(sign.sign.snapshot().files.P?.data).toBe(`0F09${ARROW}`);
  });

  it("applies Reading missingDotsPause: drop, as p. 40 reads", () => {
    const sign = oneSign({ missingDotsPause: "drop" });
    sign.send(CONFIGURE);
    writePicture(sign, "P", "0F09", ARROW, 20);
    expect(sign.sign.snapshot().files.P?.data).toBe("");
    expect(sign.sign.snapshot().ignored.map((i) => i.reason)).toEqual(["missing-dots-pause"]);
  });

  it("keeps a picture of another size than its File as sent, as a real 4120C did", () => {
    // docs/hardware-results.md, "DOTS PICTURE size against its File": a 2x2 picture
    // written into a 15x9 File read back as 0202 with rows 11 and 11.
    const sign = oneSign();
    sign.send(CONFIGURE);
    writePicture(sign, "P", "0202", "11\r11\r");
    expect(sign.sign.snapshot().files.P?.data).toBe("020211\r11\r");
  });

  it("applies Reading dotsPictureSize: drop, as p. 39 reads (it must match)", () => {
    const sign = oneSign({ dotsPictureSize: "drop" });
    sign.send(CONFIGURE);
    writePicture(sign, "P", "0202", "11\r11\r");
    expect(sign.sign.snapshot().files.P?.data).toBe("");
    expect(sign.sign.snapshot().ignored.map((i) => i.reason)).toEqual(["dots-size-mismatch"]);
  });

  it("ignores a write to a File that is not a DOTS PICTURE File", () => {
    const sign = oneSign();
    sign.send(CONFIGURE);
    writePicture(sign, "A", "0101", "1\r");
    expect(sign.sign.snapshot().files.A?.data).toBe("");
    expect(sign.sign.snapshot().ignored.map((i) => i.reason)).toEqual(["wrong-file-type"]);
  });

  it("blanks the display while it is written (p. 39)", () => {
    const sign = oneSign();
    sign.send(CONFIGURE);
    writePicture(sign, "P", "0F09", ARROW);
    expect(sign.sign.snapshot().display.fileLabel).toBeNull();
  });
});

describe("Read SMALL DOTS PICTURE File", () => {
  it("answers with Command Code I, the File Label, and the picture (Table 24, p. 41)", () => {
    const sign = oneSign();
    sign.send(CONFIGURE);
    writePicture(sign, "P", "0F09", ARROW);
    const [reply] = sign.send(`${SYNC}\x01Z01\x02JP\x04`);
    const head = `${NULS_4120C}\x01000\x02IP0F09${ARROW}\x03`;
    expect(reply?.slice(0, head.length)).toBe(head);
    // Then a 4-digit Checksum and EOT.
    expect(reply?.slice(head.length, -1)).toMatch(/^[0-9A-F]{4}$/);
    expect(reply?.slice(-1)).toBe("\x04");
  });

  it("answers with the File's size and no rows before anything is written", () => {
    const sign = oneSign();
    sign.send(CONFIGURE);
    const [reply] = sign.send(`${SYNC}\x01Z01\x02JP\x04`);
    expect(reply?.startsWith(`${NULS_4120C}\x01000\x02IP0F09\x03`)).toBe(true);
  });

  it("sends nothing for a File that is not configured", () => {
    const sign = oneSign();
    expect(sign.send(`${SYNC}\x01Z01\x02JP\x04`)).toEqual([]);
  });
});

describe("Call SMALL DOTS PICTURE (14H, p. 81)", () => {
  function withArrow(textData: string) {
    const state = stateWith({ text: { A: textData } });
    state.files.P = { label: "P", type: "DOTS", data: `0F09${ARROW}` };
    return buildDisplay(state, model4120C, RESTART_MS + 1);
  }

  it("draws the picture in its own colors at the text cursor", () => {
    const display = withArrow("\x1b0bAB\x14PCD");
    expect(lineTexts(display)).toEqual(["ABCD"]);
    expect(display.lines[0]?.map((run) => run.picture ?? null)).toEqual([null, "P", null]);
    const rows = art(display.pixels).split("\n");
    // Row 7 of the arrow, "111111112": eight red pixels and a green tip.
    const tip = rows.find((row) => row.includes("RRRRRRRRG"));
    expect(tip).toBeDefined();
    const start = tip?.indexOf("RRRRRRRRG") ?? -1;
    // AB is drawn to its left and CD to its right.
    const lit = (row: string, from: number, to: number) => /[^.]/.test(row.slice(from, to));
    expect(rows.some((row) => lit(row, 0, start))).toBe(true);
    expect(rows.some((row) => lit(row, start + 9, row.length))).toBe(true);
  });

  it("cuts the picture to 8 rows, its top level with the text's, as a real 4120C did", () => {
    // docs/hardware-results.md, "Where a called DOTS PICTURE is drawn": beside "AB" and
    // "CD" the 4120C showed rows 0-7 of the 15-row arrow; the picture's top was level
    // with the 7-high letters' top, its bottom one row below theirs.
    const display = withArrow("\x1b0bAB\x14PCD");
    const rows = art(display.pixels).split("\n");
    const tipRow = rows.findIndex((row) => row.includes("RRRRRRRRG"));
    const start = rows[tipRow]?.indexOf("RRRRRRRRG") ?? -1;
    const arrow = rows.map((row) => row.slice(start, start + 9));
    const letters = rows.map((row) => row.slice(0, start));
    const litRows = (part: string[]) => part.flatMap((row, i) => (/[^.]/.test(row) ? [i] : []));
    // Rows 2-7 of the arrow are lit; rows 8-14 are not drawn.
    expect(arrow.slice(tipRow - 5, tipRow + 1)).toEqual([
      "...R.....",
      "...RR....",
      "...RRR...",
      "...RRRR..",
      "RRRRRRRR.",
      "RRRRRRRRG",
    ]);
    expect(litRows(arrow)).toEqual([0, 1, 2, 3, 4, 5].map((i) => tipRow - 5 + i));
    // Arrow row 0 is tipRow - 7: the letters' top row. Their bottom is tipRow - 1.
    expect(litRows(letters)).toEqual([0, 1, 2, 3, 4, 5, 6].map((i) => tipRow - 7 + i));
  });

  // docs/hardware-results.md, "Where a called DOTS PICTURE is drawn": a 15-row bar
  // between "AB" and "CD" on a 4120C, counted from the display's top row.
  it.each([
    ["five high", "1", [6, 7, 8, 9, 10]],
    ["seven high", "3", [4, 5, 6, 7, 8, 9, 10]],
  ])(
    "puts the picture in rows 4-11 and %s text on row 10, as a real 4120C did",
    (_, code, textRows) => {
      const state = stateWith({ text: { A: `\x1b0b\x1a${code}AB\x14PCD` } });
      state.files.P = { label: "P", type: "DOTS", data: `0F01${"1\r".repeat(15)}` };
      const rows = art(buildDisplay(state, model4120C, RESTART_MS + 1).pixels).split("\n");
      // Row 11 is below the text, so only the bar is lit there.
      const column = rows[11]?.indexOf("R") ?? -1;
      const lit = (from: number, to: number) =>
        rows.flatMap((row, i) => (/[^.]/.test(row.slice(from, to)) ? [i] : []));
      expect(lit(column, column + 1)).toEqual([4, 5, 6, 7, 8, 9, 10, 11]);
      expect(lit(0, column)).toEqual(textRows);
    },
  );

  it("draws codes 4-8 in the 4120C's three colors, as a real 4120C did", () => {
    // docs/hardware-results.md, "DOTS PICTURE colors 4-8": dim red showed as red, dim
    // green as green, and brown, orange, and yellow all as yellow (amber).
    const state = stateWith({ text: { A: "\x1b0b\x14P" } });
    state.files.P = { label: "P", type: "DOTS", data: "0109012345678\r" };
    const display = buildDisplay(state, model4120C, RESTART_MS + 1);
    expect(art(display.pixels)).toContain("RGARGAAA");
  });

  it("draws nothing for a label that is not a DOTS PICTURE File", () => {
    const display = withArrow("\x1b0b\x14Q");
    expect(art(display.pixels)).not.toMatch(/[^.\n]/);
  });
});
