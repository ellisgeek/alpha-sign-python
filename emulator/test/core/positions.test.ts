// Position rules for a two-line Sign (7.10.3.2, pp. 95-96), checked on a real 4120C
// (docs/hardware-results.md).
import { describe, expect, it } from "vitest";
import { buildDisplay, model4120C } from "../../src/core";
import { art, RESTART_MS, stateWith } from "./display-helpers";

function drawn(text: string, picture?: string): string[] {
  const state = stateWith({ text: { A: text } });
  if (picture) state.files.P = { label: "P", type: "DOTS", data: picture };
  return art(buildDisplay(state, model4120C, RESTART_MS + 1).pixels).split("\n");
}

const litRows = (rows: string[], from = 0, to?: number) =>
  rows.flatMap((row, i) => (/[^.]/.test(row.slice(from, to)) ? [i] : []));

// A 15-row bar, one column wide.
const BAR = `0F01${"1\r".repeat(15)}`;

describe("Fill, Top, and Bottom on a two-line Sign", () => {
  it.each([
    ["fill", "0"],
    ["top", '"'],
    ["bottom", "&"],
  ])("size full height down to seven high in %s (p. 96)", (_, position) => {
    expect(drawn(`\x1b${position}b\x1a9ABCD`)).toEqual(drawn(`\x1b${position}b\x1a3ABCD`));
  });

  it("size full height fancy down to seven high fancy (p. 96: 15 high fancy)", () => {
    expect(drawn("\x1b0b\x1a8ABCD")).toEqual(drawn("\x1b0b\x1a5ABCD"));
  });
});

describe("Middle on a two-line Sign", () => {
  it("draws full height text full size (p. 95: one line 16 dots high)", () => {
    const rows = litRows(drawn("\x1b b\x1a9ABCD"));
    expect((rows.at(-1) ?? 0) - (rows[0] ?? 0) + 1).toBeGreaterThanOrEqual(15);
  });

  it("shows all 15 rows of a picture from the top row, as a real 4120C did", () => {
    // p. 95: only rows past the 16th are cut. Beside full height "AB" and "CD" a 4120C
    // showed the 15-row bar in rows 0-14, level with the letters' top.
    const rows = drawn("\x1b b\x1a9AB\x14PCD", BAR);
    const columns = [...(rows[0] ?? "")].map((_, x) => litRows(rows, x, x + 1));
    // The bar's column is lit in rows 0-14; the letters reach row 0 too.
    expect(columns).toContainEqual([...Array(15).keys()]);
    expect(litRows(rows)[0]).toBe(0);
  });

  it("while Fill cuts it to 8, as a real 4120C did", () => {
    expect(litRows(drawn("\x1b0b\x14P", BAR))).toHaveLength(8);
  });
});
